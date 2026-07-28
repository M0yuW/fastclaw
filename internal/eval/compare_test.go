package eval

import (
	"bytes"
	"math"
	"strings"
	"testing"
)

func TestCompare(t *testing.T) {
	baseline := Report{
		Suite: "smoke",
		Metrics: Metrics{
			RunPassRate:               0.6,
			PassAt1:                   0.5,
			PassAtK:                   0.7,
			ConsistencyRate:           0.8,
			LatencyP50MS:              100,
			LatencyP95MS:              200,
			TokensPerPassedRun:        50,
			MATeamEstimatedCostUSD:    0.10,
			MACostPerSuccessfulRunUSD: 0.05,
			MACoordinatorTokens:       1000,
			MASubAgentTokens:          2000,
		},
	}
	candidate := Report{
		Suite: "smoke",
		Metrics: Metrics{
			RunPassRate:               0.8,
			PassAt1:                   0.7,
			PassAtK:                   0.9,
			ConsistencyRate:           0.9,
			LatencyP50MS:              90,
			LatencyP95MS:              240,
			TokensPerPassedRun:        40,
			MATeamEstimatedCostUSD:    0.08,
			MACostPerSuccessfulRunUSD: 0.04,
			MACoordinatorTokens:       900,
			MASubAgentTokens:          1600,
		},
	}
	comparison, err := Compare(baseline, candidate)
	if err != nil {
		t.Fatal(err)
	}
	if math.Abs(comparison.Delta.RunPassRatePoints-20) > 0.0001 {
		t.Fatalf("run pass rate delta = %v", comparison.Delta.RunPassRatePoints)
	}
	if math.Abs(comparison.Delta.LatencyP50Percent+10) > 0.0001 {
		t.Fatalf("p50 delta = %v", comparison.Delta.LatencyP50Percent)
	}
	if math.Abs(comparison.Delta.LatencyP95Percent-20) > 0.0001 {
		t.Fatalf("p95 delta = %v", comparison.Delta.LatencyP95Percent)
	}
	if math.Abs(comparison.Delta.MATeamCostPercent+20) > 0.0001 ||
		math.Abs(comparison.Delta.MACostPerSuccessPercent+20) > 0.0001 ||
		math.Abs(comparison.Delta.MASubAgentTokensPercent+20) > 0.0001 {
		t.Fatalf("multi-agent efficiency delta = %+v", comparison.Delta)
	}

	var output bytes.Buffer
	if err := WriteComparisonText(&output, comparison); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(output.String(), "run pass rate") ||
		!strings.Contains(output.String(), "+20.0pp") ||
		!strings.Contains(output.String(), "MA cost/success") {
		t.Fatalf("unexpected comparison output:\n%s", output.String())
	}
}
