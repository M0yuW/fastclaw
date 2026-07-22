package bus

import (
	"context"
	"errors"
	"testing"
	"time"
)

func TestCallInternalRoundTrip(t *testing.T) {
	b := New()
	done := make(chan struct{})
	go func() {
		delivery := <-b.Internal
		b.ResolveInternal(InternalReply{
			CorrelationID: delivery.CorrelationID,
			TaskID:        "task-1",
			Result:        "ok",
		})
		close(done)
	}()

	reply, err := b.CallInternal(context.Background(), InternalRequest{
		OwnerUserID:   "u1",
		SourceAgentID: "a",
		TargetAgentID: "b",
		CallPath:      []string{"a"},
	})
	if err != nil {
		t.Fatalf("CallInternal: %v", err)
	}
	if reply.Result != "ok" || reply.TaskID != "task-1" {
		t.Fatalf("unexpected reply: %#v", reply)
	}
	<-done
}

func TestCallInternalRejectsPathCycle(t *testing.T) {
	b := New()
	_, err := b.CallInternal(context.Background(), InternalRequest{
		OwnerUserID:   "u1",
		SourceAgentID: "b",
		TargetAgentID: "a",
		CallPath:      []string{"a", "b"},
	})
	if !errors.Is(err, ErrInternalCycle) {
		t.Fatalf("expected cycle error, got %v", err)
	}
}

func TestCallInternalDetectsCrossRootWaitCycle(t *testing.T) {
	b := New()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	firstDone := make(chan error, 1)
	go func() {
		_, err := b.CallInternal(ctx, InternalRequest{
			OwnerUserID:   "u1",
			SourceAgentID: "a",
			TargetAgentID: "b",
			CallPath:      []string{"a"},
		})
		firstDone <- err
	}()

	select {
	case <-b.Internal:
	case <-time.After(time.Second):
		t.Fatal("first internal request was not published")
	}
	_, err := b.CallInternal(context.Background(), InternalRequest{
		OwnerUserID:   "u1",
		SourceAgentID: "b",
		TargetAgentID: "a",
		CallPath:      []string{"b"},
	})
	if !errors.Is(err, ErrInternalCycle) {
		t.Fatalf("expected cross-root cycle error, got %v", err)
	}
	cancel()
	<-firstDone
}

func TestStopInternalReleasesWaiter(t *testing.T) {
	b := New()
	result := make(chan error, 1)
	go func() {
		_, err := b.CallInternal(context.Background(), InternalRequest{
			OwnerUserID:   "u1",
			SourceAgentID: "a",
			TargetAgentID: "b",
			CallPath:      []string{"a"},
		})
		result <- err
	}()
	select {
	case <-b.Internal:
	case <-time.After(time.Second):
		t.Fatal("internal request was not published")
	}
	b.StopInternal(nil)
	select {
	case err := <-result:
		if !errors.Is(err, ErrInternalStopped) {
			t.Fatalf("expected stopped error, got %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("waiter was not released")
	}
}
