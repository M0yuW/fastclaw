package api

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/agent"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

func TestRequestToolRegistryUsesCannedResultsAndNormalizesSchema(t *testing.T) {
	registry, err := requestToolRegistry([]provider.Tool{
		{
			Type: "function",
			Function: provider.ToolFunction{
				Name:        "math.area",
				Description: "calculate area",
				Parameters: map[string]any{
					"type": "dict",
					"properties": map[string]any{
						"radius": map[string]any{"type": "float"},
					},
				},
			},
		},
	}, map[string]string{"math.area": "12.5"})
	if err != nil {
		t.Fatal(err)
	}
	definitions := registry.Definitions()
	parameters := definitions[0].Function.Parameters.(map[string]any)
	if parameters["type"] != "object" {
		t.Fatalf("schema type = %v", parameters["type"])
	}
	properties := parameters["properties"].(map[string]any)
	if properties["radius"].(map[string]any)["type"] != "number" {
		t.Fatalf("nested schema = %+v", properties)
	}
	result, err := registry.Execute(t.Context(), "math.area", `{"radius":2}`)
	if err != nil || result != "12.5" {
		t.Fatalf("Execute() = %q, %v", result, err)
	}
}

func TestRequestToolEnvironmentMutatesAndSnapshotsState(t *testing.T) {
	registry, snapshot, err := buildRequestToolEnvironment(
		[]provider.Tool{
			{
				Type: "function",
				Function: provider.ToolFunction{
					Name:       "get_order",
					Parameters: map[string]any{"type": "object"},
				},
			},
			{
				Type: "function",
				Function: provider.ToolFunction{
					Name:       "cancel_order",
					Parameters: map[string]any{"type": "object"},
				},
			},
		},
		nil,
		map[string]any{
			"orders": map[string]any{
				"ord-1": map[string]any{"status": "pending"},
			},
		},
		map[string]evalToolBehavior{
			"get_order": {
				ResultPath: "orders.{order_id}",
			},
			"cancel_order": {
				Conditions: []evalStateCondition{
					{
						Path:   "orders.{order_id}.status",
						Equals: "pending",
						Error:  "only pending orders can be cancelled",
					},
				},
				Updates: []evalStateUpdate{
					{Path: "orders.{order_id}.status", Value: "cancelled"},
				},
				ResultPath: "orders.{order_id}",
			},
		},
	)
	if err != nil {
		t.Fatal(err)
	}

	result, err := registry.Execute(t.Context(), "get_order", `{"order_id":"ord-1"}`)
	if err != nil {
		t.Fatal(err)
	}
	var order map[string]any
	if err := json.Unmarshal([]byte(result), &order); err != nil {
		t.Fatal(err)
	}
	if order["status"] != "pending" {
		t.Fatalf("get_order status = %v", order["status"])
	}

	result, err = registry.Execute(t.Context(), "cancel_order", `{"order_id":"ord-1"}`)
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal([]byte(result), &order); err != nil {
		t.Fatal(err)
	}
	if order["status"] != "cancelled" {
		t.Fatalf("cancel_order status = %v", order["status"])
	}
	status, exists := lookupStatePath(snapshot(), "orders.ord-1.status")
	if !exists || status != "cancelled" {
		t.Fatalf("snapshot status = %v, exists = %v", status, exists)
	}

	if _, err := registry.Execute(t.Context(), "cancel_order", `{"order_id":"ord-1"}`); err == nil {
		t.Fatal("second cancellation error = nil")
	}
}

func TestRequestToolEnvironmentSupportsVirtualFileMaps(t *testing.T) {
	definitions := []provider.Tool{
		{
			Type: "function",
			Function: provider.ToolFunction{
				Name:       "list_files",
				Parameters: map[string]any{"type": "object"},
			},
		},
		{
			Type: "function",
			Function: provider.ToolFunction{
				Name:       "read_file",
				Parameters: map[string]any{"type": "object"},
			},
		},
		{
			Type: "function",
			Function: provider.ToolFunction{
				Name:       "write_file",
				Parameters: map[string]any{"type": "object"},
			},
		},
	}
	behaviors := map[string]evalToolBehavior{
		"list_files": {ResultKeysPath: "files"},
		"read_file": {
			ResultMapPath:        "files",
			ResultMapKeyArgument: "path",
		},
		"write_file": {
			Updates: []evalStateUpdate{
				{
					MapPath:           "files",
					KeyFromArgument:   "path",
					ValueFromArgument: "content",
				},
			},
			ResultMapPath:        "files",
			ResultMapKeyArgument: "path",
		},
	}
	registry, snapshot, err := buildRequestToolEnvironment(
		definitions,
		nil,
		map[string]any{"files": map[string]any{"main.go": "package main\n"}},
		behaviors,
	)
	if err != nil {
		t.Fatal(err)
	}

	files, err := registry.Execute(t.Context(), "list_files", `{}`)
	if err != nil || files != `["main.go"]` {
		t.Fatalf("list_files = %q, %v", files, err)
	}
	content, err := registry.Execute(t.Context(), "read_file", `{"path":"main.go"}`)
	if err != nil || content != "package main\n" {
		t.Fatalf("read_file = %q, %v", content, err)
	}
	updated := "package main\n\nfunc main() {}\n"
	arguments, err := json.Marshal(map[string]string{"path": "main.go", "content": updated})
	if err != nil {
		t.Fatal(err)
	}
	content, err = registry.Execute(t.Context(), "write_file", string(arguments))
	if err != nil || content != updated {
		t.Fatalf("write_file = %q, %v", content, err)
	}
	state := snapshot()
	if state["files"].(map[string]any)["main.go"] != updated {
		t.Fatalf("unexpected state: %+v", state)
	}
}

func TestRequestToolEnvironmentInjectsArgumentScopedFaults(t *testing.T) {
	registry, _, err := buildRequestToolEnvironment(
		[]provider.Tool{{
			Type: "function",
			Function: provider.ToolFunction{
				Name:       "spawn_subagent",
				Parameters: map[string]any{"type": "object"},
			},
		}},
		nil,
		map[string]any{
			"responses": map[string]any{
				"healthy": "healthy report",
				"broken":  "nominal report",
			},
		},
		map[string]evalToolBehavior{
			"spawn_subagent": {
				ResultMapPath:        "responses",
				ResultMapKeyArgument: "agentId",
				Faults: []evalToolFault{
					{Argument: "agentId", Value: "broken", Error: "specialist unavailable"},
					{Argument: "agentId", Value: "malformed", Result: "{not-json"},
				},
			},
		},
	)
	if err != nil {
		t.Fatal(err)
	}

	result, err := registry.Execute(t.Context(), "spawn_subagent", `{"agentId":"healthy"}`)
	if err != nil || result != "healthy report" {
		t.Fatalf("healthy result = %q, %v", result, err)
	}
	if _, err := registry.Execute(t.Context(), "spawn_subagent", `{"agentId":"broken"}`); err == nil ||
		err.Error() != "specialist unavailable" {
		t.Fatalf("fault error = %v", err)
	}
	result, err = registry.Execute(t.Context(), "spawn_subagent", `{"agentId":"malformed"}`)
	if err != nil || result != "{not-json" {
		t.Fatalf("malformed result = %q, %v", result, err)
	}
}

func TestRequestToolEnvironmentFaultDelayHonorsCancellation(t *testing.T) {
	registry, _, err := buildRequestToolEnvironment(
		[]provider.Tool{{
			Type: "function",
			Function: provider.ToolFunction{
				Name:       "slow_tool",
				Parameters: map[string]any{"type": "object"},
			},
		}},
		nil,
		nil,
		map[string]evalToolBehavior{
			"slow_tool": {
				Faults: []evalToolFault{{
					Argument: "id",
					Value:    "slow",
					DelayMS:  500,
					Error:    "timed out",
				}},
			},
		},
	)
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(t.Context(), 10*time.Millisecond)
	defer cancel()
	startedAt := time.Now()
	_, err = registry.Execute(ctx, "slow_tool", `{"id":"slow"}`)
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("fault delay error = %v", err)
	}
	if time.Since(startedAt) > 250*time.Millisecond {
		t.Fatalf("fault did not stop promptly: %s", time.Since(startedAt))
	}
}

func TestRequestToolEnvironmentRejectsExcessiveFaultDelay(t *testing.T) {
	_, _, err := buildRequestToolEnvironment(
		[]provider.Tool{{
			Type: "function",
			Function: provider.ToolFunction{
				Name:       "slow_tool",
				Parameters: map[string]any{"type": "object"},
			},
		}},
		nil,
		nil,
		map[string]evalToolBehavior{
			"slow_tool": {
				Faults: []evalToolFault{{
					Argument: "id",
					Value:    "slow",
					DelayMS:  maxEvalToolFaultDelayMS + 1,
					Error:    "timed out",
				}},
			},
		},
	)
	if err == nil || !strings.Contains(err.Error(), "delay cannot exceed") {
		t.Fatalf("excessive fault delay error = %v", err)
	}
}

func TestStartTraceCaptureCollectsToolEvents(t *testing.T) {
	ctx, finish := startTraceCapture(context.Background())
	events := agent.ChatEventsFromContext(ctx)
	events <- agent.ChatEvent{
		Type: "tool_call",
		Data: map[string]any{
			"id": "call-1", "name": "lookup", "arguments": `{"id":1}`, "round": 1,
		},
	}
	events <- agent.ChatEvent{
		Type: "tool_result",
		Data: map[string]any{
			"id": "call-1", "name": "lookup", "result": "ok", "round": 1,
		},
	}
	events <- agent.ChatEvent{Type: "done", Data: map[string]any{"round": 1}}

	trace := finish()
	if len(trace) != 2 || trace[0].Type != "tool_call" || trace[1].Result != "ok" {
		t.Fatalf("unexpected trace: %+v", trace)
	}
}
