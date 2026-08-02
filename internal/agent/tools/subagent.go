package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
)

// SubAgentSpawner is the interface for spawning sub-agents.
type SubAgentSpawner interface {
	// SpawnSubAgent sends a task to another agent and returns its response.
	SpawnSubAgent(ctx context.Context, agentID string, msg bus.InboundMessage) (string, error)
}

type spawnSubagentArgs struct {
	AgentID       string                    `json:"agentId"`
	Task          string                    `json:"task"`
	SharedContext string                    `json:"sharedContext"`
	Delegations   []spawnSubagentDelegation `json:"delegations"`
}

type spawnSubagentDelegation struct {
	AgentID string `json:"agentId"`
	Task    string `json:"task"`
}

type spawnSubagentBatchResult struct {
	Results []spawnSubagentDelegationResult `json:"results"`
}

type spawnSubagentDelegationResult struct {
	AgentID string `json:"agentId"`
	Result  string `json:"result,omitempty"`
	Error   string `json:"error,omitempty"`
}

var subAgentCallCounter uint64

type subAgentDedupKey struct{}

type subAgentResult struct {
	done   chan struct{}
	result string
	err    error
}

type subAgentDedup struct {
	mu         sync.Mutex
	targetOnly bool
	results    map[string]*subAgentResult
}

// ContextWithSubAgentDedup reuses an identical target/task delegation within
// one parent turn while preserving distinct tasks for the same target.
func ContextWithSubAgentDedup(ctx context.Context) context.Context {
	return contextWithSubAgentDedup(ctx, false)
}

// ContextWithSubAgentTargetDedup is the stricter eval-only mode: each target
// executes at most once during a parent turn, regardless of task wording.
func ContextWithSubAgentTargetDedup(ctx context.Context) context.Context {
	return contextWithSubAgentDedup(ctx, true)
}

func contextWithSubAgentDedup(ctx context.Context, targetOnly bool) context.Context {
	if ctx == nil {
		ctx = context.Background()
	}
	if _, ok := ctx.Value(subAgentDedupKey{}).(*subAgentDedup); ok {
		return ctx
	}
	return context.WithValue(ctx, subAgentDedupKey{}, &subAgentDedup{
		targetOnly: targetOnly,
		results:    make(map[string]*subAgentResult),
	})
}

// RegisterSubAgent registers the spawn_subagent tool.
func RegisterSubAgent(r *Registry, spawner SubAgentSpawner, callerAgentID string) {
	r.Register("spawn_subagent", "Delegate one task or a batch of independent tasks. Batch mode sends sharedContext to every delegation once at runtime and executes distinct targets concurrently. Identical repeated target/task calls within one parent turn reuse the first result.", map[string]interface{}{
		"type": "object",
		"properties": map[string]interface{}{
			"agentId": map[string]interface{}{
				"type":        "string",
				"description": "The ID of the agent to spawn",
			},
			"task": map[string]interface{}{
				"type":        "string",
				"description": "The message/prompt to send to the sub-agent",
			},
			"sharedContext": map[string]interface{}{
				"type":        "string",
				"description": "Batch-only evidence or context appended once by the runtime to every delegated task",
			},
			"delegations": map[string]interface{}{
				"type":        "array",
				"description": "Batch-only list of independent specialist targets and focused tasks",
				"minItems":    1,
				"maxItems":    16,
				"items": map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"agentId": map[string]interface{}{"type": "string"},
						"task":    map[string]interface{}{"type": "string"},
					},
					"required": []string{"agentId", "task"},
				},
			},
		},
		"anyOf": []map[string]interface{}{
			{"required": []string{"agentId", "task"}},
			{"required": []string{"sharedContext", "delegations"}},
		},
	}, makeSubAgentTool(spawner, callerAgentID))
}

func makeSubAgentTool(spawner SubAgentSpawner, callerAgentID string) ToolFunc {
	return func(ctx context.Context, rawArgs json.RawMessage) (string, error) {
		var args spawnSubagentArgs
		if err := json.Unmarshal(rawArgs, &args); err != nil {
			return "", fmt.Errorf("parse args: %w", err)
		}
		if len(args.Delegations) > 0 {
			if args.AgentID != "" || args.Task != "" {
				return "", fmt.Errorf("single and batch delegation fields cannot be combined")
			}
			return spawnSubAgentBatch(ctx, spawner, callerAgentID, args.SharedContext, args.Delegations)
		}

		if args.AgentID == "" {
			return "", fmt.Errorf("agentId is required")
		}
		if args.Task == "" {
			return "", fmt.Errorf("task is required")
		}
		if args.AgentID == callerAgentID {
			return "", fmt.Errorf("cannot spawn yourself as a sub-agent")
		}
		if dedup, ok := ctx.Value(subAgentDedupKey{}).(*subAgentDedup); ok {
			return dedup.call(ctx, args.AgentID, args.Task, func() (string, error) {
				return spawnSubAgent(ctx, spawner, callerAgentID, args)
			})
		}
		return spawnSubAgent(ctx, spawner, callerAgentID, args)
	}
}

func spawnSubAgentBatch(
	ctx context.Context,
	spawner SubAgentSpawner,
	callerAgentID string,
	sharedContext string,
	delegations []spawnSubagentDelegation,
) (string, error) {
	if len(delegations) == 0 {
		return "", fmt.Errorf("delegations are required")
	}
	if len(delegations) > 16 {
		return "", fmt.Errorf("delegations cannot exceed 16")
	}
	seen := make(map[string]struct{}, len(delegations))
	for _, delegation := range delegations {
		if delegation.AgentID == "" {
			return "", fmt.Errorf("delegation agentId is required")
		}
		if delegation.Task == "" {
			return "", fmt.Errorf("delegation task is required")
		}
		if delegation.AgentID == callerAgentID {
			return "", fmt.Errorf("cannot spawn yourself as a sub-agent")
		}
		if _, exists := seen[delegation.AgentID]; exists {
			return "", fmt.Errorf("duplicate batch target %q", delegation.AgentID)
		}
		seen[delegation.AgentID] = struct{}{}
	}

	batch := spawnSubagentBatchResult{Results: make([]spawnSubagentDelegationResult, len(delegations))}
	var waitGroup sync.WaitGroup
	for index, delegation := range delegations {
		waitGroup.Add(1)
		go func() {
			defer waitGroup.Done()
			task := delegation.Task
			if sharedContext != "" {
				task += "\n\nShared context:\n" + sharedContext
			}
			args := spawnSubagentArgs{AgentID: delegation.AgentID, Task: task}
			var result string
			var err error
			if dedup, ok := ctx.Value(subAgentDedupKey{}).(*subAgentDedup); ok {
				result, err = dedup.call(ctx, args.AgentID, args.Task, func() (string, error) {
					return spawnSubAgent(ctx, spawner, callerAgentID, args)
				})
			} else {
				result, err = spawnSubAgent(ctx, spawner, callerAgentID, args)
			}
			batch.Results[index] = spawnSubagentDelegationResult{AgentID: delegation.AgentID, Result: result}
			if err != nil {
				batch.Results[index].Error = err.Error()
			}
		}()
	}
	waitGroup.Wait()
	encoded, err := json.Marshal(batch)
	if err != nil {
		return "", fmt.Errorf("encode batch result: %w", err)
	}
	return string(encoded), nil
}

func (d *subAgentDedup) call(
	ctx context.Context,
	agentID string,
	task string,
	execute func() (string, error),
) (string, error) {
	key := agentID + "\x00" + task
	if d.targetOnly {
		key = agentID
	}
	d.mu.Lock()
	if existing := d.results[key]; existing != nil {
		d.mu.Unlock()
		select {
		case <-existing.done:
			return existing.result, existing.err
		case <-ctx.Done():
			return "", ctx.Err()
		}
	}
	entry := &subAgentResult{done: make(chan struct{})}
	d.results[key] = entry
	d.mu.Unlock()

	entry.result, entry.err = execute()
	close(entry.done)
	return entry.result, entry.err
}

func spawnSubAgent(
	ctx context.Context,
	spawner SubAgentSpawner,
	callerAgentID string,
	args spawnSubagentArgs,
) (string, error) {
	callID := fmt.Sprintf("%d-%d", time.Now().UnixNano(), atomic.AddUint64(&subAgentCallCounter, 1))
	msg := bus.InboundMessage{
		Channel:   "subagent",
		ChatID:    fmt.Sprintf("subagent-%s-%s-%s", callerAgentID, args.AgentID, callID),
		UserID:    callerAgentID,
		Text:      args.Task,
		MessageID: callID,
		PeerKind:  "dm",
		Source:    bus.SourceSubAgent,
	}
	result, err := spawner.SpawnSubAgent(ctx, args.AgentID, msg)
	if err != nil {
		return "", fmt.Errorf("spawn sub-agent %q: %w", args.AgentID, err)
	}
	return result, nil
}
