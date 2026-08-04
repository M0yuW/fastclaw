package eval

import (
	"bytes"
	"context"
	"encoding/json"
	"path/filepath"
	"strings"
	"testing"
)

const fixedSlugSource = `package slug

import (
	"regexp"
	"strings"
)

var nonAlphanumeric = regexp.MustCompile(` + "`[^a-z0-9]+`" + `)

func Slugify(input string) string {
	lower := strings.ToLower(input)
	return strings.Trim(nonAlphanumeric.ReplaceAllString(lower, "-"), "-")
}
`

func TestLoadBundledSWESuite(t *testing.T) {
	path := filepath.Join("..", "..", "evals", "swebench-local-subset.yaml")
	suite, err := LoadSWESuite(path)
	if err != nil {
		t.Fatal(err)
	}
	if suite.Name != "swebench-style-local-subset" || len(suite.Cases) != 3 {
		t.Fatalf("unexpected suite: %s, cases = %d", suite.Name, len(suite.Cases))
	}
}

func TestBundledSWEFixturesHaveFailingBaselines(t *testing.T) {
	path := filepath.Join("..", "..", "evals", "swebench-local-subset.yaml")
	suite, err := LoadSWESuite(path)
	if err != nil {
		t.Fatal(err)
	}
	for _, evalCase := range suite.Cases {
		fixture, err := resolveSWEFixture(suite.Source, evalCase.Fixture)
		if err != nil {
			t.Fatal(err)
		}
		if err := verifySWEBaseline(t.Context(), fixture, evalCase.TestCommand); err != nil {
			t.Fatalf("%s baseline: %v", evalCase.InstanceID, err)
		}
	}
}

func TestSWERunnerGeneratesPatchAndResolvesHiddenTests(t *testing.T) {
	path := filepath.Join("..", "..", "evals", "swebench-local-subset.yaml")
	suite, err := LoadSWESuite(path)
	if err != nil {
		t.Fatal(err)
	}
	suite.Cases = suite.Cases[:1]
	suite.Defaults.Repetitions = 1

	runner := SWERunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			if len(request.Tools) != 3 {
				t.Fatalf("tools = %d", len(request.Tools))
			}
			files := request.State["files"].(map[string]any)
			if _, exposed := files["slug_test.go"]; exposed {
				t.Fatal("hidden tests were exposed to the agent")
			}
			files["slug.go"] = fixedSlugSource
			return ExecutionResponse{
				Output: "Implemented normalized separators.",
				Model:  "fake-coder",
				State:  request.State,
				Trace: []TraceEvent{
					{Type: "tool_call", Name: "write_file", Arguments: `{"path":"slug.go"}`},
				},
			}, nil
		}),
	}

	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	attempt := report.Cases[0].Attempts[0]
	if !attempt.Passed || !attempt.Completed || !attempt.TestsPassed {
		t.Fatalf("unexpected attempt: %+v", attempt)
	}
	if !strings.Contains(attempt.Patch, "diff --git a/slug.go b/slug.go") {
		t.Fatalf("unexpected patch:\n%s", attempt.Patch)
	}
	metrics := report.Metrics
	if metrics.SWEResolutionRate != 1 ||
		metrics.SWEPatchGenerationRate != 1 ||
		metrics.SWETestExecutionRate != 1 {
		t.Fatalf("unexpected SWE metrics: %+v", metrics)
	}

	var predictions bytes.Buffer
	if err := WriteSWEPredictions(&predictions, report); err != nil {
		t.Fatal(err)
	}
	var prediction SWEPrediction
	if err := json.Unmarshal(predictions.Bytes(), &prediction); err != nil {
		t.Fatal(err)
	}
	if prediction.InstanceID != suite.Cases[0].InstanceID ||
		prediction.ModelNameOrPath != "fake-coder" ||
		prediction.ModelPatch != attempt.Patch {
		t.Fatalf("unexpected prediction: %+v", prediction)
	}
}

func TestSWERunnerRejectsUndeclaredFiles(t *testing.T) {
	path := filepath.Join("..", "..", "evals", "swebench-local-subset.yaml")
	suite, err := LoadSWESuite(path)
	if err != nil {
		t.Fatal(err)
	}
	suite.Cases = suite.Cases[:1]
	suite.Cases[0].SkipBaselineCheck = true
	suite.Defaults.Repetitions = 1

	runner := SWERunner{
		Executor: executorFunc(func(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
			request.State["files"].(map[string]any)["slug_test.go"] = "package slug"
			return ExecutionResponse{State: request.State}, nil
		}),
	}
	report, err := runner.Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	attempt := report.Cases[0].Attempts[0]
	if attempt.Passed || attempt.Completed || !strings.Contains(attempt.Error, "added or removed") {
		t.Fatalf("unexpected attempt: %+v", attempt)
	}
	if report.Metrics.SWEResolutionRate != 0 || report.Metrics.SWETestExecutionRate != 0 {
		t.Fatalf("unexpected metrics: %+v", report.Metrics)
	}
}
