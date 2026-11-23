package eval

import (
	"errors"
	"fmt"
	"io"
	"os"
	"regexp"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

const defaultTimeout = 2 * time.Minute

func LoadSuite(path string) (Suite, error) {
	file, err := os.Open(path)
	if err != nil {
		return Suite{}, fmt.Errorf("open eval suite: %w", err)
	}
	defer file.Close()

	var suite Suite
	decoder := yaml.NewDecoder(file)
	decoder.KnownFields(true)
	if err := decoder.Decode(&suite); err != nil {
		return Suite{}, fmt.Errorf("decode eval suite: %w", err)
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		if err == nil {
			return Suite{}, errors.New("decode eval suite: multiple YAML documents are not supported")
		}
		return Suite{}, fmt.Errorf("decode eval suite: %w", err)
	}
	suite.Source = path
	if err := suite.Validate(); err != nil {
		return Suite{}, err
	}
	return suite, nil
}

func (s *Suite) Validate() error {
	if s.Version != SuiteVersion {
		return fmt.Errorf("eval suite version must be %d", SuiteVersion)
	}
	if strings.TrimSpace(s.Name) == "" {
		return errors.New("eval suite name is required")
	}
	if len(s.Cases) == 0 {
		return errors.New("eval suite must contain at least one case")
	}
	if s.Defaults.Repetitions < 0 {
		return errors.New("default repetitions cannot be negative")
	}
	if s.Defaults.Timeout.Value() < 0 {
		return errors.New("default timeout cannot be negative")
	}

	seen := make(map[string]struct{}, len(s.Cases))
	for index := range s.Cases {
		evalCase := &s.Cases[index]
		if strings.TrimSpace(evalCase.ID) == "" {
			return fmt.Errorf("case %d: id is required", index+1)
		}
		if _, exists := seen[evalCase.ID]; exists {
			return fmt.Errorf("case %q: duplicate id", evalCase.ID)
		}
		seen[evalCase.ID] = struct{}{}
		if strings.TrimSpace(evalCase.Prompt) == "" {
			return fmt.Errorf("case %q: prompt is required", evalCase.ID)
		}
		if evalCase.Repetitions < 0 {
			return fmt.Errorf("case %q: repetitions cannot be negative", evalCase.ID)
		}
		if evalCase.Timeout.Value() < 0 {
			return fmt.Errorf("case %q: timeout cannot be negative", evalCase.ID)
		}
		if len(evalCase.Graders) == 0 {
			return fmt.Errorf("case %q: at least one grader is required", evalCase.ID)
		}
		toolNames := make(map[string]struct{}, len(evalCase.Tools))
		for toolIndex, tool := range evalCase.Tools {
			if strings.TrimSpace(tool.Name) == "" {
				return fmt.Errorf("case %q tool %d: name is required", evalCase.ID, toolIndex+1)
			}
			if _, exists := toolNames[tool.Name]; exists {
				return fmt.Errorf("case %q tool %d: duplicate name %q", evalCase.ID, toolIndex+1, tool.Name)
			}
			toolNames[tool.Name] = struct{}{}
			if tool.Parameters == nil {
				return fmt.Errorf("case %q tool %d: parameters are required", evalCase.ID, toolIndex+1)
			}
		}
		for graderIndex, grader := range evalCase.Graders {
			if err := validateGrader(grader); err != nil {
				return fmt.Errorf("case %q grader %d: %w", evalCase.ID, graderIndex+1, err)
			}
			if grader.Type == "tool_trace" {
				for callIndex, call := range grader.Calls {
					if _, exists := toolNames[call.Name]; !exists {
						return fmt.Errorf(
							"case %q grader %d call %d: tool %q is not defined",
							evalCase.ID,
							graderIndex+1,
							callIndex+1,
							call.Name,
						)
					}
				}
			}
		}
	}
	return nil
}

func (s Suite) repetitions(evalCase Case, override int) int {
	if override > 0 {
		return override
	}
	if evalCase.Repetitions > 0 {
		return evalCase.Repetitions
	}
	if s.Defaults.Repetitions > 0 {
		return s.Defaults.Repetitions
	}
	return 1
}

func (s Suite) timeout(evalCase Case, override time.Duration) time.Duration {
	if override > 0 {
		return override
	}
	if evalCase.Timeout.Value() > 0 {
		return evalCase.Timeout.Value()
	}
	if s.Defaults.Timeout.Value() > 0 {
		return s.Defaults.Timeout.Value()
	}
	return defaultTimeout
}

func validateGrader(spec GraderSpec) error {
	switch spec.Type {
	case "exact":
		if spec.Value == "" {
			return errors.New("exact grader requires value")
		}
	case "contains", "not_contains":
		if len(graderValues(spec)) == 0 {
			return fmt.Errorf("%s grader requires value or values", spec.Type)
		}
	case "regex":
		if spec.Pattern == "" {
			return errors.New("regex grader requires pattern")
		}
		pattern := spec.Pattern
		if !spec.CaseSensitive {
			pattern = "(?i)" + pattern
		}
		if _, err := regexp.Compile(pattern); err != nil {
			return fmt.Errorf("invalid regex pattern: %w", err)
		}
	case "json_valid":
	case "tool_trace":
		for index, call := range spec.Calls {
			if strings.TrimSpace(call.Name) == "" {
				return fmt.Errorf("tool_trace call %d requires name", index+1)
			}
			for argument, alternatives := range call.Arguments {
				if strings.TrimSpace(argument) == "" {
					return fmt.Errorf("tool_trace call %d has an empty argument name", index+1)
				}
				if len(alternatives) == 0 {
					return fmt.Errorf(
						"tool_trace call %d argument %q requires at least one accepted value",
						index+1,
						argument,
					)
				}
			}
		}
	default:
		return fmt.Errorf("unsupported grader type %q", spec.Type)
	}
	return nil
}

func graderValues(spec GraderSpec) []string {
	if len(spec.Values) > 0 {
		return spec.Values
	}
	if spec.Value != "" {
		return []string{spec.Value}
	}
	return nil
}
