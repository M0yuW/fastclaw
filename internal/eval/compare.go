package eval

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
)

type MetricDelta struct {
	RunPassRatePoints           float64 `json:"run_pass_rate_points"`
	PassAt1Points               float64 `json:"pass_at_1_points"`
	PassAtKPoints               float64 `json:"pass_at_k_points"`
	ConsistencyRatePoints       float64 `json:"consistency_rate_points"`
	LatencyP50Percent           float64 `json:"latency_p50_percent"`
	LatencyP95Percent           float64 `json:"latency_p95_percent"`
	TokensPerSuccessPercent     float64 `json:"tokens_per_success_percent"`
	ToolTraceAccuracyPoints     float64 `json:"tool_trace_accuracy_points"`
	InvalidToolCallRatePoints   float64 `json:"invalid_tool_call_rate_points"`
	StateAccuracyPoints         float64 `json:"state_accuracy_points"`
	CommunicationPoints         float64 `json:"communication_accuracy_points"`
	PolicyCompliancePoints      float64 `json:"policy_compliance_rate_points"`
	EndToEndSuccessPoints       float64 `json:"end_to_end_task_success_points"`
	SWEResolutionRatePoints     float64 `json:"swe_resolution_rate_points"`
	SWEPatchGenerationPoints    float64 `json:"swe_patch_generation_rate_points"`
	SWETestExecutionPoints      float64 `json:"swe_test_execution_rate_points"`
	MATeamSuccessPoints         float64 `json:"multi_agent_team_success_rate_points"`
	MASoloSuccessPoints         float64 `json:"multi_agent_solo_success_rate_points"`
	MACollaborationGainPoints   float64 `json:"multi_agent_collaboration_gain_points"`
	MACollaborationGainValid    bool    `json:"multi_agent_collaboration_gain_valid"`
	MASoloOpenBookPoints        float64 `json:"multi_agent_solo_open_book_success_rate_points"`
	MATeamOutcomePoints         float64 `json:"multi_agent_team_outcome_success_rate_points"`
	MAOracleTeamPoints          float64 `json:"multi_agent_oracle_team_success_rate_points"`
	MAFairGainPoints            float64 `json:"multi_agent_fair_collaboration_gain_points"`
	MAFairGainValid             bool    `json:"multi_agent_fair_collaboration_gain_valid"`
	MAMilestoneKPIPoints        float64 `json:"multi_agent_milestone_kpi_points"`
	MACoordinationPoints        float64 `json:"multi_agent_coordination_score_points"`
	MAFaultInjectionPoints      float64 `json:"multi_agent_fault_injection_rate_points"`
	MAFaultObservationPoints    float64 `json:"multi_agent_fault_observation_rate_points"`
	MAFaultAttributionPoints    float64 `json:"multi_agent_fault_attribution_rate_points"`
	MAGracefulDegradationPoints float64 `json:"multi_agent_graceful_degradation_rate_points"`
	MAUnsupportedClaimPoints    float64 `json:"multi_agent_unsupported_claim_rate_points"`
	MATeamCostPercent           float64 `json:"multi_agent_team_cost_percent"`
	MATeamLatencyP50Percent     float64 `json:"multi_agent_team_latency_p50_percent"`
	MATeamLatencyP95Percent     float64 `json:"multi_agent_team_latency_p95_percent"`
	MATeamTokensPerSuccessPct   float64 `json:"multi_agent_team_tokens_per_success_percent"`
	MACostPerSuccessPercent     float64 `json:"multi_agent_cost_per_success_percent"`
	MACoordinatorTokensPercent  float64 `json:"multi_agent_coordinator_tokens_percent"`
	MASubAgentTokensPercent     float64 `json:"multi_agent_subagent_tokens_percent"`
}

type Comparison struct {
	Suite     string      `json:"suite"`
	Baseline  Metrics     `json:"baseline"`
	Candidate Metrics     `json:"candidate"`
	Delta     MetricDelta `json:"delta"`
}

func LoadReport(path string) (Report, error) {
	file, err := os.Open(path)
	if err != nil {
		return Report{}, fmt.Errorf("open eval report: %w", err)
	}
	defer file.Close()

	var report Report
	if err := json.NewDecoder(file).Decode(&report); err != nil {
		return Report{}, fmt.Errorf("decode eval report: %w", err)
	}
	if report.Version != SuiteVersion {
		return Report{}, fmt.Errorf("eval report version must be %d", SuiteVersion)
	}
	if report.Suite == "" {
		return Report{}, fmt.Errorf("eval report suite is required")
	}
	return report, nil
}

func Compare(baseline, candidate Report) (Comparison, error) {
	if baseline.Suite != candidate.Suite {
		return Comparison{}, fmt.Errorf(
			"cannot compare different suites %q and %q",
			baseline.Suite,
			candidate.Suite,
		)
	}
	if err := validateComparableCases(baseline.Cases, candidate.Cases); err != nil {
		return Comparison{}, err
	}
	comparison := Comparison{
		Suite:     baseline.Suite,
		Baseline:  baseline.Metrics,
		Candidate: candidate.Metrics,
		Delta: MetricDelta{
			RunPassRatePoints:           percentagePointDelta(baseline.Metrics.RunPassRate, candidate.Metrics.RunPassRate),
			PassAt1Points:               percentagePointDelta(baseline.Metrics.PassAt1, candidate.Metrics.PassAt1),
			PassAtKPoints:               percentagePointDelta(baseline.Metrics.PassAtK, candidate.Metrics.PassAtK),
			ConsistencyRatePoints:       percentagePointDelta(baseline.Metrics.ConsistencyRate, candidate.Metrics.ConsistencyRate),
			LatencyP50Percent:           percentDelta(baseline.Metrics.LatencyP50MS, candidate.Metrics.LatencyP50MS),
			LatencyP95Percent:           percentDelta(baseline.Metrics.LatencyP95MS, candidate.Metrics.LatencyP95MS),
			TokensPerSuccessPercent:     percentDelta(baseline.Metrics.TokensPerPassedRun, candidate.Metrics.TokensPerPassedRun),
			ToolTraceAccuracyPoints:     percentagePointDelta(baseline.Metrics.ToolTraceAccuracy, candidate.Metrics.ToolTraceAccuracy),
			InvalidToolCallRatePoints:   percentagePointDelta(baseline.Metrics.InvalidToolCallRate, candidate.Metrics.InvalidToolCallRate),
			StateAccuracyPoints:         percentagePointDelta(baseline.Metrics.StateAccuracy, candidate.Metrics.StateAccuracy),
			CommunicationPoints:         percentagePointDelta(baseline.Metrics.CommunicationAccuracy, candidate.Metrics.CommunicationAccuracy),
			PolicyCompliancePoints:      percentagePointDelta(baseline.Metrics.PolicyComplianceRate, candidate.Metrics.PolicyComplianceRate),
			EndToEndSuccessPoints:       percentagePointDelta(baseline.Metrics.EndToEndTaskSuccess, candidate.Metrics.EndToEndTaskSuccess),
			SWEResolutionRatePoints:     percentagePointDelta(baseline.Metrics.SWEResolutionRate, candidate.Metrics.SWEResolutionRate),
			SWEPatchGenerationPoints:    percentagePointDelta(baseline.Metrics.SWEPatchGenerationRate, candidate.Metrics.SWEPatchGenerationRate),
			SWETestExecutionPoints:      percentagePointDelta(baseline.Metrics.SWETestExecutionRate, candidate.Metrics.SWETestExecutionRate),
			MATeamSuccessPoints:         percentagePointDelta(baseline.Metrics.MATeamSuccessRate, candidate.Metrics.MATeamSuccessRate),
			MASoloSuccessPoints:         percentagePointDelta(baseline.Metrics.MASoloSuccessRate, candidate.Metrics.MASoloSuccessRate),
			MASoloOpenBookPoints:        percentagePointDelta(baseline.Metrics.MASoloOpenBookSuccessRate, candidate.Metrics.MASoloOpenBookSuccessRate),
			MATeamOutcomePoints:         percentagePointDelta(baseline.Metrics.MATeamOutcomeSuccessRate, candidate.Metrics.MATeamOutcomeSuccessRate),
			MAOracleTeamPoints:          percentagePointDelta(baseline.Metrics.MAOracleTeamSuccessRate, candidate.Metrics.MAOracleTeamSuccessRate),
			MAMilestoneKPIPoints:        percentagePointDelta(baseline.Metrics.MAMilestoneKPI, candidate.Metrics.MAMilestoneKPI),
			MACoordinationPoints:        percentagePointDelta(baseline.Metrics.MACoordinationScore, candidate.Metrics.MACoordinationScore),
			MAFaultInjectionPoints:      percentagePointDelta(faultObservationRate(baseline.Metrics), faultObservationRate(candidate.Metrics)),
			MAFaultObservationPoints:    percentagePointDelta(faultObservationRate(baseline.Metrics), faultObservationRate(candidate.Metrics)),
			MAFaultAttributionPoints:    percentagePointDelta(baseline.Metrics.MAFaultAttributionRate, candidate.Metrics.MAFaultAttributionRate),
			MAGracefulDegradationPoints: percentagePointDelta(baseline.Metrics.MAGracefulDegradationRate, candidate.Metrics.MAGracefulDegradationRate),
			MAUnsupportedClaimPoints:    percentagePointDelta(baseline.Metrics.MAUnsupportedClaimRate, candidate.Metrics.MAUnsupportedClaimRate),
			MATeamCostPercent:           percentDelta(baseline.Metrics.MATeamEstimatedCostUSD, candidate.Metrics.MATeamEstimatedCostUSD),
			MATeamLatencyP50Percent:     percentDelta(baseline.Metrics.MATeamLatencyP50MS, candidate.Metrics.MATeamLatencyP50MS),
			MATeamLatencyP95Percent:     percentDelta(baseline.Metrics.MATeamLatencyP95MS, candidate.Metrics.MATeamLatencyP95MS),
			MATeamTokensPerSuccessPct:   percentDelta(baseline.Metrics.MATeamTokensPerSuccess, candidate.Metrics.MATeamTokensPerSuccess),
			MACostPerSuccessPercent:     percentDelta(baseline.Metrics.MACostPerSuccessfulRunUSD, candidate.Metrics.MACostPerSuccessfulRunUSD),
			MACoordinatorTokensPercent:  percentDelta(float64(baseline.Metrics.MACoordinatorTokens), float64(candidate.Metrics.MACoordinatorTokens)),
			MASubAgentTokensPercent:     percentDelta(float64(baseline.Metrics.MASubAgentTokens), float64(candidate.Metrics.MASubAgentTokens)),
		},
	}
	if collaborationGainAvailable(baseline.Metrics) && collaborationGainAvailable(candidate.Metrics) {
		comparison.Delta.MACollaborationGainValid = true
		comparison.Delta.MACollaborationGainPoints = percentagePointDelta(
			baseline.Metrics.MACollaborationGain,
			candidate.Metrics.MACollaborationGain,
		)
	}
	if fairCollaborationGainAvailable(baseline.Metrics) && fairCollaborationGainAvailable(candidate.Metrics) {
		comparison.Delta.MAFairGainValid = true
		comparison.Delta.MAFairGainPoints = percentagePointDelta(
			baseline.Metrics.MAFairCollaborationGain,
			candidate.Metrics.MAFairCollaborationGain,
		)
	}
	return comparison, nil
}

func validateComparableCases(baseline, candidate []CaseResult) error {
	baselineAttempts, err := caseAttemptCounts("baseline", baseline)
	if err != nil {
		return err
	}
	candidateAttempts, err := caseAttemptCounts("candidate", candidate)
	if err != nil {
		return err
	}
	if len(baselineAttempts) != len(candidateAttempts) {
		return fmt.Errorf(
			"cannot compare different case sets: baseline has %d cases, candidate has %d",
			len(baselineAttempts),
			len(candidateAttempts),
		)
	}
	for caseID, attempts := range baselineAttempts {
		candidateCount, ok := candidateAttempts[caseID]
		if !ok {
			return fmt.Errorf("cannot compare different case sets: candidate is missing case %q", caseID)
		}
		if attempts != candidateCount {
			return fmt.Errorf(
				"cannot compare case %q with different attempt counts: baseline has %d, candidate has %d",
				caseID,
				attempts,
				candidateCount,
			)
		}
	}
	return nil
}

func caseAttemptCounts(label string, cases []CaseResult) (map[string]int, error) {
	counts := make(map[string]int, len(cases))
	for _, evalCase := range cases {
		if _, exists := counts[evalCase.ID]; exists {
			return nil, fmt.Errorf("%s report contains duplicate case %q", label, evalCase.ID)
		}
		counts[evalCase.ID] = len(evalCase.Attempts)
	}
	return counts, nil
}

func WriteComparisonJSON(writer io.Writer, comparison Comparison) error {
	encoder := json.NewEncoder(writer)
	encoder.SetIndent("", "  ")
	return encoder.Encode(comparison)
}

func WriteComparisonText(writer io.Writer, comparison Comparison) error {
	if _, err := fmt.Fprintf(writer, "Eval comparison: %s\n", comparison.Suite); err != nil {
		return err
	}
	rows := []struct {
		name      string
		baseline  float64
		candidate float64
		delta     float64
		unit      string
	}{
		{"run pass rate", comparison.Baseline.RunPassRate * 100, comparison.Candidate.RunPassRate * 100, comparison.Delta.RunPassRatePoints, "pp"},
		{"pass@1", comparison.Baseline.PassAt1 * 100, comparison.Candidate.PassAt1 * 100, comparison.Delta.PassAt1Points, "pp"},
		{"pass@k", comparison.Baseline.PassAtK * 100, comparison.Candidate.PassAtK * 100, comparison.Delta.PassAtKPoints, "pp"},
		{"consistency", comparison.Baseline.ConsistencyRate * 100, comparison.Candidate.ConsistencyRate * 100, comparison.Delta.ConsistencyRatePoints, "pp"},
		{"latency p50", comparison.Baseline.LatencyP50MS, comparison.Candidate.LatencyP50MS, comparison.Delta.LatencyP50Percent, "%"},
		{"latency p95", comparison.Baseline.LatencyP95MS, comparison.Candidate.LatencyP95MS, comparison.Delta.LatencyP95Percent, "%"},
		{"tokens/success", comparison.Baseline.TokensPerPassedRun, comparison.Candidate.TokensPerPassedRun, comparison.Delta.TokensPerSuccessPercent, "%"},
		{"tool trace acc", comparison.Baseline.ToolTraceAccuracy * 100, comparison.Candidate.ToolTraceAccuracy * 100, comparison.Delta.ToolTraceAccuracyPoints, "pp"},
		{"invalid tools", comparison.Baseline.InvalidToolCallRate * 100, comparison.Candidate.InvalidToolCallRate * 100, comparison.Delta.InvalidToolCallRatePoints, "pp"},
		{"state accuracy", comparison.Baseline.StateAccuracy * 100, comparison.Candidate.StateAccuracy * 100, comparison.Delta.StateAccuracyPoints, "pp"},
		{"communication", comparison.Baseline.CommunicationAccuracy * 100, comparison.Candidate.CommunicationAccuracy * 100, comparison.Delta.CommunicationPoints, "pp"},
		{"policy comply", comparison.Baseline.PolicyComplianceRate * 100, comparison.Candidate.PolicyComplianceRate * 100, comparison.Delta.PolicyCompliancePoints, "pp"},
		{"end-to-end", comparison.Baseline.EndToEndTaskSuccess * 100, comparison.Candidate.EndToEndTaskSuccess * 100, comparison.Delta.EndToEndSuccessPoints, "pp"},
		{"SWE resolved", comparison.Baseline.SWEResolutionRate * 100, comparison.Candidate.SWEResolutionRate * 100, comparison.Delta.SWEResolutionRatePoints, "pp"},
		{"SWE patches", comparison.Baseline.SWEPatchGenerationRate * 100, comparison.Candidate.SWEPatchGenerationRate * 100, comparison.Delta.SWEPatchGenerationPoints, "pp"},
		{"SWE test exec", comparison.Baseline.SWETestExecutionRate * 100, comparison.Candidate.SWETestExecutionRate * 100, comparison.Delta.SWETestExecutionPoints, "pp"},
		{"MA team success", comparison.Baseline.MATeamSuccessRate * 100, comparison.Candidate.MATeamSuccessRate * 100, comparison.Delta.MATeamSuccessPoints, "pp"},
		{"MA solo success", comparison.Baseline.MASoloSuccessRate * 100, comparison.Candidate.MASoloSuccessRate * 100, comparison.Delta.MASoloSuccessPoints, "pp"},
		{"MA solo open", comparison.Baseline.MASoloOpenBookSuccessRate * 100, comparison.Candidate.MASoloOpenBookSuccessRate * 100, comparison.Delta.MASoloOpenBookPoints, "pp"},
		{"MA team outcome", comparison.Baseline.MATeamOutcomeSuccessRate * 100, comparison.Candidate.MATeamOutcomeSuccessRate * 100, comparison.Delta.MATeamOutcomePoints, "pp"},
		{"MA oracle team", comparison.Baseline.MAOracleTeamSuccessRate * 100, comparison.Candidate.MAOracleTeamSuccessRate * 100, comparison.Delta.MAOracleTeamPoints, "pp"},
		{"MA milestone KPI", comparison.Baseline.MAMilestoneKPI * 100, comparison.Candidate.MAMilestoneKPI * 100, comparison.Delta.MAMilestoneKPIPoints, "pp"},
		{"MA coordination", comparison.Baseline.MACoordinationScore * 100, comparison.Candidate.MACoordinationScore * 100, comparison.Delta.MACoordinationPoints, "pp"},
		{"MA fault observed", faultObservationRate(comparison.Baseline) * 100, faultObservationRate(comparison.Candidate) * 100, comparison.Delta.MAFaultObservationPoints, "pp"},
		{"MA fault attrib", comparison.Baseline.MAFaultAttributionRate * 100, comparison.Candidate.MAFaultAttributionRate * 100, comparison.Delta.MAFaultAttributionPoints, "pp"},
		{"MA graceful", comparison.Baseline.MAGracefulDegradationRate * 100, comparison.Candidate.MAGracefulDegradationRate * 100, comparison.Delta.MAGracefulDegradationPoints, "pp"},
		{"MA unsupported", comparison.Baseline.MAUnsupportedClaimRate * 100, comparison.Candidate.MAUnsupportedClaimRate * 100, comparison.Delta.MAUnsupportedClaimPoints, "pp"},
		{"MA team cost", comparison.Baseline.MATeamEstimatedCostUSD, comparison.Candidate.MATeamEstimatedCostUSD, comparison.Delta.MATeamCostPercent, "%"},
		{"MA team p50", comparison.Baseline.MATeamLatencyP50MS, comparison.Candidate.MATeamLatencyP50MS, comparison.Delta.MATeamLatencyP50Percent, "%"},
		{"MA team p95", comparison.Baseline.MATeamLatencyP95MS, comparison.Candidate.MATeamLatencyP95MS, comparison.Delta.MATeamLatencyP95Percent, "%"},
		{"MA team tok/succ", comparison.Baseline.MATeamTokensPerSuccess, comparison.Candidate.MATeamTokensPerSuccess, comparison.Delta.MATeamTokensPerSuccessPct, "%"},
		{"MA cost/success", comparison.Baseline.MACostPerSuccessfulRunUSD, comparison.Candidate.MACostPerSuccessfulRunUSD, comparison.Delta.MACostPerSuccessPercent, "%"},
		{"MA coord tokens", float64(comparison.Baseline.MACoordinatorTokens), float64(comparison.Candidate.MACoordinatorTokens), comparison.Delta.MACoordinatorTokensPercent, "%"},
		{"MA sub tokens", float64(comparison.Baseline.MASubAgentTokens), float64(comparison.Candidate.MASubAgentTokens), comparison.Delta.MASubAgentTokensPercent, "%"},
	}
	if _, err := fmt.Fprintln(writer, "METRIC           BASELINE   CANDIDATE      DELTA"); err != nil {
		return err
	}
	for _, row := range rows {
		if _, err := fmt.Fprintf(
			writer,
			"%-16s %9.1f %11.1f %+9.1f%s\n",
			row.name,
			row.baseline,
			row.candidate,
			row.delta,
			row.unit,
		); err != nil {
			return err
		}
	}
	if err := writeOptionalComparisonRow(
		writer,
		"MA collab gain",
		comparison.Baseline.MACollaborationGain*100,
		comparison.Candidate.MACollaborationGain*100,
		comparison.Delta.MACollaborationGainPoints,
		comparison.Delta.MACollaborationGainValid,
	); err != nil {
		return err
	}
	if err := writeOptionalComparisonRow(
		writer,
		"MA fair gain",
		comparison.Baseline.MAFairCollaborationGain*100,
		comparison.Candidate.MAFairCollaborationGain*100,
		comparison.Delta.MAFairGainPoints,
		comparison.Delta.MAFairGainValid,
	); err != nil {
		return err
	}
	return nil
}

func writeOptionalComparisonRow(
	writer io.Writer,
	name string,
	baseline float64,
	candidate float64,
	delta float64,
	valid bool,
) error {
	if !valid {
		_, err := fmt.Fprintf(writer, "%-16s %9s %11s %9s\n", name, "n/a", "n/a", "n/a")
		return err
	}
	_, err := fmt.Fprintf(
		writer,
		"%-16s %9.1f %11.1f %+9.1fpp\n",
		name,
		baseline,
		candidate,
		delta,
	)
	return err
}

func collaborationGainAvailable(metrics Metrics) bool {
	if metrics.MACollaborationGainValid {
		return true
	}
	return metrics.MASoloEvaluated > 0 && metrics.MAAttempts > 0
}

func fairCollaborationGainAvailable(metrics Metrics) bool {
	if metrics.MAFairCollaborationValid {
		return true
	}
	team, hasTeam := metrics.MABaselines[MultiAgentBaselineTeam]
	return metrics.MASoloOpenBookEvaluated > 0 && hasTeam && team.Evaluated > 0
}

func faultObservationRate(metrics Metrics) float64 {
	if metrics.MAFaultObservationRate != 0 || metrics.MAFaultInjectionRate == 0 {
		return metrics.MAFaultObservationRate
	}
	return metrics.MAFaultInjectionRate
}

func percentagePointDelta(baseline, candidate float64) float64 {
	return (candidate - baseline) * 100
}

func percentDelta(baseline, candidate float64) float64 {
	if baseline == 0 {
		return 0
	}
	return (candidate - baseline) / baseline * 100
}
