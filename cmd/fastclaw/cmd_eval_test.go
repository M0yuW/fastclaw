package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	evalpkg "github.com/fastclaw-ai/fastclaw/internal/eval"
	"github.com/fastclaw-ai/fastclaw/internal/evaltenant"
)

func TestEvalRunCommandIntegration(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		if request.Header.Get("Authorization") != "Bearer command-key" {
			t.Errorf("authorization = %q", request.Header.Get("Authorization"))
		}
		writer.Header().Set("Content-Type", "application/json")
		if _, err := writer.Write([]byte(`{
			"model": "fake",
			"choices": [{"message": {"role": "assistant", "content": "OK"}}],
			"usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}
		}`)); err != nil {
			t.Error(err)
		}
	}))
	defer server.Close()

	suitePath := filepath.Join(t.TempDir(), "suite.yaml")
	if err := os.WriteFile(suitePath, []byte(`
version: 1
name: cli-integration
cases:
  - id: answer
    prompt: Reply OK.
    graders:
      - type: exact
        value: OK
        case_sensitive: true
`), 0o600); err != nil {
		t.Fatal(err)
	}

	command := evalRunCmd()
	var output bytes.Buffer
	command.SetOut(&output)
	command.SetArgs([]string{
		suitePath,
		"--base-url", server.URL,
		"--api-key", "command-key",
		"--format", "json",
		"--fail-under", "1",
	})
	if err := command.ExecuteContext(t.Context()); err != nil {
		t.Fatal(err)
	}

	var report evalpkg.Report
	if err := json.Unmarshal(output.Bytes(), &report); err != nil {
		t.Fatalf("decode command output: %v\n%s", err, output.String())
	}
	if report.Suite != "cli-integration" || report.Metrics.RunPassRate != 1 {
		t.Fatalf("unexpected report: %+v", report)
	}
	if report.Metrics.TotalTokens != 3 {
		t.Fatalf("total tokens = %d", report.Metrics.TotalTokens)
	}
}

func TestEvalRunCommandRejectsInvalidFormatBeforeLoadingSuite(t *testing.T) {
	command := evalRunCmd()
	command.SetArgs([]string{"missing.yaml", "--format", "xml"})
	err := command.Execute()
	if err == nil || err.Error() != `unsupported output format "xml"` {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestEvalTauRunCommandIntegration(t *testing.T) {
	var (
		callCount  int
		sessionKey string
	)
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		callCount++
		if sessionKey == "" {
			sessionKey = request.Header.Get("x-fastclaw-session-key")
		} else if request.Header.Get("x-fastclaw-session-key") != sessionKey {
			t.Errorf("session changed between turns")
		}
		var completionRequest map[string]any
		if err := json.NewDecoder(request.Body).Decode(&completionRequest); err != nil {
			t.Error(err)
			http.Error(writer, err.Error(), http.StatusBadRequest)
			return
		}
		fastClaw := completionRequest["fastclaw"].(map[string]any)
		if _, exists := fastClaw["tool_behaviors"]; !exists {
			t.Error("tool_behaviors missing")
		}
		state := fastClaw["state"].(map[string]any)
		output := "Please confirm cancellation."
		trace := []map[string]any{}
		if callCount == 2 {
			state["status"] = "cancelled"
			output = "The order was cancelled."
			trace = append(trace, map[string]any{
				"type": "tool_call", "name": "cancel_order", "arguments": `{}`,
			})
		}
		writer.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(writer).Encode(map[string]any{
			"model": "fake",
			"choices": []map[string]any{
				{"message": map[string]string{"role": "assistant", "content": output}},
			},
			"usage": map[string]int{},
			"fastclaw": map[string]any{
				"trace": trace,
				"state": state,
			},
		}); err != nil {
			t.Error(err)
		}
	}))
	defer server.Close()

	suitePath := filepath.Join(t.TempDir(), "tau.yaml")
	if err := os.WriteFile(suitePath, []byte(`
version: 1
name: cli-tau
cases:
  - id: cancel
    initial_state:
      status: pending
    tools:
      - name: cancel_order
        parameters:
          type: object
        behavior:
          updates:
            - path: status
              value: cancelled
    turns:
      - prompt: Cancel the order.
        expected_state:
          status: pending
        communicate: [confirm]
        forbidden_tools: [cancel_order]
      - prompt: I confirm.
    expected_state:
      status: cancelled
    communicate: [cancelled]
`), 0o600); err != nil {
		t.Fatal(err)
	}

	command := evalTauRunCmd()
	var output bytes.Buffer
	command.SetOut(&output)
	command.SetArgs([]string{
		suitePath,
		"--base-url", server.URL,
		"--format", "json",
		"--fail-under", "1",
	})
	if err := command.ExecuteContext(t.Context()); err != nil {
		t.Fatal(err)
	}

	var report evalpkg.Report
	if err := json.Unmarshal(output.Bytes(), &report); err != nil {
		t.Fatalf("decode command output: %v\n%s", err, output.String())
	}
	if report.Metrics.EndToEndTaskSuccess != 1 ||
		report.Metrics.StateAccuracy != 1 ||
		report.Metrics.PolicyComplianceRate != 1 {
		t.Fatalf("unexpected tau metrics: %+v", report.Metrics)
	}
	if callCount != 2 {
		t.Fatalf("HTTP calls = %d", callCount)
	}
}

func TestEvalSWERunCommandIntegration(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		var completionRequest map[string]any
		if err := json.NewDecoder(request.Body).Decode(&completionRequest); err != nil {
			t.Error(err)
			http.Error(writer, err.Error(), http.StatusBadRequest)
			return
		}
		fastClaw := completionRequest["fastclaw"].(map[string]any)
		files := fastClaw["state"].(map[string]any)["files"].(map[string]any)
		if _, exposed := files["calc_test.go"]; exposed {
			t.Error("hidden test was exposed")
		}
		files["calc.go"] = "package calc\n\nfunc Add(left, right int) int { return left + right }\n"
		writer.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(writer).Encode(map[string]any{
			"model": "fake-coder",
			"choices": []map[string]any{
				{"message": map[string]string{"role": "assistant", "content": "Fixed Add."}},
			},
			"usage": map[string]int{},
			"fastclaw": map[string]any{
				"state": fastClaw["state"],
				"trace": []map[string]any{
					{"type": "tool_call", "name": "write_file", "arguments": `{"path":"calc.go"}`},
				},
			},
		}); err != nil {
			t.Error(err)
		}
	}))
	defer server.Close()

	root := t.TempDir()
	fixture := filepath.Join(root, "fixture")
	if err := os.MkdirAll(fixture, 0o700); err != nil {
		t.Fatal(err)
	}
	files := map[string]string{
		"go.mod":       "module example.com/calc\n\ngo 1.25\n",
		"calc.go":      "package calc\n\nfunc Add(left, right int) int { return left - right }\n",
		"calc_test.go": "package calc\n\nimport \"testing\"\n\nfunc TestAdd(t *testing.T) { if Add(1, 2) != 3 { t.Fatal(\"wrong sum\") } }\n",
	}
	for name, content := range files {
		if err := os.WriteFile(filepath.Join(fixture, name), []byte(content), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	suitePath := filepath.Join(root, "swe.yaml")
	if err := os.WriteFile(suitePath, []byte(`
version: 1
name: cli-swe
cases:
  - instance_id: local__calc-1
    fixture: fixture
    editable_files: [calc.go]
    test_command: go test ./...
    problem_statement: Add must return the sum of both inputs.
`), 0o600); err != nil {
		t.Fatal(err)
	}
	predictionsPath := filepath.Join(root, "predictions.jsonl")

	command := evalSWERunCmd()
	var output bytes.Buffer
	command.SetOut(&output)
	command.SetArgs([]string{
		suitePath,
		"--base-url", server.URL,
		"--format", "json",
		"--predictions-output", predictionsPath,
		"--fail-under", "1",
	})
	if err := command.ExecuteContext(t.Context()); err != nil {
		t.Fatal(err)
	}
	var report evalpkg.Report
	if err := json.Unmarshal(output.Bytes(), &report); err != nil {
		t.Fatalf("decode command output: %v\n%s", err, output.String())
	}
	if report.Metrics.SWEResolutionRate != 1 || report.Metrics.SWECompletedInstances != 1 {
		t.Fatalf("unexpected SWE metrics: %+v", report.Metrics)
	}
	predictions, err := os.ReadFile(predictionsPath)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Contains(predictions, []byte(`"instance_id":"local__calc-1"`)) ||
		!bytes.Contains(predictions, []byte(`"model_name_or_path":"fake-coder"`)) {
		t.Fatalf("unexpected predictions:\n%s", predictions)
	}
}

func TestEvalMultiAgentRunCommandIntegration(t *testing.T) {
	var callCount int
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		callCount++
		var completionRequest map[string]any
		if err := json.NewDecoder(request.Body).Decode(&completionRequest); err != nil {
			t.Error(err)
			http.Error(writer, err.Error(), http.StatusBadRequest)
			return
		}
		fastClaw := completionRequest["fastclaw"].(map[string]any)
		if fastClaw["isolate_tools"] != true ||
			fastClaw["eval"] != true ||
			fastClaw["include_usage_breakdown"] != true {
			t.Errorf("missing isolated eval options: %+v", fastClaw)
		}
		if _, exists := fastClaw["pricing"]; !exists {
			t.Error("pricing missing from eval request")
		}
		output := "I do not have the specialist evidence."
		trace := []map[string]any{}
		modelCalls := []map[string]any{{
			"sequence": 1, "agent_id": "coordinator", "role": "coordinator",
			"model": "fake-coordinator", "total_tokens": 50,
			"estimated_cost_usd": 0.001, "priced": true, "latency_ms": 100,
		}}
		if callCount == 1 {
			if _, exists := completionRequest["tools"]; exists {
				t.Error("solo request unexpectedly included tools")
			}
		} else {
			tools := completionRequest["tools"].([]any)
			if len(tools) != 1 {
				t.Fatalf("team tools = %d", len(tools))
			}
			output = "Signal alpha and signal beta support action gamma."
			trace = []map[string]any{
				{
					"type": "tool_call", "name": "spawn_subagent",
					"arguments": `{"agentId":"alpha-agent","task":"analyze alpha"}`,
				},
				{
					"type": "tool_call", "name": "spawn_subagent",
					"arguments": `{"agentId":"beta-agent","task":"analyze beta"}`,
				},
			}
			modelCalls = []map[string]any{
				{
					"sequence": 1, "agent_id": "coordinator", "role": "coordinator",
					"model": "fake-coordinator", "total_tokens": 80,
					"estimated_cost_usd": 0.002, "priced": true, "latency_ms": 200,
				},
				{
					"sequence": 2, "agent_id": "alpha-agent", "role": "subagent",
					"model": "fake-specialist", "total_tokens": 40,
					"estimated_cost_usd": 0.0004, "priced": true, "latency_ms": 50,
				},
				{
					"sequence": 3, "agent_id": "beta-agent", "role": "subagent",
					"model": "fake-specialist", "total_tokens": 40,
					"estimated_cost_usd": 0.0004, "priced": true, "latency_ms": 60,
				},
			}
		}
		writer.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(writer).Encode(map[string]any{
			"model": "fake-coordinator",
			"choices": []map[string]any{
				{"message": map[string]string{"role": "assistant", "content": output}},
			},
			"usage": map[string]int{},
			"fastclaw": map[string]any{
				"trace": trace, "model_calls": modelCalls,
			},
		}); err != nil {
			t.Error(err)
		}
	}))
	defer server.Close()

	suitePath := filepath.Join(t.TempDir(), "multiagent.yaml")
	if err := os.WriteFile(suitePath, []byte(`
version: 1
name: cli-multiagent
pricing:
  fake-coordinator:
    input_per_million: 1
    output_per_million: 2
cases:
  - id: synthesis
    prompt: Combine the private specialist signals into an action.
    max_delegations: 2
    agents:
      - id: alpha-agent
        role: Analyze alpha.
        response: Signal alpha.
        contribution_values: [signal alpha]
      - id: beta-agent
        role: Analyze beta.
        response: Signal beta.
        contribution_values: [signal beta]
    milestones:
      - id: evidence
        values: [signal alpha, signal beta]
      - id: action
        values: [action gamma]
`), 0o600); err != nil {
		t.Fatal(err)
	}

	command := evalMultiAgentRunCmd()
	var output bytes.Buffer
	command.SetOut(&output)
	command.SetArgs([]string{
		suitePath,
		"--base-url", server.URL,
		"--format", "json",
		"--fail-under", "1",
	})
	if err := command.ExecuteContext(t.Context()); err != nil {
		t.Fatal(err)
	}
	var report evalpkg.Report
	if err := json.Unmarshal(output.Bytes(), &report); err != nil {
		t.Fatalf("decode command output: %v\n%s", err, output.String())
	}
	if report.Metrics.MATeamSuccessRate != 1 ||
		report.Metrics.MASoloSuccessRate != 0 ||
		report.Metrics.MACollaborationGain != 1 ||
		report.Metrics.MACoordinatorTokens != 80 ||
		report.Metrics.MASubAgentTokens != 80 ||
		report.Metrics.MAPricingCoverage != 1 {
		t.Fatalf("unexpected multi-agent metrics: %+v", report.Metrics)
	}
	if callCount != 2 {
		t.Fatalf("HTTP calls = %d", callCount)
	}
}

func TestEvalMultiAgentTenantProvisionCommandIntegration(t *testing.T) {
	home := t.TempDir()
	t.Setenv("FASTCLAW_HOME", home)
	t.Setenv(
		"FASTCLAW_STORAGE_DSN",
		"file:"+filepath.Join(home, "runtime-benchmark.db")+"?_fk=1",
	)

	command := evalMultiAgentTenantProvisionCmd()
	outputPath := filepath.Join(home, "runtime-tenant.json")
	command.SetArgs([]string{
		"--coordinator-model", "provider/coordinator",
		"--specialist-model", "provider/specialist",
		"--output", outputPath,
	})
	if err := command.ExecuteContext(t.Context()); err != nil {
		t.Fatal(err)
	}
	output, err := os.ReadFile(outputPath)
	if err != nil {
		t.Fatal(err)
	}
	var result evaltenant.Result
	if err := json.Unmarshal(output, &result); err != nil {
		t.Fatalf("decode provision output: %v\n%s", err, output)
	}
	if result.Username != evaltenant.Username ||
		result.APIKey == "" ||
		len(result.AgentIDs) != 5 {
		t.Fatalf("provision result = %+v", result)
	}
	fileInfo, err := os.Stat(outputPath)
	if err != nil {
		t.Fatal(err)
	}
	if fileInfo.Mode().Perm() != 0o600 {
		t.Fatalf("credential mode = %o", fileInfo.Mode().Perm())
	}
}
