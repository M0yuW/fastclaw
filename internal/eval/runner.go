package eval

import (
	"context"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"sync/atomic"
	"time"
)

var runSequence atomic.Uint64

type RunOptions struct {
	AgentID          string
	Model            string
	Repetitions      int
	Timeout          time.Duration
	SessionKeyPrefix string
	CaseIDs          []string
}

type Runner struct {
	Executor Executor
	Options  RunOptions
}

func (r Runner) Run(ctx context.Context, suite Suite) (Report, error) {
	if r.Executor == nil {
		return Report{}, fmt.Errorf("eval executor is required")
	}
	if err := suite.Validate(); err != nil {
		return Report{}, err
	}

	startedAt := time.Now()
	sessionPrefix := r.Options.SessionKeyPrefix
	if sessionPrefix == "" {
		sessionPrefix = "eval"
	}
	runID := fmt.Sprintf(
		"%s-%d-%d",
		sanitizeSessionPart(sessionPrefix),
		startedAt.UnixNano(),
		runSequence.Add(1),
	)
	report := Report{
		Version:     SuiteVersion,
		Suite:       suite.Name,
		Description: suite.Description,
		Source:      suite.Source,
		StartedAt:   startedAt,
		Cases:       make([]CaseResult, 0, len(suite.Cases)),
	}

	for _, evalCase := range suite.Cases {
		caseResult := CaseResult{
			ID:          evalCase.ID,
			Description: evalCase.Description,
			Tags:        append([]string(nil), evalCase.Tags...),
		}
		repetitions := suite.repetitions(evalCase, r.Options.Repetitions)
		for attempt := 1; attempt <= repetitions; attempt++ {
			result := r.runAttempt(ctx, suite, evalCase, attempt, runID)
			caseResult.Attempts = append(caseResult.Attempts, result)
		}
		caseResult.PassAt1 = caseResult.Attempts[0].Passed
		caseResult.Consistent = attemptsConsistent(caseResult.Attempts)
		for _, attempt := range caseResult.Attempts {
			caseResult.PassAtK = caseResult.PassAtK || attempt.Passed
		}
		report.Cases = append(report.Cases, caseResult)
	}

	report.FinishedAt = time.Now()
	report.DurationMS = milliseconds(report.FinishedAt.Sub(startedAt))
	report.Metrics = calculateMetrics(report.Cases)
	return report, nil
}

func (r Runner) runAttempt(ctx context.Context, suite Suite, evalCase Case, attempt int, runID string) AttemptResult {
	timeout := suite.timeout(evalCase, r.Options.Timeout)
	attemptContext, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	agentID := firstNonEmpty(r.Options.AgentID, evalCase.AgentID, suite.Defaults.AgentID)
	model := firstNonEmpty(r.Options.Model, evalCase.Model, suite.Defaults.Model)
	sessionKey := fmt.Sprintf(
		"%s-%s-%s-%d",
		runID,
		sanitizeSessionPart(suite.Name),
		sanitizeSessionPart(evalCase.ID),
		attempt,
	)

	startedAt := time.Now()
	response, err := r.Executor.Execute(attemptContext, ExecutionRequest{
		Prompt:     evalCase.Prompt,
		AgentID:    agentID,
		Model:      model,
		SessionKey: sessionKey,
		Tools:      append([]ToolDefinition(nil), evalCase.Tools...),
	})
	latency := milliseconds(time.Since(startedAt))
	if err != nil {
		return AttemptResult{
			Attempt:   attempt,
			Passed:    false,
			Error:     err.Error(),
			LatencyMS: latency,
		}
	}

	graders, passed := GradeAttempt(response.Output, response.Trace, evalCase.Graders)
	return AttemptResult{
		Attempt:   attempt,
		Passed:    passed,
		Output:    response.Output,
		LatencyMS: latency,
		Model:     response.Model,
		Usage:     response.Usage,
		Trace:     response.Trace,
		Graders:   graders,
	}
}

func calculateMetrics(results []CaseResult) Metrics {
	metrics := Metrics{TotalCases: len(results)}
	latencies := make([]float64, 0)
	maTeamLatencies := make([]float64, 0)
	totalTurns := 0
	turnRuns := 0
	var (
		maTeamPassed        int
		maSoloPassed        int
		maMilestones        int
		maPassedMilestones  int
		maExpected          int
		maValid             int
		maDelegations       int
		maUniqueDelegations int
		maContributions     int
		maUsedContributions int
		maFaultAttributed   int
		maGraceful          int
	)
	for _, result := range results {
		if result.PassAt1 {
			metrics.PassAt1++
		}
		if result.PassAtK {
			metrics.PassAtK++
		}
		if result.Consistent {
			metrics.ConsistencyRate++
		}
		for _, attempt := range result.Attempts {
			metrics.TotalRuns++
			if attempt.Passed {
				metrics.PassedRuns++
			}
			latencies = append(latencies, attempt.LatencyMS)
			metrics.PromptTokens += attempt.Usage.PromptTokens
			metrics.CompletionTokens += attempt.Usage.CompletionTokens
			metrics.TotalTokens += attempt.Usage.TotalTokens
			if attempt.Turns > 0 {
				totalTurns += attempt.Turns
				turnRuns++
			}
			if attempt.Kind == "swe" {
				metrics.SWESubmittedInstances++
				if attempt.Completed {
					metrics.SWECompletedInstances++
				}
				if attempt.Passed {
					metrics.SWEResolvedInstances++
				}
				if strings.TrimSpace(attempt.Patch) != "" {
					metrics.SWEPatchesGenerated++
				}
			}
			if attempt.Kind == "multiagent" && attempt.MultiAgent != nil {
				metrics.MAAttempts++
				if attempt.Passed {
					maTeamPassed++
				}
				if attempt.MultiAgent.SoloEvaluated {
					metrics.MASoloEvaluated++
					if attempt.MultiAgent.SoloPassed {
						maSoloPassed++
					}
				}
				maMilestones += attempt.MultiAgent.TotalMilestones
				maPassedMilestones += attempt.MultiAgent.PassedMilestones
				maExpected += attempt.MultiAgent.ExpectedDelegations
				maValid += attempt.MultiAgent.ValidDelegations
				maDelegations += attempt.MultiAgent.TotalDelegations
				maUniqueDelegations += attempt.MultiAgent.UniqueDelegations
				metrics.MAUnexpectedDelegations += attempt.MultiAgent.UnexpectedDelegations
				maContributions += attempt.MultiAgent.ContributionsExpected
				maUsedContributions += attempt.MultiAgent.ContributionsUtilized
				metrics.MAGroundingAssertions += attempt.MultiAgent.GroundingAssertions
				metrics.MAGroundingViolations += attempt.MultiAgent.GroundingViolations
				if attempt.MultiAgent.FaultsExpected > 0 {
					metrics.MAFaultInjectedAttempts++
					metrics.MAFaultsExpected += attempt.MultiAgent.FaultsExpected
					metrics.MAFaultsObserved += attempt.MultiAgent.FaultsObserved
					maFaultAttributed += attempt.MultiAgent.FaultsAttributed
					metrics.MAUnsupportedClaims += attempt.MultiAgent.UnsupportedClaims
					metrics.MAUncorrelatedToolResults += attempt.MultiAgent.UncorrelatedToolResults
					if attempt.MultiAgent.GracefullyDegraded {
						maGraceful++
					}
				}
				for _, baseline := range attempt.Baselines {
					if metrics.MABaselines == nil {
						metrics.MABaselines = make(map[string]MultiAgentBaselineMetrics)
					}
					baselineMetrics := metrics.MABaselines[baseline.Mode]
					if baseline.Error != "" {
						baselineMetrics.Errored++
					} else {
						baselineMetrics.Evaluated++
						if baseline.Passed {
							baselineMetrics.Passed++
						}
						baselineMetrics.AverageLatencyMS += baseline.LatencyMS
					}
					baselineMetrics.TotalTokens += baseline.Usage.TotalTokens
					baselineMetrics.PromptTokens += baseline.Usage.PromptTokens
					baselineMetrics.CompletionTokens += baseline.Usage.CompletionTokens
					baselineMetrics.GroundingAssertions += baseline.GroundingAssertions
					baselineMetrics.GroundingViolations += baseline.GroundingViolations
					for _, call := range baseline.ModelCalls {
						baselineMetrics.EstimatedCostUSD += call.EstimatedCostUSD
						baselineMetrics.CacheReadTokens += call.CacheReadTokens
						baselineMetrics.CacheCreationTokens += call.CacheCreationTokens
						baselineMetrics.UncachedPromptTokens += max(
							0,
							call.PromptTokens-call.CacheReadTokens,
						)
					}
					metrics.MABaselines[baseline.Mode] = baselineMetrics
					if baseline.Mode == MultiAgentBaselineTeam {
						metrics.MATeamTotalTokens += baseline.Usage.TotalTokens
						if baseline.Error == "" {
							maTeamLatencies = append(maTeamLatencies, baseline.LatencyMS)
						}
					}
				}
				for _, call := range attempt.ModelCalls {
					metrics.MAModelCalls++
					metrics.MATotalEstimatedCostUSD += call.EstimatedCostUSD
					if call.Priced {
						metrics.MAPricedModelCalls++
					}
					switch call.Phase {
					case "solo", MultiAgentBaselineSoloClosedBook:
						metrics.MASoloEstimatedCostUSD += call.EstimatedCostUSD
					case MultiAgentBaselineSoloOpenBook:
						metrics.MASoloOpenBookCostUSD += call.EstimatedCostUSD
					case MultiAgentBaselineSoloTwoPass:
						metrics.MASoloTwoPassCostUSD += call.EstimatedCostUSD
					case MultiAgentBaselineTeam:
						metrics.MATeamEstimatedCostUSD += call.EstimatedCostUSD
						switch call.Role {
						case "coordinator":
							metrics.MACoordinatorTokens += call.TotalTokens
							metrics.MACoordinatorCostUSD += call.EstimatedCostUSD
							metrics.MACoordinatorLatencyMS += call.LatencyMS
						case "subagent":
							metrics.MASubAgentTokens += call.TotalTokens
							metrics.MASubAgentCostUSD += call.EstimatedCostUSD
							metrics.MASubAgentLatencyMS += call.LatencyMS
						}
					case MultiAgentBaselineOracleTeam:
						metrics.MAOracleTeamCostUSD += call.EstimatedCostUSD
					}
				}
			}
			for _, event := range attempt.Trace {
				if event.Type != "tool_call" {
					continue
				}
				metrics.TotalToolCalls++
				if !validToolArguments(event.Arguments) {
					metrics.InvalidToolCalls++
				}
			}
			for _, grader := range attempt.Graders {
				switch grader.Type {
				case "tool_trace":
					metrics.ToolTraceGraders++
					if grader.Passed {
						metrics.PassedToolTraceGraders++
					}
				case "tau_state":
					metrics.StateGraders++
					if grader.Passed {
						metrics.PassedStateGraders++
					}
				case "tau_communicate":
					metrics.CommunicationGraders++
					if grader.Passed {
						metrics.PassedCommunication++
					}
				case "tau_policy":
					metrics.PolicyGraders++
					if grader.Passed {
						metrics.PassedPolicyGraders++
					}
				}
			}
		}
	}
	metrics.FailedRuns = metrics.TotalRuns - metrics.PassedRuns
	if metrics.TotalRuns > 0 {
		metrics.RunPassRate = float64(metrics.PassedRuns) / float64(metrics.TotalRuns)
		metrics.EndToEndTaskSuccess = metrics.RunPassRate
	}
	if metrics.TotalCases > 0 {
		metrics.PassAt1 /= float64(metrics.TotalCases)
		metrics.PassAtK /= float64(metrics.TotalCases)
		metrics.ConsistencyRate /= float64(metrics.TotalCases)
	}
	if metrics.PassedRuns > 0 {
		metrics.TokensPerPassedRun = float64(metrics.TotalTokens) / float64(metrics.PassedRuns)
	}
	if metrics.TotalToolCalls > 0 {
		metrics.InvalidToolCallRate = float64(metrics.InvalidToolCalls) / float64(metrics.TotalToolCalls)
	}
	if metrics.ToolTraceGraders > 0 {
		metrics.ToolTraceAccuracy = float64(metrics.PassedToolTraceGraders) / float64(metrics.ToolTraceGraders)
	}
	if metrics.StateGraders > 0 {
		metrics.StateAccuracy = float64(metrics.PassedStateGraders) / float64(metrics.StateGraders)
	}
	if metrics.CommunicationGraders > 0 {
		metrics.CommunicationAccuracy = float64(metrics.PassedCommunication) / float64(metrics.CommunicationGraders)
	}
	if metrics.PolicyGraders > 0 {
		metrics.PolicyComplianceRate = float64(metrics.PassedPolicyGraders) / float64(metrics.PolicyGraders)
	}
	if turnRuns > 0 {
		metrics.AverageTurns = float64(totalTurns) / float64(turnRuns)
	}
	if metrics.SWESubmittedInstances > 0 {
		submitted := float64(metrics.SWESubmittedInstances)
		metrics.SWEResolutionRate = float64(metrics.SWEResolvedInstances) / submitted
		metrics.SWEPatchGenerationRate = float64(metrics.SWEPatchesGenerated) / submitted
		metrics.SWETestExecutionRate = float64(metrics.SWECompletedInstances) / submitted
	}
	if metrics.MAAttempts > 0 {
		metrics.MATeamSuccessRate = float64(maTeamPassed) / float64(metrics.MAAttempts)
		metrics.MAAverageDelegations = float64(maDelegations) / float64(metrics.MAAttempts)
		metrics.MACoordinatorLatencyMS /= float64(metrics.MAAttempts)
		metrics.MASubAgentLatencyMS /= float64(metrics.MAAttempts)
	}
	if metrics.MAModelCalls > 0 {
		metrics.MAPricingCoverage = float64(metrics.MAPricedModelCalls) / float64(metrics.MAModelCalls)
	}
	if metrics.MASoloEvaluated > 0 {
		metrics.MASoloSuccessRate = float64(maSoloPassed) / float64(metrics.MASoloEvaluated)
	}
	for mode, baseline := range metrics.MABaselines {
		if baseline.Evaluated > 0 {
			baseline.SuccessRate = float64(baseline.Passed) / float64(baseline.Evaluated)
			baseline.AverageLatencyMS /= float64(baseline.Evaluated)
		}
		if baseline.GroundingAssertions > 0 {
			baseline.GroundingAccuracy = 1 -
				float64(baseline.GroundingViolations)/float64(baseline.GroundingAssertions)
		}
		metrics.MABaselines[mode] = baseline
	}
	teamBaseline, teamBaselineExists := metrics.MABaselines[MultiAgentBaselineTeam]
	if teamBaselineExists {
		metrics.MATeamOutcomeEvaluated = teamBaseline.Evaluated
		metrics.MATeamOutcomeSuccessRate = teamBaseline.SuccessRate
		if teamBaseline.Passed > 0 {
			metrics.MACostPerSuccessfulRunUSD = metrics.MATeamEstimatedCostUSD /
				float64(teamBaseline.Passed)
			metrics.MATeamTokensPerSuccess = float64(metrics.MATeamTotalTokens) /
				float64(teamBaseline.Passed)
		}
	}
	if metrics.MASoloEvaluated > 0 && teamBaselineExists && teamBaseline.Evaluated > 0 {
		if baseline, ok := metrics.MABaselines[MultiAgentBaselineSoloClosedBook]; ok &&
			multiAgentBaselinesComparable(teamBaseline, baseline) {
			metrics.MACollaborationGain = teamBaseline.SuccessRate - baseline.SuccessRate
			metrics.MACollaborationGainValid = true
		}
	}
	if baseline, ok := metrics.MABaselines[MultiAgentBaselineSoloOpenBook]; ok {
		metrics.MASoloOpenBookEvaluated = baseline.Evaluated
		metrics.MASoloOpenBookSuccessRate = baseline.SuccessRate
		if teamBaselineExists && multiAgentBaselinesComparable(teamBaseline, baseline) {
			metrics.MAFairCollaborationGain = teamBaseline.SuccessRate - baseline.SuccessRate
			metrics.MAFairCollaborationValid = true
		}
	}
	if baseline, ok := metrics.MABaselines[MultiAgentBaselineSoloTwoPass]; ok {
		metrics.MASoloTwoPassEvaluated = baseline.Evaluated
		metrics.MASoloTwoPassSuccessRate = baseline.SuccessRate
		if teamBaselineExists && multiAgentBaselinesComparable(teamBaseline, baseline) {
			metrics.MAComputeMatchedGain = teamBaseline.SuccessRate - baseline.SuccessRate
			metrics.MAComputeMatchedGainValid = true
		}
	}
	if baseline, ok := metrics.MABaselines[MultiAgentBaselineOracleTeam]; ok {
		metrics.MAOracleTeamEvaluated = baseline.Evaluated
		metrics.MAOracleTeamSuccessRate = baseline.SuccessRate
	}
	if metrics.MAFaultsExpected > 0 {
		metrics.MAFaultObservationRate = float64(metrics.MAFaultsObserved) /
			float64(metrics.MAFaultsExpected)
		metrics.MAFaultInjectionRate = metrics.MAFaultObservationRate
		metrics.MAFaultAttributionRate = float64(maFaultAttributed) /
			float64(metrics.MAFaultsExpected)
		metrics.MAUnsupportedClaimRate = float64(metrics.MAUnsupportedClaims) /
			float64(metrics.MAFaultsExpected)
	}
	if metrics.MAFaultInjectedAttempts > 0 {
		metrics.MAGracefulDegradationRate = float64(maGraceful) /
			float64(metrics.MAFaultInjectedAttempts)
	}
	if maMilestones > 0 {
		metrics.MAMilestoneKPI = float64(maPassedMilestones) / float64(maMilestones)
	}
	if maUniqueDelegations > 0 {
		metrics.MADelegationPrecision = float64(maValid) / float64(maUniqueDelegations)
	}
	if maExpected > 0 {
		metrics.MADelegationRecall = float64(maValid) / float64(maExpected)
	}
	if metrics.MADelegationPrecision+metrics.MADelegationRecall > 0 {
		metrics.MADelegationF1 = 2 * metrics.MADelegationPrecision * metrics.MADelegationRecall /
			(metrics.MADelegationPrecision + metrics.MADelegationRecall)
	}
	if maContributions > 0 {
		metrics.MAContributionUtilization = float64(maUsedContributions) / float64(maContributions)
	}
	if metrics.MAGroundingAssertions > 0 {
		metrics.MAGroundingAccuracy = 1 -
			float64(metrics.MAGroundingViolations)/float64(metrics.MAGroundingAssertions)
	}
	metrics.MACoordinationScore = (metrics.MADelegationF1 + metrics.MAContributionUtilization) / 2
	if maContributions == 0 {
		metrics.MACoordinationScore = metrics.MADelegationF1
	}
	sort.Float64s(latencies)
	metrics.LatencyP50MS = percentile(latencies, 0.50)
	metrics.LatencyP95MS = percentile(latencies, 0.95)
	sort.Float64s(maTeamLatencies)
	metrics.MATeamLatencyP50MS = percentile(maTeamLatencies, 0.50)
	metrics.MATeamLatencyP95MS = percentile(maTeamLatencies, 0.95)
	return metrics
}

func multiAgentBaselinesComparable(team, comparator MultiAgentBaselineMetrics) bool {
	return team.Evaluated > 0 &&
		team.Errored == 0 &&
		comparator.Errored == 0 &&
		team.Evaluated == comparator.Evaluated
}

func validToolArguments(arguments string) bool {
	var object map[string]any
	return json.Unmarshal([]byte(arguments), &object) == nil && object != nil
}

func attemptsConsistent(attempts []AttemptResult) bool {
	if len(attempts) < 2 {
		return true
	}
	first := attempts[0].Passed
	for _, attempt := range attempts[1:] {
		if attempt.Passed != first {
			return false
		}
	}
	return true
}

func percentile(values []float64, quantile float64) float64 {
	if len(values) == 0 {
		return 0
	}
	index := int(float64(len(values)-1)*quantile + 0.5)
	return values[index]
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}

func sanitizeSessionPart(value string) string {
	value = strings.TrimSpace(value)
	if value == "" {
		return "default"
	}
	var builder strings.Builder
	for _, char := range value {
		switch {
		case char >= 'a' && char <= 'z':
			builder.WriteRune(char)
		case char >= 'A' && char <= 'Z':
			builder.WriteRune(char + ('a' - 'A'))
		case char >= '0' && char <= '9':
			builder.WriteRune(char)
		default:
			builder.WriteByte('-')
		}
	}
	sanitized := strings.Trim(builder.String(), "-")
	if sanitized == "" {
		return "default"
	}
	return sanitized
}

func milliseconds(duration time.Duration) float64 {
	return float64(duration.Microseconds()) / 1000
}
