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
	AgentID string `json:"agentId"`
	Task    string `json:"task"`
}

var subAgentCallCounter uint64

type subAgentDedupKey struct{}

type subAgentResult struct {
	done   chan struct{}
	result string
	err    error
}

type subAgentDedup struct {
	mu      sync.Mutex
	results map[string]*subAgentResult
}

// ContextWithSubAgentDedup scopes sub-agent calls so each target executes at
// most once during a parent turn. Repeated calls reuse the first result.
func ContextWithSubAgentDedup(ctx context.Context) context.Context {
	if ctx == nil {
		ctx = context.Background()
	}
	return context.WithValue(ctx, subAgentDedupKey{}, &subAgentDedup{
		results: make(map[string]*subAgentResult),
	})
}

// RegisterSubAgent registers the spawn_subagent tool.
func RegisterSubAgent(r *Registry, spawner SubAgentSpawner, callerAgentID string) {
	r.Register("spawn_subagent", "Delegate to a specialized agent and return its response. Call each target agent at most once per parent turn; repeated calls reuse the first result.", map[string]interface{}{
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
		},
		"required": []string{"agentId", "task"},
	}, makeSubAgentTool(spawner, callerAgentID))
}

func makeSubAgentTool(spawner SubAgentSpawner, callerAgentID string) ToolFunc {
	return func(ctx context.Context, rawArgs json.RawMessage) (string, error) {
		var args spawnSubagentArgs
		if err := json.Unmarshal(rawArgs, &args); err != nil {
			return "", fmt.Errorf("parse args: %w", err)
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
			return dedup.call(ctx, args.AgentID, func() (string, error) {
				return spawnSubAgent(ctx, spawner, callerAgentID, args)
			})
		}
		return spawnSubAgent(ctx, spawner, callerAgentID, args)
	}
}

func (d *subAgentDedup) call(
	ctx context.Context,
	agentID string,
	execute func() (string, error),
) (string, error) {
	d.mu.Lock()
	if existing := d.results[agentID]; existing != nil {
		d.mu.Unlock()
		select {
		case <-existing.done:
			return existing.result, existing.err
		case <-ctx.Done():
			return "", ctx.Err()
		}
	}
	entry := &subAgentResult{done: make(chan struct{})}
	d.results[agentID] = entry
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
