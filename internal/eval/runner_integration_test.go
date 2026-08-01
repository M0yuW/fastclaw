package eval

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

func TestIntegrationRunnerHTTP(t *testing.T) {
	var (
		mu          sync.Mutex
		flakyCalls  int
		sessionKeys = make(map[string]struct{})
	)
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		if request.URL.Path != "/v1/chat/completions" {
			t.Errorf("path = %q", request.URL.Path)
		}
		if request.Header.Get("Authorization") != "Bearer test-key" {
			t.Errorf("authorization = %q", request.Header.Get("Authorization"))
		}
		if request.Header.Get("x-fastclaw-agent-id") != "eval-agent" {
			t.Errorf("agent ID = %q", request.Header.Get("x-fastclaw-agent-id"))
		}
		sessionKey := request.Header.Get("x-fastclaw-session-key")
		mu.Lock()
		if _, exists := sessionKeys[sessionKey]; exists {
			t.Errorf("session key %q was reused", sessionKey)
		}
		sessionKeys[sessionKey] = struct{}{}
		mu.Unlock()

		var completionRequest chatCompletionRequest
		if err := json.NewDecoder(request.Body).Decode(&completionRequest); err != nil {
			t.Error(err)
			http.Error(writer, err.Error(), http.StatusBadRequest)
			return
		}
		output := "42"
		if completionRequest.Messages[0].Content == "flaky" {
			mu.Lock()
			flakyCalls++
			call := flakyCalls
			mu.Unlock()
			if call == 1 {
				output = "not yet"
			}
		}
		writer.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(writer).Encode(map[string]any{
			"model": "fake-model",
			"choices": []map[string]any{
				{"message": map[string]string{"role": "assistant", "content": output}},
			},
			"usage": map[string]int{
				"prompt_tokens":     4,
				"completion_tokens": 6,
				"total_tokens":      10,
			},
		}); err != nil {
			t.Error(err)
		}
	}))
	defer server.Close()

	suite := Suite{
		Version: SuiteVersion,
		Name:    "integration",
		Defaults: Defaults{
			AgentID:     "eval-agent",
			Repetitions: 2,
		},
		Cases: []Case{
			{
				ID:      "stable",
				Prompt:  "stable",
				Graders: []GraderSpec{{Type: "exact", Value: "42"}},
			},
			{
				ID:      "flaky",
				Prompt:  "flaky",
				Graders: []GraderSpec{{Type: "exact", Value: "42"}},
			},
		},
	}
	runner := Runner{
		Executor: &HTTPExecutor{
			BaseURL: server.URL,
			APIKey:  "test-key",
			Client:  server.Client(),
		},
	}
	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}

	metrics := report.Metrics
	if metrics.TotalCases != 2 || metrics.TotalRuns != 4 || metrics.PassedRuns != 3 {
		t.Fatalf("unexpected run counts: %+v", metrics)
	}
	if metrics.RunPassRate != 0.75 || metrics.PassAt1 != 0.5 || metrics.PassAtK != 1 {
		t.Fatalf("unexpected pass metrics: %+v", metrics)
	}
	if metrics.ConsistencyRate != 0.5 {
		t.Fatalf("consistency rate = %v", metrics.ConsistencyRate)
	}
	if metrics.TotalTokens != 40 || metrics.TokensPerPassedRun != 40.0/3.0 {
		t.Fatalf("unexpected token metrics: %+v", metrics)
	}
	if len(sessionKeys) != 4 {
		t.Fatalf("unique session keys = %d, want 4", len(sessionKeys))
	}
}

func TestIntegrationHTTPExecutorSurfacesAPIErrors(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		http.Error(writer, "agent not found", http.StatusNotFound)
	}))
	defer server.Close()

	executor := HTTPExecutor{BaseURL: server.URL, Client: server.Client()}
	_, err := executor.Execute(t.Context(), ExecutionRequest{Prompt: "hello"})
	if err == nil {
		t.Fatal("Execute() error = nil")
	}
}

func TestIntegrationHTTPExecutorSurfacesAgentTurnErrors(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		writer.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(writer).Encode(map[string]any{
			"model": "fake-model",
			"choices": []map[string]any{
				{"message": map[string]string{"role": "assistant", "content": "Sorry, I encountered an error processing your request."}},
			},
			"usage": map[string]int{"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
			"fastclaw": map[string]any{
				"trace": []map[string]any{{"type": "error", "message": "provider read timed out"}},
				"model_calls": []map[string]any{{
					"sequence": 1, "agent_id": "eval-agent", "role": "coordinator",
					"model": "fake-model", "prompt_tokens": 4, "completion_tokens": 2,
					"total_tokens": 6, "error": "provider read timed out",
				}},
			},
		}); err != nil {
			t.Error(err)
		}
	}))
	defer server.Close()

	executor := HTTPExecutor{BaseURL: server.URL, Client: server.Client()}
	response, err := executor.Execute(t.Context(), ExecutionRequest{Prompt: "hello"})
	if err == nil || !strings.Contains(err.Error(), "provider read timed out") {
		t.Fatalf("Execute() error = %v", err)
	}
	if response.Usage.TotalTokens != 6 || len(response.ModelCalls) != 1 {
		t.Fatalf("failed turn telemetry was discarded: %+v", response)
	}
}

func TestIntegrationRunnerHTTPToolTrace(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		var completionRequest chatCompletionRequest
		if err := json.NewDecoder(request.Body).Decode(&completionRequest); err != nil {
			t.Error(err)
			http.Error(writer, err.Error(), http.StatusBadRequest)
			return
		}
		if len(completionRequest.Tools) != 1 || completionRequest.Tools[0].Function.Name != "math.gcd" {
			t.Errorf("unexpected tools: %+v", completionRequest.Tools)
		}
		if !completionRequest.FastClaw.Eval || !completionRequest.FastClaw.IncludeTrace {
			t.Errorf("missing eval trace options: %+v", completionRequest.FastClaw)
		}
		writer.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(writer).Encode(map[string]any{
			"model": "fake-model",
			"choices": []map[string]any{
				{"message": map[string]string{"role": "assistant", "content": "10"}},
			},
			"usage": map[string]int{},
			"fastclaw": map[string]any{
				"trace": []map[string]any{
					{
						"type": "tool_call", "id": "call-1", "name": "math.gcd",
						"arguments": `{"num1":40,"num2":50}`, "round": 1,
					},
					{
						"type": "tool_result", "id": "call-1", "name": "math.gcd",
						"result": "10", "round": 1,
					},
				},
			},
		}); err != nil {
			t.Error(err)
		}
	}))
	defer server.Close()

	suite := Suite{
		Version: SuiteVersion,
		Name:    "tool-trace",
		Cases: []Case{
			{
				ID:     "gcd",
				Prompt: "Calculate the GCD of 40 and 50.",
				Tools: []ToolDefinition{
					{
						Name:       "math.gcd",
						Parameters: map[string]any{"type": "object"},
						Result:     "10",
					},
				},
				Graders: []GraderSpec{
					{
						Type: "tool_trace",
						Calls: []ExpectedToolCall{
							{
								Name: "math.gcd",
								Arguments: map[string][]any{
									"num1": {40},
									"num2": {50},
								},
							},
						},
					},
				},
			},
		},
	}
	runner := Runner{Executor: &HTTPExecutor{BaseURL: server.URL, Client: server.Client()}}
	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	if report.Metrics.ToolTraceAccuracy != 1 || report.Metrics.TotalToolCalls != 1 {
		t.Fatalf("unexpected tool metrics: %+v", report.Metrics)
	}
	if report.Metrics.InvalidToolCallRate != 0 || !report.Cases[0].PassAt1 {
		t.Fatalf("unexpected report: %+v", report)
	}
}
