package eval

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

type MultiAgentSuite struct {
	Version     int                     `json:"version" yaml:"version"`
	Name        string                  `json:"name" yaml:"name"`
	Description string                  `json:"description,omitempty" yaml:"description,omitempty"`
	Defaults    Defaults                `json:"defaults,omitempty" yaml:"defaults,omitempty"`
	Baselines   []string                `json:"baselines,omitempty" yaml:"baselines,omitempty"`
	Pricing     map[string]ModelPricing `json:"pricing,omitempty" yaml:"pricing,omitempty"`
	Cases       []MultiAgentCase        `json:"cases" yaml:"cases"`
	Source      string                  `json:"-" yaml:"-"`
}

type MultiAgentCase struct {
	ID                 string                   `json:"id" yaml:"id"`
	Description        string                   `json:"description,omitempty" yaml:"description,omitempty"`
	Prompt             string                   `json:"prompt" yaml:"prompt"`
	ExecutionMode      string                   `json:"execution_mode,omitempty" yaml:"execution_mode,omitempty"`
	CoordinatorAgentID string                   `json:"coordinator_agent_id,omitempty" yaml:"coordinator_agent_id,omitempty"`
	Model              string                   `json:"model,omitempty" yaml:"model,omitempty"`
	Repetitions        int                      `json:"repetitions,omitempty" yaml:"repetitions,omitempty"`
	Timeout            Duration                 `json:"timeout,omitempty" yaml:"timeout,omitempty"`
	Tags               []string                 `json:"tags,omitempty" yaml:"tags,omitempty"`
	SkipSolo           bool                     `json:"skip_solo,omitempty" yaml:"skip_solo,omitempty"`
	Baselines          []string                 `json:"baselines,omitempty" yaml:"baselines,omitempty"`
	MaxDelegations     int                      `json:"max_delegations,omitempty" yaml:"max_delegations,omitempty"`
	Agents             []MultiAgentCollaborator `json:"agents" yaml:"agents"`
	Milestones         []MultiAgentMilestone    `json:"milestones" yaml:"milestones"`
}

type MultiAgentCollaborator struct {
	ID                 string           `json:"id" yaml:"id"`
	Role               string           `json:"role" yaml:"role"`
	Response           string           `json:"response" yaml:"response"`
	TaskValues         []string         `json:"task_values,omitempty" yaml:"task_values,omitempty"`
	ContributionValues []string         `json:"contribution_values" yaml:"contribution_values"`
	Fault              *MultiAgentFault `json:"fault,omitempty" yaml:"fault,omitempty"`
}

type MultiAgentFault struct {
	Type                  string   `json:"type" yaml:"type"`
	Delay                 Duration `json:"delay,omitempty" yaml:"delay,omitempty"`
	Message               string   `json:"message,omitempty" yaml:"message,omitempty"`
	Response              string   `json:"response,omitempty" yaml:"response,omitempty"`
	ExpectedOutputValues  []string `json:"expected_output_values,omitempty" yaml:"expected_output_values,omitempty"`
	ForbiddenOutputValues []string `json:"forbidden_output_values,omitempty" yaml:"forbidden_output_values,omitempty"`
}

type MultiAgentMilestone struct {
	ID     string   `json:"id" yaml:"id"`
	Values []string `json:"values" yaml:"values"`
}

type MultiAgentRunner struct {
	Executor Executor
	Options  RunOptions
}

type MultiAgentAttemptMetrics struct {
	SoloEvaluated           bool    `json:"solo_evaluated"`
	SoloPassed              bool    `json:"solo_passed"`
	TotalMilestones         int     `json:"total_milestones"`
	PassedMilestones        int     `json:"passed_milestones"`
	ExpectedDelegations     int     `json:"expected_delegations"`
	ValidDelegations        int     `json:"valid_delegations"`
	TotalDelegations        int     `json:"total_delegations"`
	UnexpectedDelegations   int     `json:"unexpected_delegations"`
	DelegationPrecision     float64 `json:"delegation_precision"`
	DelegationRecall        float64 `json:"delegation_recall"`
	DelegationF1            float64 `json:"delegation_f1"`
	ContributionsExpected   int     `json:"contributions_expected"`
	ContributionsUtilized   int     `json:"contributions_utilized"`
	ContributionUtilization float64 `json:"contribution_utilization"`
	CoordinationScore       float64 `json:"coordination_score"`
	FaultsExpected          int     `json:"faults_expected"`
	FaultsObserved          int     `json:"faults_observed"`
	FaultsAttributed        int     `json:"faults_attributed"`
	UnsupportedClaims       int     `json:"unsupported_claims"`
	FaultInjectionRate      float64 `json:"fault_injection_rate"`
	FaultAttributionRate    float64 `json:"fault_attribution_rate"`
	GracefullyDegraded      bool    `json:"gracefully_degraded"`
}

type MultiAgentBaselineResult struct {
	Mode       string           `json:"mode"`
	Passed     bool             `json:"passed"`
	Output     string           `json:"output,omitempty"`
	Error      string           `json:"error,omitempty"`
	LatencyMS  float64          `json:"latency_ms"`
	Usage      Usage            `json:"usage"`
	ModelCalls []ModelCallUsage `json:"model_calls,omitempty"`
}

const (
	MultiAgentBaselineSoloClosedBook = "solo_closed_book"
	MultiAgentBaselineSoloOpenBook   = "solo_open_book"
	MultiAgentBaselineTeam           = "team"
	MultiAgentBaselineOracleTeam     = "oracle_team"
)

type multiAgentDelegation struct {
	AgentID string
	Task    string
}

func LoadMultiAgentSuite(path string) (MultiAgentSuite, error) {
	file, err := os.Open(path)
	if err != nil {
		return MultiAgentSuite{}, fmt.Errorf("open multi-agent eval suite: %w", err)
	}
	defer file.Close()

	var suite MultiAgentSuite
	decoder := yaml.NewDecoder(file)
	decoder.KnownFields(true)
	if err := decoder.Decode(&suite); err != nil {
		return MultiAgentSuite{}, fmt.Errorf("decode multi-agent eval suite: %w", err)
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		if err == nil {
			return MultiAgentSuite{}, errors.New("decode multi-agent eval suite: multiple YAML documents are not supported")
		}
		return MultiAgentSuite{}, fmt.Errorf("decode multi-agent eval suite: %w", err)
	}
	suite.Source = path
	if err := suite.Validate(); err != nil {
		return MultiAgentSuite{}, err
	}
	return suite, nil
}

func (s *MultiAgentSuite) Validate() error {
	if s.Version != SuiteVersion {
		return fmt.Errorf("multi-agent eval suite version must be %d", SuiteVersion)
	}
	if strings.TrimSpace(s.Name) == "" {
		return errors.New("multi-agent eval suite name is required")
	}
	if len(s.Cases) == 0 {
		return errors.New("multi-agent eval suite must contain at least one case")
	}
	if s.Defaults.Repetitions < 0 {
		return errors.New("default repetitions cannot be negative")
	}
	if s.Defaults.Timeout.Value() < 0 {
		return errors.New("default timeout cannot be negative")
	}
	if err := validateMultiAgentBaselines("suite", s.Baselines); err != nil {
		return err
	}
	for model, pricing := range s.Pricing {
		if strings.TrimSpace(model) == "" {
			return errors.New("pricing model name is required")
		}
		if pricing.InputPerMillion < 0 ||
			pricing.OutputPerMillion < 0 ||
			pricing.CacheReadPerMillion < 0 ||
			pricing.CacheWritePerMillion < 0 {
			return fmt.Errorf("pricing for model %q cannot contain negative rates", model)
		}
	}

	seenCases := make(map[string]struct{}, len(s.Cases))
	for caseIndex := range s.Cases {
		evalCase := &s.Cases[caseIndex]
		if strings.TrimSpace(evalCase.ID) == "" {
			return fmt.Errorf("case %d: id is required", caseIndex+1)
		}
		if _, exists := seenCases[evalCase.ID]; exists {
			return fmt.Errorf("case %q: duplicate id", evalCase.ID)
		}
		seenCases[evalCase.ID] = struct{}{}
		if strings.TrimSpace(evalCase.Prompt) == "" {
			return fmt.Errorf("case %q: prompt is required", evalCase.ID)
		}
		switch evalCase.ExecutionMode {
		case "", "simulated", "runtime":
		default:
			return fmt.Errorf("case %q: execution_mode must be simulated or runtime", evalCase.ID)
		}
		if evalCase.Repetitions < 0 {
			return fmt.Errorf("case %q: repetitions cannot be negative", evalCase.ID)
		}
		if evalCase.Timeout.Value() < 0 {
			return fmt.Errorf("case %q: timeout cannot be negative", evalCase.ID)
		}
		if err := validateMultiAgentBaselines(fmt.Sprintf("case %q", evalCase.ID), evalCase.Baselines); err != nil {
			return err
		}
		if !containsBaseline(multiAgentBaselines(*s, *evalCase), MultiAgentBaselineTeam) {
			return fmt.Errorf("case %q: baselines must include %q", evalCase.ID, MultiAgentBaselineTeam)
		}
		if len(evalCase.Agents) < 2 {
			return fmt.Errorf("case %q: at least two collaborator agents are required", evalCase.ID)
		}
		if evalCase.MaxDelegations < 0 {
			return fmt.Errorf("case %q: max_delegations cannot be negative", evalCase.ID)
		}
		if evalCase.MaxDelegations > 0 && evalCase.MaxDelegations < len(evalCase.Agents) {
			return fmt.Errorf("case %q: max_delegations cannot be less than collaborator count", evalCase.ID)
		}
		seenAgents := make(map[string]struct{}, len(evalCase.Agents))
		for agentIndex, collaborator := range evalCase.Agents {
			if strings.TrimSpace(collaborator.ID) == "" {
				return fmt.Errorf("case %q agent %d: id is required", evalCase.ID, agentIndex+1)
			}
			if _, exists := seenAgents[collaborator.ID]; exists {
				return fmt.Errorf("case %q: duplicate agent %q", evalCase.ID, collaborator.ID)
			}
			seenAgents[collaborator.ID] = struct{}{}
			if strings.TrimSpace(collaborator.Role) == "" {
				return fmt.Errorf("case %q agent %q: role is required", evalCase.ID, collaborator.ID)
			}
			if evalCase.ExecutionMode != "runtime" && strings.TrimSpace(collaborator.Response) == "" {
				return fmt.Errorf("case %q agent %q: response is required", evalCase.ID, collaborator.ID)
			}
			if len(collaborator.ContributionValues) == 0 {
				return fmt.Errorf("case %q agent %q: contribution_values is required", evalCase.ID, collaborator.ID)
			}
			if collaborator.Fault != nil {
				if evalCase.ExecutionMode == "runtime" {
					return fmt.Errorf("case %q agent %q: fault injection requires simulated execution_mode", evalCase.ID, collaborator.ID)
				}
				if err := validateMultiAgentFault(evalCase.ID, collaborator); err != nil {
					return err
				}
			}
		}
		for _, baseline := range multiAgentBaselines(*s, *evalCase) {
			if baseline != MultiAgentBaselineSoloOpenBook && baseline != MultiAgentBaselineOracleTeam {
				continue
			}
			for _, collaborator := range evalCase.Agents {
				if strings.TrimSpace(collaborator.Response) == "" {
					return fmt.Errorf(
						"case %q agent %q: response is required for %s baseline",
						evalCase.ID,
						collaborator.ID,
						baseline,
					)
				}
			}
		}
		if len(evalCase.Milestones) == 0 {
			return fmt.Errorf("case %q: milestones are required", evalCase.ID)
		}
		seenMilestones := make(map[string]struct{}, len(evalCase.Milestones))
		for milestoneIndex, milestone := range evalCase.Milestones {
			if strings.TrimSpace(milestone.ID) == "" {
				return fmt.Errorf("case %q milestone %d: id is required", evalCase.ID, milestoneIndex+1)
			}
			if _, exists := seenMilestones[milestone.ID]; exists {
				return fmt.Errorf("case %q: duplicate milestone %q", evalCase.ID, milestone.ID)
			}
			seenMilestones[milestone.ID] = struct{}{}
			if len(milestone.Values) == 0 {
				return fmt.Errorf("case %q milestone %q: values are required", evalCase.ID, milestone.ID)
			}
		}
	}
	return nil
}

func validateMultiAgentBaselines(scope string, baselines []string) error {
	seen := make(map[string]struct{}, len(baselines))
	for _, baseline := range baselines {
		switch baseline {
		case MultiAgentBaselineSoloClosedBook,
			MultiAgentBaselineSoloOpenBook,
			MultiAgentBaselineTeam,
			MultiAgentBaselineOracleTeam:
		default:
			return fmt.Errorf("%s: unsupported multi-agent baseline %q", scope, baseline)
		}
		if _, exists := seen[baseline]; exists {
			return fmt.Errorf("%s: duplicate multi-agent baseline %q", scope, baseline)
		}
		seen[baseline] = struct{}{}
	}
	return nil
}

func validateMultiAgentFault(caseID string, collaborator MultiAgentCollaborator) error {
	fault := collaborator.Fault
	switch fault.Type {
	case "error", "timeout":
		if strings.TrimSpace(fault.Message) == "" {
			return fmt.Errorf("case %q agent %q: %s fault requires message", caseID, collaborator.ID, fault.Type)
		}
	case "malformed", "contradictory":
		if strings.TrimSpace(fault.Response) == "" {
			return fmt.Errorf("case %q agent %q: %s fault requires response", caseID, collaborator.ID, fault.Type)
		}
	default:
		return fmt.Errorf("case %q agent %q: unsupported fault type %q", caseID, collaborator.ID, fault.Type)
	}
	if fault.Delay.Value() < 0 {
		return fmt.Errorf("case %q agent %q: fault delay cannot be negative", caseID, collaborator.ID)
	}
	if fault.Type == "timeout" && fault.Delay.Value() <= 0 {
		return fmt.Errorf("case %q agent %q: timeout fault requires a positive delay", caseID, collaborator.ID)
	}
	if len(fault.ExpectedOutputValues) == 0 {
		return fmt.Errorf("case %q agent %q: fault expected_output_values is required", caseID, collaborator.ID)
	}
	return nil
}

func multiAgentBaselines(suite MultiAgentSuite, evalCase MultiAgentCase) []string {
	baselines := evalCase.Baselines
	if len(baselines) == 0 {
		baselines = suite.Baselines
	}
	if len(baselines) == 0 {
		baselines = []string{MultiAgentBaselineSoloClosedBook, MultiAgentBaselineTeam}
	}
	result := append([]string(nil), baselines...)
	if evalCase.SkipSolo {
		result = removeBaseline(result, MultiAgentBaselineSoloClosedBook)
		result = removeBaseline(result, MultiAgentBaselineSoloOpenBook)
	}
	return result
}

func containsBaseline(baselines []string, target string) bool {
	for _, baseline := range baselines {
		if baseline == target {
			return true
		}
	}
	return false
}

func removeBaseline(baselines []string, target string) []string {
	result := baselines[:0]
	for _, baseline := range baselines {
		if baseline != target {
			result = append(result, baseline)
		}
	}
	return result
}

func (r MultiAgentRunner) Run(ctx context.Context, suite MultiAgentSuite) (Report, error) {
	if r.Executor == nil {
		return Report{}, fmt.Errorf("eval executor is required")
	}
	if err := suite.Validate(); err != nil {
		return Report{}, err
	}
	selectedCases, err := selectMultiAgentCases(suite.Cases, r.Options.CaseIDs)
	if err != nil {
		return Report{}, err
	}

	startedAt := time.Now()
	sessionPrefix := r.Options.SessionKeyPrefix
	if sessionPrefix == "" {
		sessionPrefix = "multiagent-eval"
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
		Cases:       make([]CaseResult, 0, len(selectedCases)),
	}

	for _, evalCase := range selectedCases {
		caseResult := CaseResult{
			ID:          evalCase.ID,
			Description: evalCase.Description,
			Tags:        append([]string(nil), evalCase.Tags...),
		}
		repetitions := multiAgentRepetitions(suite, evalCase, r.Options.Repetitions)
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

func selectMultiAgentCases(cases []MultiAgentCase, caseIDs []string) ([]MultiAgentCase, error) {
	if len(caseIDs) == 0 {
		return cases, nil
	}
	requested := make(map[string]struct{}, len(caseIDs))
	for _, caseID := range caseIDs {
		caseID = strings.TrimSpace(caseID)
		if caseID != "" {
			requested[caseID] = struct{}{}
		}
	}
	selected := make([]MultiAgentCase, 0, len(requested))
	for _, evalCase := range cases {
		if _, ok := requested[evalCase.ID]; ok {
			selected = append(selected, evalCase)
			delete(requested, evalCase.ID)
		}
	}
	if len(requested) > 0 {
		missing := make([]string, 0, len(requested))
		for caseID := range requested {
			missing = append(missing, caseID)
		}
		return nil, fmt.Errorf("multi-agent cases not found: %s", strings.Join(missing, ", "))
	}
	return selected, nil
}

func (r MultiAgentRunner) runAttempt(
	ctx context.Context,
	suite MultiAgentSuite,
	evalCase MultiAgentCase,
	attempt int,
	runID string,
) AttemptResult {
	startedAt := time.Now()
	agentID := firstNonEmpty(r.Options.AgentID, evalCase.CoordinatorAgentID, suite.Defaults.AgentID)
	model := firstNonEmpty(r.Options.Model, evalCase.Model, suite.Defaults.Model)
	sessionBase := fmt.Sprintf(
		"%s-%s-%s-%d",
		runID,
		sanitizeSessionPart(suite.Name),
		sanitizeSessionPart(evalCase.ID),
		attempt,
	)
	result := AttemptResult{
		Attempt: attempt,
		Kind:    "multiagent",
		MultiAgent: &MultiAgentAttemptMetrics{
			TotalMilestones:       len(evalCase.Milestones),
			ExpectedDelegations:   len(evalCase.Agents),
			ContributionsExpected: healthyCollaboratorCount(evalCase),
			FaultsExpected:        faultedCollaboratorCount(evalCase),
		},
	}

	for _, baseline := range multiAgentBaselines(suite, evalCase) {
		baselineResult, response := r.runBaseline(
			ctx,
			suite,
			evalCase,
			baseline,
			agentID,
			model,
			sessionBase,
		)
		result.Baselines = append(result.Baselines, baselineResult)
		result.Usage = addUsage(result.Usage, baselineResult.Usage)
		result.ModelCalls = append(result.ModelCalls, baselineResult.ModelCalls...)

		switch baseline {
		case MultiAgentBaselineSoloClosedBook:
			result.BaselineOutput = baselineResult.Output
			result.MultiAgent.SoloEvaluated = true
			result.MultiAgent.SoloPassed = baselineResult.Passed
		case MultiAgentBaselineTeam:
			if baselineResult.Error != "" {
				result.Error = "team execution: " + baselineResult.Error
				continue
			}
			result.Output = response.Output
			result.Model = firstNonEmpty(response.Model, model)
			result.Trace = response.Trace
			result.Graders = gradeMultiAgentAttempt(
				evalCase,
				response.Output,
				response.Trace,
				result.MultiAgent,
			)
			result.Passed = true
			for _, grader := range result.Graders {
				result.Passed = result.Passed && grader.Passed
			}
		}
	}
	result.LatencyMS = milliseconds(time.Since(startedAt))
	return result
}

func (r MultiAgentRunner) runBaseline(
	ctx context.Context,
	suite MultiAgentSuite,
	evalCase MultiAgentCase,
	mode string,
	agentID string,
	model string,
	sessionBase string,
) (MultiAgentBaselineResult, ExecutionResponse) {
	baselineContext, cancel := context.WithTimeout(
		ctx,
		multiAgentTimeout(suite, evalCase, r.Options.Timeout),
	)
	defer cancel()
	request := ExecutionRequest{
		AgentID:      agentID,
		Model:        model,
		SessionKey:   sessionBase + "-" + mode,
		IsolateTools: true,
		Pricing:      suite.Pricing,
	}
	switch mode {
	case MultiAgentBaselineSoloClosedBook:
		request.Prompt = multiAgentSoloPrompt(evalCase)
	case MultiAgentBaselineSoloOpenBook:
		request.Prompt = multiAgentOpenBookPrompt(evalCase)
	case MultiAgentBaselineOracleTeam:
		request.Prompt = multiAgentOracleTeamPrompt(evalCase)
	case MultiAgentBaselineTeam:
		request.Prompt = multiAgentTeamPrompt(evalCase)
		if evalCase.ExecutionMode == "runtime" {
			request.IsolateTools = false
		} else {
			request.Tools = multiAgentTools(evalCase)
			request.State = multiAgentState(evalCase)
		}
	}

	startedAt := time.Now()
	response, err := r.Executor.Execute(baselineContext, request)
	baselineResult := MultiAgentBaselineResult{
		Mode:       mode,
		Output:     response.Output,
		LatencyMS:  milliseconds(time.Since(startedAt)),
		Usage:      response.Usage,
		ModelCalls: appendModelCallPhase(nil, response.ModelCalls, mode),
	}
	if err != nil {
		baselineResult.Error = err.Error()
		return baselineResult, response
	}
	baselineResult.Passed = allMultiAgentMilestonesPass(response.Output, evalCase.Milestones)
	return baselineResult, response
}

func appendModelCallPhase(target, calls []ModelCallUsage, phase string) []ModelCallUsage {
	for _, call := range calls {
		call.Phase = phase
		target = append(target, call)
	}
	return target
}

func multiAgentTools(evalCase MultiAgentCase) []ToolDefinition {
	return []ToolDefinition{
		{
			Name:        "spawn_subagent",
			Description: "Delegate one focused task to a named specialist and return that specialist's report.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"agentId": map[string]any{"type": "string"},
					"task":    map[string]any{"type": "string"},
				},
				"required": []string{"agentId", "task"},
			},
			Behavior: &StateToolBehavior{
				ResultMapPath:        "responses",
				ResultMapKeyArgument: "agentId",
				Faults:               multiAgentToolFaults(evalCase),
			},
		},
	}
}

func multiAgentState(evalCase MultiAgentCase) map[string]any {
	responses := make(map[string]any, len(evalCase.Agents))
	for _, collaborator := range evalCase.Agents {
		response := collaborator.Response
		if collaborator.Fault != nil {
			switch collaborator.Fault.Type {
			case "malformed", "contradictory":
				response = collaborator.Fault.Response
			}
		}
		responses[collaborator.ID] = response
	}
	return map[string]any{"responses": responses}
}

func multiAgentToolFaults(evalCase MultiAgentCase) []StateToolFault {
	var faults []StateToolFault
	for _, collaborator := range evalCase.Agents {
		if collaborator.Fault == nil {
			continue
		}
		fault := StateToolFault{
			Argument: "agentId",
			Value:    collaborator.ID,
			DelayMS:  int(collaborator.Fault.Delay.Value() / time.Millisecond),
		}
		switch collaborator.Fault.Type {
		case "error", "timeout":
			fault.Error = collaborator.Fault.Message
		case "malformed", "contradictory":
			fault.Result = collaborator.Fault.Response
		}
		faults = append(faults, fault)
	}
	return faults
}

func multiAgentSoloPrompt(evalCase MultiAgentCase) string {
	return fmt.Sprintf(
		`Solve the following task independently. No specialist tools or reports are available.

Task:
%s`,
		evalCase.Prompt,
	)
}

func multiAgentOpenBookPrompt(evalCase MultiAgentCase) string {
	return fmt.Sprintf(
		`Solve the following task independently. You have the same evidence
available to the team, flattened into an anonymous evidence packet. Do not
claim facts that are absent or marked unavailable.

Task:
%s

Evidence packet:
%s`,
		evalCase.Prompt,
		multiAgentEvidencePacket(evalCase, false),
	)
}

func multiAgentOracleTeamPrompt(evalCase MultiAgentCase) string {
	return fmt.Sprintf(
		`You are an oracle coordinator. Routing is assumed perfect and every
specialist report that could be obtained is provided below. Synthesize the
reports into one final answer. Explicitly identify unavailable, malformed, or
conflicting evidence and do not invent replacements.

Task:
%s

Specialist reports:
%s`,
		evalCase.Prompt,
		multiAgentEvidencePacket(evalCase, true),
	)
}

func multiAgentEvidencePacket(evalCase MultiAgentCase, includeIdentity bool) string {
	var packet strings.Builder
	for index, collaborator := range evalCase.Agents {
		label := fmt.Sprintf("evidence-%d", index+1)
		if includeIdentity {
			label = fmt.Sprintf("%s (%s)", collaborator.ID, collaborator.Role)
		}
		fmt.Fprintf(&packet, "- %s: %s\n", label, multiAgentObservedResponse(collaborator))
	}
	return packet.String()
}

func multiAgentObservedResponse(collaborator MultiAgentCollaborator) string {
	if collaborator.Fault == nil {
		return collaborator.Response
	}
	switch collaborator.Fault.Type {
	case "error", "timeout":
		return "[UNAVAILABLE: " + collaborator.Fault.Message + "]"
	case "malformed", "contradictory":
		return collaborator.Fault.Response
	default:
		return collaborator.Response
	}
}

func multiAgentTeamPrompt(evalCase MultiAgentCase) string {
	var team strings.Builder
	for _, collaborator := range evalCase.Agents {
		fmt.Fprintf(&team, "- %s: %s\n", collaborator.ID, collaborator.Role)
	}
	return fmt.Sprintf(
		`You are the coordinator of a specialist team.

Task:
%s

Available specialists:
%s
Delegate one focused task to every specialist with spawn_subagent, then
synthesize their reports into one final answer. Do not delegate to unknown
agents or call the same specialist twice.`,
		evalCase.Prompt,
		team.String(),
	)
}

func healthyCollaboratorCount(evalCase MultiAgentCase) int {
	return len(evalCase.Agents) - faultedCollaboratorCount(evalCase)
}

func faultedCollaboratorCount(evalCase MultiAgentCase) int {
	count := 0
	for _, collaborator := range evalCase.Agents {
		if collaborator.Fault != nil {
			count++
		}
	}
	return count
}

func gradeMultiAgentAttempt(
	evalCase MultiAgentCase,
	output string,
	trace []TraceEvent,
	metrics *MultiAgentAttemptMetrics,
) []GraderResult {
	delegations := multiAgentDelegations(trace)
	metrics.TotalDelegations = len(delegations)
	expected := make(map[string]MultiAgentCollaborator, len(evalCase.Agents))
	for _, collaborator := range evalCase.Agents {
		expected[collaborator.ID] = collaborator
	}
	valid := make(map[string]bool, len(expected))
	for _, delegation := range delegations {
		collaborator, exists := expected[delegation.AgentID]
		if !exists {
			metrics.UnexpectedDelegations++
			continue
		}
		if containsAllFold(delegation.Task, collaborator.TaskValues) {
			valid[delegation.AgentID] = true
		}
	}
	metrics.ValidDelegations = len(valid)
	if metrics.TotalDelegations > 0 {
		metrics.DelegationPrecision = float64(metrics.ValidDelegations) / float64(metrics.TotalDelegations)
	}
	if metrics.ExpectedDelegations > 0 {
		metrics.DelegationRecall = float64(metrics.ValidDelegations) / float64(metrics.ExpectedDelegations)
	}
	if metrics.DelegationPrecision+metrics.DelegationRecall > 0 {
		metrics.DelegationF1 = 2 * metrics.DelegationPrecision * metrics.DelegationRecall /
			(metrics.DelegationPrecision + metrics.DelegationRecall)
	}

	results := make([]GraderResult, 0, len(evalCase.Milestones)+7)
	allMilestonesPassed := true
	for _, milestone := range evalCase.Milestones {
		passed := containsAllFold(output, milestone.Values)
		if passed {
			metrics.PassedMilestones++
		} else {
			allMilestonesPassed = false
		}
		result := GraderResult{Type: "ma_milestone", Passed: passed}
		if !passed {
			result.Message = fmt.Sprintf("milestone %q was not achieved", milestone.ID)
		}
		results = append(results, result)
	}
	for _, collaborator := range evalCase.Agents {
		if collaborator.Fault != nil {
			continue
		}
		if valid[collaborator.ID] && containsAllFold(output, collaborator.ContributionValues) {
			metrics.ContributionsUtilized++
		}
	}
	if metrics.ContributionsExpected > 0 {
		metrics.ContributionUtilization = float64(metrics.ContributionsUtilized) /
			float64(metrics.ContributionsExpected)
	}
	metrics.CoordinationScore = (metrics.DelegationF1 + metrics.ContributionUtilization) / 2

	delegationPassed := metrics.DelegationPrecision == 1 && metrics.DelegationRecall == 1
	results = append(results, GraderResult{
		Type:    "ma_delegation",
		Passed:  delegationPassed,
		Message: multiAgentDelegationMessage(metrics),
	})
	contributionPassed := metrics.ContributionUtilization == 1
	results = append(results, GraderResult{
		Type:    "ma_contribution",
		Passed:  contributionPassed,
		Message: multiAgentContributionMessage(metrics),
	})
	maxDelegations := evalCase.MaxDelegations
	if maxDelegations == 0 {
		maxDelegations = len(evalCase.Agents)
	}
	efficiencyPassed := metrics.TotalDelegations <= maxDelegations
	results = append(results, GraderResult{
		Type:    "ma_efficiency",
		Passed:  efficiencyPassed,
		Message: multiAgentEfficiencyMessage(metrics.TotalDelegations, maxDelegations),
	})
	if metrics.FaultsExpected > 0 {
		gradeMultiAgentFaults(evalCase, output, trace, metrics)
		faultsExercised := metrics.FaultsObserved == metrics.FaultsExpected
		results = append(results, GraderResult{
			Type:    "ma_fault_exercised",
			Passed:  faultsExercised,
			Message: multiAgentRatioMessage("observed injected faults", metrics.FaultsObserved, metrics.FaultsExpected),
		})
		faultsAttributed := metrics.FaultsAttributed == metrics.FaultsExpected
		results = append(results, GraderResult{
			Type:    "ma_fault_attribution",
			Passed:  faultsAttributed,
			Message: multiAgentRatioMessage("attributed faults", metrics.FaultsAttributed, metrics.FaultsExpected),
		})
		noUnsupportedClaims := metrics.UnsupportedClaims == 0
		results = append(results, GraderResult{
			Type:    "ma_unsupported_claim",
			Passed:  noUnsupportedClaims,
			Message: multiAgentUnsupportedClaimMessage(metrics.UnsupportedClaims),
		})
		metrics.GracefullyDegraded = allMilestonesPassed &&
			faultsExercised &&
			faultsAttributed &&
			noUnsupportedClaims
		results = append(results, GraderResult{
			Type:    "ma_graceful_degradation",
			Passed:  metrics.GracefullyDegraded,
			Message: multiAgentGracefulDegradationMessage(metrics),
		})
	}
	return results
}

func gradeMultiAgentFaults(
	evalCase MultiAgentCase,
	output string,
	trace []TraceEvent,
	metrics *MultiAgentAttemptMetrics,
) {
	observedResults := multiAgentDelegationResults(trace)
	for _, collaborator := range evalCase.Agents {
		if collaborator.Fault == nil {
			continue
		}
		if faultObserved(collaborator, observedResults[collaborator.ID]) {
			metrics.FaultsObserved++
		}
		if containsAllFold(output, collaborator.Fault.ExpectedOutputValues) {
			metrics.FaultsAttributed++
		}
		for _, unsupported := range collaborator.Fault.ForbiddenOutputValues {
			if containsAllFold(output, []string{unsupported}) {
				metrics.UnsupportedClaims++
			}
		}
	}
	if metrics.FaultsExpected > 0 {
		metrics.FaultInjectionRate = float64(metrics.FaultsObserved) / float64(metrics.FaultsExpected)
		metrics.FaultAttributionRate = float64(metrics.FaultsAttributed) / float64(metrics.FaultsExpected)
	}
}

func multiAgentDelegationResults(trace []TraceEvent) map[string][]string {
	agentsByCallID := make(map[string]string)
	results := make(map[string][]string)
	for _, event := range trace {
		if event.Type == "tool_call" && event.Name == "spawn_subagent" {
			var arguments struct {
				AgentID string `json:"agentId"`
			}
			if json.Unmarshal([]byte(event.Arguments), &arguments) == nil {
				agentsByCallID[event.ID] = arguments.AgentID
			}
			continue
		}
		if event.Type != "tool_result" || event.Name != "spawn_subagent" {
			continue
		}
		if agentID := agentsByCallID[event.ID]; agentID != "" {
			results[agentID] = append(results[agentID], event.Result)
		}
	}
	return results
}

func faultObserved(collaborator MultiAgentCollaborator, results []string) bool {
	for _, result := range results {
		switch collaborator.Fault.Type {
		case "error", "timeout":
			if containsAllFold(result, []string{collaborator.Fault.Message}) {
				return true
			}
		case "malformed", "contradictory":
			if strings.Contains(result, collaborator.Fault.Response) {
				return true
			}
		}
	}
	return false
}

func multiAgentDelegations(trace []TraceEvent) []multiAgentDelegation {
	var delegations []multiAgentDelegation
	for _, event := range trace {
		if event.Type != "tool_call" || event.Name != "spawn_subagent" {
			continue
		}
		var arguments struct {
			AgentID string `json:"agentId"`
			Task    string `json:"task"`
		}
		if json.Unmarshal([]byte(event.Arguments), &arguments) != nil {
			continue
		}
		delegations = append(delegations, multiAgentDelegation{
			AgentID: arguments.AgentID,
			Task:    arguments.Task,
		})
	}
	return delegations
}

func allMultiAgentMilestonesPass(output string, milestones []MultiAgentMilestone) bool {
	for _, milestone := range milestones {
		if !containsAllFold(output, milestone.Values) {
			return false
		}
	}
	return true
}

func containsAllFold(text string, values []string) bool {
	normalizedText := normalizeMatchText(text)
	for _, value := range values {
		matched := false
		for _, alternative := range strings.Split(value, "||") {
			if strings.Contains(normalizedText, normalizeMatchText(alternative)) {
				matched = true
				break
			}
		}
		if !matched {
			return false
		}
	}
	return true
}

func normalizeMatchText(value string) string {
	value = strings.ToLower(value)
	value = strings.ReplaceAll(value, "%", " percent ")
	value = strings.NewReplacer(
		",", "",
		"`", "",
		"*", "",
		"-", " ",
		"_", " ",
		"/", " ",
		":", " ",
		"(", " ",
		")", " ",
	).Replace(value)
	numberWords := map[string]string{
		"zero":  "0",
		"one":   "1",
		"two":   "2",
		"three": "3",
		"four":  "4",
		"five":  "5",
		"six":   "6",
		"seven": "7",
		"eight": "8",
		"nine":  "9",
		"ten":   "10",
	}
	stopWords := map[string]struct{}{
		"a":   {},
		"an":  {},
		"the": {},
	}
	fields := strings.Fields(value)
	normalized := make([]string, 0, len(fields))
	for _, field := range fields {
		if _, skip := stopWords[field]; skip {
			continue
		}
		if number, ok := numberWords[field]; ok {
			field = number
		}
		if len(field) > 3 && strings.HasSuffix(field, "s") {
			field = strings.TrimSuffix(field, "s")
		}
		normalized = append(normalized, field)
	}
	return strings.Join(normalized, " ")
}

func multiAgentDelegationMessage(metrics *MultiAgentAttemptMetrics) string {
	if metrics.DelegationPrecision == 1 && metrics.DelegationRecall == 1 {
		return ""
	}
	return fmt.Sprintf(
		"delegation precision %.3f, recall %.3f, unexpected %d",
		metrics.DelegationPrecision,
		metrics.DelegationRecall,
		metrics.UnexpectedDelegations,
	)
}

func multiAgentContributionMessage(metrics *MultiAgentAttemptMetrics) string {
	if metrics.ContributionUtilization == 1 {
		return ""
	}
	return fmt.Sprintf(
		"utilized %d/%d specialist contributions",
		metrics.ContributionsUtilized,
		metrics.ContributionsExpected,
	)
}

func multiAgentEfficiencyMessage(total, maximum int) string {
	if total <= maximum {
		return ""
	}
	return fmt.Sprintf("used %d delegations, maximum is %d", total, maximum)
}

func multiAgentRatioMessage(label string, actual, expected int) string {
	if actual == expected {
		return ""
	}
	return fmt.Sprintf("%s %d/%d", label, actual, expected)
}

func multiAgentUnsupportedClaimMessage(count int) string {
	if count == 0 {
		return ""
	}
	return fmt.Sprintf("output contained %d unsupported fault-related claims", count)
}

func multiAgentGracefulDegradationMessage(metrics *MultiAgentAttemptMetrics) string {
	if metrics.GracefullyDegraded {
		return ""
	}
	return fmt.Sprintf(
		"fault injection %.3f, attribution %.3f, unsupported claims %d",
		metrics.FaultInjectionRate,
		metrics.FaultAttributionRate,
		metrics.UnsupportedClaims,
	)
}

func addUsage(left, right Usage) Usage {
	return Usage{
		PromptTokens:     left.PromptTokens + right.PromptTokens,
		CompletionTokens: left.CompletionTokens + right.CompletionTokens,
		TotalTokens:      left.TotalTokens + right.TotalTokens,
	}
}

func multiAgentRepetitions(suite MultiAgentSuite, evalCase MultiAgentCase, override int) int {
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

func multiAgentTimeout(suite MultiAgentSuite, evalCase MultiAgentCase, override time.Duration) time.Duration {
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
