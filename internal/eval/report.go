package eval

import (
	"encoding/json"
	"fmt"
	"io"
)

func WriteJSON(writer io.Writer, report Report) error {
	encoder := json.NewEncoder(writer)
	encoder.SetIndent("", "  ")
	return encoder.Encode(report)
}

func WriteText(writer io.Writer, report Report) error {
	metrics := report.Metrics
	if _, err := fmt.Fprintf(writer, "Eval suite: %s\n", report.Suite); err != nil {
		return err
	}
	if _, err := fmt.Fprintf(
		writer,
		"Runs: %d/%d passed (%.1f%%) | pass@1 %.1f%% | pass@k %.1f%% | consistency %.1f%%\n",
		metrics.PassedRuns,
		metrics.TotalRuns,
		metrics.RunPassRate*100,
		metrics.PassAt1*100,
		metrics.PassAtK*100,
		metrics.ConsistencyRate*100,
	); err != nil {
		return err
	}
	if _, err := fmt.Fprintf(
		writer,
		"Latency: p50 %.1f ms | p95 %.1f ms | tokens/success %.1f\n",
		metrics.LatencyP50MS,
		metrics.LatencyP95MS,
		metrics.TokensPerPassedRun,
	); err != nil {
		return err
	}
	if metrics.TotalToolCalls > 0 || metrics.ToolTraceGraders > 0 {
		if _, err := fmt.Fprintf(
			writer,
			"Tools: %d calls | trace accuracy %.1f%% | invalid call rate %.1f%%\n",
			metrics.TotalToolCalls,
			metrics.ToolTraceAccuracy*100,
			metrics.InvalidToolCallRate*100,
		); err != nil {
			return err
		}
	}
	if metrics.StateGraders > 0 || metrics.CommunicationGraders > 0 || metrics.PolicyGraders > 0 {
		if _, err := fmt.Fprintf(
			writer,
			"Tau: end-to-end %.1f%% | state %.1f%% | communicate %.1f%% | policy %.1f%% | turns %.1f\n",
			metrics.EndToEndTaskSuccess*100,
			metrics.StateAccuracy*100,
			metrics.CommunicationAccuracy*100,
			metrics.PolicyComplianceRate*100,
			metrics.AverageTurns,
		); err != nil {
			return err
		}
	}
	if metrics.SWESubmittedInstances > 0 {
		if _, err := fmt.Fprintf(
			writer,
			"SWE: %d/%d resolved (%.1f%%) | patches %.1f%% | tests executed %.1f%%\n",
			metrics.SWEResolvedInstances,
			metrics.SWESubmittedInstances,
			metrics.SWEResolutionRate*100,
			metrics.SWEPatchGenerationRate*100,
			metrics.SWETestExecutionRate*100,
		); err != nil {
			return err
		}
	}
	if metrics.MAAttempts > 0 {
		if _, err := fmt.Fprintf(
			writer,
			"Multi-agent: team %.1f%% | solo %.1f%% | gain %+.1f pp | KPI %.1f%% | coordination %.1f%% | delegations %.1f\n",
			metrics.MATeamSuccessRate*100,
			metrics.MASoloSuccessRate*100,
			metrics.MACollaborationGain*100,
			metrics.MAMilestoneKPI*100,
			metrics.MACoordinationScore*100,
			metrics.MAAverageDelegations,
		); err != nil {
			return err
		}
		if _, err := fmt.Fprintf(
			writer,
			"MA usage: coordinator %d tokens / $%.4f / %.1f ms | sub-agents %d tokens / $%.4f / %.1f ms | team $%.4f | cost/success $%.4f | pricing %.1f%%\n",
			metrics.MACoordinatorTokens,
			metrics.MACoordinatorCostUSD,
			metrics.MACoordinatorLatencyMS,
			metrics.MASubAgentTokens,
			metrics.MASubAgentCostUSD,
			metrics.MASubAgentLatencyMS,
			metrics.MATeamEstimatedCostUSD,
			metrics.MACostPerSuccessfulRunUSD,
			metrics.MAPricingCoverage*100,
		); err != nil {
			return err
		}
	}
	for _, evalCase := range report.Cases {
		status := "PASS"
		if !evalCase.PassAt1 {
			status = "FAIL"
		}
		if _, err := fmt.Fprintf(writer, "%s  %-24s", status, evalCase.ID); err != nil {
			return err
		}
		for _, attempt := range evalCase.Attempts {
			symbol := "✓"
			if !attempt.Passed {
				symbol = "✗"
			}
			if _, err := fmt.Fprintf(writer, " %s %.1fms", symbol, attempt.LatencyMS); err != nil {
				return err
			}
		}
		if _, err := fmt.Fprintln(writer); err != nil {
			return err
		}
	}
	return nil
}
