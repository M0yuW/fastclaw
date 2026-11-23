package main

import (
	"math"
	"path/filepath"
	"testing"

	evalpkg "github.com/fastclaw-ai/fastclaw/internal/eval"
)

func TestCurrentGraderReanalysisMatchesAuditedCounts(t *testing.T) {
	root, err := findRoot()
	if err != nil {
		t.Fatal(err)
	}
	suite, err := evalpkg.LoadMultiAgentSuite(filepath.Join(root, "evals", "multiagent-finance-runtime.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	outcomes, err := regradeArtifacts(suite, artifactPaths(root, 2, 5), currentOptions())
	if err != nil {
		t.Fatal(err)
	}

	wantPasses := map[string]int{
		evalpkg.MultiAgentBaselineSoloOpenBook: 15,
		evalpkg.MultiAgentBaselineSoloTwoPass:  16,
		evalpkg.MultiAgentBaselineTeam:         18,
		evalpkg.MultiAgentBaselineOracleTeam:   18,
	}
	for mode, want := range wantPasses {
		summary := summarizeModes(outcomes)[mode]
		if summary.Passed != want || summary.Total != 24 {
			t.Fatalf("%s = %d/%d, want %d/24", mode, summary.Passed, summary.Total, want)
		}
	}

	comparison := paired(outcomes, evalpkg.MultiAgentBaselineTeam, evalpkg.MultiAgentBaselineSoloOpenBook)
	if comparison.LeftOnly != 6 || comparison.RightOnly != 3 ||
		math.Abs(comparison.ExactTwoSided-0.5078125) > 1e-12 {
		t.Fatalf("unexpected Team/Open pairing: %+v", comparison)
	}
}

func TestCurrentGraderReanalysisQuantifiesStoredDrift(t *testing.T) {
	root, err := findRoot()
	if err != nil {
		t.Fatal(err)
	}
	suite, err := evalpkg.LoadMultiAgentSuite(filepath.Join(root, "evals", "multiagent-finance-runtime.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	drift := calculateDrift(suite, artifactPaths(root, 1, 5), currentOptions())
	want := []int{4, 1, 2, 1, 0}
	for index, entry := range drift {
		if entry.StoredDifferences != want[index] {
			t.Fatalf("%s drift = %d, want %d", entry.Artifact, entry.StoredDifferences, want[index])
		}
	}
}
