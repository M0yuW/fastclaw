package tools

import (
	"context"
	"encoding/json"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

type policyCase struct{ name, event, affected, corrected string }
type fixtureCall struct{ agent, input, output string }
type strategySpecialists struct {
	scenario         policyCase
	initial          map[string]string
	armed, published chan struct{}
	mu               sync.Mutex
	calls            []fixtureCall
}

func (s *strategySpecialists) SpawnSubAgent(ctx context.Context, agent string, msg bus.InboundMessage) (string, error) {
	answer := s.initial[agent]
	if msg.Text == "initial" {
		if agent == "risk" {
			close(s.armed)
			select {
			case <-s.published:
			case <-ctx.Done():
				return "", ctx.Err()
			}
		} else {
			select {
			case <-s.armed:
			case <-ctx.Done():
				return "", ctx.Err()
			}
			defer close(s.published)
			if s.scenario.event != "" {
				child := ContextWithExecutionScope(bus.ContextWithInternalCallPath(ctx, []string{"coord", agent}), ExecutionScope{UserID: "owner", AgentID: agent})
				data, _ := json.Marshal(fact{Key: s.scenario.name, Content: s.scenario.event, Source: "fixture"})
				if _, err := publishEvidence(child, data); err != nil {
					return "", err
				}
			}
		}
	} else {
		if agent == s.scenario.affected && strings.Contains(msg.Text, s.scenario.event) {
			answer = s.scenario.corrected
		}
		if strings.HasPrefix(msg.Text, reviewInstructions) {
			b, _ := json.Marshal(reviewDecision{"revised", answer, s.scenario.event})
			answer = string(b)
		}
	}
	s.mu.Lock()
	s.calls = append(s.calls, fixtureCall{agent, msg.Text, answer})
	s.mu.Unlock()
	return answer, nil
}

type policyMetrics struct {
	Stale, Missed, Unrelated, ExtraCalls, Traceable, FixtureTokens int
	ElapsedUs                                                      int64
}

func TestEvidenceStrategyComparison(t *testing.T) {
	cases := []policyCase{{"none", "", "", ""}, {"irrelevant", "office opens", "", ""}, {"risk", "leadership changed", "risk", "high"}, {"correction", "corrected revenue is 90", "income", "90"}}
	for _, policy := range []string{"summary", "targeted", "rerun"} {
		t.Run(policy, func(t *testing.T) {
			m := policyMetrics{}
			for _, c := range cases {
				started := time.Now()
				ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
				ctx = StartTaskEvidence(ContextWithExecutionScope(bus.ContextWithInternalExecution(ctx, c.name), ExecutionScope{UserID: "owner", AgentID: "coord"}), "owner", false)

				s := &strategySpecialists{scenario: c, initial: map[string]string{"risk": "low", "income": "100"}, armed: make(chan struct{}), published: make(chan struct{})}
				tool := makeSubAgentTool(s, "coord")
				batch := func(task string) map[string]string {
					args, _ := json.Marshal(spawnSubagentArgs{Delegations: []spawnSubagentDelegation{{"risk", task}, {"income", task}}})
					raw, err := tool(ctx, args)
					if err != nil {
						t.Fatal(err)
					}
					var replies spawnSubagentBatchResult
					if err = json.Unmarshal([]byte(raw), &replies); err != nil {
						t.Fatal(err)
					}
					claims := map[string]string{}
					for _, r := range replies.Results {
						if r.Status != "success" {
							t.Fatal(r)
						}
						claims[r.AgentID] = r.Result
					}
					return claims
				}
				final := batch("initial")
				if _, err := configureDelivery(ctx, deliveryOptions{Mode: "seal"}); err != nil {
					t.Fatal(err)
				}
				raw, _ := json.Marshal(final)
				summary := PrepareEvidenceInput(ctx, []provider.Message{{Role: "tool", Content: string(raw)}})[0].Content
				_, payload, ok := strings.Cut(summary, "\nTask evidence:\n")
				var snapshot struct {
					Evidence         []evidenceEvent
					ResultsForReview map[string]reviewSource
				}
				event := ""
				if ok {
					if err := json.Unmarshal([]byte(payload), &snapshot); err != nil {
						t.Fatal(err)
					}
					event = snapshot.Evidence[0].Content
				}
				switch {
				case event != "" && policy == "rerun":
					final = batch("Recompute with " + event)
				case event != "" && policy == "targeted" && c.affected != "":
					id := ""
					for k, v := range snapshot.ResultsForReview {
						if v.Agent == c.affected {
							id = k
						}
					}
					args, _ := json.Marshal(spawnSubagentArgs{Review: &reviewRequest{id, final[c.affected], "fixture period", 2}})
					raw, err := tool(ctx, args)
					if err != nil {
						t.Fatal(err)
					}
					var out struct{ Decision reviewDecision }
					if err = json.Unmarshal([]byte(raw), &out); err != nil {
						t.Fatal(err)
					}
					final[c.affected] = out.Decision.Conclusion
				case strings.HasPrefix(event, "corrected revenue"):
					final["income"] = strings.TrimPrefix(event, "corrected revenue is ")
				}
				output, _ := json.Marshal(map[string]any{"claims": final, "citedEvent": event})
				m.FixtureTokens += len(summary) + len(output)
				if c.affected != "" && !strings.Contains(string(output), c.event) {
					m.Missed++
				}
				for agent, value := range final {
					expected := s.initial[agent]
					if agent == c.affected {
						expected = c.corrected
					}
					if value != expected {
						m.Stale++
					}
					traced := false
					for _, call := range s.calls {
						if call.agent != agent {
							continue
						}
						if call.input != "initial" {
							m.ExtraCalls++
							if agent != c.affected {
								m.Unrelated++
							}
						}
						m.FixtureTokens += len(call.input) + len(call.output)
						var d reviewDecision
						if call.output == value || json.Unmarshal([]byte(call.output), &d) == nil && d.Conclusion == value {
							traced = true
						}
					}
					if traced || agent == "income" && event == "corrected revenue is "+value {
						m.Traceable++
					}
				}
				m.ElapsedUs += time.Since(started).Microseconds()
				cancel()
			}
			wantStale := 0
			if policy == "summary" {
				wantStale = 1
			}
			if m.Stale != wantStale || m.Missed != 0 || m.ExtraCalls != map[string]int{"summary": 0, "targeted": 2, "rerun": 6}[policy] || m.Unrelated != map[string]int{"rerun": 4}[policy] || m.Traceable != 8 {
				t.Fatal(m)
			}
			t.Logf("%+v", m)
		})
	}
}
