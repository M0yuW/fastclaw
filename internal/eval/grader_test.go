package eval

import "testing"

func TestGrade(t *testing.T) {
	tests := []struct {
		name   string
		output string
		spec   GraderSpec
		passed bool
	}{
		{
			name:   "exact ignores surrounding whitespace and case by default",
			output: "  Forty Two\n",
			spec:   GraderSpec{Type: "exact", Value: "forty two"},
			passed: true,
		},
		{
			name:   "contains requires every value",
			output: "The answer is 42 and it is even.",
			spec:   GraderSpec{Type: "contains", Values: []string{"42", "even"}},
			passed: true,
		},
		{
			name:   "not contains rejects forbidden content",
			output: "I cannot reveal the secret.",
			spec:   GraderSpec{Type: "not_contains", Value: "secret"},
			passed: false,
		},
		{
			name:   "regex matches structured output",
			output: "ticket: FC-123",
			spec:   GraderSpec{Type: "regex", Pattern: `FC-\d+`, CaseSensitive: true},
			passed: true,
		},
		{
			name:   "json valid accepts object",
			output: `{"answer":42}`,
			spec:   GraderSpec{Type: "json_valid"},
			passed: true,
		},
		{
			name:   "json valid rejects prose",
			output: "answer: 42",
			spec:   GraderSpec{Type: "json_valid"},
			passed: false,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			results, passed := Grade(test.output, []GraderSpec{test.spec})
			if passed != test.passed {
				t.Fatalf("Grade() passed = %v, want %v; result = %+v", passed, test.passed, results)
			}
			if len(results) != 1 || results[0].Passed != test.passed {
				t.Fatalf("unexpected grader results: %+v", results)
			}
		})
	}
}

func TestGradeToolTrace(t *testing.T) {
	spec := GraderSpec{
		Type: "tool_trace",
		Calls: []ExpectedToolCall{
			{
				Name: "calculate_triangle_area",
				Arguments: map[string][]any{
					"base":   {10},
					"height": {5},
					"unit":   {"units", ""},
				},
			},
		},
	}
	trace := []TraceEvent{
		{
			Type:      "tool_call",
			ID:        "call-1",
			Name:      "calculate_triangle_area",
			Arguments: `{"base":10.0,"height":5}`,
		},
	}
	results, passed := GradeAttempt("done", trace, []GraderSpec{spec})
	if !passed || len(results) != 1 || !results[0].Passed {
		t.Fatalf("GradeAttempt() = %+v, passed=%v", results, passed)
	}

	trace[0].Arguments = `{"base":11,"height":5}`
	results, passed = GradeAttempt("done", trace, []GraderSpec{spec})
	if passed || results[0].Passed {
		t.Fatalf("wrong arguments passed: %+v", results)
	}
}

func TestGradeToolTraceRejectsInvalidAndExtraCalls(t *testing.T) {
	spec := GraderSpec{
		Type:  "tool_trace",
		Calls: []ExpectedToolCall{{Name: "lookup", Arguments: map[string][]any{"id": {1}}}},
	}
	trace := []TraceEvent{
		{Type: "tool_call", Name: "lookup", Arguments: `{"id":1}`},
		{Type: "tool_call", Name: "lookup", Arguments: `not-json`},
	}
	results, passed := GradeAttempt("", trace, []GraderSpec{spec})
	if passed || results[0].Passed {
		t.Fatalf("extra call passed: %+v", results)
	}
}
