package agent

import (
	"context"
	"fmt"
	"sync/atomic"
	"time"
)

// ChatEvent represents a real-time event emitted during the agent ReAct loop.
type ChatEvent struct {
	Type    string         `json:"type"` // legacy types plus v2 "content_delta"
	Data    map[string]any `json:"data,omitempty"`
	Version int            `json:"version,omitempty"`
}

var chatEventIDCounter atomic.Uint64

func newChatEventID(prefix string) string {
	return fmt.Sprintf("%s-%d-%d", prefix, time.Now().UnixNano(), chatEventIDCounter.Add(1))
}

type turnEventEmitter struct {
	ctx    context.Context
	turnID string
	seq    int
	done   bool
}

func newTurnEventEmitter(ctx context.Context) *turnEventEmitter {
	return &turnEventEmitter{ctx: ctx, turnID: newChatEventID("turn")}
}

func (e *turnEventEmitter) hasSink() bool {
	return e != nil && ChatEventsFromContext(e.ctx) != nil
}

func (e *turnEventEmitter) messageID() string {
	return newChatEventID("message")
}

type chatEventsKey struct{}

type withoutChatEventsContext struct {
	context.Context
}

func (c withoutChatEventsContext) Value(key any) any {
	if _, ok := key.(chatEventsKey); ok {
		return nil
	}
	return c.Context.Value(key)
}

// ChatEventsFromContext retrieves the events channel from context, if present.
func ChatEventsFromContext(ctx context.Context) chan<- ChatEvent {
	if ctx == nil {
		return nil
	}
	ch, _ := ctx.Value(chatEventsKey{}).(chan<- ChatEvent)
	return ch
}

// ContextWithChatEvents returns a new context with the events channel attached.
func ContextWithChatEvents(ctx context.Context, ch chan<- ChatEvent) context.Context {
	if ctx == nil {
		ctx = context.Background()
	}
	return context.WithValue(ctx, chatEventsKey{}, ch)
}

// ContextWithoutChatEvents returns a context that preserves request values but
// prevents nested agents from emitting into the caller's live web stream.
func ContextWithoutChatEvents(ctx context.Context) context.Context {
	if ctx == nil {
		ctx = context.Background()
	}
	return withoutChatEventsContext{Context: ctx}
}

// emit sends a versioned event with stable turn/round/message correlation.
func (e *turnEventEmitter) emit(eventType string, data map[string]any, messageID string, round int) {
	if e == nil || e.done || !e.hasSink() {
		return
	}
	if eventType == "done" {
		e.done = true
	}
	if data == nil {
		data = make(map[string]any)
	}
	e.seq++
	data["turnId"] = e.turnID
	data["seq"] = e.seq
	if messageID != "" {
		data["messageId"] = messageID
	}
	if round > 0 {
		data["round"] = round
	}
	emitEvent(e.ctx, ChatEvent{Type: eventType, Data: data, Version: 2})
}

func (e *turnEventEmitter) contentDelta(content, messageID string, round int) {
	if content != "" {
		e.emit("content_delta", map[string]any{"content": content, "delta": content}, messageID, round)
	}
}

func (e *turnEventEmitter) contentSnapshot(content, messageID string, round int) {
	e.emit("content", map[string]any{"content": content}, messageID, round)
}

func (e *turnEventEmitter) toolCall(id, name, arguments, messageID string, round int) {
	e.emit("tool_call", map[string]any{
		"id": id, "name": name, "arguments": arguments,
	}, messageID, round)
}

func (e *turnEventEmitter) toolResult(id, name, result, messageID string, round int, metadata map[string]any) {
	data := map[string]any{"id": id, "name": name, "result": result}
	if metadata != nil {
		data["metadata"] = metadata
	}
	e.emit("tool_result", data, messageID, round)
}

func (e *turnEventEmitter) fail(err error, messageID string, round int) {
	if err != nil {
		e.emit("error", map[string]any{"message": err.Error()}, messageID, round)
	}
	e.emit("done", nil, messageID, round)
}

func (e *turnEventEmitter) finish(messageID string, round int) {
	e.emit("done", nil, messageID, round)
}

// emitEvent sends an event to the channel in context, if present.
func emitEvent(ctx context.Context, evt ChatEvent) {
	ch := ChatEventsFromContext(ctx)
	if ch == nil {
		return
	}
	select {
	case ch <- evt:
	case <-ctx.Done():
	}
}
