package tools

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"sync"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

type evidenceKey struct{}
type fact struct {
	Key         string `json:"key"`
	Content     string `json:"content"`
	Source      string `json:"source"`
	PublishedAt string `json:"publishedAt,omitempty"`
}
type evidenceEvent struct {
	fact
	Version    int       `json:"version"`
	Agent      string    `json:"agent"`
	ReceivedAt time.Time `json:"receivedAt"`
}
type evidenceInput struct {
	Agent   string `json:"agent"`
	Session string `json:"session"`
	Round   int    `json:"round"`
	Events  []int  `json:"eventVersions"`
}
type taskEvidence struct {
	reviewInputs map[string]int
	mu           sync.Mutex
	owner, root  string
	events       []evidenceEvent
	inputs       []evidenceInput
	results      map[string]reviewSource
	reviews      subAgentDedup
}

// StartTaskEvidence establishes a fresh scope only at an external turn.
func StartTaskEvidence(ctx context.Context, owner string, internal bool) context.Context {
	if internal || owner == "" {
		return ctx
	}
	root := bus.InternalExecutionIDFromContext(ctx)
	if root == "" {
		return ctx
	}
	return context.WithValue(ctx, evidenceKey{}, &taskEvidence{reviewInputs: make(map[string]int), owner: owner, root: root, results: make(map[string]reviewSource), reviews: subAgentDedup{results: make(map[string]*subAgentResult)}})
}
func evidenceFor(ctx context.Context) (*taskEvidence, ExecutionScope) {
	scope, _ := ExecutionScopeFromContext(ctx)
	state, _ := ctx.Value(evidenceKey{}).(*taskEvidence)
	if state == nil || state.owner != scope.UserID || state.root != bus.InternalExecutionIDFromContext(ctx) {
		return nil, scope
	}
	return state, scope
}
func WithEvidencePublisher(ctx context.Context, r *Registry) *Registry {
	state, _ := evidenceFor(ctx)
	if state == nil || len(bus.InternalCallPathFromContext(ctx)) < 2 {
		return r
	}
	out := r.Filter(func(string) bool { return true })
	out.Register("publish_evidence", "Share a sourced fact with the coordinator for this task.", map[string]any{
		"type": "object", "required": []string{"key", "content", "source"}, "properties": map[string]any{
			"key": map[string]string{"type": "string"}, "content": map[string]string{"type": "string"}, "source": map[string]string{"type": "string"}, "publishedAt": map[string]string{"type": "string", "format": "date-time"}},
	}, publishEvidence)
	return out
}
func publishEvidence(ctx context.Context, args json.RawMessage) (string, error) {
	state, scope := evidenceFor(ctx)
	path := bus.InternalCallPathFromContext(ctx)
	if state == nil || len(path) < 2 || path[len(path)-1] != scope.AgentID {
		return "", errors.New("missing delegated task")
	}
	var f fact
	if err := json.Unmarshal(args, &f); err != nil {
		return "", err
	}
	if strings.TrimSpace(f.Key) == "" || strings.TrimSpace(f.Content) == "" || strings.TrimSpace(f.Source) == "" {
		return "", errors.New("key, content and source are required")
	}
	if f.PublishedAt != "" {
		if _, err := time.Parse(time.RFC3339, f.PublishedAt); err != nil {
			return "", err
		}
	}
	state.mu.Lock()
	defer state.mu.Unlock()
	if err := ctx.Err(); err != nil {
		return "", err
	}
	for _, event := range state.events {
		if event.Agent == scope.AgentID && event.Key == f.Key {
			if event.fact != f {
				return "", errors.New("conflicting evidence key")
			}
			data, _ := json.Marshal(event)
			return string(data), nil
		}
	}
	event := evidenceEvent{f, len(state.events) + 2, scope.AgentID, time.Now().UTC()}
	state.events = append(state.events, event)
	data, _ := json.Marshal(event)
	return string(data), nil
}

// PrepareEvidenceInput adds the frozen summary before scrubbing, without writing evidence to session history.
func PrepareEvidenceInput(ctx context.Context, msgs []provider.Message) []provider.Message {
	state, _ := evidenceFor(ctx)
	if state == nil || len(bus.InternalCallPathFromContext(ctx)) > 1 || len(msgs) == 0 {
		return msgs
	}
	last := len(msgs) - 1
	if msgs[last].Role != "tool" {
		return msgs
	}
	state.mu.Lock()
	defer state.mu.Unlock()
	if len(state.events) == 0 {
		return msgs
	}
	data, _ := json.Marshal(map[string]any{"root": state.root, "cutoff": len(state.events) + 1, "evidence": state.events, "specialistInputs": state.inputs, "resultsForReview": state.results})
	out := append([]provider.Message(nil), msgs...)
	out[last].Content += "\nTask evidence:\n" + string(data)
	return out
}
func RecordEvidenceInput(ctx context.Context, msgs []provider.Message, round int) {
	state, scope := evidenceFor(ctx)
	if state == nil || len(bus.InternalCallPathFromContext(ctx)) < 2 {
		return
	}
	state.mu.Lock()
	defer state.mu.Unlock()
	input := evidenceInput{scope.AgentID, scope.SessionID, round, []int{}}
	for _, event := range state.events {
		data, _ := json.Marshal(event)
		for _, msg := range msgs {
			if (msg.Role == "tool" && msg.Name == "publish_evidence" && msg.Content == string(data)) || (msg.Role == "user" && state.reviewInputs[msg.Content] == event.Version) {
				input.Events = append(input.Events, event.Version)
				break
			}
		}
	}
	state.inputs = append(state.inputs, input)
}
