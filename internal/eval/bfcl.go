package eval

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"

	"gopkg.in/yaml.v3"
)

type BFCLImportOptions struct {
	IDs     []string
	Limit   int
	AgentID string
}

type bfclQuestion struct {
	ID       string          `json:"id"`
	Question [][]bfclMessage `json:"question"`
	Function []bfclFunction  `json:"function"`
}

type bfclMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type bfclFunction struct {
	Name        string         `json:"name"`
	Description string         `json:"description"`
	Parameters  map[string]any `json:"parameters"`
}

type bfclAnswer struct {
	ID          string                        `json:"id"`
	GroundTruth []map[string]map[string][]any `json:"ground_truth"`
}

func ImportBFCL(questionsPath, answersPath string, options BFCLImportOptions) (Suite, error) {
	if options.Limit < 0 {
		return Suite{}, errors.New("BFCL import limit cannot be negative")
	}
	questions, questionOrder, err := loadBFCLQuestions(questionsPath)
	if err != nil {
		return Suite{}, err
	}
	answers, err := loadBFCLAnswers(answersPath)
	if err != nil {
		return Suite{}, err
	}

	ids := options.IDs
	if len(ids) == 0 {
		ids = questionOrder
	}
	if options.Limit > 0 && len(ids) > options.Limit {
		ids = ids[:options.Limit]
	}
	suite := Suite{
		Version:     SuiteVersion,
		Name:        "bfcl-v4-simple-subset",
		Description: "BFCL V4 single-turn subset imported for FastClaw tool-trace evaluation.",
		Defaults: Defaults{
			AgentID:     options.AgentID,
			Repetitions: 1,
			Timeout:     Duration(defaultTimeout),
		},
		Cases: make([]Case, 0, len(ids)),
	}
	seen := make(map[string]struct{}, len(ids))
	for _, id := range ids {
		if _, exists := seen[id]; exists {
			return Suite{}, fmt.Errorf("BFCL import contains duplicate id %q", id)
		}
		seen[id] = struct{}{}
		question, exists := questions[id]
		if !exists {
			return Suite{}, fmt.Errorf("BFCL question %q not found", id)
		}
		answer, exists := answers[id]
		if !exists {
			return Suite{}, fmt.Errorf("BFCL answer %q not found", id)
		}
		evalCase, err := convertBFCLCase(question, answer)
		if err != nil {
			return Suite{}, fmt.Errorf("BFCL case %q: %w", id, err)
		}
		suite.Cases = append(suite.Cases, evalCase)
	}
	if err := suite.Validate(); err != nil {
		return Suite{}, err
	}
	return suite, nil
}

func WriteSuiteYAML(writer io.Writer, suite Suite) error {
	encoder := yaml.NewEncoder(writer)
	encoder.SetIndent(2)
	defer encoder.Close()
	return encoder.Encode(suite)
}

func loadBFCLQuestions(path string) (map[string]bfclQuestion, []string, error) {
	var records []bfclQuestion
	if err := readJSONL(path, &records); err != nil {
		return nil, nil, fmt.Errorf("load BFCL questions: %w", err)
	}
	byID := make(map[string]bfclQuestion, len(records))
	order := make([]string, 0, len(records))
	for _, record := range records {
		if record.ID == "" {
			return nil, nil, errors.New("question id is required")
		}
		if _, exists := byID[record.ID]; exists {
			return nil, nil, fmt.Errorf("duplicate question id %q", record.ID)
		}
		byID[record.ID] = record
		order = append(order, record.ID)
	}
	return byID, order, nil
}

func loadBFCLAnswers(path string) (map[string]bfclAnswer, error) {
	var records []bfclAnswer
	if err := readJSONL(path, &records); err != nil {
		return nil, fmt.Errorf("load BFCL answers: %w", err)
	}
	byID := make(map[string]bfclAnswer, len(records))
	for _, record := range records {
		if record.ID == "" {
			return nil, errors.New("answer id is required")
		}
		if _, exists := byID[record.ID]; exists {
			return nil, fmt.Errorf("duplicate answer id %q", record.ID)
		}
		byID[record.ID] = record
	}
	return byID, nil
}

func readJSONL[T any](path string, records *[]T) error {
	file, err := os.Open(path)
	if err != nil {
		return err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 64<<10), 8<<20)
	line := 0
	for scanner.Scan() {
		line++
		content := strings.TrimSpace(scanner.Text())
		if content == "" {
			continue
		}
		var record T
		decoder := json.NewDecoder(strings.NewReader(content))
		decoder.UseNumber()
		if err := decoder.Decode(&record); err != nil {
			return fmt.Errorf("line %d: %w", line, err)
		}
		*records = append(*records, record)
	}
	if err := scanner.Err(); err != nil {
		return err
	}
	return nil
}

func convertBFCLCase(question bfclQuestion, answer bfclAnswer) (Case, error) {
	if len(question.Question) != 1 {
		return Case{}, fmt.Errorf("only single-turn BFCL records are supported")
	}
	var prompt string
	for _, message := range question.Question[0] {
		if message.Role == "user" {
			prompt = message.Content
		}
	}
	if strings.TrimSpace(prompt) == "" {
		return Case{}, errors.New("user prompt is required")
	}
	tools := make([]ToolDefinition, 0, len(question.Function))
	for index, function := range question.Function {
		if function.Name == "" {
			return Case{}, fmt.Errorf("function %d requires name", index+1)
		}
		parameters, ok := normalizeBFCLSchema(function.Parameters).(map[string]any)
		if !ok || parameters == nil {
			return Case{}, fmt.Errorf("function %d requires an object parameter schema", index+1)
		}
		tools = append(tools, ToolDefinition{
			Name:        function.Name,
			Description: function.Description,
			Parameters:  parameters,
			Result:      `{"ok":true}`,
		})
	}
	calls := make([]ExpectedToolCall, 0, len(answer.GroundTruth))
	for index, groundTruth := range answer.GroundTruth {
		if len(groundTruth) != 1 {
			return Case{}, fmt.Errorf("ground truth call %d must contain exactly one function", index+1)
		}
		for name, arguments := range groundTruth {
			normalizedArguments := make(map[string][]any, len(arguments))
			for argument, alternatives := range arguments {
				normalized := make([]any, len(alternatives))
				for alternativeIndex, alternative := range alternatives {
					normalized[alternativeIndex] = normalizeBFCLValue(alternative)
				}
				normalizedArguments[argument] = normalized
			}
			calls = append(calls, ExpectedToolCall{Name: name, Arguments: normalizedArguments})
		}
	}
	return Case{
		ID:          question.ID,
		Description: "Imported from BFCL V4 single-turn function calling data.",
		Prompt:      prompt,
		Tags:        []string{"bfcl-v4", "simple-python", "tool-calling"},
		Tools:       tools,
		Graders: []GraderSpec{
			{Type: "tool_trace", Calls: calls},
		},
	}, nil
}

func normalizeBFCLValue(value any) any {
	switch typed := value.(type) {
	case json.Number:
		if integer, err := typed.Int64(); err == nil {
			return integer
		}
		if number, err := typed.Float64(); err == nil {
			return number
		}
		return typed.String()
	case map[string]any:
		normalized := make(map[string]any, len(typed))
		for key, child := range typed {
			normalized[key] = normalizeBFCLValue(child)
		}
		return normalized
	case []any:
		normalized := make([]any, len(typed))
		for index, child := range typed {
			normalized[index] = normalizeBFCLValue(child)
		}
		return normalized
	default:
		return value
	}
}

func normalizeBFCLSchema(value any) any {
	switch typed := value.(type) {
	case map[string]any:
		normalized := make(map[string]any, len(typed))
		for key, child := range typed {
			if key == "type" {
				if typeName, ok := child.(string); ok {
					switch typeName {
					case "dict":
						child = "object"
					case "float":
						child = "number"
					}
				}
			}
			normalized[key] = normalizeBFCLSchema(child)
		}
		return normalized
	case []any:
		normalized := make([]any, len(typed))
		for index, child := range typed {
			normalized[index] = normalizeBFCLSchema(child)
		}
		return normalized
	default:
		return value
	}
}
