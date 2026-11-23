package auth

import (
	"context"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/fastclaw-ai/fastclaw/internal/store"
	"github.com/fastclaw-ai/fastclaw/internal/users"
)

func newAuthIntegrationStore(t *testing.T) store.Store {
	t.Helper()
	dataStore, err := store.New(&store.StorageConfig{
		Type:        store.StorageSQLite,
		DSN:         "file:" + filepath.Join(t.TempDir(), "auth.db") + "?_fk=1",
		AutoMigrate: true,
	}, t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := dataStore.Close(); err != nil {
			t.Error(err)
		}
	})
	return dataStore
}

func TestIntegrationResolverSessionBearerAndActAs(t *testing.T) {
	dataStore := newAuthIntegrationStore(t)
	accounts, err := users.NewAccounts(dataStore)
	if err != nil {
		t.Fatal(err)
	}
	admin, err := accounts.Create(
		context.Background(),
		"admin",
		"admin@example.com",
		"admin-password",
		"",
		users.RoleSuperAdmin,
	)
	if err != nil {
		t.Fatal(err)
	}
	developer, err := accounts.Create(
		context.Background(),
		"developer",
		"developer@example.com",
		"developer-password",
		"",
		users.RoleUser,
	)
	if err != nil {
		t.Fatal(err)
	}
	if err := dataStore.SaveAgent(context.Background(), &store.AgentRecord{
		ID:     "agent-allowed",
		UserID: developer.ID,
		Name:   "allowed",
	}); err != nil {
		t.Fatal(err)
	}
	apiKeys, err := users.NewAPIKeys(dataStore)
	if err != nil {
		t.Fatal(err)
	}
	_, token, err := apiKeys.Create(context.Background(), developer.ID, "test", []string{"agent-allowed"})
	if err != nil {
		t.Fatal(err)
	}
	resolver, err := NewResolver(dataStore)
	if err != nil {
		t.Fatal(err)
	}

	sessionCookie, err := resolver.IssueSession(context.Background(), admin.ID)
	if err != nil {
		t.Fatal(err)
	}
	sessionRequest := httptest.NewRequest(http.MethodGet, "/protected?actAs="+developer.ID, nil)
	sessionRequest.AddCookie(sessionCookie)
	sessionResponse := httptest.NewRecorder()
	resolver.Middleware(func(w http.ResponseWriter, request *http.Request) {
		identity, ok := FromContext(request.Context())
		if !ok || identity.EffectiveUserID() != developer.ID || !identity.ReadOnly() {
			t.Fatalf("unexpected session identity: %+v ok=%v", identity, ok)
		}
		w.WriteHeader(http.StatusNoContent)
	})(sessionResponse, sessionRequest)
	if sessionResponse.Code != http.StatusNoContent {
		t.Fatalf("session middleware status = %d", sessionResponse.Code)
	}

	bearerRequest := httptest.NewRequest(http.MethodGet, "/protected?actAs="+admin.ID, nil)
	bearerRequest.Header.Set("Authorization", "Bearer "+token)
	bearerResponse := httptest.NewRecorder()
	resolver.Middleware(func(w http.ResponseWriter, request *http.Request) {
		identity, ok := FromContext(request.Context())
		if !ok || identity.EffectiveUserID() != developer.ID || identity.ReadOnly() {
			t.Fatalf("unexpected bearer identity: %+v ok=%v", identity, ok)
		}
		if !identity.CanAccessAgent("agent-allowed") || identity.CanAccessAgent("agent-denied") {
			t.Fatalf("unexpected bearer ACL: %+v", identity.APIKeyAgents)
		}
		w.WriteHeader(http.StatusNoContent)
	})(bearerResponse, bearerRequest)
	if bearerResponse.Code != http.StatusNoContent {
		t.Fatalf("bearer middleware status = %d", bearerResponse.Code)
	}

	if _, err := accounts.Update(context.Background(), developer.ID, "", "", users.StatusDisabled); err != nil {
		t.Fatal(err)
	}
	disabledRequest := httptest.NewRequest(http.MethodGet, "/protected", nil)
	disabledRequest.Header.Set("Authorization", "Bearer "+token)
	disabledResponse := httptest.NewRecorder()
	resolver.Middleware(func(http.ResponseWriter, *http.Request) {
		t.Fatal("disabled account reached protected handler")
	})(disabledResponse, disabledRequest)
	if disabledResponse.Code != http.StatusUnauthorized {
		t.Fatalf("disabled account status = %d", disabledResponse.Code)
	}
}
