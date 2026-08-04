package eval

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestLoadSuite(t *testing.T) {
	path := filepath.Join(t.TempDir(), "suite.yaml")
	content := `
version: 1
name: smoke
defaults:
  agent_id: reviewer
  repetitions: 3
  timeout: 15s
cases:
  - id: json-answer
    prompt: Return JSON.
    tags: [format]
    graders:
      - type: json_valid
`
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}

	suite, err := LoadSuite(path)
	if err != nil {
		t.Fatal(err)
	}
	if suite.Name != "smoke" || suite.Defaults.AgentID != "reviewer" {
		t.Fatalf("unexpected suite: %+v", suite)
	}
	if suite.Defaults.Repetitions != 3 || suite.Defaults.Timeout.Value() != 15*time.Second {
		t.Fatalf("unexpected defaults: %+v", suite.Defaults)
	}
	if suite.Source != path {
		t.Fatalf("source = %q, want %q", suite.Source, path)
	}
}

func TestLoadSuiteRejectsUnknownFields(t *testing.T) {
	path := filepath.Join(t.TempDir(), "suite.yaml")
	content := `
version: 1
name: smoke
unknown: true
cases:
  - id: answer
    prompt: Answer.
    graders:
      - type: exact
        value: yes
`
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}

	_, err := LoadSuite(path)
	if err == nil || !strings.Contains(err.Error(), "field unknown not found") {
		t.Fatalf("LoadSuite() error = %v", err)
	}
}

func TestSuiteValidateRejectsInvalidCases(t *testing.T) {
	suite := Suite{
		Version: SuiteVersion,
		Name:    "invalid",
		Cases: []Case{
			{
				ID:      "duplicate",
				Prompt:  "first",
				Graders: []GraderSpec{{Type: "exact", Value: "ok"}},
			},
			{
				ID:      "duplicate",
				Prompt:  "second",
				Graders: []GraderSpec{{Type: "regex", Pattern: "["}},
			},
		},
	}
	if err := suite.Validate(); err == nil || !strings.Contains(err.Error(), "duplicate id") {
		t.Fatalf("Validate() error = %v", err)
	}
}
