package tools

import (
	"context"
	"testing"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

func TestEvidenceIsolationAndRetry(t *testing.T) {
	root := func(owner, id string) context.Context {
		ctx := bus.ContextWithInternalExecution(context.Background(), id)
		ctx = ContextWithExecutionScope(ctx, ExecutionScope{UserID: owner, AgentID: "coordinator"})
		return StartTaskEvidence(ctx, owner, false)
	}
	ctx := root("owner", "one")
	child := ContextWithExecutionScope(ctx, ExecutionScope{UserID: "owner", AgentID: "a"})
	child = bus.ContextWithInternalCallPath(child, []string{"coordinator", "a"})
	args := []byte(`{"key":"event","content":"announcement","source":"fixture"}`)
	first, err := publishEvidence(child, args)
	if err != nil {
		t.Fatal(err)
	}
	second, err := publishEvidence(child, args)
	if err != nil || first != second {
		t.Fatal("retry did not return same receipt", err)
	}
	if _, err := publishEvidence(child, []byte(`{"key":"event","content":"changed","source":"fixture"}`)); err == nil {
		t.Fatal("accepted conflicting evidence")
	}
	messages := []provider.Message{{Role: "tool", Content: "initial"}}
	for _, other := range []context.Context{root("owner", "two"), root("another", "one")} {
		if got := PrepareEvidenceInput(other, messages); got[0].Content != "initial" {
			t.Fatal("leaked evidence")
		}
	}
	for _, other := range []context.Context{ContextWithExecutionScope(child, ExecutionScope{UserID: "another", AgentID: "a"}), bus.ContextWithInternalExecution(child, "two")} {
		if _, err := publishEvidence(other, args); err == nil {
			t.Fatal("accepted mismatched scope")
		}
	}
}
