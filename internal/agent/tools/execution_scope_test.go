package tools

import (
	"context"
	"testing"
)

func TestExecutionScopeRoundTrip(t *testing.T) {
	expected := ExecutionScope{
		UserID:    "user-1",
		AgentID:   "agent-1",
		SessionID: "session-1",
	}
	ctx := ContextWithExecutionScope(context.Background(), expected)
	actual, ok := ExecutionScopeFromContext(ctx)
	if !ok {
		t.Fatal("execution scope missing")
	}
	if actual != expected {
		t.Fatalf("unexpected scope: %#v", actual)
	}
}
