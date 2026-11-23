package agent

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
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
	models      []string
}

type recordingSubAgentSpawner struct {
	mu       sync.Mutex
	messages []bus.InboundMessage
}

func (spawner *recordingSubAgentSpawner) SpawnSubAgent(
	_ context.Context,
	_ string,
	message bus.InboundMessage,
) (string, error) {
	spawner.mu.Lock()
	defer spawner.mu.Unlock()
	spawner.messages = append(spawner.messages, message)
	return "specialist result", nil
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
	p.models = append(p.models, model)
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

func TestRunTurnStopsAfterTruncatedToolArguments(t *testing.T) {
	fake := newFakeStreamingProvider(openAIToolStream("call-1", "spawn_subagent", `{"sharedContext":"unfinished`, ""))
	defer fake.server.Close()
	agent := newStreamingTestAgent(t, fake, 8)
	message := bus.InboundMessage{Channel: "test", ChatID: "truncated-arguments", Text: "delegate"}
	_ = agent.HandleMessage(context.Background(), message)
	if fake.streamCalls != 1 {
		t.Fatalf("stream calls = %d, want one failed call without retries", fake.streamCalls)
	}
}

func TestRunTurnUsesContextModelOverride(t *testing.T) {
	fake := newFakeStreamingProvider(openAITextStream("overridden"))
	defer fake.server.Close()
	agent := newStreamingTestAgent(t, fake, 4)
	ctx := ContextWithModelOverride(context.Background(), "provider/capacity-matched")

	if got := agent.HandleMessage(ctx, bus.InboundMessage{Channel: "test", ChatID: "model-override", Text: "hi"}); got != "overridden" {
		t.Fatalf("HandleMessage() = %q, want overridden", got)
	}
	fake.mu.Lock()
	defer fake.mu.Unlock()
	if len(fake.models) != 1 || fake.models[0] != "provider/capacity-matched" {
		t.Fatalf("provider models = %v, want context override", fake.models)
	}
}

func TestRunTurnEmitsMissingIdentityFailure(t *testing.T) {
	fake := newFakeStreamingProvider()
	defer fake.server.Close()
	agent := newStreamingTestAgent(t, fake, 4)
	agent.ctxBuilder.SetRequiredIdentityFiles([]string{"SOUL.md"})
	eventCh := make(chan ChatEvent, 4)
	ctx := ContextWithChatEvents(context.Background(), eventCh)
	msg := bus.InboundMessage{Channel: "test", ChatID: "missing-identity", Text: "hi"}

	reply := agent.HandleMessage(ctx, msg)
	if !strings.Contains(reply, "required identity file SOUL.md is missing or empty") {
		t.Fatalf("HandleMessage() = %q", reply)
	}

	events := collectChatEvents(eventCh)
	if len(events) != 2 || events[0].Type != "error" || events[1].Type != "done" {
		t.Fatalf("events = %+v, want error then done", events)
	}
	if message, _ := events[0].Data["message"].(string); message != reply {
		t.Fatalf("error message = %q, want %q", message, reply)
	}
	if events[0].Data["messageId"] == "" ||
		events[0].Data["messageId"] != events[1].Data["messageId"] ||
		events[0].Data["round"] != 1 ||
		events[1].Data["round"] != 1 {
		t.Fatalf("missing failure correlation: %+v", events)
	}
	if fake.streamCalls != 0 || fake.chatCalls != 0 {
		t.Fatalf("provider called for invalid identity: stream=%d chat=%d", fake.streamCalls, fake.chatCalls)
	}
}

func TestHandleMessageStreamReportsMissingIdentityFailure(t *testing.T) {
	fake := newFakeStreamingProvider()
	defer fake.server.Close()
	agent := newStreamingTestAgent(t, fake, 4)
	agent.ctxBuilder.SetRequiredIdentityFiles([]string{"SOUL.md"})

	reader := agent.HandleMessageStream(
		context.Background(),
		bus.InboundMessage{Channel: "test", ChatID: "missing-identity-stream", Text: "hi"},
	)
	if chunk, ok := reader.Next(); ok {
		t.Fatalf("unexpected stream chunk: %+v", chunk)
	}
	if err := reader.Err(); err == nil ||
		!strings.Contains(err.Error(), "required identity file SOUL.md is missing or empty") {
		t.Fatalf("stream error = %v", err)
	}
	if fake.streamCalls != 0 || fake.chatCalls != 0 {
		t.Fatalf("provider called for invalid identity: stream=%d chat=%d", fake.streamCalls, fake.chatCalls)
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

func TestDeterministicMalformedFinanceCallReplay(t *testing.T) {
	reviewTool := func(_ context.Context, raw json.RawMessage) (string, error) {
		var arguments map[string]any
		if err := json.Unmarshal(raw, &arguments); err != nil {
			return "", err
		}
		if _, ok := arguments["thesis_id"]; !ok {
			return "", errors.New("missing required field: thesis_id")
		}
		return "review saved", nil
	}
	parameters := map[string]any{"type": "object", "required": []string{"thesis_id"}}
	t.Run("error then corrected call completes", func(t *testing.T) {
		fake := newFakeStreamingProvider(
			openAIToolStream("bad-call", "finance_review_fixture", `{"alert_id":"fa_fixture"}`, ""),
			openAIToolStream("good-call", "finance_review_fixture", `{"thesis_id":"th_fixture","alert_id":"fa_fixture"}`, ""),
			openAITextStream("review complete"),
		)
		defer fake.server.Close()
		agent := newStreamingTestAgent(t, fake, 3)
		agent.ToolRegistry().Register("finance_review_fixture", "local replay", parameters, reviewTool)
		eventCh := make(chan ChatEvent, 32)
		ctx := ContextWithChatEvents(context.Background(), eventCh)
		if reply := agent.HandleMessage(ctx, bus.InboundMessage{Channel: "test", ChatID: "finance-recovery", Text: "review"}); reply != "review complete" {
			t.Fatalf("reply = %q", reply)
		}
		events := collectChatEvents(eventCh)
		var results []string
		var calls, done int
		for _, event := range events {
			switch event.Type {
			case "tool_call":
				calls++
			case "tool_result":
				results = append(results, event.Data["result"].(string))
			case "done":
				done++
			}
		}
		if calls != 2 || len(results) != 2 || done != 1 ||
			!strings.Contains(results[0], "missing required field: thesis_id") ||
			!strings.Contains(results[1], "review saved") {
			t.Fatalf("calls=%d results=%v done=%d", calls, results, done)
		}
	})
	t.Run("invalid JSON receives one correction opportunity", func(t *testing.T) {
		fake := newFakeStreamingProvider(
			openAIToolStream("malformed-call", "finance_review_fixture", `{"thesis_id":"th_fixture"}}`, ""),
			openAIToolStream("corrected-call", "finance_review_fixture", `{"thesis_id":"th_fixture"}`, ""),
			openAITextStream("review complete"),
		)
		defer fake.server.Close()
		agent := newStreamingTestAgent(t, fake, 4)
		agent.ToolRegistry().Register("finance_review_fixture", "local replay", parameters, reviewTool)
		eventCh := make(chan ChatEvent, 32)
		ctx := ContextWithChatEvents(context.Background(), eventCh)
		if reply := agent.HandleMessage(ctx, bus.InboundMessage{Channel: "test", ChatID: "finance-json-recovery", Text: "review"}); reply != "review complete" {
			t.Fatalf("reply = %q", reply)
		}
		var results []string
		var terminal int
		for _, event := range collectChatEvents(eventCh) {
			switch event.Type {
			case "tool_result":
				results = append(results, event.Data["result"].(string))
			case "terminal":
				terminal++
			}
		}
		if len(results) != 2 || !strings.Contains(results[0], "invalid tool arguments JSON") ||
			!strings.Contains(results[1], "review saved") || terminal != 0 {
			t.Fatalf("results=%v terminal=%d", results, terminal)
		}
	})
	t.Run("repeated invalid JSON has typed terminal", func(t *testing.T) {
		fake := newFakeStreamingProvider(
			openAIToolStream("malformed-call-1", "finance_review_fixture", `{"thesis_id":"th_fixture"}}`, ""),
			openAIToolStream("malformed-call-2", "finance_review_fixture", `{"thesis_id":"th_fixture"}}`, ""),
		)
		defer fake.server.Close()
		agent := newStreamingTestAgent(t, fake, 4)
		agent.ToolRegistry().Register("finance_review_fixture", "local replay", parameters, reviewTool)
		eventCh := make(chan ChatEvent, 32)
		ctx := ContextWithChatEvents(context.Background(), eventCh)
		reply := agent.HandleMessage(ctx, bus.InboundMessage{Channel: "test", ChatID: "finance-json-exhausted", Text: "review"})
		if !strings.Contains(reply, "could not produce valid tool arguments") || fake.streamCalls != 2 {
			t.Fatalf("reply=%q streamCalls=%d", reply, fake.streamCalls)
		}
		var code string
		for _, event := range collectChatEvents(eventCh) {
			if event.Type == "terminal" {
				code, _ = event.Data["code"].(string)
			}
		}
		if code != "malformed_tool_arguments_exhausted" {
			t.Fatalf("terminal code=%q", code)
		}
	})
	t.Run("mixed malformed batch never partially executes", func(t *testing.T) {
		payload, _ := json.Marshal(map[string]any{
			"choices": []any{map[string]any{"delta": map[string]any{
				"tool_calls": []any{
					map[string]any{"index": 0, "id": "bad", "type": "function", "function": map[string]any{
						"name": "finance_review_fixture", "arguments": `{"thesis_id":"th_fixture"}}`,
					}},
					map[string]any{"index": 1, "id": "good", "type": "function", "function": map[string]any{
						"name": "finance_review_fixture", "arguments": `{"thesis_id":"th_fixture"}`,
					}},
				},
			}}},
		})
		fake := newFakeStreamingProvider("data: "+string(payload)+"\ndata: [DONE]\n", openAITextStream("no write"))
		defer fake.server.Close()
		agent := newStreamingTestAgent(t, fake, 3)
		var executions atomic.Int32
		agent.ToolRegistry().Register("finance_review_fixture", "local replay", parameters,
			func(ctx context.Context, raw json.RawMessage) (string, error) {
				executions.Add(1)
				return reviewTool(ctx, raw)
			})
		eventCh := make(chan ChatEvent, 32)
		ctx := ContextWithChatEvents(context.Background(), eventCh)
		if reply := agent.HandleMessage(ctx, bus.InboundMessage{Channel: "test", ChatID: "mixed-json-batch", Text: "review"}); reply != "no write" {
			t.Fatalf("reply=%q", reply)
		}
		if executions.Load() != 0 {
			t.Fatalf("valid peer executed in malformed batch: %d", executions.Load())
		}
		var results int
		for _, event := range collectChatEvents(eventCh) {
			if event.Type == "tool_result" {
				results++
			}
		}
		if results != 2 {
			t.Fatalf("paired results=%d, want 2", results)
		}
	})
	t.Run("budget exhausted is detectable", func(t *testing.T) {
		fake := newFakeStreamingProvider(
			openAIToolStream("bad-call-1", "finance_review_fixture", `{"alert_id":"fa_fixture"}`, ""),
			openAIToolStream("bad-call-2", "finance_review_fixture", `{"alert_id":"fa_fixture","attempt":2}`, ""),
		)
		defer fake.server.Close()
		agent := newStreamingTestAgent(t, fake, 2)
		agent.ToolRegistry().Register("finance_review_fixture", "local replay", parameters, reviewTool)
		eventCh := make(chan ChatEvent, 32)
		ctx := ContextWithChatEvents(context.Background(), eventCh)
		reply := agent.HandleMessage(ctx, bus.InboundMessage{Channel: "test", ChatID: "finance-budget", Text: "review"})
		if !strings.Contains(reply, "maximum number of tool iterations") {
			t.Fatalf("budget terminal not identifiable: %q", reply)
		}
		events := collectChatEvents(eventCh)
		var calls, results, done, errorsSeen int
		var terminalCode string
		for _, event := range events {
			switch event.Type {
			case "tool_call":
				calls++
			case "tool_result":
				results++
			case "done":
				done++
			case "error":
				errorsSeen++
			case "terminal":
				terminalCode, _ = event.Data["code"].(string)
			}
		}
		if calls != 2 || results != 2 || done != 1 || errorsSeen != 0 || terminalCode != "tool_iteration_budget_exhausted" {
			t.Fatalf("calls=%d results=%d done=%d error_events=%d terminal=%q", calls, results, done, errorsSeen, terminalCode)
		}
	})
}

func TestPseudoToolCallTextGetsBoundedNativeCorrection(t *testing.T) {
	pseudo := `<｜｜DSML｜｜ calls><｜｜DSML｜｜ invoke name="test_tool"></｜｜DSML｜｜ invoke></｜｜DSML｜｜ calls>`
	t.Run("corrected native call executes once", func(t *testing.T) {
		fake := newFakeStreamingProvider(
			openAITextStream(pseudo),
			openAIToolStream("call-1", "test_tool", `{}`, ""),
			openAITextStream("completed"),
		)
		defer fake.server.Close()
		agent := newStreamingTestAgent(t, fake, 4)
		var executions atomic.Int32
		agent.ToolRegistry().Register("test_tool", "local replay", map[string]any{"type": "object"},
			func(context.Context, json.RawMessage) (string, error) {
				executions.Add(1)
				return "tool output", nil
			})
		eventCh := make(chan ChatEvent, 32)
		ctx := ContextWithChatEvents(context.Background(), eventCh)
		if reply := agent.HandleMessage(ctx, bus.InboundMessage{Channel: "test", ChatID: "pseudo-corrected", Text: "use tool"}); reply != "completed" {
			t.Fatalf("reply = %q", reply)
		}
		if fake.streamCalls != 3 || executions.Load() != 1 {
			t.Fatalf("stream calls=%d tool executions=%d", fake.streamCalls, executions.Load())
		}
		var toolCalls, terminal int
		for _, event := range collectChatEvents(eventCh) {
			switch event.Type {
			case "tool_call":
				toolCalls++
			case "terminal":
				terminal++
			}
		}
		if toolCalls != 1 || terminal != 0 {
			t.Fatalf("native tool calls=%d terminal events=%d", toolCalls, terminal)
		}
	})
	t.Run("repeated markup fails closed", func(t *testing.T) {
		fake := newFakeStreamingProvider(openAITextStream(pseudo), openAITextStream(pseudo))
		defer fake.server.Close()
		agent := newStreamingTestAgent(t, fake, 4)
		var executions atomic.Int32
		agent.ToolRegistry().Register("test_tool", "local replay", map[string]any{"type": "object"},
			func(context.Context, json.RawMessage) (string, error) {
				executions.Add(1)
				return "tool output", nil
			})
		eventCh := make(chan ChatEvent, 32)
		ctx := ContextWithChatEvents(context.Background(), eventCh)
		reply := agent.HandleMessage(ctx, bus.InboundMessage{Channel: "test", ChatID: "pseudo-exhausted", Text: "use tool"})
		if !strings.Contains(reply, "workflow is incomplete") || fake.streamCalls != 2 || executions.Load() != 0 {
			t.Fatalf("reply=%q streamCalls=%d executions=%d", reply, fake.streamCalls, executions.Load())
		}
		var terminalCode string
		for _, event := range collectChatEvents(eventCh) {
			if event.Type == "terminal" {
				terminalCode, _ = event.Data["code"].(string)
			}
		}
		if terminalCode != "pseudo_tool_calls_exhausted" {
			t.Fatalf("terminal code=%q", terminalCode)
		}
	})
	t.Run("ordinary final answer remains valid", func(t *testing.T) {
		fake := newFakeStreamingProvider(openAITextStream("The documentation mentions DSML, but no tool is needed."))
		defer fake.server.Close()
		agent := newStreamingTestAgent(t, fake, 3)
		agent.ToolRegistry().Register("test_tool", "local replay", map[string]any{"type": "object"},
			func(context.Context, json.RawMessage) (string, error) { return "unused", nil })
		reply := agent.HandleMessage(context.Background(), bus.InboundMessage{Channel: "test", ChatID: "no-pseudo", Text: "answer"})
		if !strings.Contains(reply, "no tool is needed") || fake.streamCalls != 1 {
			t.Fatalf("reply=%q streamCalls=%d", reply, fake.streamCalls)
		}
	})
}

func TestRunTurnDoesNotDeduplicateProductionSubAgentCalls(t *testing.T) {
	fake := newFakeStreamingProvider(
		openAIToolStream("call-1", "spawn_subagent", `{"agentId":"child","task":"first task"}`, ""),
		openAIToolStream("call-2", "spawn_subagent", `{"agentId":"child","task":"second task"}`, ""),
		openAITextStream("final answer"),
	)
	defer fake.server.Close()
	agent := newStreamingTestAgent(t, fake, 4)
	spawner := &recordingSubAgentSpawner{}
	agent.SetSubAgentSpawner(spawner)

	reply := agent.HandleMessage(
		context.Background(),
		bus.InboundMessage{Channel: "test", ChatID: "production-subagents", Text: "delegate twice"},
	)
	if reply != "final answer" {
		t.Fatalf("HandleMessage() = %q", reply)
	}
	spawner.mu.Lock()
	defer spawner.mu.Unlock()
	if len(spawner.messages) != 2 {
		t.Fatalf("sub-agent calls = %d, want 2", len(spawner.messages))
	}
	if spawner.messages[0].Text != "first task" || spawner.messages[1].Text != "second task" {
		t.Fatalf("sub-agent tasks = %+v", spawner.messages)
	}
}

func TestRunTurnDeduplicatesIdenticalProductionSubAgentCalls(t *testing.T) {
	fake := newFakeStreamingProvider(
		openAIToolStream("call-1", "spawn_subagent", `{"agentId":"child","task":"same task"}`, ""),
		openAIToolStream("call-2", "spawn_subagent", `{"agentId":"child","task":"same task"}`, ""),
		openAITextStream("final answer"),
	)
	defer fake.server.Close()
	agent := newStreamingTestAgent(t, fake, 4)
	spawner := &recordingSubAgentSpawner{}
	agent.SetSubAgentSpawner(spawner)

	reply := agent.HandleMessage(
		context.Background(),
		bus.InboundMessage{Channel: "test", ChatID: "production-identical-subagents", Text: "delegate twice"},
	)
	if reply != "final answer" {
		t.Fatalf("HandleMessage() = %q", reply)
	}
	spawner.mu.Lock()
	defer spawner.mu.Unlock()
	if len(spawner.messages) != 1 {
		t.Fatalf("sub-agent calls = %d, want 1", len(spawner.messages))
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
