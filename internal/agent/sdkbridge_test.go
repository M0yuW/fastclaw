package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	agenttools "github.com/fastclaw-ai/fastclaw/internal/agent/tools"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

func TestSDKEngineRunsDistinctSubAgentsConcurrently(t *testing.T) {
	if maximum := runSubAgentConcurrencyProbe(t, []string{"first", "second"}); maximum != 2 {
		t.Fatalf("maximum concurrent distinct sub-agents = %d, want 2", maximum)
	}
}

func TestSDKEngineSerializesDuplicateSubAgentTargets(t *testing.T) {
	if maximum := runSubAgentConcurrencyProbe(t, []string{"same", "same"}); maximum != 1 {
		t.Fatalf("maximum concurrent duplicate sub-agents = %d, want 1", maximum)
	}
}

func TestSDKEngineContainsToolPanic(t *testing.T) {
	registry := agenttools.NewEmptyRegistry()
	registry.Register(
		"read_file",
		"test",
		map[string]any{"type": "object"},
		func(context.Context, json.RawMessage) (string, error) {
			panic("probe panic")
		},
	)
	results := newSDKEngine(t.Name()).executeToolsConcurrently(
		t.Context(),
		registry,
		[]provider.ToolCall{{
			ID: "panic-call",
			Function: provider.FunctionCall{
				Name:      "read_file",
				Arguments: `{}`,
			},
		}},
		t.TempDir(),
	)
	if len(results) != 1 || results[0].err == nil ||
		!strings.Contains(results[0].err.Error(), "probe panic") {
		t.Fatalf("panic result = %+v", results)
	}
}

func TestSDKEngineDoesNotReuseDuplicateOrEmptyToolCallIDs(t *testing.T) {
	registry := agenttools.NewEmptyRegistry()
	registry.Register(
		"read_file",
		"test",
		map[string]any{"type": "object"},
		func(_ context.Context, raw json.RawMessage) (string, error) {
			var arguments struct {
				Path string `json:"path"`
			}
			if err := json.Unmarshal(raw, &arguments); err != nil {
				return "", err
			}
			return "content-" + arguments.Path, nil
		},
	)
	results := newSDKEngine(t.Name()).executeToolsConcurrently(
		t.Context(),
		registry,
		[]provider.ToolCall{
			{ID: "duplicate", Function: provider.FunctionCall{Name: "read_file", Arguments: `{"path":"first"}`}},
			{ID: "duplicate", Function: provider.FunctionCall{Name: "read_file", Arguments: `{"path":"second"}`}},
			{ID: "", Function: provider.FunctionCall{Name: "read_file", Arguments: `{"path":"empty"}`}},
		},
		t.TempDir(),
	)
	if len(results) != 3 {
		t.Fatalf("results = %d", len(results))
	}
	if results[0].result != "content-first" || results[0].err != nil {
		t.Fatalf("first duplicate result = %+v", results[0])
	}
	if results[1].err == nil || strings.Contains(results[1].result, "content-first") {
		t.Fatalf("second duplicate reused a result: %+v", results[1])
	}
	if results[2].err == nil || !strings.Contains(results[2].err.Error(), "empty") {
		t.Fatalf("empty ID result = %+v", results[2])
	}
}

func TestSDKEngineRecordsPerToolDuration(t *testing.T) {
	registry := agenttools.NewEmptyRegistry()
	registry.Register(
		"read_file",
		"test",
		map[string]any{"type": "object"},
		func(_ context.Context, raw json.RawMessage) (string, error) {
			var arguments struct {
				DelayMS int `json:"delayMs"`
			}
			if err := json.Unmarshal(raw, &arguments); err != nil {
				return "", err
			}
			time.Sleep(time.Duration(arguments.DelayMS) * time.Millisecond)
			return "ok", nil
		},
	)
	results := newSDKEngine(t.Name()).executeToolsConcurrently(
		t.Context(),
		registry,
		[]provider.ToolCall{
			{ID: "short", Function: provider.FunctionCall{Name: "read_file", Arguments: `{"delayMs":10}`}},
			{ID: "long", Function: provider.FunctionCall{Name: "read_file", Arguments: `{"delayMs":60}`}},
		},
		t.TempDir(),
	)
	if len(results) != 2 || results[0].duration <= 0 || results[1].duration <= 0 {
		t.Fatalf("durations missing: %+v", results)
	}
	if results[1].duration-results[0].duration < 30*time.Millisecond {
		t.Fatalf("durations are batch-level rather than per-tool: %+v", results)
	}
}

func runSubAgentConcurrencyProbe(t *testing.T, agentIDs []string) int32 {
	t.Helper()
	registry := agenttools.NewEmptyRegistry()
	var active atomic.Int32
	var maximum atomic.Int32
	registry.Register(
		"spawn_subagent",
		"test",
		map[string]any{"type": "object"},
		func(context.Context, json.RawMessage) (string, error) {
			current := active.Add(1)
			for {
				observed := maximum.Load()
				if current <= observed || maximum.CompareAndSwap(observed, current) {
					break
				}
			}
			time.Sleep(25 * time.Millisecond)
			active.Add(-1)
			return "ok", nil
		},
	)
	calls := make([]provider.ToolCall, 0, len(agentIDs))
	for index, agentID := range agentIDs {
		arguments, err := json.Marshal(map[string]string{"agentId": agentID, "task": "test"})
		if err != nil {
			t.Fatal(err)
		}
		calls = append(calls, provider.ToolCall{
			ID: fmt.Sprintf("call-%d", index+1),
			Function: provider.FunctionCall{
				Name:      "spawn_subagent",
				Arguments: string(arguments),
			},
		})
	}
	results := newSDKEngine(t.Name()).executeToolsConcurrently(
		t.Context(),
		registry,
		calls,
		t.TempDir(),
	)
	if len(results) != len(calls) {
		t.Fatalf("results = %d, want %d", len(results), len(calls))
	}
	for _, result := range results {
		if result.err != nil {
			t.Fatalf("tool result error: %v", result.err)
		}
	}
	return maximum.Load()
}
