package taskqueue

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
)

func TestSubmitInternalRejectsIncompleteSpec(t *testing.T) {
	q := NewQueue(1, time.Second, func(context.Context, *Task) (string, error) {
		return "", nil
	})
	defer q.Stop()

	_, err := q.SubmitInternal(nil, InternalTaskSpec{ChatKey: "subagent:u1:child"}, nil)
	if err == nil {
		t.Fatal("expected incomplete internal task spec to fail")
	}
	if got := len(q.internalSlots); got != 0 {
		t.Fatalf("internal slot leaked after validation failure: %d", got)
	}
}

func TestSubmitInternalCompletionPanicReleasesSlot(t *testing.T) {
	q := NewQueue(1, time.Second, func(context.Context, *Task) (string, error) {
		return "ok", nil
	})
	defer q.Stop()

	_, err := q.SubmitInternal(context.Background(), InternalTaskSpec{
		AgentID:       "child",
		OwnerUserID:   "u1",
		SourceAgentID: "parent",
		CorrelationID: "corr",
		ChatKey:       "subagent:u1:child",
	}, func(TaskResult) { panic("callback failed") })
	if err != nil {
		t.Fatalf("submit: %v", err)
	}

	deadline := time.After(time.Second)
	for len(q.internalSlots) != 0 {
		select {
		case <-deadline:
			t.Fatal("completion panic leaked internal slot")
		default:
			time.Sleep(time.Millisecond)
		}
	}
}

func TestSubmitInternalRejectsParentChatReentry(t *testing.T) {
	q := NewQueue(1, time.Second, func(context.Context, *Task) (string, error) {
		return "", nil
	})
	defer q.Stop()

	_, err := q.SubmitInternal(context.Background(), InternalTaskSpec{
		AgentID:       "child",
		OwnerUserID:   "u1",
		SourceAgentID: "parent",
		CorrelationID: "corr",
		ChatKey:       "task-root",
		ParentChatKey: "task-root",
	}, nil)
	if err == nil {
		t.Fatal("expected parent chat reentry to fail")
	}
}

func TestSubmitInternalCopiesCallPath(t *testing.T) {
	started := make(chan struct{})
	release := make(chan struct{})
	observed := make(chan []string, 1)
	q := NewQueue(1, time.Second, func(_ context.Context, task *Task) (string, error) {
		close(started)
		<-release
		observed <- append([]string(nil), task.CallPath...)
		return "ok", nil
	})
	defer q.Stop()

	path := []string{"parent", "child"}
	_, err := q.SubmitInternal(context.Background(), InternalTaskSpec{
		AgentID:       "child",
		OwnerUserID:   "u1",
		SourceAgentID: "parent",
		CorrelationID: "corr",
		ChatKey:       "subagent:u1:child",
		CallPath:      path,
	}, nil)
	if err != nil {
		t.Fatalf("submit: %v", err)
	}
	<-started
	path[0] = "mutated"
	close(release)
	if got := <-observed; got[0] != "parent" {
		t.Fatalf("call path was not copied: %v", got)
	}
}

func TestInternalTaskInheritsExecutionAtMaxConcurrentOne(t *testing.T) {
	var q *Queue
	childResult := make(chan TaskResult, 1)
	q = NewQueue(1, time.Second, func(ctx context.Context, task *Task) (string, error) {
		if task.AgentID == "parent" {
			_, err := q.SubmitInternal(ctx, InternalTaskSpec{
				AgentID:       "child",
				OwnerUserID:   "u1",
				SourceAgentID: "parent",
				CorrelationID: "corr-1",
				ChatKey:       "subagent:u1:child",
				Message:       bus.InboundMessage{ChatID: "child-chat"},
				CallPath:      []string{"parent", "child"},
			}, func(result TaskResult) { childResult <- result })
			if err != nil {
				return "", err
			}
			select {
			case result := <-childResult:
				return result.Value, result.Err
			case <-ctx.Done():
				return "", ctx.Err()
			}
		}
		return "child-ok", nil
	})
	defer q.Stop()

	parentDone := make(chan TaskResult, 1)
	_, err := q.SubmitInternal(context.Background(), InternalTaskSpec{
		AgentID:       "parent",
		OwnerUserID:   "u1",
		SourceAgentID: "root",
		CorrelationID: "corr-root",
		ChatKey:       "internal:u1:parent",
		Message:       bus.InboundMessage{ChatID: "parent-chat"},
		CallPath:      []string{"root", "parent"},
	}, func(result TaskResult) { parentDone <- result })
	if err != nil {
		t.Fatalf("submit parent: %v", err)
	}
	select {
	case result := <-parentDone:
		if result.Err != nil || result.Value != "child-ok" {
			t.Fatalf("unexpected parent result: %#v", result)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("parent-child queue execution deadlocked")
	}
}

func TestSubmitInternalCompletionExactlyOnceOnStop(t *testing.T) {
	started := make(chan struct{})
	q := NewQueue(1, time.Minute, func(ctx context.Context, task *Task) (string, error) {
		close(started)
		<-ctx.Done()
		return "", ctx.Err()
	})
	results := make(chan TaskResult, 2)
	_, err := q.SubmitInternal(context.Background(), InternalTaskSpec{
		AgentID:       "child",
		OwnerUserID:   "u1",
		SourceAgentID: "parent",
		CorrelationID: "corr",
		ChatKey:       "subagent:u1:child",
		CallPath:      []string{"parent", "child"},
	}, func(result TaskResult) { results <- result })
	if err != nil {
		t.Fatalf("submit: %v", err)
	}
	<-started
	q.Stop()
	select {
	case result := <-results:
		if !errors.Is(result.Err, context.Canceled) {
			t.Fatalf("expected cancellation, got %v", result.Err)
		}
	case <-time.After(time.Second):
		t.Fatal("completion did not fire")
	}
	select {
	case extra := <-results:
		t.Fatalf("completion fired twice: %#v", extra)
	case <-time.After(50 * time.Millisecond):
	}
}
