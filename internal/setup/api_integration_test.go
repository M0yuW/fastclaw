package setup

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"path/filepath"
	"testing"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/auth"
	"github.com/fastclaw-ai/fastclaw/internal/bus"
	"github.com/fastclaw-ai/fastclaw/internal/store"
	"github.com/fastclaw-ai/fastclaw/internal/taskqueue"
)

type apiIntegrationFixture struct {
	store  store.Store
	app    *Server
	server *httptest.Server
	client *http.Client
}

func newAPIIntegrationFixture(t *testing.T) *apiIntegrationFixture {
	t.Helper()

	dsn := "file:" + filepath.Join(t.TempDir(), "integration.db") + "?_fk=1"
	dataStore, err := store.New(&store.StorageConfig{
		Type:        store.StorageSQLite,
		DSN:         dsn,
		AutoMigrate: true,
	}, t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	resolver, err := auth.NewResolver(dataStore)
	if err != nil {
		dataStore.Close()
		t.Fatal(err)
	}
	app := NewServer(0)
	app.SetStore(dataStore)
	app.SetAuth(resolver)
	handler, err := app.Handler()
	if err != nil {
		dataStore.Close()
		t.Fatal(err)
	}
	httpServer := httptest.NewServer(handler)
	jar, err := cookiejar.New(nil)
	if err != nil {
		httpServer.Close()
		dataStore.Close()
		t.Fatal(err)
	}
	client := httpServer.Client()
	client.Jar = jar

	fixture := &apiIntegrationFixture{
		store:  dataStore,
		app:    app,
		server: httpServer,
		client: client,
	}
	t.Cleanup(func() {
		httpServer.Close()
		if err := dataStore.Close(); err != nil {
			t.Error(err)
		}
	})
	return fixture
}

func (f *apiIntegrationFixture) newClient(t *testing.T) *http.Client {
	t.Helper()
	jar, err := cookiejar.New(nil)
	if err != nil {
		t.Fatal(err)
	}
	baseClient := f.server.Client()
	clientCopy := *baseClient
	client := &clientCopy
	client.Jar = jar
	return client
}

func requestJSON(
	t *testing.T,
	client *http.Client,
	method string,
	url string,
	body any,
	bearer string,
	wantStatus int,
) map[string]any {
	t.Helper()

	var payload *bytes.Reader
	if body == nil {
		payload = bytes.NewReader(nil)
	} else {
		data, err := json.Marshal(body)
		if err != nil {
			t.Fatal(err)
		}
		payload = bytes.NewReader(data)
	}
	request, err := http.NewRequest(method, url, payload)
	if err != nil {
		t.Fatal(err)
	}
	if body != nil {
		request.Header.Set("Content-Type", "application/json")
	}
	if bearer != "" {
		request.Header.Set("Authorization", "Bearer "+bearer)
	}
	response, err := client.Do(request)
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	var decoded map[string]any
	if err := json.NewDecoder(response.Body).Decode(&decoded); err != nil {
		t.Fatalf("%s %s decode response: %v", method, url, err)
	}
	if response.StatusCode != wantStatus {
		t.Fatalf("%s %s status=%d want=%d body=%v", method, url, response.StatusCode, wantStatus, decoded)
	}
	return decoded
}

func onboardAdmin(t *testing.T, fixture *apiIntegrationFixture) (map[string]any, string) {
	t.Helper()
	body := requestJSON(t, fixture.client, http.MethodPost, fixture.server.URL+"/api/onboard", map[string]any{
		"username":  "admin",
		"email":     "admin@example.com",
		"password":  "correct-horse-battery-staple",
		"provider":  "openai",
		"apiBase":   "https://api.example.test/v1",
		"apiKey":    "sk-integration-secret",
		"apiType":   "openai",
		"model":     "test-model",
		"agentName": "coordinator",
	}, "", http.StatusOK)
	agentID, _ := body["agentId"].(string)
	if agentID == "" {
		t.Fatalf("onboard response missing agentId: %v", body)
	}
	return body, agentID
}

func TestAPIIntegrationOnboardLoginLogoutPersistsState(t *testing.T) {
	fixture := newAPIIntegrationFixture(t)

	status := requestJSON(t, fixture.client, http.MethodGet, fixture.server.URL+"/api/status", nil, "", http.StatusOK)
	if configured, _ := status["configured"].(bool); configured {
		t.Fatalf("fresh store reported configured: %v", status)
	}

	onboard, agentID := onboardAdmin(t, fixture)
	user := onboard["user"].(map[string]any)
	userID := user["id"].(string)
	if user["role"] != "super_admin" {
		t.Fatalf("onboard role = %v", user["role"])
	}

	if count, err := fixture.store.CountUsers(context.Background()); err != nil || count != 1 {
		t.Fatalf("CountUsers()=%d err=%v", count, err)
	}
	agentRecord, err := fixture.store.GetAgent(context.Background(), agentID)
	if err != nil || agentRecord.UserID != userID || agentRecord.Name != "coordinator" {
		t.Fatalf("persisted agent=%+v err=%v", agentRecord, err)
	}
	providerRecord, err := fixture.store.GetConfigByName(
		context.Background(),
		store.KindProvider,
		store.ScopeSystem,
		"",
		"openai",
	)
	if err != nil || providerRecord.Data["apiKey"] != "sk-integration-secret" {
		t.Fatalf("persisted provider=%+v err=%v", providerRecord, err)
	}

	me := requestJSON(t, fixture.client, http.MethodGet, fixture.server.URL+"/api/me", nil, "", http.StatusOK)
	if me["authMethod"] != "session" || me["readOnly"] != false {
		t.Fatalf("unexpected session identity: %v", me)
	}
	requestJSON(t, fixture.client, http.MethodPost, fixture.server.URL+"/api/onboard", map[string]any{
		"username": "second",
		"email":    "second@example.com",
		"password": "not-used",
	}, "", http.StatusConflict)

	requestJSON(t, fixture.client, http.MethodPost, fixture.server.URL+"/api/logout", nil, "", http.StatusOK)
	requestJSON(t, fixture.client, http.MethodGet, fixture.server.URL+"/api/me", nil, "", http.StatusUnauthorized)
	requestJSON(t, fixture.client, http.MethodPost, fixture.server.URL+"/api/login", map[string]any{
		"login":    "admin",
		"password": "wrong",
	}, "", http.StatusUnauthorized)
	requestJSON(t, fixture.client, http.MethodPost, fixture.server.URL+"/api/login", map[string]any{
		"login":    "admin@example.com",
		"password": "correct-horse-battery-staple",
	}, "", http.StatusOK)
	requestJSON(t, fixture.client, http.MethodGet, fixture.server.URL+"/api/me", nil, "", http.StatusOK)
}

func TestAPIIntegrationTenantIsolationAndAPIKeyACL(t *testing.T) {
	fixture := newAPIIntegrationFixture(t)
	onboard, adminAgentID := onboardAdmin(t, fixture)
	adminID := onboard["user"].(map[string]any)["id"].(string)

	createdUser := requestJSON(t, fixture.client, http.MethodPost, fixture.server.URL+"/api/admin/users", map[string]any{
		"username":    "developer",
		"email":       "developer@example.com",
		"password":    "developer-password",
		"displayName": "AI Test Developer",
	}, "", http.StatusCreated)
	developerID := createdUser["user"].(map[string]any)["id"].(string)

	developerClient := fixture.newClient(t)
	requestJSON(t, developerClient, http.MethodPost, fixture.server.URL+"/api/login", map[string]any{
		"login":    "developer",
		"password": "developer-password",
	}, "", http.StatusOK)
	first := requestJSON(t, developerClient, http.MethodPost, fixture.server.URL+"/api/agents", map[string]any{
		"name":  "allowed-agent",
		"model": "openai/test-model",
	}, "", http.StatusCreated)
	second := requestJSON(t, developerClient, http.MethodPost, fixture.server.URL+"/api/agents", map[string]any{
		"name": "denied-agent",
	}, "", http.StatusCreated)
	firstID := first["agent"].(map[string]any)["id"].(string)
	secondID := second["agent"].(map[string]any)["id"].(string)

	ownAgents := requestJSON(t, developerClient, http.MethodGet, fixture.server.URL+"/api/agents", nil, "", http.StatusOK)
	if agents := ownAgents["agents"].([]any); len(agents) != 2 {
		t.Fatalf("developer agent count = %d", len(agents))
	}
	requestJSON(t, developerClient, http.MethodGet, fixture.server.URL+"/api/agents/"+adminAgentID, nil, "", http.StatusForbidden)

	actAsURL := fixture.server.URL + "/api/agents?actAs=" + developerID
	actedList := requestJSON(t, fixture.client, http.MethodGet, actAsURL, nil, "", http.StatusOK)
	if agents := actedList["agents"].([]any); len(agents) != 2 {
		t.Fatalf("actAs agent count = %d", len(agents))
	}
	actedIdentity := requestJSON(t, fixture.client, http.MethodGet, fixture.server.URL+"/api/me?actAs="+developerID, nil, "", http.StatusOK)
	if actedIdentity["readOnly"] != true || actedIdentity["actAsUserId"] != developerID {
		t.Fatalf("unexpected actAs identity: %v", actedIdentity)
	}
	requestJSON(t, fixture.client, http.MethodPost, actAsURL, map[string]any{"name": "forbidden"}, "", http.StatusForbidden)

	keyResponse := requestJSON(t, developerClient, http.MethodPost, fixture.server.URL+"/api/apikeys", map[string]any{
		"name":     "integration-key",
		"agentIds": []string{firstID},
	}, "", http.StatusCreated)
	token := keyResponse["token"].(string)
	keyID := keyResponse["apikey"].(map[string]any)["id"].(string)
	bearerClient := fixture.newClient(t)

	me := requestJSON(t, bearerClient, http.MethodGet, fixture.server.URL+"/api/me", nil, token, http.StatusOK)
	if me["authMethod"] != "apikey" {
		t.Fatalf("bearer auth method = %v", me["authMethod"])
	}
	visible := requestJSON(t, bearerClient, http.MethodGet, fixture.server.URL+"/api/agents", nil, token, http.StatusOK)
	visibleAgents := visible["agents"].([]any)
	if len(visibleAgents) != 1 || visibleAgents[0].(map[string]any)["id"] != firstID {
		t.Fatalf("API key visible agents = %v", visibleAgents)
	}
	requestJSON(t, bearerClient, http.MethodGet, fixture.server.URL+"/api/agents/"+firstID, nil, token, http.StatusOK)
	requestJSON(t, bearerClient, http.MethodGet, fixture.server.URL+"/api/agents/"+secondID, nil, token, http.StatusForbidden)

	queue := taskqueue.NewQueue(3, time.Second, func(context.Context, *taskqueue.Task) (string, error) {
		return "done", nil
	})
	defer queue.Stop()
	fixture.app.SetTaskQueue(queue)
	queue.Submit(firstID, "developer:first", bus.InboundMessage{OwnerUserID: developerID}, "")
	queue.Submit(secondID, "developer:second", bus.InboundMessage{OwnerUserID: developerID}, "")
	queue.Submit(adminAgentID, "admin:only", bus.InboundMessage{OwnerUserID: adminID}, "")
	deadline := time.Now().Add(time.Second)
	for {
		tasks := queue.RecentTasks(10)
		done := len(tasks) == 3
		for _, task := range tasks {
			done = done && task.Status == taskqueue.TaskDone
		}
		if done {
			break
		}
		if time.Now().After(deadline) {
			t.Fatalf("tasks did not finish: %+v", tasks)
		}
		time.Sleep(time.Millisecond)
	}

	developerTasks := requestJSONArray(t, developerClient, http.MethodGet, fixture.server.URL+"/api/tasks", "", http.StatusOK)
	if len(developerTasks) != 2 {
		t.Fatalf("developer task count = %d", len(developerTasks))
	}
	adminTasks := requestJSONArray(t, fixture.client, http.MethodGet, fixture.server.URL+"/api/tasks", "", http.StatusOK)
	if len(adminTasks) != 3 {
		t.Fatalf("admin task count = %d", len(adminTasks))
	}
	actedTasks := requestJSONArray(t, fixture.client, http.MethodGet, fixture.server.URL+"/api/tasks?actAs="+developerID, "", http.StatusOK)
	if len(actedTasks) != 2 {
		t.Fatalf("actAs task count = %d", len(actedTasks))
	}
	apiKeyTasks := requestJSONArray(t, bearerClient, http.MethodGet, fixture.server.URL+"/api/tasks", token, http.StatusOK)
	if len(apiKeyTasks) != 1 || apiKeyTasks[0].(map[string]any)["agentId"] != firstID {
		t.Fatalf("API key tasks = %v", apiKeyTasks)
	}

	rotated := requestJSON(t, developerClient, http.MethodPost, fixture.server.URL+"/api/apikeys/"+keyID+"/rotate", nil, "", http.StatusOK)
	newToken := rotated["token"].(string)
	requestJSON(t, bearerClient, http.MethodGet, fixture.server.URL+"/api/me", nil, token, http.StatusUnauthorized)
	requestJSON(t, bearerClient, http.MethodGet, fixture.server.URL+"/api/me", nil, newToken, http.StatusOK)
}

func requestJSONArray(
	t *testing.T,
	client *http.Client,
	method string,
	url string,
	bearer string,
	wantStatus int,
) []any {
	t.Helper()
	request, err := http.NewRequest(method, url, nil)
	if err != nil {
		t.Fatal(err)
	}
	if bearer != "" {
		request.Header.Set("Authorization", "Bearer "+bearer)
	}
	response, err := client.Do(request)
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	var decoded []any
	if err := json.NewDecoder(response.Body).Decode(&decoded); err != nil {
		t.Fatalf("%s %s decode response: %v", method, url, err)
	}
	if response.StatusCode != wantStatus {
		t.Fatalf("%s %s status=%d want=%d body=%v", method, url, response.StatusCode, wantStatus, decoded)
	}
	return decoded
}
