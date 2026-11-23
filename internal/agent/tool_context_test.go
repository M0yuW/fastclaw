package agent

import (
	"context"
	"encoding/json"
	"testing"

	"github.com/fastclaw-ai/fastclaw/internal/agent/tools"
	"github.com/fastclaw-ai/fastclaw/internal/bus"
)

func TestRequestToolRegistryOverridesSharedRegistryForOneTurn(t *testing.T) {
	fake := newFakeStreamingProvider(
		openAIToolStream("call-1", "scoped_tool", `{}`, ""),
		openAITextStream("final"),
	)
	defer fake.server.Close()
	testAgent := newStreamingTestAgent(t, fake, 4)
	testAgent.ToolRegistry().Register(
		"scoped_tool",
		"shared",
		map[string]any{"type": "object"},
		func(context.Context, json.RawMessage) (string, error) {
			return "shared result", nil
		},
	)
	requestRegistry := tools.NewEmptyRegistry()
	requestRegistry.Register(
		"scoped_tool",
		"request",
		map[string]any{"type": "object"},
		func(context.Context, json.RawMessage) (string, error) {
			return "request result", nil
		},
	)
	ctx := ContextWithToolRegistry(t.Context(), requestRegistry)
	reply := testAgent.HandleMessage(ctx, bus.InboundMessage{
		Channel: "test",
		ChatID:  "request-tools",
		Text:    "use the scoped tool",
	})
	if reply != "final" {
		t.Fatalf("reply = %q", reply)
	}
	messages := testAgent.Sessions().Get("test", "request-tools").GetMessages()
	if len(messages) != 4 || messages[2].Role != "tool" || messages[2].Content != "request result" {
		t.Fatalf("unexpected messages: %+v", messages)
	}
}
