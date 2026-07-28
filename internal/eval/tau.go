package eval

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"reflect"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

type TauSuite struct {
	Version     int       `json:"version" yaml:"version"`
	Name        string    `json:"name" yaml:"name"`
	Description string    `json:"description,omitempty" yaml:"description,omitempty"`
	Defaults    Defaults  `json:"defaults,omitempty" yaml:"defaults,omitempty"`
	Cases       []TauCase `json:"cases" yaml:"cases"`
	Source      string    `json:"-" yaml:"-"`
}

type TauCase struct {
	ID             string           `json:"id" yaml:"id"`
	Description    string           `json:"description,omitempty" yaml:"description,omitempty"`
	AgentID        string           `json:"agent_id,omitempty" yaml:"agent_id,omitempty"`
	Model          string           `json:"model,omitempty" yaml:"model,omitempty"`
	Repetitions    int              `json:"repetitions,omitempty" yaml:"repetitions,omitempty"`
	Timeout        Duration         `json:"timeout,omitempty" yaml:"timeout,omitempty"`
	Tags           []string         `json:"tags,omitempty" yaml:"tags,omitempty"`
	InitialState   map[string]any   `json:"initial_state" yaml:"initial_state"`
	Tools          []ToolDefinition `json:"tools" yaml:"tools"`
	Turns          []TauTurn        `json:"turns" yaml:"turns"`
	ExpectedState  map[string]any   `json:"expected_state" yaml:"expected_state"`
	StateMode      string           `json:"state_mode,omitempty" yaml:"state_mode,omitempty"`
	Communicate    []string         `json:"communicate,omitempty" yaml:"communicate,omitempty"`
	ForbiddenTools []string         `json:"forbidden_tools,omitempty" yaml:"forbidden_tools,omitempty"`
}

type TauTurn struct {
	Prompt         string         `json:"prompt" yaml:"prompt"`
	ExpectedState  map[string]any `json:"expected_state,omitempty" yaml:"expected_state,omitempty"`
	StateMode      string         `json:"state_mode,omitempty" yaml:"state_mode,omitempty"`
	Communicate    []string       `json:"communicate,omitempty" yaml:"communicate,omitempty"`
	ForbiddenTools []string       `json:"forbidden_tools,omitempty" yaml:"forbidden_tools,omitempty"`
}

type TauRunner struct {
	Executor Executor
	Options  RunOptions
}

func LoadTauSuite(path string) (TauSuite, error) {
	file, err := os.Open(path)
	if err != nil {
		return TauSuite{}, fmt.Errorf("open tau eval suite: %w", err)
	}
	defer file.Close()

	var suite TauSuite
	decoder := yaml.NewDecoder(file)
	decoder.KnownFields(true)
	if err := decoder.Decode(&suite); err != nil {
		return TauSuite{}, fmt.Errorf("decode tau eval suite: %w", err)
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		if err == nil {
			return TauSuite{}, errors.New("decode tau eval suite: multiple YAML documents are not supported")
		}
		return TauSuite{}, fmt.Errorf("decode tau eval suite: %w", err)
	}
	suite.Source = path
	if err := suite.Validate(); err != nil {
		return TauSuite{}, err
	}
	return suite, nil
}

func (s *TauSuite) Validate() error {
	if s.Version != SuiteVersion {
		return fmt.Errorf("tau eval suite version must be %d", SuiteVersion)
	}
	if strings.TrimSpace(s.Name) == "" {
		return errors.New("tau eval suite name is required")
	}
	if len(s.Cases) == 0 {
		return errors.New("tau eval suite must contain at least one case")
	}
	if s.Defaults.Repetitions < 0 {
		return errors.New("default repetitions cannot be negative")
	}
	if s.Defaults.Timeout.Value() < 0 {
		return errors.New("default timeout cannot be negative")
	}

	seen := make(map[string]struct{}, len(s.Cases))
	for caseIndex := range s.Cases {
		evalCase := &s.Cases[caseIndex]
		if strings.TrimSpace(evalCase.ID) == "" {
			return fmt.Errorf("case %d: id is required", caseIndex+1)
		}
		if _, exists := seen[evalCase.ID]; exists {
			return fmt.Errorf("case %q: duplicate id", evalCase.ID)
		}
		seen[evalCase.ID] = struct{}{}
		if evalCase.Repetitions < 0 {
			return fmt.Errorf("case %q: repetitions cannot be negative", evalCase.ID)
		}
		if evalCase.Timeout.Value() < 0 {
			return fmt.Errorf("case %q: timeout cannot be negative", evalCase.ID)
		}
		if evalCase.InitialState == nil {
			return fmt.Errorf("case %q: initial_state is required", evalCase.ID)
		}
		if evalCase.ExpectedState == nil {
			return fmt.Errorf("case %q: expected_state is required", evalCase.ID)
		}
		if err := validateStateMode(evalCase.StateMode); err != nil {
			return fmt.Errorf("case %q: %w", evalCase.ID, err)
		}
		if len(evalCase.Turns) == 0 {
			return fmt.Errorf("case %q: at least one turn is required", evalCase.ID)
		}
		for turnIndex, turn := range evalCase.Turns {
			if strings.TrimSpace(turn.Prompt) == "" {
				return fmt.Errorf("case %q turn %d: prompt is required", evalCase.ID, turnIndex+1)
			}
			if err := validateStateMode(turn.StateMode); err != nil {
				return fmt.Errorf("case %q turn %d: %w", evalCase.ID, turnIndex+1, err)
			}
		}
		if err := validateTauTools(evalCase); err != nil {
			return err
		}
	}
	return nil
}

func validateTauTools(evalCase *TauCase) error {
	if len(evalCase.Tools) == 0 {
		return fmt.Errorf("case %q: at least one tool is required", evalCase.ID)
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
		if tool.Behavior == nil {
			return fmt.Errorf("case %q tool %d: behavior is required", evalCase.ID, toolIndex+1)
		}
		for conditionIndex, condition := range tool.Behavior.Conditions {
			if strings.TrimSpace(condition.Path) == "" {
				return fmt.Errorf(
					"case %q tool %d condition %d: path is required",
					evalCase.ID,
					toolIndex+1,
					conditionIndex+1,
				)
			}
		}
		for updateIndex, update := range tool.Behavior.Updates {
			if strings.TrimSpace(update.Path) == "" && strings.TrimSpace(update.MapPath) == "" {
				return fmt.Errorf(
					"case %q tool %d update %d: path or map_path is required",
					evalCase.ID,
					toolIndex+1,
					updateIndex+1,
				)
			}
			if update.Path != "" && update.MapPath != "" {
				return fmt.Errorf(
					"case %q tool %d update %d: path and map_path are mutually exclusive",
					evalCase.ID,
					toolIndex+1,
					updateIndex+1,
				)
			}
			if update.MapPath != "" && strings.TrimSpace(update.KeyFromArgument) == "" {
				return fmt.Errorf(
					"case %q tool %d update %d: key_from_argument is required with map_path",
					evalCase.ID,
					toolIndex+1,
					updateIndex+1,
				)
			}
			if update.ValueFromArgument != "" && update.Value != nil {
				return fmt.Errorf(
					"case %q tool %d update %d: value and value_from_argument are mutually exclusive",
					evalCase.ID,
					toolIndex+1,
					updateIndex+1,
				)
			}
		}
	}
	for _, forbidden := range appendCaseForbiddenTools(*evalCase) {
		if _, exists := toolNames[forbidden]; !exists {
			return fmt.Errorf("case %q: forbidden tool %q is not defined", evalCase.ID, forbidden)
		}
	}
	return nil
}

func appendCaseForbiddenTools(evalCase TauCase) []string {
	tools := append([]string(nil), evalCase.ForbiddenTools...)
	for _, turn := range evalCase.Turns {
		tools = append(tools, turn.ForbiddenTools...)
	}
	return tools
}

func validateStateMode(mode string) error {
	switch mode {
	case "", "exact", "subset":
		return nil
	default:
		return fmt.Errorf("state_mode must be exact or subset")
	}
}

func (r TauRunner) Run(ctx context.Context, suite TauSuite) (Report, error) {
	if r.Executor == nil {
		return Report{}, fmt.Errorf("eval executor is required")
	}
	if err := suite.Validate(); err != nil {
		return Report{}, err
	}

	startedAt := time.Now()
	sessionPrefix := r.Options.SessionKeyPrefix
	if sessionPrefix == "" {
		sessionPrefix = "tau-eval"
	}
	runID := fmt.Sprintf(
		"%s-%d-%d",
		sanitizeSessionPart(sessionPrefix),
		startedAt.UnixNano(),
		runSequence.Add(1),
	)
	report := Report{
		Version:     SuiteVersion,
		Suite:       suite.Name,
		Description: suite.Description,
		Source:      suite.Source,
		StartedAt:   startedAt,
		Cases:       make([]CaseResult, 0, len(suite.Cases)),
	}

	for _, evalCase := range suite.Cases {
		caseResult := CaseResult{
			ID:          evalCase.ID,
			Description: evalCase.Description,
			Tags:        append([]string(nil), evalCase.Tags...),
		}
		repetitions := tauRepetitions(suite, evalCase, r.Options.Repetitions)
		for attempt := 1; attempt <= repetitions; attempt++ {
			caseResult.Attempts = append(
				caseResult.Attempts,
				r.runAttempt(ctx, suite, evalCase, attempt, runID),
			)
		}
		caseResult.PassAt1 = caseResult.Attempts[0].Passed
		caseResult.Consistent = attemptsConsistent(caseResult.Attempts)
		for _, attempt := range caseResult.Attempts {
			caseResult.PassAtK = caseResult.PassAtK || attempt.Passed
		}
		report.Cases = append(report.Cases, caseResult)
	}

	report.FinishedAt = time.Now()
	report.DurationMS = milliseconds(report.FinishedAt.Sub(startedAt))
	report.Metrics = calculateMetrics(report.Cases)
	return report, nil
}

func (r TauRunner) runAttempt(
	ctx context.Context,
	suite TauSuite,
	evalCase TauCase,
	attempt int,
	runID string,
) AttemptResult {
	timeout := tauTimeout(suite, evalCase, r.Options.Timeout)
	attemptContext, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	agentID := firstNonEmpty(r.Options.AgentID, evalCase.AgentID, suite.Defaults.AgentID)
	model := firstNonEmpty(r.Options.Model, evalCase.Model, suite.Defaults.Model)
	sessionKey := fmt.Sprintf(
		"%s-%s-%s-%d",
		runID,
		sanitizeSessionPart(suite.Name),
		sanitizeSessionPart(evalCase.ID),
		attempt,
	)
	state := cloneEvalState(evalCase.InitialState)
	var (
		outputs []string
		trace   []TraceEvent
		graders []GraderResult
		usage   Usage
	)

	startedAt := time.Now()
	for turnIndex, turn := range evalCase.Turns {
		response, err := r.Executor.Execute(attemptContext, ExecutionRequest{
			Prompt:     turn.Prompt,
			AgentID:    agentID,
			Model:      model,
			SessionKey: sessionKey,
			Tools:      append([]ToolDefinition(nil), evalCase.Tools...),
			State:      state,
		})
		if err != nil {
			return AttemptResult{
				Attempt:   attempt,
				Passed:    false,
				Error:     fmt.Sprintf("turn %d: %v", turnIndex+1, err),
				LatencyMS: milliseconds(time.Since(startedAt)),
				Turns:     turnIndex + 1,
				State:     state,
			}
		}
		if response.State != nil {
			state = response.State
		}
		outputs = append(outputs, response.Output)
		usage.PromptTokens += response.Usage.PromptTokens
		usage.CompletionTokens += response.Usage.CompletionTokens
		usage.TotalTokens += response.Usage.TotalTokens
		for _, event := range response.Trace {
			event.Turn = turnIndex + 1
			trace = append(trace, event)
		}
		graders = append(graders, gradeTauTurn(turnIndex+1, turn, response.Output, response.Trace, state)...)
		if model == "" {
			model = response.Model
		}
	}

	combinedOutput := strings.Join(outputs, "\n")
	graders = append(graders, gradeTauFinal(evalCase, combinedOutput, trace, state)...)
	passed := true
	for _, grader := range graders {
		passed = passed && grader.Passed
	}
	return AttemptResult{
		Attempt:   attempt,
		Passed:    passed,
		Output:    combinedOutput,
		LatencyMS: milliseconds(time.Since(startedAt)),
		Model:     model,
		Usage:     usage,
		Trace:     trace,
		Graders:   graders,
		Turns:     len(evalCase.Turns),
		State:     state,
	}
}

func gradeTauTurn(
	turnNumber int,
	turn TauTurn,
	output string,
	trace []TraceEvent,
	state map[string]any,
) []GraderResult {
	var results []GraderResult
	if turn.ExpectedState != nil {
		result := gradeTauState(state, turn.ExpectedState, turn.StateMode)
		result.Message = prefixTauMessage(turnNumber, result.Message)
		results = append(results, result)
	}
	if len(turn.Communicate) > 0 {
		result := gradeTauCommunication(output, turn.Communicate)
		result.Message = prefixTauMessage(turnNumber, result.Message)
		results = append(results, result)
	}
	if len(turn.ForbiddenTools) > 0 {
		result := gradeTauPolicy(trace, turn.ForbiddenTools)
		result.Message = prefixTauMessage(turnNumber, result.Message)
		results = append(results, result)
	}
	return results
}

func gradeTauFinal(
	evalCase TauCase,
	output string,
	trace []TraceEvent,
	state map[string]any,
) []GraderResult {
	results := []GraderResult{gradeTauState(state, evalCase.ExpectedState, evalCase.StateMode)}
	if len(evalCase.Communicate) > 0 {
		results = append(results, gradeTauCommunication(output, evalCase.Communicate))
	}
	if len(evalCase.ForbiddenTools) > 0 {
		results = append(results, gradeTauPolicy(trace, evalCase.ForbiddenTools))
	}
	return results
}

func gradeTauState(actual, expected map[string]any, mode string) GraderResult {
	passed := false
	if mode == "subset" {
		passed = stateContains(actual, expected)
	} else {
		passed = reflect.DeepEqual(normalizeEvalJSON(actual), normalizeEvalJSON(expected))
	}
	result := GraderResult{Type: "tau_state", Passed: passed}
	if !passed {
		result.Message = fmt.Sprintf("final state did not match expected %s state", firstNonEmpty(mode, "exact"))
	}
	return result
}

func gradeTauCommunication(output string, required []string) GraderResult {
	lowerOutput := strings.ToLower(output)
	var missing []string
	for _, value := range required {
		if !strings.Contains(lowerOutput, strings.ToLower(value)) {
			missing = append(missing, value)
		}
	}
	result := GraderResult{Type: "tau_communicate", Passed: len(missing) == 0}
	if len(missing) > 0 {
		result.Message = fmt.Sprintf("missing required communication: %s", strings.Join(missing, ", "))
	}
	return result
}

func gradeTauPolicy(trace []TraceEvent, forbidden []string) GraderResult {
	forbiddenSet := make(map[string]struct{}, len(forbidden))
	for _, name := range forbidden {
		forbiddenSet[name] = struct{}{}
	}
	var violations []string
	for _, event := range trace {
		if event.Type != "tool_call" {
			continue
		}
		if _, exists := forbiddenSet[event.Name]; exists {
			violations = append(violations, event.Name)
		}
	}
	result := GraderResult{Type: "tau_policy", Passed: len(violations) == 0}
	if len(violations) > 0 {
		result.Message = fmt.Sprintf("forbidden tools called: %s", strings.Join(violations, ", "))
	}
	return result
}

func stateContains(actual, expected any) bool {
	expectedObject, expectedIsObject := expected.(map[string]any)
	if !expectedIsObject {
		return reflect.DeepEqual(normalizeEvalJSON(actual), normalizeEvalJSON(expected))
	}
	actualObject, actualIsObject := actual.(map[string]any)
	if !actualIsObject {
		return false
	}
	for key, expectedValue := range expectedObject {
		actualValue, exists := actualObject[key]
		if !exists || !stateContains(actualValue, expectedValue) {
			return false
		}
	}
	return true
}

func prefixTauMessage(turn int, message string) string {
	if message == "" {
		return ""
	}
	return fmt.Sprintf("turn %d: %s", turn, message)
}

func normalizeEvalJSON(value any) any {
	encoded, err := json.Marshal(value)
	if err != nil {
		return value
	}
	var normalized any
	if err := json.Unmarshal(encoded, &normalized); err != nil {
		return value
	}
	return normalized
}

func cloneEvalState(state map[string]any) map[string]any {
	cloned, _ := normalizeEvalJSON(state).(map[string]any)
	return cloned
}

func tauRepetitions(suite TauSuite, evalCase TauCase, override int) int {
	if override > 0 {
		return override
	}
	if evalCase.Repetitions > 0 {
		return evalCase.Repetitions
	}
	if suite.Defaults.Repetitions > 0 {
		return suite.Defaults.Repetitions
	}
	return 1
}

func tauTimeout(suite TauSuite, evalCase TauCase, override time.Duration) time.Duration {
	if override > 0 {
		return override
	}
	if evalCase.Timeout.Value() > 0 {
		return evalCase.Timeout.Value()
	}
	if suite.Defaults.Timeout.Value() > 0 {
		return suite.Defaults.Timeout.Value()
	}
	return defaultTimeout
}
