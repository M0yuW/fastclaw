package tools

import (
	"context"
	"encoding/json"
	"errors"
	"strings"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
)

type reviewSource struct {
	Agent  string `json:"agent"`
	Result string `json:"result"`
}
type reviewRequest struct {
	ResultID string `json:"resultId"`
	Claim    string `json:"claim"`
	Period   string `json:"period"`
	Event    int    `json:"eventVersion"`
}
type reviewDecision struct {
	Status     string `json:"status"`
	Conclusion string `json:"conclusion"`
	Reason     string `json:"reason"`
}

func reviewSchema() map[string]any {
	return map[string]any{
		"type":        "object",
		"description": "Recheck a quoted claim from resultsForReview against one published event. Submit review alone.",
		"required":    []string{"resultId", "claim", "period", "eventVersion"},
		"properties": map[string]any{
			"resultId":     map[string]string{"type": "string"},
			"claim":        map[string]string{"type": "string"},
			"period":       map[string]string{"type": "string"},
			"eventVersion": map[string]string{"type": "integer"},
		},
	}
}

const reviewInstructions = "Review the quoted claim for the specified period using the supplied evidence. Return only JSON with status (unchanged, revised, or pending), conclusion and reason. For unchanged repeat the original claim exactly.\n"

func parseReview(raw, claim string) reviewDecision {
	var reply reviewDecision
	if json.Unmarshal([]byte(raw), &reply) == nil && strings.TrimSpace(reply.Reason) != "" {
		switch reply.Status {
		case "pending":
			return reply
		case "unchanged":
			if reply.Conclusion == claim {
				return reply
			}
		case "revised":
			if strings.TrimSpace(reply.Conclusion) != "" && reply.Conclusion != claim {
				return reply
			}
		}
	}
	return reviewDecision{Status: "pending", Reason: "Invalid specialist review response"}
}

func runReview(ctx context.Context, spawner SubAgentSpawner, caller string, req reviewRequest) (string, error) {
	state, _ := evidenceFor(ctx)
	if state == nil || len(bus.InternalCallPathFromContext(ctx)) > 1 {
		return "", errors.New("review requires a coordinator task")
	}
	state.mu.Lock()
	source, ok := state.results[req.ResultID]
	if !ok || strings.TrimSpace(req.Claim) == "" || !strings.Contains(source.Result, req.Claim) || strings.TrimSpace(req.Period) == "" || req.Event < 2 || req.Event-2 >= len(state.events) {
		state.mu.Unlock()
		return "", errors.New("unknown original result, claim, period or event")
	}
	event := state.events[req.Event-2]
	state.mu.Unlock()
	key, _ := json.Marshal(req)
	return state.reviews.call(ctx, source.Agent, string(key), func() (string, error) {
		decision := reviewDecision{Status: "pending"}
		packet, _ := json.Marshal(map[string]any{"review": req, "evidence": event})
		task := reviewInstructions + string(packet)
		state.mu.Lock()
		state.reviewInputs[task] = event.Version
		state.mu.Unlock()
		raw, err := spawnSubAgent(ctx, spawner, caller, spawnSubagentArgs{AgentID: source.Agent, Task: task, Review: &req})
		if err == nil {
			decision = parseReview(raw, req.Claim)
		}
		if err != nil {
			decision.Reason = err.Error()
		}
		encoded, _ := json.Marshal(map[string]any{"review": req, "agent": source.Agent, "decision": decision})
		return string(encoded), nil
	})
}
