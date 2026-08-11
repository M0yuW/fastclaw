package agent

import (
	"context"
	"encoding/json"
	"strings"
	"testing"
	"time"
)

// A zero StartTime used to render as 2562047h47m16.854775807s (time.Since of
// the zero Time) in the "after tool call" log line. The hook must fall back
// only when it actually has a baseline.
func TestLoggingHookIgnoresZeroStartTime(t *testing.T) {
	hook := LoggingHook()
	hc := &HookContext{AgentName: "a", Point: AfterToolCall, ToolName: "exec"}

	hook(context.Background(), hc)

	if !hc.StartTime.IsZero() {
		t.Fatal("AfterToolCall must not stamp StartTime")
	}
	// The elapsed value the hook would log; recompute the same way to assert
	// it is not the absurd zero-Time delta.
	elapsed := hc.Duration
	if elapsed <= 0 && !hc.StartTime.IsZero() {
		elapsed = time.Since(hc.StartTime)
	}
	if elapsed > time.Hour {
		t.Fatalf("elapsed = %v; zero StartTime leaked into the duration", elapsed)
	}
}

func TestLoggingHookPrefersMeasuredDuration(t *testing.T) {
	hook := LoggingHook()
	before := &HookContext{AgentName: "a", Point: BeforeToolCall, ToolName: "exec"}
	hook(context.Background(), before)
	if before.StartTime.IsZero() {
		t.Fatal("BeforeToolCall must stamp StartTime")
	}

	// A measured duration from the bridge wins over wall-clock since Before,
	// so a tool that waited behind a concurrency gate isn't over-reported.
	after := &HookContext{
		AgentName: "a",
		Point:     AfterToolCall,
		ToolName:  "exec",
		StartTime: before.StartTime,
		Duration:  1500 * time.Millisecond,
	}
	hook(context.Background(), after)
	if after.Duration != 1500*time.Millisecond {
		t.Fatalf("hook mutated Duration to %v", after.Duration)
	}
}

func TestToolTimingRecorderKeysByToolCallID(t *testing.T) {
	rec := newToolTimingRecorder()
	rec.record("call-a", 2*time.Second)
	rec.record("call-b", 50*time.Millisecond)

	if got := rec.duration("call-a"); got != 2*time.Second {
		t.Fatalf("call-a duration = %v", got)
	}
	if got := rec.duration("call-b"); got != 50*time.Millisecond {
		t.Fatalf("call-b duration = %v", got)
	}
	// A call that never reached the adapter must report zero rather than
	// borrowing a sibling's timing.
	if got := rec.duration("call-missing"); got != 0 {
		t.Fatalf("unknown call duration = %v, want 0", got)
	}
	if got := rec.duration(""); got != 0 {
		t.Fatalf("empty ID duration = %v, want 0", got)
	}
}

func TestToolTimingRecorderNilSafe(t *testing.T) {
	var rec *toolTimingRecorder
	rec.record("x", time.Second) // must not panic
	if got := rec.duration("x"); got != 0 {
		t.Fatalf("nil recorder returned %v", got)
	}
}

// The adapter strips the smuggled tool_call ID so it never reaches the tool as
// an argument, while still attributing the measured time to that call.
func TestToolAdapterStripsToolCallIDAndRecordsDuration(t *testing.T) {
	rec := newToolTimingRecorder()
	var seenArgs string
	adapter := &toolAdapter{
		name: "probe",
		fn: func(_ context.Context, args json.RawMessage) (string, error) {
			seenArgs = string(args)
			return "ok", nil
		},
		timings: rec,
	}

	_, err := adapter.Call(context.Background(), map[string]interface{}{
		"command":             "id",
		toolCallIDMetadataKey: "call-1",
	}, nil)
	if err != nil {
		t.Fatalf("adapter call failed: %v", err)
	}
	if strings.Contains(seenArgs, toolCallIDMetadataKey) {
		t.Fatalf("metadata key leaked into tool args: %s", seenArgs)
	}
	if !strings.Contains(seenArgs, "command") {
		t.Fatalf("real args were dropped: %s", seenArgs)
	}
	if _, ok := rec.durations["call-1"]; !ok {
		t.Fatal("adapter did not record a duration for call-1")
	}
}
