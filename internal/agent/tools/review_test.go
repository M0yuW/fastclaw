package tools

import (
	"context"
	"encoding/json"
	"strings"
	"testing"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
)

func TestReviewOnlySelectedClaim(t *testing.T) {
	for _, status := range []string{"unchanged", "revised", "pending"} {
		t.Run(status, func(t *testing.T) {
			ctx := ContextWithExecutionScope(bus.ContextWithInternalExecution(context.Background(), "root"), ExecutionScope{UserID: "owner", AgentID: "coord"})
			ctx = StartTaskEvidence(ContextWithSubAgentDedup(ctx), "owner", false)
			const claim = "NVIDIA transition risk is low"
			spawner := &fakeSubAgentSpawner{result: claim}
			tool := makeSubAgentTool(spawner, "coord")
			if _, err := tool(ctx, []byte(`{"agentId":"risk","task":"assess"}`)); err != nil {
				t.Fatal(err)
			}
			originalID := spawner.messages[0].ChatID
			spawner.result = "last quarter revenue 100"
			if _, err := tool(ctx, []byte(`{"agentId":"accounts","task":"assess"}`)); err != nil {
				t.Fatal(err)
			}
			child := ContextWithExecutionScope(bus.ContextWithInternalCallPath(ctx, []string{"coord", "risk"}), ExecutionScope{UserID: "owner", AgentID: "risk"})
			if _, err := publishEvidence(child, []byte(`{"key":"E","content":"new management announcement","source":"fixture"}`)); err != nil {
				t.Fatal(err)
			}
			conclusion := claim
			if status == "revised" {
				conclusion = "risk increased"
			}
			reply, _ := json.Marshal(reviewDecision{status, conclusion, "assessed the announcement"})
			spawner.result = string(reply)
			if status == "pending" {
				spawner.result = "incomplete response"
			}
			req, _ := json.Marshal(map[string]any{"review": reviewRequest{originalID, claim, "next quarter", 2}})
			for i := 0; i < 2; i++ {
				result, err := tool(ctx, req)
				if err != nil {
					t.Fatal(err)
				}
				var out struct {
					Decision reviewDecision
					Review   reviewRequest
				}
				if err := json.Unmarshal([]byte(result), &out); err != nil || out.Decision.Status != status || out.Review.ResultID != originalID {
					t.Fatal(result)
				}
			}
			if len(spawner.messages) != 3 || !strings.Contains(spawner.messages[2].ChatID, "-risk-") || !strings.Contains(spawner.messages[2].Text, "new management announcement") {
				t.Fatal(spawner.messages)
			}
			state, _ := evidenceFor(ctx)
			if state.results[originalID].Result != claim || len(state.results) != 2 {
				t.Fatal(state.results)
			}
		})
	}
}
