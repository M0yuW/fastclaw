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
		closedGain := formatGain(metrics.MACollaborationGainValid, metrics.MACollaborationGain)
		soloClosed := formatRate(metrics.MASoloEvaluated > 0, metrics.MASoloSuccessRate)
		if _, err := fmt.Fprintf(
			writer,
			"Multi-agent: team %.1f%% | solo closed %s | closed gain %s | KPI %.1f%% | coordination %.1f%% | delegations %.1f\n",
			metrics.MATeamSuccessRate*100,
			soloClosed,
			closedGain,
			metrics.MAMilestoneKPI*100,
			metrics.MACoordinationScore*100,
			metrics.MAAverageDelegations,
		); err != nil {
			return err
		}
		_, hasSoloOpenBook := metrics.MABaselines[MultiAgentBaselineSoloOpenBook]
		_, hasOracleTeam := metrics.MABaselines[MultiAgentBaselineOracleTeam]
		if hasSoloOpenBook || hasOracleTeam {
			fairGain := formatGain(metrics.MAFairCollaborationValid, metrics.MAFairCollaborationGain)
			teamOutcome := formatRate(metrics.MATeamOutcomeEvaluated > 0, metrics.MATeamOutcomeSuccessRate)
			soloOpen := formatRate(metrics.MASoloOpenBookEvaluated > 0, metrics.MASoloOpenBookSuccessRate)
			oracleTeam := formatRate(metrics.MAOracleTeamEvaluated > 0, metrics.MAOracleTeamSuccessRate)
			if _, err := fmt.Fprintf(
				writer,
				"MA fair baselines: team outcome %s | solo open %s | fair gain %s | oracle team %s\n",
				teamOutcome,
				soloOpen,
				fairGain,
				oracleTeam,
			); err != nil {
				return err
			}
		}
		if metrics.MAFaultInjectedAttempts > 0 {
			if _, err := fmt.Fprintf(
				writer,
				"MA faults: observed %.1f%% | attribution %.1f%% | graceful degradation %.1f%% | faults with unsupported claims %.1f%% | uncorrelated results %d\n",
				metrics.MAFaultObservationRate*100,
				metrics.MAFaultAttributionRate*100,
				metrics.MAGracefulDegradationRate*100,
				metrics.MAUnsupportedClaimRate*100,
				metrics.MAUncorrelatedToolResults,
			); err != nil {
				return err
			}
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
		if _, err := fmt.Fprintf(
			writer,
			"MA team outcome usage: %d tokens | %.1f tokens/success | p50 %.1f ms | p95 %.1f ms | total eval cost $%.4f\n",
			metrics.MATeamTotalTokens,
			metrics.MATeamTokensPerSuccess,
			metrics.MATeamLatencyP50MS,
			metrics.MATeamLatencyP95MS,
			metrics.MATotalEstimatedCostUSD,
		); err != nil {
			return err
		}
		for _, mode := range []string{
			MultiAgentBaselineSoloClosedBook,
			MultiAgentBaselineSoloOpenBook,
			MultiAgentBaselineTeam,
			MultiAgentBaselineOracleTeam,
		} {
			baseline, exists := metrics.MABaselines[mode]
			if !exists {
				continue
			}
			if _, err := fmt.Fprintf(
				writer,
				"MA baseline %-16s valid %d | errors %d | success %.1f%% | tokens %d | cost $%.4f | avg valid latency %.1f ms\n",
				mode,
				baseline.Evaluated,
				baseline.Errored,
				baseline.SuccessRate*100,
				baseline.TotalTokens,
				baseline.EstimatedCostUSD,
				baseline.AverageLatencyMS,
			); err != nil {
				return err
			}
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
		for _, attempt := range evalCase.Attempts {
			for _, baseline := range attempt.Baselines {
				if baseline.Error == "" {
					continue
				}
				if _, err := fmt.Fprintf(
					writer,
					"    baseline %s ERROR: %s\n",
					baseline.Mode,
					baseline.Error,
				); err != nil {
					return err
				}
			}
		}
	}
	return nil
}

func formatGain(valid bool, value float64) string {
	if !valid {
		return "n/a"
	}
	return fmt.Sprintf("%+.1f pp", value*100)
}

func formatRate(valid bool, value float64) string {
	if !valid {
		return "n/a"
	}
	return fmt.Sprintf("%.1f%%", value*100)
}
