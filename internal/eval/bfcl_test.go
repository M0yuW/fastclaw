package eval

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestImportBFCL(t *testing.T) {
	directory := t.TempDir()
	questionsPath := filepath.Join(directory, "questions.jsonl")
	answersPath := filepath.Join(directory, "answers.jsonl")
	questions := `{"id":"simple_python_0","question":[[{"role":"user","content":"Find the area."}]],"function":[{"name":"triangle.area","description":"area","parameters":{"type":"dict","properties":{"base":{"type":"float"}},"required":["base"]}}]}
{"id":"simple_python_1","question":[[{"role":"user","content":"Ignore me."}]],"function":[{"name":"other","description":"other","parameters":{"type":"dict","properties":{}}}]}
`
	answers := `{"id":"simple_python_0","ground_truth":[{"triangle.area":{"base":[10,10.0],"unit":["units",""]}}]}
{"id":"simple_python_1","ground_truth":[{"other":{}}]}
`
	if err := os.WriteFile(questionsPath, []byte(questions), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(answersPath, []byte(answers), 0o600); err != nil {
		t.Fatal(err)
	}

	suite, err := ImportBFCL(questionsPath, answersPath, BFCLImportOptions{
		IDs:     []string{"simple_python_0"},
		AgentID: "bfcl-agent",
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(suite.Cases) != 1 || suite.Cases[0].Prompt != "Find the area." {
		t.Fatalf("unexpected suite: %+v", suite)
	}
	if suite.Cases[0].Tools[0].Parameters["type"] != "object" {
		t.Fatalf("top-level schema was not normalized: %+v", suite.Cases[0].Tools[0].Parameters)
	}
	properties := suite.Cases[0].Tools[0].Parameters["properties"].(map[string]any)
	if properties["base"].(map[string]any)["type"] != "number" {
		t.Fatalf("nested schema was not normalized: %+v", properties)
	}
	baseAlternative := suite.Cases[0].Graders[0].Calls[0].Arguments["base"][0]
	if _, ok := baseAlternative.(int64); !ok {
		t.Fatalf("ground-truth number type = %T, want int64", baseAlternative)
	}

	var yamlOutput bytes.Buffer
	if err := WriteSuiteYAML(&yamlOutput, suite); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(yamlOutput.String(), "type: tool_trace") || !strings.Contains(yamlOutput.String(), "timeout: 2m0s") {
		t.Fatalf("unexpected suite YAML:\n%s", yamlOutput.String())
	}
	generatedPath := filepath.Join(directory, "suite.yaml")
	if err := os.WriteFile(generatedPath, yamlOutput.Bytes(), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadSuite(generatedPath); err != nil {
		t.Fatalf("generated suite does not round-trip: %v", err)
	}
}

func TestBundledBFCLSubsetLoads(t *testing.T) {
	path := filepath.Join("..", "..", "evals", "bfcl-v4-simple-subset.yaml")
	suite, err := LoadSuite(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(suite.Cases) != 3 {
		t.Fatalf("case count = %d", len(suite.Cases))
	}
}
