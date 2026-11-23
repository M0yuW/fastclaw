package evaltenant_test

import (
	"path/filepath"
	"strings"
	"testing"

	"github.com/fastclaw-ai/fastclaw/internal/eval"
	"github.com/fastclaw-ai/fastclaw/internal/evaltenant"
	"github.com/fastclaw-ai/fastclaw/internal/scope"
	"github.com/fastclaw-ai/fastclaw/internal/store"
	"github.com/fastclaw-ai/fastclaw/internal/users"
)

func TestIntegrationProvisionFixedRuntimeBenchmarkTenant(t *testing.T) {
	dataStore := newBenchmarkStore(t)
	first, err := evaltenant.Provision(t.Context(), dataStore, evaltenant.Options{
		CoordinatorModel: "provider/coordinator-v1",
		SpecialistModel:  "provider/specialist-v1",
	})
	if err != nil {
		t.Fatal(err)
	}
	if first.APIKey == "" || len(first.AgentIDs) != 5 {
		t.Fatalf("provision result = %+v", first)
	}

	account, err := dataStore.GetUserByLogin(t.Context(), evaltenant.Username)
	if err != nil {
		t.Fatal(err)
	}
	if account.ID != first.UserID || account.Role != users.RoleUser || account.Status != users.StatusActive {
		t.Fatalf("account = %+v", account)
	}
	defaults, err := scope.Setting(
		t.Context(),
		dataStore,
		"agents.defaults",
		account.ID,
		"",
		"",
	)
	if err != nil || defaults["model"] != "provider/coordinator-v1" {
		t.Fatalf("tenant defaults = %+v, err=%v", defaults, err)
	}
	agents, err := dataStore.ListAgents(t.Context(), account.ID)
	if err != nil {
		t.Fatal(err)
	}
	if len(agents) != 5 {
		t.Fatalf("agents = %+v", agents)
	}
	for _, benchmarkAgent := range agents {
		model, _ := benchmarkAgent.Config["model"].(string)
		expectedModel := "provider/specialist-v1"
		if benchmarkAgent.ID == evaltenant.CoordinatorID {
			expectedModel = "provider/coordinator-v1"
		}
		if model != expectedModel {
			t.Fatalf("agent %s model = %q", benchmarkAgent.ID, model)
		}
		soul, err := dataStore.GetAgentFile(t.Context(), benchmarkAgent.ID, account.ID, "SOUL.md")
		if err != nil || len(soul) == 0 {
			t.Fatalf("agent %s SOUL.md = %q, err=%v", benchmarkAgent.ID, soul, err)
		}
	}
	coordinatorSoul, err := dataStore.GetAgentFile(
		t.Context(),
		evaltenant.CoordinatorID,
		account.ID,
		"SOUL.md",
	)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(coordinatorSoul), "OBS-101") {
		t.Fatal("coordinator leaked specialist evidence")
	}

	apiKeys, err := users.NewAPIKeys(dataStore)
	if err != nil {
		t.Fatal(err)
	}
	resolved, err := apiKeys.LookupByToken(t.Context(), first.APIKey)
	if err != nil {
		t.Fatal(err)
	}
	if len(resolved.Agents) != 5 {
		t.Fatalf("API key agents = %+v", resolved.Agents)
	}

	second, err := evaltenant.Provision(t.Context(), dataStore, evaltenant.Options{
		CoordinatorModel: "provider/coordinator-v2",
		SpecialistModel:  "provider/specialist-v2",
	})
	if err != nil {
		t.Fatal(err)
	}
	if second.UserID != first.UserID || second.APIKey == first.APIKey {
		t.Fatalf("idempotent provision first=%+v second=%+v", first, second)
	}
	if _, err := apiKeys.LookupByToken(t.Context(), first.APIKey); err == nil {
		t.Fatal("rotated API key remained valid")
	}
	if _, err := apiKeys.LookupByToken(t.Context(), second.APIKey); err != nil {
		t.Fatalf("new API key invalid: %v", err)
	}

	suite, err := eval.LoadMultiAgentSuite(
		filepath.Join("..", "..", "evals", "multiagent-runtime-tenant.yaml"),
	)
	if err != nil {
		t.Fatal(err)
	}
	if len(suite.Cases) != 8 {
		t.Fatalf("runtime suite cases = %d", len(suite.Cases))
	}
	for _, evalCase := range suite.Cases {
		if evalCase.ExecutionMode != "runtime" ||
			evalCase.CoordinatorAgentID != "" && evalCase.CoordinatorAgentID != evaltenant.CoordinatorID {
			t.Fatalf("invalid runtime case: %+v", evalCase)
		}
	}
}

func TestProvisionRejectsModelsFromDifferentProviders(t *testing.T) {
	dataStore := newBenchmarkStore(t)
	_, err := evaltenant.Provision(t.Context(), dataStore, evaltenant.Options{
		CoordinatorModel: "provider-a/coordinator",
		SpecialistModel:  "provider-b/specialist",
	})
	if err == nil || !strings.Contains(err.Error(), "same provider key") {
		t.Fatalf("Provision() error = %v", err)
	}
}

func newBenchmarkStore(t *testing.T) store.Store {
	t.Helper()
	dataStore, err := store.New(&store.StorageConfig{
		Type:        store.StorageSQLite,
		DSN:         "file:" + filepath.Join(t.TempDir(), "runtime-benchmark.db") + "?_fk=1",
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
