package eval

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"regexp"
	"strings"
)

func Grade(output string, specs []GraderSpec) ([]GraderResult, bool) {
	return GradeAttempt(output, nil, specs)
}

func GradeAttempt(output string, trace []TraceEvent, specs []GraderSpec) ([]GraderResult, bool) {
	results := make([]GraderResult, 0, len(specs))
	passed := true
	for _, spec := range specs {
		result := gradeOne(output, trace, spec)
		results = append(results, result)
		passed = passed && result.Passed
	}
	return results, passed
}

func gradeOne(output string, trace []TraceEvent, spec GraderSpec) GraderResult {
	switch spec.Type {
	case "exact":
		actual := normalize(output, spec.CaseSensitive)
		expected := normalize(spec.Value, spec.CaseSensitive)
		if actual == expected {
			return GraderResult{Type: spec.Type, Passed: true}
		}
		return GraderResult{
			Type:    spec.Type,
			Passed:  false,
			Message: fmt.Sprintf("expected exact value %q", spec.Value),
		}
	case "contains":
		for _, value := range graderValues(spec) {
			if !strings.Contains(normalize(output, spec.CaseSensitive), normalize(value, spec.CaseSensitive)) {
				return GraderResult{
					Type:    spec.Type,
					Passed:  false,
					Message: fmt.Sprintf("missing required value %q", value),
				}
			}
		}
		return GraderResult{Type: spec.Type, Passed: true}
	case "not_contains":
		for _, value := range graderValues(spec) {
			if strings.Contains(normalize(output, spec.CaseSensitive), normalize(value, spec.CaseSensitive)) {
				return GraderResult{
					Type:    spec.Type,
					Passed:  false,
					Message: fmt.Sprintf("found forbidden value %q", value),
				}
			}
		}
		return GraderResult{Type: spec.Type, Passed: true}
	case "regex":
		pattern := spec.Pattern
		if !spec.CaseSensitive {
			pattern = "(?i)" + pattern
		}
		matched, err := regexp.MatchString(pattern, output)
		if err != nil {
			return GraderResult{Type: spec.Type, Passed: false, Message: err.Error()}
		}
		if !matched {
			return GraderResult{
				Type:    spec.Type,
				Passed:  false,
				Message: fmt.Sprintf("output did not match %q", spec.Pattern),
			}
		}
		return GraderResult{Type: spec.Type, Passed: true}
	case "json_valid":
		if json.Valid([]byte(strings.TrimSpace(output))) {
			return GraderResult{Type: spec.Type, Passed: true}
		}
		return GraderResult{Type: spec.Type, Passed: false, Message: "output is not valid JSON"}
	case "tool_trace":
		return gradeToolTrace(trace, spec)
	default:
		return GraderResult{Type: spec.Type, Passed: false, Message: "unsupported grader type"}
	}
}

func gradeToolTrace(trace []TraceEvent, spec GraderSpec) GraderResult {
	actual := make([]TraceEvent, 0)
	for _, event := range trace {
		if event.Type == "tool_call" {
			actual = append(actual, event)
		}
	}
	if len(actual) < len(spec.Calls) {
		return GraderResult{
			Type:    spec.Type,
			Passed:  false,
			Message: fmt.Sprintf("expected %d tool calls, got %d", len(spec.Calls), len(actual)),
		}
	}
	if !spec.AllowExtra && len(actual) != len(spec.Calls) {
		return GraderResult{
			Type:    spec.Type,
			Passed:  false,
			Message: fmt.Sprintf("expected exactly %d tool calls, got %d", len(spec.Calls), len(actual)),
		}
	}

	if spec.OrderSensitive {
		for index, expected := range spec.Calls {
			if message := matchToolCall(actual[index], expected, spec.AllowExtra); message != "" {
				return GraderResult{
					Type:    spec.Type,
					Passed:  false,
					Message: fmt.Sprintf("tool call %d: %s", index+1, message),
				}
			}
		}
		return GraderResult{Type: spec.Type, Passed: true}
	}

	used := make([]bool, len(actual))
	for expectedIndex, expected := range spec.Calls {
		matched := false
		var lastMessage string
		for actualIndex, candidate := range actual {
			if used[actualIndex] {
				continue
			}
			if message := matchToolCall(candidate, expected, spec.AllowExtra); message == "" {
				used[actualIndex] = true
				matched = true
				break
			} else {
				lastMessage = message
			}
		}
		if !matched {
			return GraderResult{
				Type:    spec.Type,
				Passed:  false,
				Message: fmt.Sprintf("expected tool call %d was not matched: %s", expectedIndex+1, lastMessage),
			}
		}
	}
	return GraderResult{Type: spec.Type, Passed: true}
}

func matchToolCall(actual TraceEvent, expected ExpectedToolCall, allowExtra bool) string {
	if actual.Name != expected.Name {
		return fmt.Sprintf("expected function %q, got %q", expected.Name, actual.Name)
	}
	arguments := make(map[string]any)
	decoder := json.NewDecoder(strings.NewReader(actual.Arguments))
	decoder.UseNumber()
	if err := decoder.Decode(&arguments); err != nil {
		return fmt.Sprintf("arguments are not a JSON object: %v", err)
	}
	if err := ensureJSONEOF(decoder); err != nil {
		return fmt.Sprintf("arguments are not valid JSON: %v", err)
	}
	for name, alternatives := range expected.Arguments {
		actualValue, exists := arguments[name]
		if !exists {
			if acceptsOmission(alternatives) {
				continue
			}
			return fmt.Sprintf("missing argument %q", name)
		}
		matched := false
		for _, expectedValue := range alternatives {
			if valuesEquivalent(actualValue, expectedValue) {
				matched = true
				break
			}
		}
		if !matched {
			return fmt.Sprintf("argument %q has unexpected value %v", name, actualValue)
		}
	}
	if !allowExtra {
		for name := range arguments {
			if _, exists := expected.Arguments[name]; !exists {
				return fmt.Sprintf("unexpected argument %q", name)
			}
		}
	}
	return ""
}

func ensureJSONEOF(decoder *json.Decoder) error {
	var extra any
	err := decoder.Decode(&extra)
	if err == io.EOF {
		return nil
	}
	if err == nil {
		return fmt.Errorf("multiple JSON values")
	}
	return err
}

func acceptsOmission(alternatives []any) bool {
	for _, alternative := range alternatives {
		if value, ok := alternative.(string); ok && value == "" {
			return true
		}
	}
	return false
}

func valuesEquivalent(actual, expected any) bool {
	actualNumber, actualIsNumber := numericValue(actual)
	expectedNumber, expectedIsNumber := numericValue(expected)
	if actualIsNumber && expectedIsNumber {
		return actualNumber == expectedNumber
	}
	actualJSON, actualErr := json.Marshal(actual)
	expectedJSON, expectedErr := json.Marshal(expected)
	return actualErr == nil && expectedErr == nil && bytes.Equal(actualJSON, expectedJSON)
}

func numericValue(value any) (float64, bool) {
	switch typed := value.(type) {
	case json.Number:
		number, err := typed.Float64()
		return number, err == nil
	case int:
		return float64(typed), true
	case int8:
		return float64(typed), true
	case int16:
		return float64(typed), true
	case int32:
		return float64(typed), true
	case int64:
		return float64(typed), true
	case uint:
		return float64(typed), true
	case uint8:
		return float64(typed), true
	case uint16:
		return float64(typed), true
	case uint32:
		return float64(typed), true
	case uint64:
		return float64(typed), true
	case float32:
		return float64(typed), true
	case float64:
		return typed, true
	default:
		return 0, false
	}
}

func normalize(value string, caseSensitive bool) string {
	value = strings.TrimSpace(value)
	if !caseSensitive {
		value = strings.ToLower(value)
	}
	return value
}
