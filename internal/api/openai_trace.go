package api

import (
	"context"
	"encoding/json"
	"fmt"
	"reflect"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/agent"
	agenttools "github.com/fastclaw-ai/fastclaw/internal/agent/tools"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

const maxRequestTools = 64
const maxTraceFieldBytes = 16 << 10
const maxBatchTraceResultBytes = 4 << 10
const maxEvalToolFaultDelayMS = int((5 * time.Minute) / time.Millisecond)

type fastClawRequestOptions struct {
	Eval                      bool                          `json:"eval,omitempty"`
	IncludeTrace              bool                          `json:"include_trace,omitempty"`
	IncludeUsageBreakdown     bool                          `json:"include_usage_breakdown,omitempty"`
	IsolateTools              bool                          `json:"isolate_tools,omitempty"`
	Pricing                   map[string]agent.ModelPricing `json:"pricing,omitempty"`
	ToolResults               map[string]string             `json:"tool_results,omitempty"`
	State                     map[string]any                `json:"state,omitempty"`
	ToolBehaviors             map[string]evalToolBehavior   `json:"tool_behaviors,omitempty"`
	SubAgentMaxCalls          int                           `json:"subagent_max_calls,omitempty"`
	SubAgentMaxCallsPerTarget int                           `json:"subagent_max_calls_per_target,omitempty"`
}

type completionMetadata struct {
	Trace      []completionTraceEvent `json:"trace,omitempty"`
	State      map[string]any         `json:"state,omitempty"`
	ModelCalls []agent.ModelCallUsage `json:"model_calls,omitempty"`
}

type evalToolBehavior struct {
	Conditions           []evalStateCondition `json:"conditions,omitempty"`
	Updates              []evalStateUpdate    `json:"updates,omitempty"`
	Faults               []evalToolFault      `json:"faults,omitempty"`
	Result               any                  `json:"result,omitempty"`
	ResultPath           string               `json:"result_path,omitempty"`
	ResultKeysPath       string               `json:"result_keys_path,omitempty"`
	ResultMapPath        string               `json:"result_map_path,omitempty"`
	ResultMapKeyArgument string               `json:"result_map_key_argument,omitempty"`
}

type evalToolFault struct {
	Argument string `json:"argument"`
	Value    string `json:"value"`
	DelayMS  int    `json:"delay_ms,omitempty"`
	Error    string `json:"error,omitempty"`
	Result   any    `json:"result,omitempty"`
}

type evalStateCondition struct {
	Path   string `json:"path"`
	Equals any    `json:"equals"`
	Error  string `json:"error,omitempty"`
}

type evalStateUpdate struct {
	Path              string `json:"path"`
	Value             any    `json:"value,omitempty"`
	ValueFromArgument string `json:"value_from_argument,omitempty"`
	MapPath           string `json:"map_path,omitempty"`
	KeyFromArgument   string `json:"key_from_argument,omitempty"`
}

type evalToolEnvironment struct {
	mu        sync.Mutex
	state     map[string]any
	results   map[string]string
	behaviors map[string]evalToolBehavior
}

type completionTraceEvent struct {
	Type      string `json:"type"`
	ID        string `json:"id,omitempty"`
	Name      string `json:"name,omitempty"`
	Arguments string `json:"arguments,omitempty"`
	Result    string `json:"result,omitempty"`
	Message   string `json:"message,omitempty"`
	Round     int    `json:"round,omitempty"`
}

func requestToolRegistry(definitions []provider.Tool, results map[string]string) (*agenttools.Registry, error) {
	registry, _, err := buildRequestToolEnvironment(definitions, results, nil, nil)
	return registry, err
}

func buildRequestToolEnvironment(
	definitions []provider.Tool,
	results map[string]string,
	state map[string]any,
	behaviors map[string]evalToolBehavior,
) (*agenttools.Registry, func() map[string]any, error) {
	if len(definitions) > maxRequestTools {
		return nil, nil, fmt.Errorf("request cannot define more than %d tools", maxRequestTools)
	}
	registry := agenttools.NewEmptyRegistry()
	environment := &evalToolEnvironment{
		state:     cloneJSONMap(state),
		results:   results,
		behaviors: behaviors,
	}
	seen := make(map[string]struct{}, len(definitions))
	for index, definition := range definitions {
		if definition.Type != "" && definition.Type != "function" {
			return nil, nil, fmt.Errorf("tool %d: unsupported type %q", index+1, definition.Type)
		}
		name := strings.TrimSpace(definition.Function.Name)
		if name == "" {
			return nil, nil, fmt.Errorf("tool %d: function name is required", index+1)
		}
		if _, exists := seen[name]; exists {
			return nil, nil, fmt.Errorf("tool %d: duplicate function name %q", index+1, name)
		}
		seen[name] = struct{}{}
		registry.Register(
			name,
			definition.Function.Description,
			normalizeToolSchema(definition.Function.Parameters),
			func(ctx context.Context, arguments json.RawMessage) (string, error) {
				return environment.execute(ctx, name, arguments)
			},
		)
	}
	for name := range behaviors {
		if _, exists := seen[name]; !exists {
			return nil, nil, fmt.Errorf("tool behavior %q has no matching request tool", name)
		}
		behavior := behaviors[name]
		for index, fault := range behavior.Faults {
			if strings.TrimSpace(fault.Argument) == "" || strings.TrimSpace(fault.Value) == "" {
				return nil, nil, fmt.Errorf("tool behavior %q fault %d requires argument and value", name, index+1)
			}
			if fault.DelayMS < 0 {
				return nil, nil, fmt.Errorf("tool behavior %q fault %d delay cannot be negative", name, index+1)
			}
			if fault.DelayMS > maxEvalToolFaultDelayMS {
				return nil, nil, fmt.Errorf(
					"tool behavior %q fault %d delay cannot exceed %dms",
					name,
					index+1,
					maxEvalToolFaultDelayMS,
				)
			}
		}
	}
	return registry, environment.snapshot, nil
}

func (e *evalToolEnvironment) execute(
	ctx context.Context,
	name string,
	rawArguments json.RawMessage,
) (string, error) {
	behavior, stateful := e.behaviors[name]
	if !stateful {
		result := e.results[name]
		if result == "" {
			result = `{"ok":true}`
		}
		return result, nil
	}

	var arguments map[string]any
	if err := json.Unmarshal(rawArguments, &arguments); err != nil {
		return "", fmt.Errorf("decode %s arguments: %w", name, err)
	}
	// Fault injection models a tool-layer short circuit. Matching faults bypass
	// normal state conditions and updates by design.
	if fault, ok := matchingEvalToolFault(behavior.Faults, arguments); ok {
		if fault.DelayMS > 0 {
			timer := time.NewTimer(time.Duration(fault.DelayMS) * time.Millisecond)
			defer timer.Stop()
			select {
			case <-ctx.Done():
				return "", ctx.Err()
			case <-timer.C:
			}
		}
		if fault.Error != "" {
			return "", fmt.Errorf("%s", fault.Error)
		}
		return encodeEvalToolResult(name, fault.Result)
	}

	e.mu.Lock()
	defer e.mu.Unlock()
	for _, condition := range behavior.Conditions {
		path, err := interpolateStatePath(condition.Path, arguments)
		if err != nil {
			return "", err
		}
		actual, exists := lookupStatePath(e.state, path)
		if !exists || !reflect.DeepEqual(actual, condition.Equals) {
			if condition.Error != "" {
				return "", fmt.Errorf("%s", condition.Error)
			}
			return "", fmt.Errorf("condition failed: %s must equal %v", path, condition.Equals)
		}
	}
	for _, update := range behavior.Updates {
		value := update.Value
		if update.ValueFromArgument != "" {
			var exists bool
			value, exists = arguments[update.ValueFromArgument]
			if !exists {
				return "", fmt.Errorf("missing tool argument %q", update.ValueFromArgument)
			}
		}
		if update.MapPath != "" {
			mapPath, err := interpolateStatePath(update.MapPath, arguments)
			if err != nil {
				return "", err
			}
			target, exists := lookupStatePath(e.state, mapPath)
			if !exists {
				return "", fmt.Errorf("state map path %q not found", mapPath)
			}
			targetMap, ok := target.(map[string]any)
			if !ok {
				return "", fmt.Errorf("state map path %q is not an object", mapPath)
			}
			key, err := stateMapKey(arguments, update.KeyFromArgument)
			if err != nil {
				return "", err
			}
			targetMap[key] = cloneJSONValue(value)
			continue
		}
		path, err := interpolateStatePath(update.Path, arguments)
		if err != nil {
			return "", err
		}
		if err := setStatePath(e.state, path, value); err != nil {
			return "", err
		}
	}

	result := behavior.Result
	switch {
	case behavior.ResultMapPath != "":
		mapPath, err := interpolateStatePath(behavior.ResultMapPath, arguments)
		if err != nil {
			return "", err
		}
		target, exists := lookupStatePath(e.state, mapPath)
		if !exists {
			return "", fmt.Errorf("state map path %q not found", mapPath)
		}
		targetMap, ok := target.(map[string]any)
		if !ok {
			return "", fmt.Errorf("state map path %q is not an object", mapPath)
		}
		key, err := stateMapKey(arguments, behavior.ResultMapKeyArgument)
		if err != nil {
			return "", err
		}
		result, exists = targetMap[key]
		if !exists {
			return "", fmt.Errorf("state map key %q not found", key)
		}
	case behavior.ResultKeysPath != "":
		mapPath, err := interpolateStatePath(behavior.ResultKeysPath, arguments)
		if err != nil {
			return "", err
		}
		target, exists := lookupStatePath(e.state, mapPath)
		if !exists {
			return "", fmt.Errorf("state map path %q not found", mapPath)
		}
		targetMap, ok := target.(map[string]any)
		if !ok {
			return "", fmt.Errorf("state map path %q is not an object", mapPath)
		}
		keys := make([]string, 0, len(targetMap))
		for key := range targetMap {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		result = keys
	case behavior.ResultPath != "":
		path, err := interpolateStatePath(behavior.ResultPath, arguments)
		if err != nil {
			return "", err
		}
		var exists bool
		result, exists = lookupStatePath(e.state, path)
		if !exists {
			return "", fmt.Errorf("state path %q not found", path)
		}
	}
	return encodeEvalToolResult(name, result)
}

func matchingEvalToolFault(
	faults []evalToolFault,
	arguments map[string]any,
) (evalToolFault, bool) {
	for _, fault := range faults {
		value, exists := arguments[fault.Argument]
		if exists && fmt.Sprint(value) == fault.Value {
			return fault, true
		}
	}
	return evalToolFault{}, false
}

func encodeEvalToolResult(name string, result any) (string, error) {
	if result == nil {
		result = map[string]any{"ok": true}
	}
	if text, ok := result.(string); ok {
		return text, nil
	}
	encoded, err := json.Marshal(result)
	if err != nil {
		return "", fmt.Errorf("encode %s result: %w", name, err)
	}
	return string(encoded), nil
}

func stateMapKey(arguments map[string]any, argumentName string) (string, error) {
	if argumentName == "" {
		return "", fmt.Errorf("map key argument is required")
	}
	value, exists := arguments[argumentName]
	if !exists {
		return "", fmt.Errorf("missing tool argument %q", argumentName)
	}
	key, ok := value.(string)
	if !ok || strings.TrimSpace(key) == "" || strings.ContainsRune(key, '\x00') {
		return "", fmt.Errorf("tool argument %q must be a non-empty string", argumentName)
	}
	return key, nil
}

func (e *evalToolEnvironment) snapshot() map[string]any {
	e.mu.Lock()
	defer e.mu.Unlock()
	return cloneJSONMap(e.state)
}

func interpolateStatePath(path string, arguments map[string]any) (string, error) {
	result := path
	for {
		start := strings.IndexByte(result, '{')
		if start < 0 {
			break
		}
		endOffset := strings.IndexByte(result[start:], '}')
		if endOffset < 0 {
			return "", fmt.Errorf("invalid state path %q", path)
		}
		end := start + endOffset
		name := result[start+1 : end]
		value, exists := arguments[name]
		if !exists {
			return "", fmt.Errorf("missing tool argument %q", name)
		}
		replacement, ok := value.(string)
		if !ok || replacement == "" || strings.Contains(replacement, ".") {
			return "", fmt.Errorf("tool argument %q must be a non-empty path-safe string", name)
		}
		result = result[:start] + replacement + result[end+1:]
	}
	if strings.TrimSpace(result) == "" {
		return "", fmt.Errorf("state path is required")
	}
	return result, nil
}

func lookupStatePath(state map[string]any, path string) (any, bool) {
	var current any = state
	for _, part := range strings.Split(path, ".") {
		object, ok := current.(map[string]any)
		if !ok {
			return nil, false
		}
		current, ok = object[part]
		if !ok {
			return nil, false
		}
	}
	return current, true
}

func setStatePath(state map[string]any, path string, value any) error {
	parts := strings.Split(path, ".")
	current := state
	for _, part := range parts[:len(parts)-1] {
		child, exists := current[part]
		if !exists {
			next := make(map[string]any)
			current[part] = next
			current = next
			continue
		}
		next, ok := child.(map[string]any)
		if !ok {
			return fmt.Errorf("state path %q traverses a non-object value", path)
		}
		current = next
	}
	current[parts[len(parts)-1]] = cloneJSONValue(value)
	return nil
}

func cloneJSONMap(value map[string]any) map[string]any {
	if value == nil {
		return make(map[string]any)
	}
	cloned, _ := cloneJSONValue(value).(map[string]any)
	return cloned
}

func cloneJSONValue(value any) any {
	encoded, err := json.Marshal(value)
	if err != nil {
		return value
	}
	var cloned any
	if err := json.Unmarshal(encoded, &cloned); err != nil {
		return value
	}
	return cloned
}

func normalizeToolSchema(value any) any {
	switch typed := value.(type) {
	case map[string]any:
		normalized := make(map[string]any, len(typed))
		for key, child := range typed {
			if key == "type" {
				if typeName, ok := child.(string); ok {
					switch typeName {
					case "dict":
						child = "object"
					case "float":
						child = "number"
					}
				}
			}
			normalized[key] = normalizeToolSchema(child)
		}
		return normalized
	case []any:
		normalized := make([]any, len(typed))
		for index, child := range typed {
			normalized[index] = normalizeToolSchema(child)
		}
		return normalized
	default:
		return value
	}
}

func startTraceCapture(ctx context.Context) (context.Context, func() []completionTraceEvent) {
	captureCtx, cancel := context.WithCancel(ctx)
	events := make(chan agent.ChatEvent, 64)
	result := make(chan []completionTraceEvent, 1)
	go func() {
		var trace []completionTraceEvent
		for {
			select {
			case event := <-events:
				if converted, ok := convertTraceEvent(event); ok {
					trace = append(trace, converted)
				}
				if event.Type == "done" {
					result <- trace
					return
				}
			case <-captureCtx.Done():
				for {
					select {
					case event := <-events:
						if converted, ok := convertTraceEvent(event); ok {
							trace = append(trace, converted)
						}
					default:
						result <- trace
						return
					}
				}
			}
		}
	}()

	tracedCtx := agent.ContextWithChatEvents(captureCtx, events)
	return tracedCtx, func() []completionTraceEvent {
		cancel()
		return <-result
	}
}

func convertTraceEvent(event agent.ChatEvent) (completionTraceEvent, bool) {
	if event.Data == nil {
		return completionTraceEvent{}, false
	}
	trace := completionTraceEvent{Type: event.Type, Round: traceRound(event.Data["round"])}
	switch event.Type {
	case "tool_call":
		trace.ID, _ = event.Data["id"].(string)
		trace.Name, _ = event.Data["name"].(string)
		trace.Arguments, _ = event.Data["arguments"].(string)
		trace.Arguments = compactTraceArguments(trace.Name, trace.Arguments)
	case "tool_result":
		trace.ID, _ = event.Data["id"].(string)
		trace.Name, _ = event.Data["name"].(string)
		trace.Result, _ = event.Data["result"].(string)
		trace.Result = compactTraceResult(trace.Name, trace.Result)
	case "error":
		trace.Message, _ = event.Data["message"].(string)
		trace.Message = truncateTraceField(trace.Message)
	default:
		return completionTraceEvent{}, false
	}
	return trace, true
}

func compactTraceArguments(name, value string) string {
	if name != "spawn_subagent" {
		return truncateTraceField(value)
	}
	var batch struct {
		SharedContext string `json:"sharedContext,omitempty"`
		Delegations   []struct {
			AgentID string `json:"agentId"`
			Task    string `json:"task"`
		} `json:"delegations,omitempty"`
	}
	if json.Unmarshal([]byte(value), &batch) != nil || len(batch.Delegations) == 0 {
		return truncateTraceField(value)
	}
	if batch.SharedContext != "" {
		batch.SharedContext = fmt.Sprintf("[omitted %d bytes from trace]", len(batch.SharedContext))
	}
	encoded, err := json.Marshal(batch)
	if err != nil {
		return truncateTraceField(value)
	}
	return truncateTraceField(string(encoded))
}

func compactTraceResult(name, value string) string {
	if name != "spawn_subagent" {
		return truncateTraceField(value)
	}
	var batch struct {
		Results []struct {
			AgentID string `json:"agentId"`
			Result  string `json:"result,omitempty"`
			Error   string `json:"error,omitempty"`
		} `json:"results"`
	}
	if json.Unmarshal([]byte(value), &batch) != nil || len(batch.Results) == 0 {
		return truncateTraceField(value)
	}
	for index := range batch.Results {
		batch.Results[index].Result = truncateTraceFieldTo(batch.Results[index].Result, maxBatchTraceResultBytes)
		batch.Results[index].Error = truncateTraceFieldTo(batch.Results[index].Error, maxBatchTraceResultBytes)
	}
	encoded, err := json.Marshal(batch)
	if err != nil {
		return truncateTraceField(value)
	}
	return truncateTraceField(string(encoded))
}

func truncateTraceField(value string) string {
	return truncateTraceFieldTo(value, maxTraceFieldBytes)
}

func truncateTraceFieldTo(value string, limit int) string {
	if len(value) <= limit {
		return value
	}
	return value[:limit] + "...[truncated]"
}

func traceRound(value any) int {
	switch typed := value.(type) {
	case int:
		return typed
	case int64:
		return int(typed)
	case float64:
		return int(typed)
	case nil:
		return 0
	default:
		return 0
	}
}
