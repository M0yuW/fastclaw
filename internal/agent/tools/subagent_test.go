package tools

import (
	"context"
	"encoding/json"
	"errors"
	"strconv"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
)

type fakeSubAgentSpawner struct {
	messages []bus.InboundMessage
	result   string
	err      error
}

type concurrentSubAgentSpawner struct {
	active  int32
	maximum int32
}

func (s *concurrentSubAgentSpawner) SpawnSubAgent(_ context.Context, agentID string, msg bus.InboundMessage) (string, error) {
	active := atomic.AddInt32(&s.active, 1)
	for {
		maximum := atomic.LoadInt32(&s.maximum)
		if active <= maximum || atomic.CompareAndSwapInt32(&s.maximum, maximum, active) {
			break
		}
	}
	time.Sleep(20 * time.Millisecond)
	atomic.AddInt32(&s.active, -1)
	if !strings.Contains(msg.Text, "Shared context:\nlocked evidence") {
		return "", errors.New("shared context missing")
	}
	return agentID + " result", nil
}

func (f *fakeSubAgentSpawner) SpawnSubAgent(_ context.Context, _ string, msg bus.InboundMessage) (string, error) {
	f.messages = append(f.messages, msg)
	return f.result, f.err
}

func TestMakeSubAgentToolCreatesUniqueInternalMessages(t *testing.T) {
	spawner := &fakeSubAgentSpawner{result: "ok"}
	tool := makeSubAgentTool(spawner, "parent")
	args := json.RawMessage(`{"agentId":"child","task":"analyze"}`)
	for i := 0; i < 2; i++ {
		result, err := tool(context.Background(), args)
		if err != nil || result != "ok" {
			t.Fatalf("call %d: result=%q err=%v", i, result, err)
		}
	}
	if len(spawner.messages) != 2 {
		t.Fatalf("got %d messages", len(spawner.messages))
	}
	if spawner.messages[0].ChatID == spawner.messages[1].ChatID || spawner.messages[0].MessageID == spawner.messages[1].MessageID {
		t.Fatal("sub-agent calls reused an identifier")
	}
	for _, msg := range spawner.messages {
		if msg.Source != bus.SourceSubAgent || msg.Channel != "subagent" {
			t.Fatalf("unexpected source message: %#v", msg)
		}
	}
}

func TestMakeSubAgentToolDeduplicatesIdenticalDelegationWithinTurn(t *testing.T) {
	spawner := &fakeSubAgentSpawner{result: "fixed evidence"}
	tool := makeSubAgentTool(spawner, "parent")
	ctx := ContextWithSubAgentDedup(context.Background())

	for _, task := range []string{"same request", "same request"} {
		args := json.RawMessage(`{"agentId":"child","task":` + strconv.Quote(task) + `}`)
		result, err := tool(ctx, args)
		if err != nil || result != "fixed evidence" {
			t.Fatalf("task %q: result=%q err=%v", task, result, err)
		}
	}
	if len(spawner.messages) != 1 {
		t.Fatalf("spawner received %d messages, want 1", len(spawner.messages))
	}
}

func TestMakeSubAgentToolPreservesDifferentTasksWithinTurn(t *testing.T) {
	spawner := &fakeSubAgentSpawner{result: "fixed evidence"}
	tool := makeSubAgentTool(spawner, "parent")
	ctx := ContextWithSubAgentDedup(context.Background())

	for _, task := range []string{"first request", "second request"} {
		args := json.RawMessage(`{"agentId":"child","task":` + strconv.Quote(task) + `}`)
		if _, err := tool(ctx, args); err != nil {
			t.Fatalf("task %q: %v", task, err)
		}
	}
	if len(spawner.messages) != 2 {
		t.Fatalf("spawner received %d messages, want 2", len(spawner.messages))
	}
}

func TestMakeSubAgentToolEvalDeduplicatesTargetWithinTurn(t *testing.T) {
	spawner := &fakeSubAgentSpawner{result: "fixed evidence"}
	tool := makeSubAgentTool(spawner, "parent")
	ctx := ContextWithSubAgentTargetDedup(context.Background())

	for _, task := range []string{"first request", "retry request"} {
		args := json.RawMessage(`{"agentId":"child","task":` + strconv.Quote(task) + `}`)
		if _, err := tool(ctx, args); err != nil {
			t.Fatalf("task %q: %v", task, err)
		}
	}
	if len(spawner.messages) != 1 {
		t.Fatalf("spawner received %d messages, want 1", len(spawner.messages))
	}
}

func TestMakeSubAgentToolReturnsSpawnerError(t *testing.T) {
	spawner := &fakeSubAgentSpawner{err: errors.New("queue stopped")}
	tool := makeSubAgentTool(spawner, "parent")
	_, err := tool(context.Background(), json.RawMessage(`{"agentId":"child","task":"analyze"}`))
	if err == nil || !strings.Contains(err.Error(), "queue stopped") {
		t.Fatalf("expected propagated error, got %v", err)
	}
}

func TestMakeSubAgentToolRejectsSelfSpawn(t *testing.T) {
	tool := makeSubAgentTool(&fakeSubAgentSpawner{}, "parent")
	_, err := tool(context.Background(), json.RawMessage(`{"agentId":"parent","task":"loop"}`))
	if err == nil {
		t.Fatal("expected self-spawn error")
	}
}

func TestMakeSubAgentToolRunsBatchWithSharedContextConcurrently(t *testing.T) {
	spawner := &concurrentSubAgentSpawner{}
	tool := makeSubAgentTool(spawner, "parent")
	result, err := tool(context.Background(), json.RawMessage(`{
		"sharedContext":"locked evidence",
		"delegations":[
			{"agentId":"trend","task":"analyze trend"},
			{"agentId":"risk","task":"analyze risk"}
		]
	}`))
	if err != nil {
		t.Fatal(err)
	}
	if atomic.LoadInt32(&spawner.maximum) != 2 {
		t.Fatalf("maximum concurrency = %d, want 2", spawner.maximum)
	}
	var batch spawnSubagentBatchResult
	if err := json.Unmarshal([]byte(result), &batch); err != nil {
		t.Fatal(err)
	}
	if len(batch.Results) != 2 || batch.Results[0].AgentID != "trend" || batch.Results[1].AgentID != "risk" {
		t.Fatalf("batch result = %+v", batch)
	}
}
