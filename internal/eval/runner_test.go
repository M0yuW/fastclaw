package eval

import (
	"context"
	"testing"
)

type executorFunc func(context.Context, ExecutionRequest) (ExecutionResponse, error)

func (function executorFunc) Execute(ctx context.Context, request ExecutionRequest) (ExecutionResponse, error) {
	return function(ctx, request)
}

func TestRunnerUsesFreshSessionsAcrossRuns(t *testing.T) {
	var sessionKeys []string
	runner := Runner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			sessionKeys = append(sessionKeys, request.SessionKey)
			return ExecutionResponse{Output: "ok"}, nil
		}),
	}
	suite := Suite{
		Version: SuiteVersion,
		Name:    "session-isolation",
		Cases: []Case{
			{
				ID:      "answer",
				Prompt:  "Reply OK.",
				Graders: []GraderSpec{{Type: "exact", Value: "ok"}},
			},
		},
	}

	if _, err := runner.Run(t.Context(), suite); err != nil {
		t.Fatal(err)
	}
	if _, err := runner.Run(t.Context(), suite); err != nil {
		t.Fatal(err)
	}
	if len(sessionKeys) != 2 {
		t.Fatalf("session key count = %d", len(sessionKeys))
	}
	if sessionKeys[0] == sessionKeys[1] {
		t.Fatalf("session key reused across runs: %q", sessionKeys[0])
	}
}

func TestRunnerCalculatesInvalidToolMetrics(t *testing.T) {
	runner := Runner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			return ExecutionResponse{
				Output: "done",
				Trace: []TraceEvent{
					{Type: "tool_call", Name: "lookup", Arguments: `not-json`},
				},
			}, nil
		}),
	}
	suite := Suite{
		Version: SuiteVersion,
		Name:    "invalid-tools",
		Cases: []Case{
			{
				ID:     "lookup",
				Prompt: "Look it up.",
				Tools: []ToolDefinition{
					{Name: "lookup", Parameters: map[string]any{"type": "object"}},
				},
				Graders: []GraderSpec{
					{
						Type: "tool_trace",
						Calls: []ExpectedToolCall{
							{Name: "lookup", Arguments: map[string][]any{"id": {1}}},
						},
					},
				},
			},
		},
	}
	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	metrics := report.Metrics
	if metrics.TotalToolCalls != 1 || metrics.InvalidToolCalls != 1 || metrics.InvalidToolCallRate != 1 {
		t.Fatalf("unexpected invalid tool metrics: %+v", metrics)
	}
	if metrics.ToolTraceGraders != 1 || metrics.ToolTraceAccuracy != 0 {
		t.Fatalf("unexpected trace metrics: %+v", metrics)
	}
}
