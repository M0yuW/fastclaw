package eval

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"gopkg.in/yaml.v3"
)

const SuiteVersion = 1

type Duration time.Duration

func (d *Duration) UnmarshalYAML(node *yaml.Node) error {
	value, err := time.ParseDuration(node.Value)
	if err != nil {
		return fmt.Errorf("invalid duration %q: %w", node.Value, err)
	}
	*d = Duration(value)
	return nil
}

func (d Duration) MarshalJSON() ([]byte, error) {
	return json.Marshal(time.Duration(d).String())
}

func (d Duration) MarshalYAML() (any, error) {
	return time.Duration(d).String(), nil
}

func (d Duration) Value() time.Duration {
	return time.Duration(d)
}

type Suite struct {
	Version     int      `json:"version" yaml:"version"`
	Name        string   `json:"name" yaml:"name"`
	Description string   `json:"description,omitempty" yaml:"description,omitempty"`
	Defaults    Defaults `json:"defaults,omitempty" yaml:"defaults,omitempty"`
	Cases       []Case   `json:"cases" yaml:"cases"`
	Source      string   `json:"-" yaml:"-"`
}

type Defaults struct {
	AgentID     string   `json:"agent_id,omitempty" yaml:"agent_id,omitempty"`
	Model       string   `json:"model,omitempty" yaml:"model,omitempty"`
	Repetitions int      `json:"repetitions,omitempty" yaml:"repetitions,omitempty"`
	Timeout     Duration `json:"timeout,omitempty" yaml:"timeout,omitempty"`
}

type Case struct {
	ID          string           `json:"id" yaml:"id"`
	Description string           `json:"description,omitempty" yaml:"description,omitempty"`
	Prompt      string           `json:"prompt" yaml:"prompt"`
	AgentID     string           `json:"agent_id,omitempty" yaml:"agent_id,omitempty"`
	Model       string           `json:"model,omitempty" yaml:"model,omitempty"`
	Repetitions int              `json:"repetitions,omitempty" yaml:"repetitions,omitempty"`
	Timeout     Duration         `json:"timeout,omitempty" yaml:"timeout,omitempty"`
	Tags        []string         `json:"tags,omitempty" yaml:"tags,omitempty"`
	Tools       []ToolDefinition `json:"tools,omitempty" yaml:"tools,omitempty"`
	Graders     []GraderSpec     `json:"graders" yaml:"graders"`
}

type GraderSpec struct {
	Type           string             `json:"type" yaml:"type"`
	Value          string             `json:"value,omitempty" yaml:"value,omitempty"`
	Values         []string           `json:"values,omitempty" yaml:"values,omitempty"`
	Pattern        string             `json:"pattern,omitempty" yaml:"pattern,omitempty"`
	CaseSensitive  bool               `json:"case_sensitive,omitempty" yaml:"case_sensitive,omitempty"`
	Calls          []ExpectedToolCall `json:"calls,omitempty" yaml:"calls,omitempty"`
	OrderSensitive bool               `json:"order_sensitive,omitempty" yaml:"order_sensitive,omitempty"`
	AllowExtra     bool               `json:"allow_extra,omitempty" yaml:"allow_extra,omitempty"`
}

type ToolDefinition struct {
	Name        string             `json:"name" yaml:"name"`
	Description string             `json:"description,omitempty" yaml:"description,omitempty"`
	Parameters  map[string]any     `json:"parameters" yaml:"parameters"`
	Result      string             `json:"result,omitempty" yaml:"result,omitempty"`
	Behavior    *StateToolBehavior `json:"behavior,omitempty" yaml:"behavior,omitempty"`
}

type StateToolBehavior struct {
	Conditions           []StateCondition `json:"conditions,omitempty" yaml:"conditions,omitempty"`
	Updates              []StateUpdate    `json:"updates,omitempty" yaml:"updates,omitempty"`
	Result               any              `json:"result,omitempty" yaml:"result,omitempty"`
	ResultPath           string           `json:"result_path,omitempty" yaml:"result_path,omitempty"`
	ResultKeysPath       string           `json:"result_keys_path,omitempty" yaml:"result_keys_path,omitempty"`
	ResultMapPath        string           `json:"result_map_path,omitempty" yaml:"result_map_path,omitempty"`
	ResultMapKeyArgument string           `json:"result_map_key_argument,omitempty" yaml:"result_map_key_argument,omitempty"`
}

type StateCondition struct {
	Path   string `json:"path" yaml:"path"`
	Equals any    `json:"equals" yaml:"equals"`
	Error  string `json:"error,omitempty" yaml:"error,omitempty"`
}

type StateUpdate struct {
	Path              string `json:"path" yaml:"path"`
	Value             any    `json:"value,omitempty" yaml:"value,omitempty"`
	ValueFromArgument string `json:"value_from_argument,omitempty" yaml:"value_from_argument,omitempty"`
	MapPath           string `json:"map_path,omitempty" yaml:"map_path,omitempty"`
	KeyFromArgument   string `json:"key_from_argument,omitempty" yaml:"key_from_argument,omitempty"`
}

type ExpectedToolCall struct {
	Name      string           `json:"name" yaml:"name"`
	Arguments map[string][]any `json:"arguments,omitempty" yaml:"arguments,omitempty"`
}

type TraceEvent struct {
	Type      string `json:"type"`
	ID        string `json:"id,omitempty"`
	Name      string `json:"name,omitempty"`
	Arguments string `json:"arguments,omitempty"`
	Result    string `json:"result,omitempty"`
	Message   string `json:"message,omitempty"`
	Round     int    `json:"round,omitempty"`
	Turn      int    `json:"turn,omitempty"`
}

type ExecutionRequest struct {
	Prompt       string
	AgentID      string
	Model        string
	SessionKey   string
	Tools        []ToolDefinition
	State        map[string]any
	IsolateTools bool
	Pricing      map[string]ModelPricing
}

type ModelPricing struct {
	InputPerMillion      float64 `json:"input_per_million" yaml:"input_per_million"`
	OutputPerMillion     float64 `json:"output_per_million" yaml:"output_per_million"`
	CacheReadPerMillion  float64 `json:"cache_read_per_million,omitempty" yaml:"cache_read_per_million,omitempty"`
	CacheWritePerMillion float64 `json:"cache_write_per_million,omitempty" yaml:"cache_write_per_million,omitempty"`
}

type Usage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

type ModelCallUsage struct {
	Sequence            int      `json:"sequence"`
	Phase               string   `json:"phase,omitempty"`
	AgentID             string   `json:"agent_id"`
	Role                string   `json:"role"`
	Model               string   `json:"model"`
	CallPath            []string `json:"call_path,omitempty"`
	PromptTokens        int      `json:"prompt_tokens"`
	CompletionTokens    int      `json:"completion_tokens"`
	TotalTokens         int      `json:"total_tokens"`
	CacheReadTokens     int      `json:"cache_read_tokens,omitempty"`
	CacheCreationTokens int      `json:"cache_creation_tokens,omitempty"`
	EstimatedCostUSD    float64  `json:"estimated_cost_usd"`
	Priced              bool     `json:"priced"`
	LatencyMS           float64  `json:"latency_ms"`
	Error               string   `json:"error,omitempty"`
}

type ExecutionResponse struct {
	Output     string
	Model      string
	Usage      Usage
	ModelCalls []ModelCallUsage
	Trace      []TraceEvent
	State      map[string]any
}

type Executor interface {
	Execute(ctx context.Context, request ExecutionRequest) (ExecutionResponse, error)
}

type GraderResult struct {
	Type    string `json:"type"`
	Passed  bool   `json:"passed"`
	Message string `json:"message,omitempty"`
}

type AttemptResult struct {
	Attempt        int                       `json:"attempt"`
	Passed         bool                      `json:"passed"`
	Output         string                    `json:"output,omitempty"`
	Error          string                    `json:"error,omitempty"`
	LatencyMS      float64                   `json:"latency_ms"`
	Model          string                    `json:"model,omitempty"`
	Usage          Usage                     `json:"usage"`
	Trace          []TraceEvent              `json:"trace,omitempty"`
	Graders        []GraderResult            `json:"graders,omitempty"`
	Turns          int                       `json:"turns,omitempty"`
	State          map[string]any            `json:"state,omitempty"`
	Kind           string                    `json:"kind,omitempty"`
	Patch          string                    `json:"patch,omitempty"`
	TestOutput     string                    `json:"test_output,omitempty"`
	TestsPassed    bool                      `json:"tests_passed,omitempty"`
	Completed      bool                      `json:"completed,omitempty"`
	BaselineOutput string                    `json:"baseline_output,omitempty"`
	ModelCalls     []ModelCallUsage          `json:"model_calls,omitempty"`
	MultiAgent     *MultiAgentAttemptMetrics `json:"multi_agent,omitempty"`
}

type CaseResult struct {
	ID          string          `json:"id"`
	Description string          `json:"description,omitempty"`
	Tags        []string        `json:"tags,omitempty"`
	Attempts    []AttemptResult `json:"attempts"`
	PassAt1     bool            `json:"pass_at_1"`
	PassAtK     bool            `json:"pass_at_k"`
	Consistent  bool            `json:"consistent"`
}

type Metrics struct {
	TotalCases                int     `json:"total_cases"`
	TotalRuns                 int     `json:"total_runs"`
	PassedRuns                int     `json:"passed_runs"`
	FailedRuns                int     `json:"failed_runs"`
	RunPassRate               float64 `json:"run_pass_rate"`
	PassAt1                   float64 `json:"pass_at_1"`
	PassAtK                   float64 `json:"pass_at_k"`
	ConsistencyRate           float64 `json:"consistency_rate"`
	LatencyP50MS              float64 `json:"latency_p50_ms"`
	LatencyP95MS              float64 `json:"latency_p95_ms"`
	PromptTokens              int     `json:"prompt_tokens"`
	CompletionTokens          int     `json:"completion_tokens"`
	TotalTokens               int     `json:"total_tokens"`
	TokensPerPassedRun        float64 `json:"tokens_per_passed_run"`
	TotalToolCalls            int     `json:"total_tool_calls"`
	InvalidToolCalls          int     `json:"invalid_tool_calls"`
	InvalidToolCallRate       float64 `json:"invalid_tool_call_rate"`
	ToolTraceGraders          int     `json:"tool_trace_graders"`
	PassedToolTraceGraders    int     `json:"passed_tool_trace_graders"`
	ToolTraceAccuracy         float64 `json:"tool_trace_accuracy"`
	StateGraders              int     `json:"state_graders"`
	PassedStateGraders        int     `json:"passed_state_graders"`
	StateAccuracy             float64 `json:"state_accuracy"`
	CommunicationGraders      int     `json:"communication_graders"`
	PassedCommunication       int     `json:"passed_communication_graders"`
	CommunicationAccuracy     float64 `json:"communication_accuracy"`
	PolicyGraders             int     `json:"policy_graders"`
	PassedPolicyGraders       int     `json:"passed_policy_graders"`
	PolicyComplianceRate      float64 `json:"policy_compliance_rate"`
	EndToEndTaskSuccess       float64 `json:"end_to_end_task_success"`
	AverageTurns              float64 `json:"average_turns"`
	SWESubmittedInstances     int     `json:"swe_submitted_instances"`
	SWECompletedInstances     int     `json:"swe_completed_instances"`
	SWEResolvedInstances      int     `json:"swe_resolved_instances"`
	SWEResolutionRate         float64 `json:"swe_resolution_rate"`
	SWEPatchesGenerated       int     `json:"swe_patches_generated"`
	SWEPatchGenerationRate    float64 `json:"swe_patch_generation_rate"`
	SWETestExecutionRate      float64 `json:"swe_test_execution_rate"`
	MAAttempts                int     `json:"multi_agent_attempts"`
	MATeamSuccessRate         float64 `json:"multi_agent_team_success_rate"`
	MASoloEvaluated           int     `json:"multi_agent_solo_evaluated"`
	MASoloSuccessRate         float64 `json:"multi_agent_solo_success_rate"`
	MACollaborationGain       float64 `json:"multi_agent_collaboration_gain"`
	MAMilestoneKPI            float64 `json:"multi_agent_milestone_kpi"`
	MADelegationPrecision     float64 `json:"multi_agent_delegation_precision"`
	MADelegationRecall        float64 `json:"multi_agent_delegation_recall"`
	MADelegationF1            float64 `json:"multi_agent_delegation_f1"`
	MAContributionUtilization float64 `json:"multi_agent_contribution_utilization"`
	MACoordinationScore       float64 `json:"multi_agent_coordination_score"`
	MAAverageDelegations      float64 `json:"multi_agent_average_delegations"`
	MAUnexpectedDelegations   int     `json:"multi_agent_unexpected_delegations"`
	MATotalEstimatedCostUSD   float64 `json:"multi_agent_total_estimated_cost_usd"`
	MASoloEstimatedCostUSD    float64 `json:"multi_agent_solo_estimated_cost_usd"`
	MATeamEstimatedCostUSD    float64 `json:"multi_agent_team_estimated_cost_usd"`
	MACoordinatorTokens       int     `json:"multi_agent_coordinator_tokens"`
	MASubAgentTokens          int     `json:"multi_agent_subagent_tokens"`
	MACoordinatorCostUSD      float64 `json:"multi_agent_coordinator_estimated_cost_usd"`
	MASubAgentCostUSD         float64 `json:"multi_agent_subagent_estimated_cost_usd"`
	MACoordinatorLatencyMS    float64 `json:"multi_agent_coordinator_model_latency_ms"`
	MASubAgentLatencyMS       float64 `json:"multi_agent_subagent_model_latency_ms"`
	MACostPerSuccessfulRunUSD float64 `json:"multi_agent_cost_per_successful_run_usd"`
	MAModelCalls              int     `json:"multi_agent_model_calls"`
	MAPricedModelCalls        int     `json:"multi_agent_priced_model_calls"`
	MAPricingCoverage         float64 `json:"multi_agent_pricing_coverage"`
}

type Report struct {
	Version     int          `json:"version"`
	Suite       string       `json:"suite"`
	Description string       `json:"description,omitempty"`
	Source      string       `json:"source,omitempty"`
	StartedAt   time.Time    `json:"started_at"`
	FinishedAt  time.Time    `json:"finished_at"`
	DurationMS  float64      `json:"duration_ms"`
	Metrics     Metrics      `json:"metrics"`
	Cases       []CaseResult `json:"cases"`
}
