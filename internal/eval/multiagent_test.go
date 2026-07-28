package eval

import (
	"context"
	"math"
	"path/filepath"
	"testing"
)

func TestContainsAllFoldNormalizesFormatsAndAlternatives(t *testing.T) {
	output := "Restore the private ACL, disable `svc-report`, wait 4 minutes, and use a 10% canary for seven-day monitoring of handshake-failure-rate."
	values := []string{
		"restore private ACL",
		"disable svc-report",
		"four minutes",
		"10 percent canary || 10% canary",
		"seven days || 7 calendar days",
		"handshake failures || handshake failure rate",
	}
	if !containsAllFold(output, values) {
		t.Fatal("expected normalized alternatives to match")
	}
}

func TestSelectMultiAgentCases(t *testing.T) {
	cases := []MultiAgentCase{{ID: "one"}, {ID: "two"}}
	selected, err := selectMultiAgentCases(cases, []string{"two"})
	if err != nil {
		t.Fatal(err)
	}
	if len(selected) != 1 || selected[0].ID != "two" {
		t.Fatalf("selected = %+v", selected)
	}
	if _, err := selectMultiAgentCases(cases, []string{"missing"}); err == nil {
		t.Fatal("expected unknown case error")
	}
}

func TestLoadBundledMultiAgentSuite(t *testing.T) {
	path := filepath.Join("..", "..", "evals", "multiagent-collaboration-subset.yaml")
	suite, err := LoadMultiAgentSuite(path)
	if err != nil {
		t.Fatal(err)
	}
	if suite.Name != "multiagentbench-style-collaboration-subset" || len(suite.Cases) != 3 {
		t.Fatalf("unexpected suite: %s, cases = %d", suite.Name, len(suite.Cases))
	}
}

func TestMultiAgentRunnerScoresSoloTeamGainAndCoordination(t *testing.T) {
	var calls int
	runner := MultiAgentRunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			calls++
			if !request.IsolateTools {
				t.Fatal("request tools were not isolated")
			}
			switch calls {
			case 1:
				if len(request.Tools) != 0 {
					t.Fatalf("solo tools = %d", len(request.Tools))
				}
				return ExecutionResponse{
					Output: "There is not enough evidence to identify the root cause.",
					Model:  "fake-coordinator",
					Usage:  Usage{PromptTokens: 40, CompletionTokens: 10, TotalTokens: 50},
					ModelCalls: []ModelCallUsage{{
						AgentID:          "coordinator",
						Role:             "coordinator",
						Model:            "fake-coordinator",
						TotalTokens:      50,
						EstimatedCostUSD: 0.001,
						Priced:           true,
						LatencyMS:        100,
					}},
				}, nil
			case 2:
				if len(request.Tools) != 1 || request.Tools[0].Name != "spawn_subagent" {
					t.Fatalf("unexpected team tools: %+v", request.Tools)
				}
				responses := request.State["responses"].(map[string]any)
				if len(responses) != 3 {
					t.Fatalf("specialist responses = %d", len(responses))
				}
				return ExecutionResponse{
					Output: `Build 842 introduced the coupon validation nil pointer.
Database latency remained normal. Rollback to build 841 immediately.`,
					Model: "fake-coordinator",
					Usage: Usage{PromptTokens: 160, CompletionTokens: 40, TotalTokens: 200},
					ModelCalls: []ModelCallUsage{
						{
							AgentID:          "coordinator",
							Role:             "coordinator",
							Model:            "fake-coordinator",
							TotalTokens:      80,
							EstimatedCostUSD: 0.002,
							Priced:           true,
							LatencyMS:        200,
						},
						{
							AgentID:          "metrics-agent",
							Role:             "subagent",
							Model:            "fake-specialist",
							TotalTokens:      40,
							EstimatedCostUSD: 0.0004,
							Priced:           true,
							LatencyMS:        50,
						},
						{
							AgentID:          "logs-agent",
							Role:             "subagent",
							Model:            "fake-specialist",
							TotalTokens:      40,
							EstimatedCostUSD: 0.0004,
							Priced:           true,
							LatencyMS:        60,
						},
						{
							AgentID:          "deploy-agent",
							Role:             "subagent",
							Model:            "fake-specialist",
							TotalTokens:      40,
							EstimatedCostUSD: 0.0004,
							Priced:           true,
							LatencyMS:        70,
						},
					},
					Trace: []TraceEvent{
						delegationTrace("metrics-agent", "analyze metrics"),
						delegationTrace("logs-agent", "analyze logs"),
						delegationTrace("deploy-agent", "analyze deployment"),
					},
				}, nil
			default:
				t.Fatalf("unexpected executor call %d", calls)
				return ExecutionResponse{}, nil
			}
		}),
	}
	suite := incidentMultiAgentSuite()

	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	attempt := report.Cases[0].Attempts[0]
	if !attempt.Passed || attempt.MultiAgent == nil || attempt.MultiAgent.SoloPassed {
		t.Fatalf("unexpected attempt: %+v", attempt)
	}
	if attempt.MultiAgent.CoordinationScore != 1 ||
		attempt.MultiAgent.PassedMilestones != 3 {
		t.Fatalf("unexpected attempt metrics: %+v", attempt.MultiAgent)
	}
	metrics := report.Metrics
	if metrics.MATeamSuccessRate != 1 ||
		metrics.MASoloSuccessRate != 0 ||
		metrics.MACollaborationGain != 1 {
		t.Fatalf("unexpected team/solo metrics: %+v", metrics)
	}
	if metrics.MAMilestoneKPI != 1 ||
		metrics.MACoordinationScore != 1 ||
		metrics.MAAverageDelegations != 3 {
		t.Fatalf("unexpected coordination metrics: %+v", metrics)
	}
	if metrics.MACoordinatorTokens != 80 ||
		metrics.MASubAgentTokens != 120 ||
		math.Abs(metrics.MATeamEstimatedCostUSD-0.0032) > 1e-12 ||
		math.Abs(metrics.MASoloEstimatedCostUSD-0.001) > 1e-12 ||
		math.Abs(metrics.MACostPerSuccessfulRunUSD-0.0032) > 1e-12 ||
		metrics.MACoordinatorLatencyMS != 200 ||
		metrics.MASubAgentLatencyMS != 180 ||
		metrics.MAPricingCoverage != 1 {
		t.Fatalf("unexpected usage metrics: %+v", metrics)
	}
	if len(attempt.ModelCalls) != 5 ||
		attempt.ModelCalls[0].Phase != "solo" ||
		attempt.ModelCalls[1].Phase != "team" {
		t.Fatalf("unexpected model calls: %+v", attempt.ModelCalls)
	}
}

func TestMultiAgentRunnerPenalizesDuplicateDelegation(t *testing.T) {
	runner := MultiAgentRunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			return ExecutionResponse{
				Output: `Build 842 introduced the coupon validation nil pointer.
Database latency remained normal. Rollback to build 841 immediately.`,
				Trace: []TraceEvent{
					delegationTrace("metrics-agent", "analyze metrics"),
					delegationTrace("metrics-agent", "repeat metrics"),
					delegationTrace("logs-agent", "analyze logs"),
					delegationTrace("deploy-agent", "analyze deployment"),
				},
			}, nil
		}),
	}
	suite := incidentMultiAgentSuite()
	suite.Cases[0].SkipSolo = true

	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	attempt := report.Cases[0].Attempts[0]
	if attempt.Passed {
		t.Fatalf("duplicate delegation unexpectedly passed: %+v", attempt)
	}
	if attempt.MultiAgent.DelegationPrecision != 0.75 ||
		attempt.MultiAgent.DelegationRecall != 1 {
		t.Fatalf("unexpected delegation metrics: %+v", attempt.MultiAgent)
	}
	if report.Metrics.MATeamSuccessRate != 0 ||
		report.Metrics.MADelegationPrecision != 0.75 {
		t.Fatalf("unexpected report metrics: %+v", report.Metrics)
	}
}

func TestMultiAgentRunnerRuntimeModeUsesGatewayAgentTools(t *testing.T) {
	runner := MultiAgentRunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			if request.IsolateTools || len(request.Tools) != 0 || request.State != nil {
				t.Fatalf("runtime request unexpectedly replaced agent tools: %+v", request)
			}
			return ExecutionResponse{
				Output: `Build 842 introduced the coupon validation nil pointer.
Database latency remained normal. Rollback to build 841 immediately.`,
				Trace: []TraceEvent{
					delegationTrace("metrics-agent", "analyze metrics"),
					delegationTrace("logs-agent", "analyze logs"),
					delegationTrace("deploy-agent", "analyze deployment"),
				},
			}, nil
		}),
	}
	suite := incidentMultiAgentSuite()
	suite.Cases[0].SkipSolo = true
	suite.Cases[0].ExecutionMode = "runtime"
	for index := range suite.Cases[0].Agents {
		suite.Cases[0].Agents[index].Response = ""
	}

	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	if !report.Cases[0].PassAt1 || report.Metrics.MATeamSuccessRate != 1 {
		t.Fatalf("unexpected runtime report: %+v", report)
	}
}

func incidentMultiAgentSuite() MultiAgentSuite {
	return MultiAgentSuite{
		Version: SuiteVersion,
		Name:    "incident-team",
		Cases: []MultiAgentCase{
			{
				ID:             "incident",
				Prompt:         "Find the root cause and remediation.",
				MaxDelegations: 3,
				Agents: []MultiAgentCollaborator{
					{
						ID:                 "metrics-agent",
						Role:               "metrics",
						Response:           "Database latency remained normal.",
						ContributionValues: []string{"database latency remained normal"},
					},
					{
						ID:                 "logs-agent",
						Role:               "logs",
						Response:           "Coupon validation nil pointer.",
						ContributionValues: []string{"nil pointer", "coupon validation"},
					},
					{
						ID:                 "deploy-agent",
						Role:               "deployments",
						Response:           "Build 842 can roll back to build 841.",
						ContributionValues: []string{"build 841"},
					},
				},
				Milestones: []MultiAgentMilestone{
					{ID: "root", Values: []string{"build 842", "coupon validation"}},
					{ID: "evidence", Values: []string{"database latency remained normal", "nil pointer"}},
					{ID: "action", Values: []string{"rollback", "build 841"}},
				},
			},
		},
	}
}

func delegationTrace(agentID, task string) TraceEvent {
	return TraceEvent{
		Type:      "tool_call",
		Name:      "spawn_subagent",
		Arguments: `{"agentId":"` + agentID + `","task":"` + task + `"}`,
	}
}
