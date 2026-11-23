package eval

import (
	"context"
	"path/filepath"
	"testing"
)

func TestLoadBundledTauSuite(t *testing.T) {
	path := filepath.Join("..", "..", "evals", "tau-retail-subset.yaml")
	suite, err := LoadTauSuite(path)
	if err != nil {
		t.Fatal(err)
	}
	if suite.Name != "tau-retail-scripted-subset" || len(suite.Cases) != 3 {
		t.Fatalf("unexpected suite: %s, cases = %d", suite.Name, len(suite.Cases))
	}
}

func TestTauRunnerCarriesStateAcrossTurnsAndScoresComponents(t *testing.T) {
	var (
		sessionKey string
		callCount  int
	)
	runner := TauRunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			callCount++
			if sessionKey == "" {
				sessionKey = request.SessionKey
			} else if request.SessionKey != sessionKey {
				t.Fatalf("session changed between turns: %q != %q", request.SessionKey, sessionKey)
			}
			status := request.State["orders"].(map[string]any)["ord-1"].(map[string]any)["status"]
			switch callCount {
			case 1:
				if status != "pending" {
					t.Fatalf("turn 1 status = %v", status)
				}
				return ExecutionResponse{
					Output: "Please confirm that you want to cancel order ord-1.",
					State:  cloneEvalState(request.State),
					Trace: []TraceEvent{
						{Type: "tool_call", Name: "get_order", Arguments: `{"order_id":"ord-1"}`},
					},
				}, nil
			case 2:
				if status != "pending" {
					t.Fatalf("turn 2 input status = %v", status)
				}
				nextState := cloneEvalState(request.State)
				nextState["orders"].(map[string]any)["ord-1"].(map[string]any)["status"] = "cancelled"
				return ExecutionResponse{
					Output: "Order ord-1 has been cancelled.",
					State:  nextState,
					Trace: []TraceEvent{
						{Type: "tool_call", Name: "cancel_order", Arguments: `{"order_id":"ord-1"}`},
					},
				}, nil
			default:
				t.Fatalf("unexpected call %d", callCount)
				return ExecutionResponse{}, nil
			}
		}),
	}

	initialState := map[string]any{
		"orders": map[string]any{
			"ord-1": map[string]any{"status": "pending"},
		},
	}
	suite := TauSuite{
		Version: SuiteVersion,
		Name:    "tau-state",
		Cases: []TauCase{
			{
				ID:           "cancel-after-confirmation",
				InitialState: initialState,
				Tools: []ToolDefinition{
					statefulTestTool("get_order"),
					statefulTestTool("cancel_order"),
				},
				Turns: []TauTurn{
					{
						Prompt:         "Cancel order ord-1.",
						ExpectedState:  initialState,
						Communicate:    []string{"confirm"},
						ForbiddenTools: []string{"cancel_order"},
					},
					{Prompt: "Yes, confirm cancellation."},
				},
				ExpectedState: map[string]any{
					"orders": map[string]any{
						"ord-1": map[string]any{"status": "cancelled"},
					},
				},
				Communicate: []string{"cancelled"},
			},
		},
	}

	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	if !report.Cases[0].PassAt1 {
		t.Fatalf("attempt failed: %+v", report.Cases[0].Attempts[0].Graders)
	}
	metrics := report.Metrics
	if metrics.EndToEndTaskSuccess != 1 || metrics.StateAccuracy != 1 {
		t.Fatalf("unexpected state metrics: %+v", metrics)
	}
	if metrics.CommunicationAccuracy != 1 || metrics.PolicyComplianceRate != 1 {
		t.Fatalf("unexpected policy metrics: %+v", metrics)
	}
	if metrics.AverageTurns != 2 {
		t.Fatalf("average turns = %v", metrics.AverageTurns)
	}
	trace := report.Cases[0].Attempts[0].Trace
	if len(trace) != 2 || trace[0].Turn != 1 || trace[1].Turn != 2 {
		t.Fatalf("unexpected turn trace: %+v", trace)
	}
}

func TestTauRunnerFailsEndToEndWhenPolicyIsViolated(t *testing.T) {
	runner := TauRunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			return ExecutionResponse{
				Output: "Done.",
				State:  cloneEvalState(request.State),
				Trace: []TraceEvent{
					{Type: "tool_call", Name: "cancel_order", Arguments: `{"order_id":"ord-1"}`},
				},
			}, nil
		}),
	}
	state := map[string]any{"status": "pending"}
	suite := TauSuite{
		Version: SuiteVersion,
		Name:    "tau-policy",
		Cases: []TauCase{
			{
				ID:             "confirmation",
				InitialState:   state,
				Tools:          []ToolDefinition{statefulTestTool("cancel_order")},
				Turns:          []TauTurn{{Prompt: "Cancel it."}},
				ExpectedState:  state,
				ForbiddenTools: []string{"cancel_order"},
			},
		},
	}
	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	if report.Metrics.PolicyComplianceRate != 0 || report.Metrics.EndToEndTaskSuccess != 0 {
		t.Fatalf("unexpected metrics: %+v", report.Metrics)
	}
}

func statefulTestTool(name string) ToolDefinition {
	return ToolDefinition{
		Name:       name,
		Parameters: map[string]any{"type": "object"},
		Behavior:   &StateToolBehavior{Result: map[string]any{"ok": true}},
	}
}
