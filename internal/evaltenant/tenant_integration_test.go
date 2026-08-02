package evaltenant_test

import (
	"os"
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
	if first.APIKey == "" || len(first.AgentIDs) != len(evaltenant.AgentIDs) {
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
	if len(agents) != len(evaltenant.AgentIDs) {
		t.Fatalf("agents = %+v", agents)
	}
	for _, benchmarkAgent := range agents {
		model, _ := benchmarkAgent.Config["model"].(string)
		expectedModel := "provider/specialist-v1"
		expectedMaxTokens := 2048
		if benchmarkAgent.ID == evaltenant.CoordinatorID || benchmarkAgent.ID == evaltenant.FinanceCoordinatorID || benchmarkAgent.ID == "finance-solo" {
			expectedModel = "provider/coordinator-v1"
		}
		if benchmarkAgent.ID == evaltenant.CoordinatorID || benchmarkAgent.ID == evaltenant.FinanceCoordinatorID {
			expectedMaxTokens = 8192
		}
		switch benchmarkAgent.ID {
		case "finance-retriever", "finance-trend", "finance-accounting", "finance-risk", "finance-solo":
			expectedMaxTokens = 8192
		}
		if model != expectedModel {
			t.Fatalf("agent %s model = %q", benchmarkAgent.ID, model)
		}
		maxTokens := 0
		switch value := benchmarkAgent.Config["maxTokens"].(type) {
		case int:
			maxTokens = value
		case float64:
			maxTokens = int(value)
		}
		if maxTokens != expectedMaxTokens {
			t.Fatalf("agent %s maxTokens = %d, want %d", benchmarkAgent.ID, maxTokens, expectedMaxTokens)
		}
		expectedThinking := ""
		switch benchmarkAgent.ID {
		case evaltenant.CoordinatorID, evaltenant.FinanceCoordinatorID, "finance-retriever", "finance-trend", "finance-accounting", "finance-risk", "finance-solo":
			expectedThinking = "off"
		}
		if thinking, _ := benchmarkAgent.Config["thinking"].(string); thinking != expectedThinking {
			t.Fatalf("agent %s thinking = %q, want %q", benchmarkAgent.ID, thinking, expectedThinking)
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
	if len(resolved.Agents) != len(evaltenant.AgentIDs) {
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
	financeSuite, err := eval.LoadMultiAgentSuite(
		filepath.Join("..", "..", "evals", "multiagent-finance-runtime.yaml"),
	)
	if err != nil {
		t.Fatal(err)
	}
	if len(financeSuite.Cases) != 6 {
		t.Fatalf("finance runtime suite cases = %d", len(financeSuite.Cases))
	}
	for _, evalCase := range financeSuite.Cases {
		if evalCase.ExecutionMode != "runtime" {
			t.Fatalf("invalid finance runtime case: %+v", evalCase)
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

func TestIntegrationProvisionLoadsVerifiedFinanceEvidencePack(t *testing.T) {
	dataStore := newBenchmarkStore(t)
	root := filepath.Join("..", "..")
	result, err := evaltenant.Provision(t.Context(), dataStore, evaltenant.Options{
		CoordinatorModel: "provider/coordinator-v1",
		SpecialistModel:  "provider/specialist-v1",
		EvidenceFile: filepath.Join(
			root,
			"evals",
			"finance_e2e",
			"runtime-agent-evidence.json",
		),
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.Suite != "evals/multiagent-finance-sec-e2e.json" || len(result.EvidenceSHA256) != 64 {
		t.Fatalf("provision result = %+v", result)
	}
	account, err := dataStore.GetUserByLogin(t.Context(), evaltenant.Username)
	if err != nil {
		t.Fatal(err)
	}
	soul, err := dataStore.GetAgentFile(t.Context(), "finance-source", account.ID, "SOUL.md")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(soul), "FSEC-NVDA-01") ||
		!strings.Contains(string(soul), "0001045810-24-000113") ||
		strings.Contains(string(soul), "2026-07-30") {
		t.Fatalf("finance source SOUL.md did not use the verified pack:\n%s", soul)
	}

	suite, err := eval.LoadMultiAgentSuite(filepath.Join(root, result.Suite))
	if err != nil {
		t.Fatal(err)
	}
	if len(suite.Cases) != 12 {
		t.Fatalf("finance SEC runtime suite cases = %d", len(suite.Cases))
	}
}

func TestIntegrationProvisionLoadsHardFinanceEvidencePack(t *testing.T) {
	dataStore := newBenchmarkStore(t)
	root := filepath.Join("..", "..")
	result, err := evaltenant.Provision(t.Context(), dataStore, evaltenant.Options{
		CoordinatorModel: "provider/coordinator-v1",
		SpecialistModel:  "provider/specialist-v1",
		EvidenceFile: filepath.Join(
			root,
			"evals",
			"finance_e2e",
			"runtime-agent-evidence-hard.json",
		),
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.Suite != "evals/multiagent-finance-sec-hard.json" {
		t.Fatalf("hard finance suite = %q", result.Suite)
	}
	account, err := dataStore.GetUserByLogin(t.Context(), evaltenant.Username)
	if err != nil {
		t.Fatal(err)
	}
	soul, err := dataStore.GetAgentFile(t.Context(), "finance-governance", account.ID, "SOUL.md")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(soul), "FHARD-NVDA-01") ||
		!strings.Contains(string(soul), "STALE-NVDA-03") {
		t.Fatalf("hard finance governance SOUL.md did not use the hard pack:\n%s", soul)
	}
}

func TestProvisionRejectsIncompleteFinanceEvidencePack(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evidence.json")
	if err := os.WriteFile(path, []byte(`{
		"version": 1,
		"dataset": "invalid",
		"evidence_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		"agents": {"finance-source": {"FSEC-NVDA-01": "evidence"}}
	}`), 0o600); err != nil {
		t.Fatal(err)
	}
	_, err := evaltenant.Provision(t.Context(), newBenchmarkStore(t), evaltenant.Options{
		CoordinatorModel: "provider/coordinator-v1",
		EvidenceFile:     path,
	})
	if err == nil || !strings.Contains(err.Error(), "all three finance specialists") {
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
