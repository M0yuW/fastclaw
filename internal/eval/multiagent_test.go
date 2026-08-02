package eval

import (
	"bytes"
	"context"
	"math"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestContainsAllFoldNormalizesFormatsAndAlternatives(t *testing.T) {
	output := "Restore the private ACL, disable `svc-report`, wait 4 minutes, use a 10% canary, record PE = 14, conviction 3 → 4, correlation of 0.89, and a loss > 25%, and retain the original ¥8-billion-yuan plan for seven-day monitoring of handshake-failure-rate."
	values := []string{
		"restore private ACL",
		"disable svc-report",
		"four minutes",
		"10 percent canary || 10% canary",
		"PE 14",
		"conviction 3 to 4",
		"correlation 0.89",
		"above 25 percent",
		"original 8 billion yuan",
		"seven days || 7 calendar days",
		"handshake failures || handshake failure rate",
	}
	if !containsAllFold(output, values) {
		t.Fatal("expected normalized alternatives to match")
	}
}

func TestContainsAllInOrderFoldAllowsBoundedParaphraseGaps(t *testing.T) {
	output := "FIL-601 reports capex guidance was reduced from 8 billion yuan to 5 billion yuan and margins expanded by 220 basis points."
	values := []string{
		"FIL-601",
		"reduced from 8 billion to 5 billion yuan",
		"220 basis points",
	}
	if !containsAllInOrderFold(output, values) {
		t.Fatal("expected ordered contribution facts to match across inserted units")
	}
	if containsAllInOrderFold("FIL-601 increased from 5 billion to 8 billion yuan.", values) {
		t.Fatal("reversed facts must not match")
	}
	if !containsAllInOrderFold(
		"EVT-301 confirms SSE-688981-77 inside the 24-hour concurrence window.",
		[]string{"EVT-301", "SSE-688981-77", "24-hour window"},
	) {
		t.Fatal("expected inserted event-window qualifier to match")
	}
	if containsAllInOrderFold(
		"staged plan was rejected one two three four five six seven eight nine rebalance nothing below 45 percent",
		[]string{"staged rebalance below 45 percent"},
	) {
		t.Fatal("unbounded cross-claim token gaps must not match")
	}
}

func TestEvidenceAwarePromptsRequireAuditableTerms(t *testing.T) {
	evalCase := MultiAgentCase{
		Prompt: "Review the evidence.",
		Agents: []MultiAgentCollaborator{{
			ID:       "filing-agent",
			Role:     "extract filing facts",
			Response: "FIL-101: revenue grew 18 percent.",
		}},
	}
	for name, prompt := range map[string]string{
		"solo_open_book": multiAgentOpenBookPrompt(evalCase),
		"solo_two_pass":  multiAgentTwoPassAnalysisPrompt(evalCase),
		"solo_synthesis": multiAgentTwoPassSynthesisPrompt(),
		"team":           multiAgentTeamPrompt(evalCase),
		"oracle_team":    multiAgentOracleTeamPrompt(evalCase),
	} {
		normalizedPrompt := strings.Join(strings.Fields(prompt), " ")
		if !strings.Contains(normalizedPrompt, "Preserve every evidence ID") {
			t.Fatalf("%s prompt does not require auditable evidence terms: %q", name, prompt)
		}
		if name == "solo_synthesis" && !strings.Contains(normalizedPrompt, "final answer must be self-contained") {
			t.Fatalf("two-pass synthesis is not self-contained: %q", prompt)
		}
	}
}

func TestMultiAgentRunnerReportsComputeMatchedBaseline(t *testing.T) {
	twoPassCalls := 0
	runner := MultiAgentRunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			if strings.HasSuffix(request.SessionKey, "-"+MultiAgentBaselineSoloTwoPass) {
				twoPassCalls++
				if twoPassCalls == 1 && !strings.Contains(request.Prompt, "first of two compute-matched passes") {
					t.Fatalf("unexpected analysis prompt: %s", request.Prompt)
				}
				if twoPassCalls == 2 && !strings.Contains(request.Prompt, "previous pass") {
					t.Fatalf("unexpected synthesis prompt: %s", request.Prompt)
				}
				output := "analysis only"
				if twoPassCalls == 2 {
					output = successfulIncidentOutput()
				}
				return ExecutionResponse{
					Output: output,
					Usage:  Usage{TotalTokens: 10},
					ModelCalls: []ModelCallUsage{{
						AgentID:          "coordinator",
						Role:             "coordinator",
						TotalTokens:      10,
						EstimatedCostUSD: 0.1,
						Priced:           true,
					}},
				}, nil
			}
			if strings.HasSuffix(request.SessionKey, "-"+MultiAgentBaselineTeam) {
				return ExecutionResponse{
					Output: successfulIncidentOutput(),
					Trace: []TraceEvent{
						delegationTrace("metrics-agent", "analyze metrics"),
						delegationTrace("logs-agent", "analyze logs"),
						delegationTrace("deploy-agent", "analyze deployment"),
					},
				}, nil
			}
			t.Fatalf("unexpected baseline session %q", request.SessionKey)
			return ExecutionResponse{}, nil
		}),
	}
	suite := incidentMultiAgentSuite()
	suite.Baselines = []string{
		MultiAgentBaselineSoloTwoPass,
		MultiAgentBaselineTeam,
	}
	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	if twoPassCalls != 2 {
		t.Fatalf("solo two-pass calls = %d", twoPassCalls)
	}
	attempt := report.Cases[0].Attempts[0]
	twoPass := attempt.Baselines[0]
	if !twoPass.Passed ||
		twoPass.Usage.TotalTokens != 20 ||
		len(twoPass.ModelCalls) != 2 ||
		twoPass.ModelCalls[0].Phase != MultiAgentBaselineSoloTwoPass ||
		twoPass.ModelCalls[1].Phase != MultiAgentBaselineSoloTwoPass {
		t.Fatalf("unexpected solo two-pass result: %+v", twoPass)
	}
	metrics := report.Metrics
	if metrics.MASoloTwoPassEvaluated != 1 ||
		metrics.MASoloTwoPassSuccessRate != 1 ||
		metrics.MAComputeMatchedGain != 0 ||
		!metrics.MAComputeMatchedGainValid ||
		math.Abs(metrics.MASoloTwoPassCostUSD-0.2) > 1e-12 {
		t.Fatalf("unexpected compute-matched metrics: %+v", metrics)
	}
}

func TestMultiAgentGroundingAppliesToTeamAndBaselines(t *testing.T) {
	runner := MultiAgentRunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			response := ExecutionResponse{
				Output: successfulIncidentOutput() + " The filing has higher evidentiary weight.",
			}
			if strings.HasSuffix(request.SessionKey, "-"+MultiAgentBaselineTeam) {
				response.Trace = []TraceEvent{
					delegationTrace("metrics-agent", "analyze metrics"),
					delegationTrace("logs-agent", "analyze logs"),
					delegationTrace("deploy-agent", "analyze deployment"),
				}
			}
			return response, nil
		}),
	}
	suite := incidentMultiAgentSuite()
	suite.Baselines = []string{
		MultiAgentBaselineSoloOpenBook,
		MultiAgentBaselineTeam,
	}
	suite.Cases[0].ForbiddenOutputValues = []string{"higher evidentiary weight"}
	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	attempt := report.Cases[0].Attempts[0]
	if attempt.Passed ||
		attempt.Baselines[0].Passed ||
		attempt.Baselines[1].Passed ||
		attempt.MultiAgent.GroundingAssertions != 1 ||
		attempt.MultiAgent.GroundingViolations != 1 {
		t.Fatalf("grounding violation did not fail outcomes: %+v", attempt)
	}
	foundGroundingGrader := false
	for _, grader := range attempt.Graders {
		if grader.Type == "ma_grounding" {
			foundGroundingGrader = true
			if grader.Passed || grader.Message != "grounding violations 1/1" {
				t.Fatalf("unexpected grounding grader: %+v", grader)
			}
		}
	}
	if !foundGroundingGrader ||
		report.Metrics.MAGroundingAssertions != 1 ||
		report.Metrics.MAGroundingViolations != 1 ||
		report.Metrics.MAGroundingAccuracy != 0 {
		t.Fatalf("unexpected grounding metrics: %+v", report.Metrics)
	}
	for _, mode := range []string{MultiAgentBaselineSoloOpenBook, MultiAgentBaselineTeam} {
		baseline := report.Metrics.MABaselines[mode]
		if baseline.GroundingAssertions != 1 ||
			baseline.GroundingViolations != 1 ||
			baseline.GroundingAccuracy != 0 {
			t.Fatalf("%s grounding metrics = %+v", mode, baseline)
		}
	}
}

func TestNumericGroundingRejectsUndeclaredDerivedValues(t *testing.T) {
	output := "In 2023, external revenue was 953 of 18,910, or 0.05039 before rounding to 5.0 percent. " +
		"Operating margin was -36.8 percent."
	assertions, violations := evaluateNumericGrounding(output, []string{"2023", "953", "18910", "5.0"})
	if assertions != 6 || violations != 2 {
		t.Fatalf("numeric grounding = %d assertions, %d violations", assertions, violations)
	}
	if multiAgentOutcomePass(output, MultiAgentCase{
		AuthorizedNumericValues: []string{"2023", "953", "18910", "5.0"},
	}) {
		t.Fatal("output with undeclared calculations passed")
	}
}

func TestNumericGroundingUnderstandsNegativeFinancialLanguage(t *testing.T) {
	for _, output := range []string{
		"NIKE Brand Digital declined 10 percent.",
		"NIKE Brand Digital reported a 10 percent decline.",
		"Intel Foundry reported an operating loss of USD 6,955 million.",
		"Intel Foundry operating income was USD (6,955) million.",
		"A revenue increase did not offset the 20.4-point gross-margin decline.",
	} {
		authorized := []string{"-10"}
		if strings.Contains(output, "6,955") {
			authorized = []string{"-6955"}
		} else if strings.Contains(output, "20.4") {
			authorized = []string{"-20.4"}
		}
		assertions, violations := evaluateNumericGrounding(output, authorized)
		if assertions != 1 || violations != 0 {
			t.Fatalf("%q = %d assertions, %d violations", output, assertions, violations)
		}
	}
}

func TestNumericGroundingUnderstandsFinancialUnitSuffixes(t *testing.T) {
	output := "Gross margin changed -3.3pp and increased 110bps in the comparison table."
	assertions, violations := evaluateNumericGrounding(output, []string{"-3.3", "110"})
	if assertions != 2 || violations != 0 {
		t.Fatalf("numeric grounding = %d assertions, %d violations", assertions, violations)
	}
}

func TestRequiredAssertionsNormalizeUnicodeMinus(t *testing.T) {
	if !containsRequiredAssertion("Gross margin changed −3.3 percentage points.", "-3.3 percentage points") {
		t.Fatal("unicode minus assertion did not match")
	}
}

func TestNumericGroundingUnderstandsCoordinatedDeclines(t *testing.T) {
	output := "Gross margin declined first by 1.1 pp then by 3.3 pp."
	assertions, violations := evaluateNumericGrounding(output, []string{"-1.1", "-3.3"})
	if assertions != 2 || violations != 0 {
		t.Fatalf("numeric grounding = %d assertions, %d violations", assertions, violations)
	}
}

func TestNumericGroundingIgnoresOrderedListMarkers(t *testing.T) {
	output := "1. Revenue was 10.\n2) Gross margin was 20 percent."
	assertions, violations := evaluateNumericGrounding(output, []string{"10", "20"})
	if assertions != 2 || violations != 0 {
		t.Fatalf("numeric grounding = %d assertions, %d violations", assertions, violations)
	}
}

func TestNumericGroundingIgnoresMarkdownSectionNumbers(t *testing.T) {
	output := "## 3.1 Calculation Audit\nRevenue was 100."
	assertions, violations := evaluateNumericGrounding(output, []string{"100"})
	if assertions != 1 || violations != 0 {
		t.Fatalf("numeric grounding = %d assertions, %d violations", assertions, violations)
	}
}

func TestNumericGroundingDoesNotTreatDescriptiveParenthesesAsNegative(t *testing.T) {
	output := "Foundry revenue (2023) was 18,910. NVDA-Q1-DC (22,600) divided by NVDA-Q1-REV (26,044)."
	assertions, violations := evaluateNumericGrounding(output, []string{"2023", "18910", "22600", "26044"})
	if assertions != 4 || violations != 0 {
		t.Fatalf("numeric grounding = %d assertions, %d violations", assertions, violations)
	}
}

func TestNumericGroundingIgnoresUnicodeHyphenatedIdentifiers(t *testing.T) {
	output := "SEC‑INTC‑01 SEC 8‑K EX‑99.1 accession 0000050863‑24‑000068 reports " +
		"INTC‑2023‑FOUNDRY‑REV USD 18,910 million."
	assertions, violations := evaluateNumericGrounding(output, []string{"18910"})
	if assertions != 1 || violations != 0 {
		t.Fatalf("numeric grounding = %d assertions, %d violations", assertions, violations)
	}
}

func TestContainsForbiddenAssertionIgnoresNegatedOrUncertainMentions(t *testing.T) {
	for _, output := range []string{
		"No refund is authorized until the duplicate-capture conflict is resolved.",
		"The policy explicitly states “no refund is authorized”.",
		"This is not a verified duplicate; evidence conflicts.",
		"We cannot confirm coupon validation as the cause.",
		"Coupon validation remains unconfirmed.",
		"| refund authorized | — | none | explicitly excluded |",
	} {
		if containsForbiddenAssertion(output, "refund is authorized") ||
			containsForbiddenAssertion(output, "verified duplicate") ||
			containsForbiddenAssertion(output, "coupon validation") {
			t.Fatalf("negated output matched forbidden assertion: %q", output)
		}
	}
	if !containsForbiddenAssertion(
		"The evidence proves a verified duplicate and refund is authorized.",
		"verified duplicate",
	) {
		t.Fatal("positive assertion did not match")
	}
	if !containsForbiddenAssertion(
		"No conflict remains and refund is authorized.",
		"refund is authorized",
	) {
		t.Fatal("unrelated negation suppressed positive assertion")
	}
	if !containsForbiddenAssertion(
		"The desk confirms: “refund is authorized”.",
		"refund is authorized",
	) {
		t.Fatal("quoted positive assertion did not match")
	}
	if !containsForbiddenAssertion("Do not authorize a refund.", "do not authorize") {
		t.Fatal("configured negative forbidden assertion did not match")
	}
	if containsForbiddenAssertion(
		"If no clarification appears within five days, escalate the review.",
		"no clarification",
	) {
		t.Fatal("conditional negative phrase was treated as a direct assertion")
	}
	if !containsForbiddenAssertion("No clarification is available.", "no clarification") {
		t.Fatal("direct negative forbidden assertion did not match")
	}
}

func TestMultiAgentOutcomeRejectsNegatedAndReversedDecisions(t *testing.T) {
	tests := []struct {
		name       string
		output     string
		milestones []MultiAgentMilestone
		forbidden  []string
	}{
		{
			name: "negated decision",
			output: "FIL-101 reports 18 percent growth and 220 basis points. " +
				"The catalyst is not confirmed. Do not move conviction from 3 to 4.",
			milestones: []MultiAgentMilestone{{
				ID:     "decision",
				Values: []string{"FIL-101", "18 percent", "catalyst confirmed", "conviction from 3 to 4"},
			}},
		},
		{
			name:   "reversed numeric direction",
			output: "FIL-601 says capex was raised from 5 billion to 8 billion yuan.",
			milestones: []MultiAgentMilestone{{
				ID:     "filing",
				Values: []string{"FIL-601", "reduced from 8 billion to 5 billion yuan"},
			}},
		},
		{
			name:   "configured opposite assertion",
			output: "FIL-201 covers C-17 at 31 percent, but the customer will renew its contract.",
			milestones: []MultiAgentMilestone{{
				ID:     "facts",
				Values: []string{"FIL-201", "C-17", "31 percent"},
			}},
			forbidden: []string{"will renew its contract"},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if multiAgentOutcomePass(test.output, MultiAgentCase{
				Milestones:            test.milestones,
				ForbiddenOutputValues: test.forbidden,
			}) {
				t.Fatalf("semantically reversed output passed: %q", test.output)
			}
		})
	}
}

func TestRequiredAssertionIgnoresTrailingNegationForAnotherClaim(t *testing.T) {
	output := "THS-111 says the catalyst is confirmed, while the invalidation is not observed."
	if !containsAllAssertions(output, []string{"catalyst confirmed"}) {
		t.Fatalf("trailing negation for another claim suppressed a positive assertion: %q", output)
	}
}

func TestRequiredAssertionPreservesConjoinedEvidence(t *testing.T) {
	output := "Revenue growth does not override restructuring and impairment evidence."
	if !containsAllAssertions(output, []string{output}) {
		t.Fatalf("conjoined required evidence did not match: %q", output)
	}
}

func TestRequiredAssertionPreservesDecimalsAndEquivalentExclusionPhrases(t *testing.T) {
	output := "PTF-501 reports average pairwise correlation of 0.89. " +
		"Request a source refresh rather than estimating missing values."
	if !containsAllAssertions(output, []string{
		"correlation 0.89",
		"instead of estimating",
	}) {
		t.Fatalf("decimal or exclusion phrase did not match: %q", output)
	}
	if containsAllAssertions("The model should estimate missing values.", []string{"instead of estimating"}) {
		t.Fatal("positive estimation matched a negative exclusion requirement")
	}
	if containsAllAssertions("If no trade is authorized, document that constraint.", []string{"no trade"}) {
		t.Fatal("conditional negative phrase satisfied a required direct assertion")
	}
}

func TestBundledContradictoryFaultAcceptsCorrectNegation(t *testing.T) {
	suite, err := LoadMultiAgentSuite(
		filepath.Join("..", "..", "evals", "multiagent-fault-injection.yaml"),
	)
	if err != nil {
		t.Fatal(err)
	}
	var evalCase MultiAgentCase
	for _, candidate := range suite.Cases {
		if candidate.ID == "contradictory-specialist-evidence" {
			evalCase = candidate
			break
		}
	}
	metrics := &MultiAgentAttemptMetrics{
		FaultsExpected: faultedCollaboratorCount(evalCase),
	}
	gradeMultiAgentFaults(
		evalCase,
		"There is a contradiction: two captures are reported by the account, "+
			"but the processor reports one successful capture. This is not a "+
			"verified duplicate, and no refund is authorized. Withhold refund.",
		nil,
		metrics,
	)
	if metrics.UnsupportedClaims != 0 {
		t.Fatalf("correct negation was treated as unsupported: %+v", metrics)
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

	suite = incidentMultiAgentSuite()
	suite.Cases[0].Agents[0].Fault = &MultiAgentFault{
		Type:                 "timeout",
		Delay:                Duration(maxMultiAgentFaultDelay + time.Millisecond),
		Message:              "unavailable",
		ExpectedOutputValues: []string{"unavailable"},
	}
	if err := suite.Validate(); err == nil || !strings.Contains(err.Error(), "cannot exceed") {
		t.Fatalf("fault delay error = %v", err)
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
		{"multiagent-finance-runtime.yaml", "finance-research-runtime", 6},
		{"multiagent-finance-sec-hard.json", "finance-sec-hard-longitudinal-runtime-v1", 4},
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
			if len(suite.SourceSHA256) != 64 {
				t.Fatalf("suite source SHA-256 = %q", suite.SourceSHA256)
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
		attempt.MultiAgent.PassedMilestones != 3 ||
		attempt.MultiAgent.ContributionItemCoverage != 1 {
		t.Fatalf("unexpected attempt metrics: %+v", attempt.MultiAgent)
	}
	metrics := report.Metrics
	if metrics.MATeamSuccessRate != 1 ||
		metrics.MASoloSuccessRate != 0 ||
		metrics.MACollaborationGain != 1 ||
		!metrics.MACollaborationGainValid {
		t.Fatalf("unexpected team/solo metrics: %+v", metrics)
	}
	if metrics.MAMilestoneKPI != 1 ||
		metrics.MACoordinationScore != 1 ||
		metrics.MAContributionItemCoverage != 1 ||
		metrics.MAAverageDelegations != 3 {
		t.Fatalf("unexpected coordination metrics: %+v", metrics)
	}
	if metrics.MACoordinatorTokens != 80 ||
		metrics.MASubAgentTokens != 120 ||
		math.Abs(metrics.MATeamEstimatedCostUSD-0.0032) > 1e-12 ||
		math.Abs(metrics.MASoloEstimatedCostUSD-0.001) > 1e-12 ||
		math.Abs(metrics.MACostPerSuccessfulRunUSD-0.0032) > 1e-12 ||
		metrics.MATeamTotalTokens != 200 ||
		metrics.MATeamTokensPerSuccess != 200 ||
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
		metrics.MAFairCollaborationGain != 0 ||
		!metrics.MACollaborationGainValid ||
		!metrics.MAFairCollaborationValid {
		t.Fatalf("unexpected fair baseline metrics: %+v", metrics)
	}
}

func TestMultiAgentRunnerIsolatesBaselineTimeouts(t *testing.T) {
	runner := MultiAgentRunner{
		Executor: executorFunc(func(ctx context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			if strings.HasSuffix(request.SessionKey, "-"+MultiAgentBaselineSoloClosedBook) ||
				strings.HasSuffix(request.SessionKey, "-"+MultiAgentBaselineSoloOpenBook) {
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
	if !attempt.Passed || len(attempt.Baselines) != 4 {
		t.Fatalf("unexpected attempt after baseline timeout: %+v", attempt)
	}
	if !strings.Contains(attempt.Baselines[0].Error, context.DeadlineExceeded.Error()) ||
		!strings.Contains(attempt.Baselines[1].Error, context.DeadlineExceeded.Error()) ||
		!attempt.Baselines[2].Passed ||
		!attempt.Baselines[3].Passed {
		t.Fatalf("unexpected baseline results: %+v", attempt.Baselines)
	}
	closed := report.Metrics.MABaselines[MultiAgentBaselineSoloClosedBook]
	open := report.Metrics.MABaselines[MultiAgentBaselineSoloOpenBook]
	if closed.Evaluated != 0 || closed.Errored != 1 ||
		open.Evaluated != 0 || open.Errored != 1 ||
		report.Metrics.MASoloEvaluated != 0 ||
		report.Metrics.MASoloOpenBookEvaluated != 0 ||
		report.Metrics.MACollaborationGainValid ||
		report.Metrics.MAFairCollaborationValid {
		t.Fatalf("baseline errors polluted gain metrics: %+v", report.Metrics)
	}
	var output bytes.Buffer
	if err := WriteText(&output, report); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(output.String(), "evidence-access delta n/a") ||
		!strings.Contains(output.String(), "fair gain n/a") ||
		!strings.Contains(output.String(), "errors 1") ||
		!strings.Contains(output.String(), "baseline solo_open_book ERROR") {
		t.Fatalf("baseline errors missing from report:\n%s", output.String())
	}
}

func TestMultiAgentRunnerTreatsEmptyBaselineOutputAsError(t *testing.T) {
	runner := MultiAgentRunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			if strings.HasSuffix(request.SessionKey, "-"+MultiAgentBaselineSoloOpenBook) {
				return ExecutionResponse{
					Usage: Usage{CompletionTokens: 2048, TotalTokens: 2048},
				}, nil
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
	}
	suite := incidentMultiAgentSuite()
	suite.Baselines = []string{
		MultiAgentBaselineSoloOpenBook,
		MultiAgentBaselineTeam,
	}
	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	attempt := report.Cases[0].Attempts[0]
	if !attempt.Passed ||
		attempt.Baselines[0].Error != "model returned empty output" ||
		report.Metrics.MABaselines[MultiAgentBaselineSoloOpenBook].Evaluated != 0 ||
		report.Metrics.MABaselines[MultiAgentBaselineSoloOpenBook].Errored != 1 ||
		report.Metrics.MAFairCollaborationValid {
		t.Fatalf("empty baseline output polluted metrics: %+v", report)
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
			responses := request.State["responses"].(map[string]any)
			if responses["logs-agent"] != "Coupon validation nil pointer." {
				t.Fatalf("fault polluted nominal state: %+v", responses)
			}
			return ExecutionResponse{
				Output: "Build 842 triggered the incident. Database latency remained normal. " +
					"The logs specialist timed out, so the exact code defect is unknown. " +
					"We cannot confirm coupon validation or a nil pointer as the cause. " +
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
	if report.Metrics.MAFaultObservationRate != 1 ||
		report.Metrics.MAFaultInjectionRate != 1 ||
		report.Metrics.MAFaultAttributionRate != 1 ||
		report.Metrics.MAGracefulDegradationRate != 1 ||
		report.Metrics.MAUnsupportedClaimRate != 0 {
		t.Fatalf("unexpected aggregate fault metrics: %+v", report.Metrics)
	}
}

func TestMultiAgentRunnerAccountsEveryBaselineCostBucket(t *testing.T) {
	costs := map[string]struct {
		tokens int
		cost   float64
	}{
		MultiAgentBaselineSoloClosedBook: {tokens: 10, cost: 0.1},
		MultiAgentBaselineSoloOpenBook:   {tokens: 20, cost: 0.2},
		MultiAgentBaselineSoloTwoPass:    {tokens: 25, cost: 0.25},
		MultiAgentBaselineTeam:           {tokens: 30, cost: 0.3},
		MultiAgentBaselineOracleTeam:     {tokens: 40, cost: 0.4},
	}
	runner := MultiAgentRunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			mode := ""
			for candidate := range costs {
				if strings.HasSuffix(request.SessionKey, "-"+candidate) {
					mode = candidate
					break
				}
			}
			entry, exists := costs[mode]
			if !exists {
				t.Fatalf("unexpected baseline session %q", request.SessionKey)
			}
			response := ExecutionResponse{
				Output: successfulIncidentOutput(),
				Usage: Usage{
					PromptTokens:     entry.tokens - 2,
					CompletionTokens: 2,
					TotalTokens:      entry.tokens,
				},
				ModelCalls: []ModelCallUsage{{
					AgentID:          "coordinator",
					Role:             "coordinator",
					PromptTokens:     entry.tokens - 2,
					CompletionTokens: 2,
					TotalTokens:      entry.tokens,
					CacheReadTokens:  2,
					EstimatedCostUSD: entry.cost,
					Priced:           true,
				}},
			}
			if mode == MultiAgentBaselineTeam {
				response.Trace = []TraceEvent{
					delegationTrace("metrics-agent", "analyze metrics"),
					delegationTrace("logs-agent", "analyze logs"),
					delegationTrace("deploy-agent", "analyze deployment"),
				}
			}
			return response, nil
		}),
	}
	suite := incidentMultiAgentSuite()
	suite.Baselines = []string{
		MultiAgentBaselineSoloClosedBook,
		MultiAgentBaselineSoloOpenBook,
		MultiAgentBaselineSoloTwoPass,
		MultiAgentBaselineTeam,
		MultiAgentBaselineOracleTeam,
	}
	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	metrics := report.Metrics
	if math.Abs(metrics.MATotalEstimatedCostUSD-1.5) > 1e-12 ||
		math.Abs(metrics.MASoloEstimatedCostUSD-0.1) > 1e-12 ||
		math.Abs(metrics.MASoloOpenBookCostUSD-0.2) > 1e-12 ||
		math.Abs(metrics.MASoloTwoPassCostUSD-0.5) > 1e-12 ||
		math.Abs(metrics.MATeamEstimatedCostUSD-0.3) > 1e-12 ||
		math.Abs(metrics.MAOracleTeamCostUSD-0.4) > 1e-12 {
		t.Fatalf("baseline cost buckets do not reconcile: %+v", metrics)
	}
	if metrics.MATeamTotalTokens != 30 ||
		metrics.MATeamTokensPerSuccess != 30 {
		t.Fatalf("unexpected team token metrics: %+v", metrics)
	}
	twoPass := metrics.MABaselines[MultiAgentBaselineSoloTwoPass]
	if twoPass.TotalTokens != 50 ||
		twoPass.PromptTokens != 46 ||
		twoPass.CompletionTokens != 4 ||
		twoPass.CacheReadTokens != 4 ||
		twoPass.UncachedPromptTokens != 42 {
		t.Fatalf("unexpected two-pass token accounting: %+v", twoPass)
	}
}

func TestMultiAgentUnsupportedClaimRateCountsFaultsNotPhrases(t *testing.T) {
	evalCase := MultiAgentCase{
		Agents: []MultiAgentCollaborator{
			{
				ID: "first",
				Fault: &MultiAgentFault{
					Type:                  "error",
					Message:               "first unavailable",
					ExpectedOutputValues:  []string{"first unavailable"},
					ForbiddenOutputValues: []string{"fabricated one", "fabricated two"},
				},
			},
			{
				ID: "second",
				Fault: &MultiAgentFault{
					Type:                  "error",
					Message:               "second unavailable",
					ExpectedOutputValues:  []string{"second unavailable"},
					ForbiddenOutputValues: []string{"fabricated three", "fabricated four", "fabricated five"},
				},
			},
		},
	}
	attemptMetrics := &MultiAgentAttemptMetrics{FaultsExpected: 2}
	gradeMultiAgentFaults(
		evalCase,
		"first unavailable; second unavailable. Fabricated one and fabricated two. "+
			"Fabricated three, fabricated four, and fabricated five.",
		nil,
		attemptMetrics,
	)
	if attemptMetrics.UnsupportedClaims != 2 {
		t.Fatalf("unsupported fault count = %d", attemptMetrics.UnsupportedClaims)
	}
	metrics := calculateMetrics([]CaseResult{{
		Attempts: []AttemptResult{{
			Kind:       "multiagent",
			MultiAgent: attemptMetrics,
		}},
	}})
	if metrics.MAUnsupportedClaimRate != 1 {
		t.Fatalf("unsupported claim rate = %v", metrics.MAUnsupportedClaimRate)
	}
}

func TestMultiAgentRunnerAllowsAllFaultGracefulDegradation(t *testing.T) {
	runner := MultiAgentRunner{
		Executor: executorFunc(func(_ context.Context, _ ExecutionRequest) (ExecutionResponse, error) {
			return ExecutionResponse{
				Output: "Metrics specialist unavailable. Logs specialist unavailable. " +
					"Deploy specialist unavailable. Pause automated action and escalate safely.",
				Trace: []TraceEvent{
					delegationTraceWithID("call-1", "metrics-agent", "inspect metrics"),
					{Type: "tool_result", ID: "call-1", Name: "spawn_subagent", Result: "metrics unavailable"},
					delegationTraceWithID("call-2", "logs-agent", "inspect logs"),
					{Type: "tool_result", ID: "call-2", Name: "spawn_subagent", Result: "logs unavailable"},
					delegationTraceWithID("call-3", "deploy-agent", "inspect deploy"),
					{Type: "tool_result", ID: "call-3", Name: "spawn_subagent", Result: "deploy unavailable"},
				},
			}, nil
		}),
	}
	suite := incidentMultiAgentSuite()
	suite.Cases[0].SkipSolo = true
	for index, message := range []string{
		"metrics unavailable",
		"logs unavailable",
		"deploy unavailable",
	} {
		suite.Cases[0].Agents[index].Fault = &MultiAgentFault{
			Type:                 "error",
			Message:              message,
			ExpectedOutputValues: strings.Fields(message),
		}
	}
	suite.Cases[0].Milestones = []MultiAgentMilestone{
		{ID: "failures", Values: []string{"metrics specialist unavailable", "logs specialist unavailable", "deploy specialist unavailable"}},
		{ID: "safe-action", Values: []string{"pause automated action", "escalate safely"}},
	}
	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	attempt := report.Cases[0].Attempts[0]
	if !attempt.Passed ||
		!attempt.MultiAgent.GracefullyDegraded ||
		attempt.MultiAgent.ContributionsExpected != 0 ||
		attempt.MultiAgent.CoordinationScore != 1 {
		t.Fatalf("all-fault case did not degrade gracefully: %+v", attempt)
	}
	for _, grader := range attempt.Graders {
		if grader.Type == "ma_contribution" {
			t.Fatalf("zero-denominator contribution grader was not skipped: %+v", attempt.Graders)
		}
	}
}

func TestMultiAgentDelegationResultsSkipEmptyCallIDs(t *testing.T) {
	results, uncorrelated := multiAgentDelegationResults([]TraceEvent{
		delegationTrace("first", "inspect first"),
		delegationTrace("second", "inspect second"),
		{Type: "tool_result", Name: "spawn_subagent", Result: "ambiguous"},
	})
	if len(results) != 0 || uncorrelated != 1 {
		t.Fatalf("unexpected empty-ID correlation: results=%v uncorrelated=%d", results, uncorrelated)
	}
}

func TestMultiAgentDelegationResultsExpandBatchCalls(t *testing.T) {
	trace := []TraceEvent{
		{
			Type: "tool_call", ID: "batch-1", Name: "spawn_subagent",
			Arguments: `{"sharedContext":"evidence","delegations":[{"agentId":"trend","task":"analyze trend"},{"agentId":"risk","task":"analyze risk"}]}`,
		},
		{
			Type: "tool_result", ID: "batch-1", Name: "spawn_subagent",
			Result: `{"results":[{"agentId":"trend","result":"trend result"},{"agentId":"risk","result":"risk result"}]}`,
		},
	}
	delegations := multiAgentDelegations(trace)
	results, uncorrelated := multiAgentDelegationResults(trace)
	if len(delegations) != 2 || len(results["trend"]) != 1 || len(results["risk"]) != 1 || uncorrelated != 0 {
		t.Fatalf("delegations=%+v results=%+v uncorrelated=%d", delegations, results, uncorrelated)
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
	if attempt.MultiAgent.DelegationPrecision != 1 ||
		attempt.MultiAgent.DelegationRecall != 1 {
		t.Fatalf("unexpected delegation metrics: %+v", attempt.MultiAgent)
	}
	if report.Metrics.MATeamSuccessRate != 0 ||
		report.Metrics.MADelegationPrecision != 1 {
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
