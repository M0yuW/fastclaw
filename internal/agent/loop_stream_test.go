package agent

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
	"github.com/fastclaw-ai/fastclaw/internal/config"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

type fakeStreamingProvider struct {
	mu          sync.Mutex
	responses   []string
	delegate    provider.Provider
	server      *httptest.Server
	chatCalls   int
	streamCalls int
}

func newFakeStreamingProvider(responses ...string) *fakeStreamingProvider {
	p := &fakeStreamingProvider{responses: responses}
	p.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		p.mu.Lock()
		if len(p.responses) == 0 {
			p.mu.Unlock()
			http.Error(w, "unexpected ChatStream call", http.StatusInternalServerError)
			return
		}
		response := p.responses[0]
		p.responses = p.responses[1:]
		p.mu.Unlock()
		w.Header().Set("Content-Type", "text/event-stream")
		_, _ = w.Write([]byte(response))
	}))
	p.delegate = provider.NewOpenAI("test", p.server.URL)
	return p
}

func (p *fakeStreamingProvider) Chat(context.Context, []provider.Message, []provider.Tool, string, int, float64) (*provider.Response, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.chatCalls++
	return nil, errors.New("Chat must not be called")
}

func (p *fakeStreamingProvider) ChatStream(ctx context.Context, messages []provider.Message, tools []provider.Tool, model string, maxTokens int, temperature float64) (*provider.StreamReader, error) {
	p.mu.Lock()
	p.streamCalls++
	p.mu.Unlock()
	return p.delegate.ChatStream(ctx, messages, tools, model, maxTokens, temperature)
}

func openAITextStream(chunks ...string) string {
	var lines []string
	for _, content := range chunks {
		payload, _ := json.Marshal(map[string]any{
			"choices": []any{map[string]any{"delta": map[string]any{"content": content}}},
		})
		lines = append(lines, "data: "+string(payload))
	}
	return strings.Join(append(lines, "data: [DONE]", ""), "\n")
}

func openAIToolStream(id, name, arguments, content string) string {
	payload, _ := json.Marshal(map[string]any{
		"choices": []any{map[string]any{"delta": map[string]any{
			"content": content,
			"tool_calls": []any{map[string]any{
				"index": 0, "id": id, "type": "function",
				"function": map[string]any{"name": name, "arguments": arguments},
			}},
		}}},
	})
	return "data: " + string(payload) + "\ndata: [DONE]\n"
}

func newStreamingTestAgent(t *testing.T, p provider.Provider, maxIterations int) *Agent {
	t.Helper()
	home := t.TempDir()
	return NewAgent(config.ResolvedAgent{
		ID:                "test-agent",
		Home:              home,
		Workspace:         home,
		Model:             "fake/model",
		MaxTokens:         128,
		MaxToolIterations: maxIterations,
	}, p, nil, home)
}

func collectChatEvents(ch <-chan ChatEvent) []ChatEvent {
	var events []ChatEvent
	for {
		select {
		case event, ok := <-ch:
			if !ok {
				return events
			}
			events = append(events, event)
		default:
			return events
		}
	}
}

func TestRunTurnStreamsOnceAndPersistsCompleteAssistant(t *testing.T) {
	fake := newFakeStreamingProvider(openAITextStream("hel", "lo"))
	defer fake.server.Close()
	agent := newStreamingTestAgent(t, fake, 4)
	eventCh := make(chan ChatEvent, 16)
	ctx := ContextWithChatEvents(context.Background(), eventCh)
	msg := bus.InboundMessage{Channel: "test", ChatID: "plain", Text: "hi"}

	if got := agent.HandleMessage(ctx, msg); got != "hello" {
		t.Fatalf("HandleMessage() = %q, want hello", got)
	}
	if fake.streamCalls != 1 || fake.chatCalls != 0 {
		t.Fatalf("ChatStream calls=%d Chat calls=%d", fake.streamCalls, fake.chatCalls)
	}

	events := collectChatEvents(eventCh)
	var types []string
	var deltas strings.Builder
	var done int
	for _, event := range events {
		types = append(types, event.Type)
		if event.Version != 2 || event.Data["turnId"] == "" || event.Data["messageId"] == "" || event.Data["round"] != 1 {
			t.Fatalf("missing v2 correlation: %+v", event)
		}
		if event.Type == "content_delta" {
			deltas.WriteString(event.Data["content"].(string))
		}
		if event.Type == "done" {
			done++
		}
	}
	for i := 1; i < len(events); i++ {
		if events[i].Data["seq"].(int) != events[i-1].Data["seq"].(int)+1 {
			t.Fatalf("non-contiguous seq: %+v", events)
		}
		if events[i].Data["turnId"] != events[0].Data["turnId"] {
			t.Fatalf("turnId changed: %+v", events)
		}
	}
	if got := strings.Join(types, ","); got != "content_delta,content_delta,content,done" {
		t.Fatalf("event order = %s", got)
	}
	if deltas.String() != "hello" || events[2].Data["content"] != "hello" || done != 1 {
		t.Fatalf("unexpected deltas/snapshot/done: %+v", events)
	}
	messages := agent.Sessions().Get("test", "plain").GetMessages()
	if len(messages) != 2 || messages[1].Role != "assistant" || messages[1].Content != "hello" {
		t.Fatalf("unexpected session: %+v", messages)
	}
}

func TestRunTurnToolRoundsStreamOnceAndPairEvents(t *testing.T) {
	fake := newFakeStreamingProvider(
		openAIToolStream("call-1", "test_tool", `{}`, "checking"),
		openAITextStream("final ", "answer"),
	)
	defer fake.server.Close()
	agent := newStreamingTestAgent(t, fake, 4)
	agent.ToolRegistry().Register("test_tool", "test", map[string]any{"type": "object"}, func(context.Context, json.RawMessage) (string, error) {
		return "tool output", nil
	})
	eventCh := make(chan ChatEvent, 32)
	ctx := ContextWithChatEvents(context.Background(), eventCh)
	msg := bus.InboundMessage{Channel: "test", ChatID: "tool", Text: "use a tool"}

	if got := agent.HandleMessage(ctx, msg); got != "final answer" {
		t.Fatalf("HandleMessage() = %q", got)
	}
	if fake.streamCalls != 2 || fake.chatCalls != 0 {
		t.Fatalf("ChatStream calls=%d Chat calls=%d", fake.streamCalls, fake.chatCalls)
	}

	events := collectChatEvents(eventCh)
	var types []string
	var callEvent, resultEvent *ChatEvent
	var done int
	for i := range events {
		event := &events[i]
		types = append(types, event.Type)
		switch event.Type {
		case "tool_call":
			callEvent = event
		case "tool_result":
			resultEvent = event
		case "done":
			done++
		}
	}
	wantOrder := "content_delta,content,tool_call,tool_result,content_delta,content_delta,content,done"
	if got := strings.Join(types, ","); got != wantOrder {
		t.Fatalf("event order = %s, want %s", got, wantOrder)
	}
	if callEvent == nil || resultEvent == nil || callEvent.Data["id"] != resultEvent.Data["id"] || callEvent.Data["messageId"] != resultEvent.Data["messageId"] || callEvent.Data["round"] != 1 || resultEvent.Data["round"] != 1 {
		t.Fatalf("unpaired tool events: call=%+v result=%+v", callEvent, resultEvent)
	}
	if done != 1 {
		t.Fatalf("done count = %d", done)
	}
	messages := agent.Sessions().Get("test", "tool").GetMessages()
	if len(messages) != 4 || messages[1].Role != "assistant" || len(messages[1].ToolCalls) != 1 || messages[2].Role != "tool" || messages[2].ToolCallID != "call-1" || messages[3].Role != "assistant" || messages[3].Content != "final answer" {
		t.Fatalf("unexpected session: %+v", messages)
	}
}

func TestHandleMessageStreamForwardsOnlyFinalAnswerRound(t *testing.T) {
	fake := newFakeStreamingProvider(
		openAIToolStream("call-1", "test_tool", `{}`, "discard me"),
		openAITextStream("keep ", "me"),
	)
	defer fake.server.Close()
	agent := newStreamingTestAgent(t, fake, 4)
	agent.ToolRegistry().Register("test_tool", "test", map[string]any{"type": "object"}, func(context.Context, json.RawMessage) (string, error) {
		return "tool output", nil
	})

	reader := agent.HandleMessageStream(context.Background(), bus.InboundMessage{Channel: "test", ChatID: "adapter", Text: "use a tool"})
	var content strings.Builder
	var done int
	for {
		chunk, ok := reader.Next()
		if !ok {
			break
		}
		content.WriteString(chunk.Content)
		if chunk.Done {
			done++
		}
	}
	if err := reader.Err(); err != nil {
		t.Fatal(err)
	}
	if content.String() != "keep me" || done != 1 {
		t.Fatalf("stream content=%q done=%d", content.String(), done)
	}
	if fake.streamCalls != 2 || fake.chatCalls != 0 {
		t.Fatalf("ChatStream calls=%d Chat calls=%d", fake.streamCalls, fake.chatCalls)
	}
}
