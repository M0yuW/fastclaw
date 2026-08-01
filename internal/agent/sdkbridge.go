package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"runtime/debug"
	"strings"
	"sync"
	"time"

	"github.com/codeany-ai/open-agent-sdk-go/costtracker"
	sdktools "github.com/codeany-ai/open-agent-sdk-go/tools"
	sdktypes "github.com/codeany-ai/open-agent-sdk-go/types"

	"github.com/fastclaw-ai/fastclaw/internal/agent/tools"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

// readOnlyTools lists tools that are safe to run concurrently.
var readOnlyTools = map[string]bool{
	"read_file":     true,
	"list_dir":      true,
	"web_fetch":     true,
	"web_search":    true,
	"memory_search": true,
	"load_skill":    true,
}

const toolCallIDMetadataKey = "__fastclaw_tool_call_id"

type toolTimingRecorder struct {
	mu        sync.Mutex
	durations map[string]time.Duration
}

func newToolTimingRecorder() *toolTimingRecorder {
	return &toolTimingRecorder{durations: make(map[string]time.Duration)}
}

func (recorder *toolTimingRecorder) record(toolCallID string, duration time.Duration) {
	if recorder == nil || toolCallID == "" {
		return
	}
	recorder.mu.Lock()
	recorder.durations[toolCallID] = duration
	recorder.mu.Unlock()
}

func (recorder *toolTimingRecorder) duration(toolCallID string) time.Duration {
	if recorder == nil || toolCallID == "" {
		return 0
	}
	recorder.mu.Lock()
	defer recorder.mu.Unlock()
	return recorder.durations[toolCallID]
}

// toolAdapter wraps a FastClaw tool as an SDK Tool interface.
type toolAdapter struct {
	name                      string
	description               string
	params                    interface{}
	fn                        tools.ToolFunc
	concurrentSubAgentTargets map[string]bool
	timings                   *toolTimingRecorder
}

func (t *toolAdapter) Name() string        { return t.name }
func (t *toolAdapter) Description() string { return t.description }

func (t *toolAdapter) InputSchema() sdktypes.ToolInputSchema {
	// Convert FastClaw params (interface{}) to SDK ToolInputSchema
	if t.params == nil {
		return sdktypes.ToolInputSchema{Type: "object"}
	}
	data, err := json.Marshal(t.params)
	if err != nil {
		return sdktypes.ToolInputSchema{Type: "object"}
	}
	var schema sdktypes.ToolInputSchema
	if err := json.Unmarshal(data, &schema); err != nil {
		return sdktypes.ToolInputSchema{Type: "object"}
	}
	return schema
}

func (t *toolAdapter) Call(
	ctx context.Context,
	input map[string]interface{},
	tCtx *sdktypes.ToolUseContext,
) (result *sdktypes.ToolResult, err error) {
	startedAt := time.Now()
	toolCallID, _ := input[toolCallIDMetadataKey].(string)
	defer func() {
		t.timings.record(toolCallID, time.Since(startedAt))
		if recovered := recover(); recovered != nil {
			slog.Error(
				"tool panicked",
				"tool", t.name,
				"tool_call_id", toolCallID,
				"panic", recovered,
				"stack", string(debug.Stack()),
			)
			message := fmt.Sprintf("tool %s panicked: %v", t.name, recovered)
			result = &sdktypes.ToolResult{
				IsError: true,
				Error:   message,
				Content: []sdktypes.ContentBlock{{
					Type: sdktypes.ContentBlockText,
					Text: message,
				}},
			}
			err = nil
		}
	}()
	cleanInput := make(map[string]interface{}, len(input))
	for key, value := range input {
		if key != toolCallIDMetadataKey {
			cleanInput[key] = value
		}
	}
	// Convert input map to JSON for FastClaw's ToolFunc
	argsJSON, err := json.Marshal(cleanInput)
	if err != nil {
		return &sdktypes.ToolResult{IsError: true, Error: err.Error()}, nil
	}

	toolOutput, err := t.fn(ctx, json.RawMessage(argsJSON))
	if err != nil {
		errText := toolOutput
		if errText != "" {
			errText += "\n"
		}
		errText += err.Error()
		return &sdktypes.ToolResult{
			IsError: true,
			Error:   errText,
			Content: []sdktypes.ContentBlock{{
				Type: sdktypes.ContentBlockText,
				Text: errText,
			}},
		}, nil
	}

	return &sdktypes.ToolResult{
		Content: []sdktypes.ContentBlock{{
			Type: sdktypes.ContentBlockText,
			Text: toolOutput,
		}},
	}, nil
}

func (t *toolAdapter) IsConcurrencySafe(input map[string]interface{}) bool {
	if t.name == "spawn_subagent" {
		agentID, ok := input["agentId"].(string)
		if !ok || agentID == "" {
			return false
		}
		return t.concurrentSubAgentTargets[agentID]
	}
	return readOnlyTools[t.name]
}

func (t *toolAdapter) IsReadOnly(input map[string]interface{}) bool {
	return readOnlyTools[t.name]
}

// sdkEngine wraps SDK components for concurrent tool execution and cost tracking.
type sdkEngine struct {
	costTracker *costtracker.Tracker
}

// newSDKEngine creates a new SDK engine with cost tracking.
func newSDKEngine(sessionID string) *sdkEngine {
	return &sdkEngine{
		costTracker: costtracker.NewTracker(sessionID),
	}
}

// buildSDKRegistry converts FastClaw's tool registry into an SDK registry.
func buildSDKRegistry(
	fcRegistry *tools.Registry,
	concurrentSubAgentTargets map[string]bool,
	timings *toolTimingRecorder,
) *sdktools.Registry {
	sdkReg := sdktools.NewRegistry()
	for _, def := range fcRegistry.Definitions() {
		fn := fcRegistry.GetFunc(def.Function.Name)
		if fn == nil {
			continue
		}
		sdkReg.Register(&toolAdapter{
			name:                      def.Function.Name,
			description:               def.Function.Description,
			params:                    def.Function.Parameters,
			fn:                        fn,
			concurrentSubAgentTargets: concurrentSubAgentTargets,
			timings:                   timings,
		})
	}
	return sdkReg
}

// toolCallResult holds the result of a single tool call with metadata.
type toolCallResult struct {
	toolCallID string
	toolName   string
	result     string
	err        error
	duration   time.Duration
}

// executeToolsConcurrently runs tool calls using the SDK's concurrent executor.
func (e *sdkEngine) executeToolsConcurrently(ctx context.Context, fcRegistry *tools.Registry, toolCalls []provider.ToolCall, workspace string) []toolCallResult {
	timings := newToolTimingRecorder()
	sdkReg := buildSDKRegistry(fcRegistry, uniqueSubAgentTargets(toolCalls), timings)
	executor := sdktools.NewExecutor(sdkReg, nil, &sdktypes.ToolUseContext{
		WorkingDir: workspace,
		AbortCtx:   ctx,
	})

	// Convert FastClaw tool calls to SDK format
	calls := make([]sdktools.ToolCallRequest, len(toolCalls))
	for i, tc := range toolCalls {
		var input map[string]interface{}
		if err := json.Unmarshal([]byte(tc.Function.Arguments), &input); err != nil {
			input = map[string]interface{}{"_raw": tc.Function.Arguments}
		}
		if input == nil {
			input = make(map[string]interface{})
		}
		input[toolCallIDMetadataKey] = tc.ID
		calls[i] = sdktools.ToolCallRequest{
			ToolUseID: tc.ID,
			ToolName:  tc.Function.Name,
			Input:     input,
		}
	}

	start := time.Now()
	responses := executor.RunTools(ctx, calls)
	e.costTracker.AddToolDuration(time.Since(start))

	// Anthropic (and OpenAI) require a tool_result for every tool_use the
	// model just emitted — orphaned tool_use IDs make the next API call
	// return 400 invalid_request_error. The SDK can short-circuit and
	// return fewer responses than requested (context cancel, executor
	// poisoned by a sandbox-creation failure, etc.), so build the result
	// slice keyed on toolCalls and look up by ToolUseID instead of zipping
	// position-by-position. Missing entries become explicit failure
	// tool_results so the conversation history stays well-formed.
	byID := make(map[string]sdktools.ToolCallResponse, len(responses))
	for _, resp := range responses {
		if resp.ToolUseID == "" {
			slog.Error("tool executor returned an empty tool_call ID")
			continue
		}
		if _, exists := byID[resp.ToolUseID]; exists {
			slog.Error("tool executor returned a duplicate tool_call ID", "tool_call_id", resp.ToolUseID)
			continue
		}
		byID[resp.ToolUseID] = resp
	}
	results := make([]toolCallResult, len(toolCalls))
	for i, tc := range toolCalls {
		duration := timings.duration(tc.ID)
		if tc.ID == "" {
			results[i] = missingToolCallResult(tc, "tool_use ID is empty", duration)
			continue
		}
		resp, ok := byID[tc.ID]
		if !ok {
			results[i] = missingToolCallResult(tc, "tool execution did not return a result", duration)
			continue
		}
		delete(byID, tc.ID)
		var resultText string
		if resp.Result != nil {
			if resp.Result.IsError {
				resultText = resp.Result.Error
				if resultText == "" && len(resp.Result.Content) > 0 {
					resultText = resp.Result.Content[0].Text
				}
				results[i] = toolCallResult{
					toolCallID: resp.ToolUseID,
					toolName:   toolCalls[i].Function.Name,
					result:     resultText + "\n[Analyze the error above and try a different approach.]",
					err:        fmt.Errorf("%s", resultText),
					duration:   duration,
				}
				continue
			}
			// Extract text from content blocks
			var parts []string
			for _, cb := range resp.Result.Content {
				if cb.Text != "" {
					parts = append(parts, cb.Text)
				}
			}
			resultText = strings.Join(parts, "\n")
		}
		if resp.Error != nil {
			results[i] = toolCallResult{
				toolCallID: resp.ToolUseID,
				toolName:   toolCalls[i].Function.Name,
				result:     resultText,
				err:        resp.Error,
				duration:   duration,
			}
		} else {
			results[i] = toolCallResult{
				toolCallID: resp.ToolUseID,
				toolName:   toolCalls[i].Function.Name,
				result:     resultText,
				duration:   duration,
			}
		}
	}
	return results
}

func missingToolCallResult(
	toolCall provider.ToolCall,
	reason string,
	duration time.Duration,
) toolCallResult {
	message := reason + " (sandbox, executor, or provider failure — check gateway logs)"
	return toolCallResult{
		toolCallID: toolCall.ID,
		toolName:   toolCall.Function.Name,
		result:     message,
		err:        fmt.Errorf("%s for tool_use %q", reason, toolCall.ID),
		duration:   duration,
	}
}

func uniqueSubAgentTargets(toolCalls []provider.ToolCall) map[string]bool {
	counts := make(map[string]int)
	for _, toolCall := range toolCalls {
		if toolCall.Function.Name != "spawn_subagent" {
			continue
		}
		var arguments struct {
			AgentID string `json:"agentId"`
		}
		if json.Unmarshal([]byte(toolCall.Function.Arguments), &arguments) != nil ||
			arguments.AgentID == "" {
			continue
		}
		counts[arguments.AgentID]++
	}
	unique := make(map[string]bool, len(counts))
	for agentID, count := range counts {
		unique[agentID] = count == 1
	}
	return unique
}
