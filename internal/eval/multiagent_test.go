package eval

import (
	"context"
	"math"
	"path/filepath"
	"strings"
	"testing"
	"time"
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

func TestMultiAgentSuiteRejectsInvalidBaselineAndRuntimeFault(t *testing.T) {
	suite := incidentMultiAgentSuite()
	suite.Baselines = []string{"unknown"}
	if err := suite.Validate(); err == nil || !strings.Contains(err.Error(), "unsupported multi-agent baseline") {
		t.Fatalf("invalid baseline error = %v", err)
	}

	suite = incidentMultiAgentSuite()
	suite.Cases[0].ExecutionMode = "runtime"
	suite.Cases[0].Agents[0].Fault = &MultiAgentFault{
		Type:                 "error",
		Message:              "unavailable",
		ExpectedOutputValues: []string{"unavailable"},
	}
	if err := suite.Validate(); err == nil || !strings.Contains(err.Error(), "requires simulated") {
		t.Fatalf("runtime fault error = %v", err)
	}
}

func TestLoadBundledMultiAgentSuite(t *testing.T) {
	tests := []struct {
		file  string
		name  string
		cases int
	}{
		{"multiagent-collaboration-subset.yaml", "multiagentbench-style-collaboration-subset", 3},
		{"multiagent-runtime-tenant.yaml", "fastclaw-fixed-runtime-tenant", 8},
		{"multiagent-fault-injection.yaml", "multiagent-runtime-fault-injection", 6},
		{"multiagent-finance-workflow.yaml", "finance-research-workflow", 6},
	}
	for _, test := range tests {
		t.Run(test.file, func(t *testing.T) {
			path := filepath.Join("..", "..", "evals", test.file)
			suite, err := LoadMultiAgentSuite(path)
			if err != nil {
				t.Fatal(err)
			}
			if suite.Name != test.name || len(suite.Cases) != test.cases {
				t.Fatalf("unexpected suite: %s, cases = %d", suite.Name, len(suite.Cases))
			}
		})
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
		attempt.ModelCalls[0].Phase != MultiAgentBaselineSoloClosedBook ||
		attempt.ModelCalls[1].Phase != "team" {
		t.Fatalf("unexpected model calls: %+v", attempt.ModelCalls)
	}
}

func TestMultiAgentRunnerReportsFairBaselines(t *testing.T) {
	runner := MultiAgentRunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			switch {
			case strings.HasSuffix(request.SessionKey, "-"+MultiAgentBaselineSoloClosedBook):
				return ExecutionResponse{Output: "insufficient evidence"}, nil
			case strings.HasSuffix(request.SessionKey, "-"+MultiAgentBaselineSoloOpenBook):
				if !strings.Contains(request.Prompt, "Database latency remained normal") ||
					strings.Contains(request.Prompt, "metrics-agent") {
					t.Fatalf("unexpected open-book prompt: %s", request.Prompt)
				}
			case strings.HasSuffix(request.SessionKey, "-"+MultiAgentBaselineOracleTeam):
				if !strings.Contains(request.Prompt, "metrics-agent (metrics)") {
					t.Fatalf("unexpected oracle prompt: %s", request.Prompt)
				}
			case strings.HasSuffix(request.SessionKey, "-"+MultiAgentBaselineTeam):
				if len(request.Tools) != 1 {
					t.Fatalf("team tools = %d", len(request.Tools))
				}
				return ExecutionResponse{
					Output: successfulIncidentOutput(),
					Trace: []TraceEvent{
						delegationTrace("metrics-agent", "analyze metrics"),
						delegationTrace("logs-agent", "analyze logs"),
						delegationTrace("deploy-agent", "analyze deployment"),
					},
				}, nil
			default:
				t.Fatalf("unexpected baseline session %q", request.SessionKey)
			}
			return ExecutionResponse{Output: successfulIncidentOutput()}, nil
		}),
	}
	suite := incidentMultiAgentSuite()
	suite.Baselines = []string{
		MultiAgentBaselineSoloClosedBook,
		MultiAgentBaselineSoloOpenBook,
		MultiAgentBaselineTeam,
		MultiAgentBaselineOracleTeam,
	}

	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	attempt := report.Cases[0].Attempts[0]
	if len(attempt.Baselines) != 4 {
		t.Fatalf("baselines = %+v", attempt.Baselines)
	}
	metrics := report.Metrics
	if metrics.MASoloSuccessRate != 0 ||
		metrics.MASoloOpenBookSuccessRate != 1 ||
		metrics.MATeamSuccessRate != 1 ||
		metrics.MATeamOutcomeSuccessRate != 1 ||
		metrics.MAOracleTeamSuccessRate != 1 ||
		metrics.MACollaborationGain != 1 ||
		metrics.MAFairCollaborationGain != 0 {
		t.Fatalf("unexpected fair baseline metrics: %+v", metrics)
	}
}

func TestMultiAgentRunnerIsolatesBaselineTimeouts(t *testing.T) {
	runner := MultiAgentRunner{
		Executor: executorFunc(func(ctx context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			if strings.HasSuffix(request.SessionKey, "-"+MultiAgentBaselineSoloClosedBook) {
				<-ctx.Done()
				return ExecutionResponse{}, ctx.Err()
			}
			return ExecutionResponse{
				Output: successfulIncidentOutput(),
				Trace: []TraceEvent{
					delegationTrace("metrics-agent", "analyze metrics"),
					delegationTrace("logs-agent", "analyze logs"),
					delegationTrace("deploy-agent", "analyze deployment"),
				},
			}, nil
		}),
		Options: RunOptions{Timeout: 10 * time.Millisecond},
	}

	report, err := runner.Run(t.Context(), incidentMultiAgentSuite())
	if err != nil {
		t.Fatal(err)
	}
	attempt := report.Cases[0].Attempts[0]
	if !attempt.Passed || len(attempt.Baselines) != 2 {
		t.Fatalf("unexpected attempt after baseline timeout: %+v", attempt)
	}
	if !strings.Contains(attempt.Baselines[0].Error, context.DeadlineExceeded.Error()) ||
		!attempt.Baselines[1].Passed {
		t.Fatalf("unexpected baseline results: %+v", attempt.Baselines)
	}
}

func TestMultiAgentRunnerGradesFaultInjectionAndGracefulDegradation(t *testing.T) {
	runner := MultiAgentRunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			faults := request.Tools[0].Behavior.Faults
			if len(faults) != 1 ||
				faults[0].Value != "logs-agent" ||
				faults[0].Error != "specialist timed out" {
				t.Fatalf("unexpected tool faults: %+v", faults)
			}
			return ExecutionResponse{
				Output: "Build 842 triggered the incident. Database latency remained normal. " +
					"The logs specialist timed out, so the exact code defect is unknown. " +
					"Rollback to build 841.",
				Trace: []TraceEvent{
					delegationTraceWithID("call-1", "metrics-agent", "analyze metrics"),
					{Type: "tool_result", ID: "call-1", Name: "spawn_subagent", Result: "Database latency remained normal."},
					delegationTraceWithID("call-2", "logs-agent", "analyze logs"),
					{Type: "tool_result", ID: "call-2", Name: "spawn_subagent", Result: "specialist timed out"},
					delegationTraceWithID("call-3", "deploy-agent", "analyze deployment"),
					{Type: "tool_result", ID: "call-3", Name: "spawn_subagent", Result: "Rollback to build 841."},
				},
			}, nil
		}),
	}
	suite := incidentMultiAgentSuite()
	suite.Cases[0].SkipSolo = true
	suite.Cases[0].Agents[1].Fault = &MultiAgentFault{
		Type:                  "timeout",
		Delay:                 Duration(10 * time.Millisecond),
		Message:               "specialist timed out",
		ExpectedOutputValues:  []string{"logs specialist", "timed out", "unknown"},
		ForbiddenOutputValues: []string{"coupon validation", "nil pointer"},
	}
	suite.Cases[0].Milestones = []MultiAgentMilestone{
		{ID: "known-impact", Values: []string{"build 842", "database latency remained normal"}},
		{ID: "safe-action", Values: []string{"rollback", "build 841"}},
	}

	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	attempt := report.Cases[0].Attempts[0]
	if !attempt.Passed || !attempt.MultiAgent.GracefullyDegraded {
		t.Fatalf("unexpected fault attempt: %+v", attempt)
	}
	if attempt.MultiAgent.FaultsObserved != 1 ||
		attempt.MultiAgent.FaultsAttributed != 1 ||
		attempt.MultiAgent.UnsupportedClaims != 0 ||
		attempt.MultiAgent.ContributionsExpected != 2 {
		t.Fatalf("unexpected fault metrics: %+v", attempt.MultiAgent)
	}
	if report.Metrics.MAFaultInjectionRate != 1 ||
		report.Metrics.MAFaultAttributionRate != 1 ||
		report.Metrics.MAGracefulDegradationRate != 1 ||
		report.Metrics.MAUnsupportedClaimRate != 0 {
		t.Fatalf("unexpected aggregate fault metrics: %+v", report.Metrics)
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
	return delegationTraceWithID("", agentID, task)
}

func delegationTraceWithID(id, agentID, task string) TraceEvent {
	return TraceEvent{
		Type:      "tool_call",
		ID:        id,
		Name:      "spawn_subagent",
		Arguments: `{"agentId":"` + agentID + `","task":"` + task + `"}`,
	}
}

func successfulIncidentOutput() string {
	return `Build 842 introduced the coupon validation nil pointer.
Database latency remained normal. Rollback to build 841 immediately.`
}
