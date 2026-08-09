package eval

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/rand"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

const (
	FinanceRetrievalModeSoloMonolithic    = "solo_monolithic"
	FinanceRetrievalModeSoloStaged        = "solo_staged"
	FinanceRetrievalModeTeamShared        = "team_shared_retrieval"
	FinanceRetrievalModeTeamRawContext    = "team_raw_context"
	FinanceRetrievalModeOracleEvidence    = "oracle_evidence"
	FinanceRetrievalModeTeamSharedAllPro  = "team_shared_retrieval_all_pro"
	financeRetrievalDefaultMinStageRecall = 0.75
)

type FinanceRetrievalSuite struct {
	Version              int                      `json:"version" yaml:"version"`
	Study                string                   `json:"study,omitempty" yaml:"study,omitempty"`
	Status               string                   `json:"status,omitempty" yaml:"status,omitempty"`
	Name                 string                   `json:"name" yaml:"name"`
	Description          string                   `json:"description,omitempty" yaml:"description,omitempty"`
	Dataset              string                   `json:"dataset" yaml:"dataset"`
	SourceLockSHA256     string                   `json:"source_lock_sha256" yaml:"source_lock_sha256"`
	Defaults             FinanceRetrievalDefaults `json:"defaults" yaml:"defaults"`
	Modes                []string                 `json:"modes" yaml:"modes"`
	PrimaryModes         []string                 `json:"primary_modes,omitempty" yaml:"primary_modes,omitempty"`
	DiagnosticModes      []string                 `json:"diagnostic_modes,omitempty" yaml:"diagnostic_modes,omitempty"`
	AblationModes        []string                 `json:"ablation_modes,omitempty" yaml:"ablation_modes,omitempty"`
	AblationCaseIDs      []string                 `json:"ablation_case_ids,omitempty" yaml:"ablation_case_ids,omitempty"`
	RandomizationSeed    int64                    `json:"randomization_seed,omitempty" yaml:"randomization_seed,omitempty"`
	PromptVersion        string                   `json:"prompt_version,omitempty" yaml:"prompt_version,omitempty"`
	GraderVersion        string                   `json:"grader_version,omitempty" yaml:"grader_version,omitempty"`
	PricingDate          string                   `json:"pricing_date,omitempty" yaml:"pricing_date,omitempty"`
	ModelAllocation      map[string]string        `json:"model_allocation,omitempty" yaml:"model_allocation,omitempty"`
	ExecutionControls    map[string]any           `json:"execution_controls,omitempty" yaml:"execution_controls,omitempty"`
	FormalFreezeBlockers []string                 `json:"formal_freeze_blockers,omitempty" yaml:"formal_freeze_blockers,omitempty"`
	Pricing              map[string]ModelPricing  `json:"pricing,omitempty" yaml:"pricing,omitempty"`
	Cases                []FinanceRetrievalCase   `json:"cases" yaml:"cases"`
	Source               string                   `json:"-" yaml:"-"`
	SourceSHA256         string                   `json:"-" yaml:"-"`
}

type FinanceRetrievalDefaults struct {
	CoordinatorAgentID     string                    `json:"coordinator_agent_id" yaml:"coordinator_agent_id"`
	SoloAgentID            string                    `json:"solo_agent_id" yaml:"solo_agent_id"`
	RetrieverAgentID       string                    `json:"retriever_agent_id" yaml:"retriever_agent_id"`
	Analysts               []FinanceRetrievalAnalyst `json:"analysts" yaml:"analysts"`
	Repetitions            int                       `json:"repetitions,omitempty" yaml:"repetitions,omitempty"`
	Timeout                Duration                  `json:"timeout,omitempty" yaml:"timeout,omitempty"`
	MinRetrievalRecall     float64                   `json:"min_retrieval_recall,omitempty" yaml:"min_retrieval_recall,omitempty"`
	MinSummaryRetention    float64                   `json:"min_summary_retention,omitempty" yaml:"min_summary_retention,omitempty"`
	MinFinalEvidenceRecall float64                   `json:"min_final_evidence_recall,omitempty" yaml:"min_final_evidence_recall,omitempty"`
	MinGroundingAccuracy   float64                   `json:"min_grounding_accuracy,omitempty" yaml:"min_grounding_accuracy,omitempty"`
	CapacityMatchedModel   string                    `json:"capacity_matched_model,omitempty" yaml:"capacity_matched_model,omitempty"`
}

type FinanceRetrievalAnalyst struct {
	AgentID     string `json:"agent_id" yaml:"agent_id"`
	Perspective string `json:"perspective" yaml:"perspective"`
	Instruction string `json:"instruction" yaml:"instruction"`
}

type FinanceRetrievalCase struct {
	ID                       string                   `json:"id" yaml:"id"`
	Company                  string                   `json:"company,omitempty" yaml:"company,omitempty"`
	TaskFamily               string                   `json:"task_family,omitempty" yaml:"task_family,omitempty"`
	ClusterID                string                   `json:"cluster_id,omitempty" yaml:"cluster_id,omitempty"`
	AsOfTimestamp            string                   `json:"as_of_timestamp,omitempty" yaml:"as_of_timestamp,omitempty"`
	AcceptedAtVerified       bool                     `json:"accepted_at_verified,omitempty" yaml:"accepted_at_verified,omitempty"`
	TemporalVerificationNote string                   `json:"temporal_verification_note,omitempty" yaml:"temporal_verification_note,omitempty"`
	ExcludedFutureSourceIDs  []string                 `json:"excluded_future_source_ids,omitempty" yaml:"excluded_future_source_ids,omitempty"`
	Description              string                   `json:"description,omitempty" yaml:"description,omitempty"`
	Question                 string                   `json:"question" yaml:"question"`
	AnalysisProtocol         string                   `json:"analysis_protocol" yaml:"analysis_protocol"`
	CorpusLoad               string                   `json:"corpus_load" yaml:"corpus_load"`
	Tags                     []string                 `json:"tags,omitempty" yaml:"tags,omitempty"`
	Records                  []FinanceRetrievalRecord `json:"records" yaml:"records"`
	GoldRecordIDs            []string                 `json:"gold_record_ids" yaml:"gold_record_ids"`
	GoldRecordGroups         [][]string               `json:"gold_record_groups,omitempty" yaml:"gold_record_groups,omitempty"`
	OracleEvidence           string                   `json:"oracle_evidence" yaml:"oracle_evidence"`
	Milestones               []MultiAgentMilestone    `json:"milestones" yaml:"milestones"`
	ForbiddenOutputValues    []string                 `json:"forbidden_output_values,omitempty" yaml:"forbidden_output_values,omitempty"`
	AuthorizedNumericValues  []string                 `json:"authorized_numeric_values,omitempty" yaml:"authorized_numeric_values,omitempty"`
	Repetitions              int                      `json:"repetitions,omitempty" yaml:"repetitions,omitempty"`
	Timeout                  Duration                 `json:"timeout,omitempty" yaml:"timeout,omitempty"`
	MinRetrievalRecall       float64                  `json:"min_retrieval_recall,omitempty" yaml:"min_retrieval_recall,omitempty"`
	MinSummaryRetention      float64                  `json:"min_summary_retention,omitempty" yaml:"min_summary_retention,omitempty"`
	MinFinalEvidenceRecall   float64                  `json:"min_final_evidence_recall,omitempty" yaml:"min_final_evidence_recall,omitempty"`
	MinGroundingAccuracy     float64                  `json:"min_grounding_accuracy,omitempty" yaml:"min_grounding_accuracy,omitempty"`
}

type FinanceRetrievalRecord struct {
	ID           string `json:"id" yaml:"id"`
	SourceID     string `json:"source_id" yaml:"source_id"`
	SourceSHA256 string `json:"source_sha256" yaml:"source_sha256"`
	Company      string `json:"company" yaml:"company"`
	Symbol       string `json:"symbol" yaml:"symbol"`
	FiledAt      string `json:"filed_at" yaml:"filed_at"`
	AcceptedAt   string `json:"accepted_at,omitempty" yaml:"accepted_at,omitempty"`
	Accession    string `json:"accession" yaml:"accession"`
	Locator      string `json:"locator" yaml:"locator"`
	Text         string `json:"text" yaml:"text"`
}

type FinanceRetrievalRunner struct {
	Executor Executor
	Options  RunOptions
}

type FinanceRetrievalReport struct {
	Version           int                          `json:"version"`
	Study             string                       `json:"study,omitempty"`
	Status            string                       `json:"status,omitempty"`
	RandomizationSeed int64                        `json:"randomization_seed,omitempty"`
	Suite             string                       `json:"suite"`
	Description       string                       `json:"description,omitempty"`
	Dataset           string                       `json:"dataset"`
	Source            string                       `json:"source,omitempty"`
	SourceSHA256      string                       `json:"source_sha256"`
	SourceLockSHA256  string                       `json:"source_lock_sha256"`
	StartedAt         time.Time                    `json:"started_at"`
	FinishedAt        time.Time                    `json:"finished_at"`
	DurationMS        float64                      `json:"duration_ms"`
	Metrics           FinanceRetrievalMetrics      `json:"metrics"`
	Cases             []FinanceRetrievalCaseResult `json:"cases"`
}

type FinanceRetrievalCaseResult struct {
	ID          string                          `json:"id"`
	Company     string                          `json:"company,omitempty"`
	TaskFamily  string                          `json:"task_family,omitempty"`
	ClusterID   string                          `json:"cluster_id,omitempty"`
	Description string                          `json:"description,omitempty"`
	CorpusLoad  string                          `json:"corpus_load"`
	Tags        []string                        `json:"tags,omitempty"`
	Attempts    []FinanceRetrievalAttemptResult `json:"attempts"`
}

type FinanceRetrievalAttemptResult struct {
	Attempt       int                          `json:"attempt"`
	PairID        string                       `json:"pair_id"`
	RealizedOrder []string                     `json:"realized_order"`
	Modes         []FinanceRetrievalModeResult `json:"modes"`
}

type FinanceRetrievalModeResult struct {
	Mode            string                       `json:"mode"`
	ObservationID   string                       `json:"observation_id"`
	OrderIndex      int                          `json:"order_index"`
	Passed          bool                         `json:"passed"`
	Error           string                       `json:"error,omitempty"`
	LatencyMS       float64                      `json:"latency_ms"`
	Usage           Usage                        `json:"usage"`
	ModelCalls      []ModelCallUsage             `json:"model_calls,omitempty"`
	Trace           []TraceEvent                 `json:"trace,omitempty"`
	RetrievalOutput string                       `json:"retrieval_output,omitempty"`
	AnalystOutputs  map[string]string            `json:"analyst_outputs,omitempty"`
	FinalOutput     string                       `json:"final_output,omitempty"`
	Stages          FinanceRetrievalStageMetrics `json:"stages"`
}

type FinanceRetrievalStageMetrics struct {
	GoldRecords              int             `json:"gold_records"`
	RetrievedRelevant        int             `json:"retrieved_relevant"`
	RetrievedTotal           int             `json:"retrieved_total"`
	RetrievalEvaluated       bool            `json:"retrieval_evaluated"`
	RetrievalRecall          float64         `json:"retrieval_recall"`
	RetrievalPrecision       float64         `json:"retrieval_precision"`
	SummaryRelevant          int             `json:"summary_relevant"`
	SummaryRetention         float64         `json:"summary_retention"`
	FinalRelevant            int             `json:"final_relevant"`
	FinalEvidenceRecall      float64         `json:"final_evidence_recall"`
	SynthesisRetention       float64         `json:"synthesis_retention"`
	CorpusCharacters         int             `json:"corpus_characters"`
	RetrievalCharacters      int             `json:"retrieval_characters"`
	EvidenceCompressionRatio float64         `json:"evidence_compression_ratio"`
	Milestones               int             `json:"milestones"`
	PassedMilestones         int             `json:"passed_milestones"`
	MilestoneResults         map[string]bool `json:"milestone_results,omitempty"`
	UnsupportedClaims        int             `json:"unsupported_claims"`
	GroundingAssertions      int             `json:"grounding_assertions"`
	GroundingViolations      int             `json:"grounding_violations"`
	GroundingViolationValues []string        `json:"grounding_violation_values,omitempty"`
	ExpectedDelegations      int             `json:"expected_delegations"`
	ValidDelegations         int             `json:"valid_delegations"`
	TotalDelegations         int             `json:"total_delegations"`
	DelegationPrecision      float64         `json:"delegation_precision"`
	DelegationRecall         float64         `json:"delegation_recall"`
	DelegationStatusCounts   map[string]int  `json:"delegation_status_counts,omitempty"`
	FirstAttemptSuccesses    int             `json:"first_attempt_successes"`
	RecoverySuccesses        int             `json:"recovery_successes"`
	RetrievalLatencyMS       float64         `json:"retrieval_latency_ms"`
	CollaborationLatencyMS   float64         `json:"collaboration_latency_ms"`
	CoordinationLatencyMS    float64         `json:"coordination_latency_ms"`
	AnalysisLatencyMS        float64         `json:"analysis_latency_ms"`
	SynthesisLatencyMS       float64         `json:"synthesis_latency_ms"`
}

type FinanceRetrievalMetrics struct {
	TotalCases int                                    `json:"total_cases"`
	Modes      map[string]FinanceRetrievalModeMetrics `json:"modes"`
}

type FinanceRetrievalModeMetrics struct {
	Attempts                      int     `json:"attempts"`
	Evaluated                     int     `json:"evaluated"`
	Errored                       int     `json:"errored"`
	Passed                        int     `json:"passed"`
	SuccessRate                   float64 `json:"success_rate"`
	AverageRetrievalRecall        float64 `json:"average_retrieval_recall"`
	AverageRetrievalPrecision     float64 `json:"average_retrieval_precision"`
	AverageSummaryRetention       float64 `json:"average_summary_retention"`
	AverageFinalEvidenceRecall    float64 `json:"average_final_evidence_recall"`
	AverageSynthesisRetention     float64 `json:"average_synthesis_retention"`
	AverageCompressionRatio       float64 `json:"average_compression_ratio"`
	MilestoneAccuracy             float64 `json:"milestone_accuracy"`
	DelegationPrecision           float64 `json:"delegation_precision"`
	DelegationRecall              float64 `json:"delegation_recall"`
	GroundingAccuracy             float64 `json:"grounding_accuracy"`
	PromptTokens                  int     `json:"prompt_tokens"`
	CompletionTokens              int     `json:"completion_tokens"`
	TotalTokens                   int     `json:"total_tokens"`
	EstimatedCostUSD              float64 `json:"estimated_cost_usd"`
	PricingCoverage               float64 `json:"pricing_coverage"`
	LatencyP50MS                  float64 `json:"latency_p50_ms"`
	LatencyP95MS                  float64 `json:"latency_p95_ms"`
	AverageRetrievalLatencyMS     float64 `json:"average_retrieval_latency_ms"`
	AverageCollaborationLatencyMS float64 `json:"average_collaboration_latency_ms"`
	AverageCoordinationLatencyMS  float64 `json:"average_coordination_latency_ms"`
	AverageAnalysisLatencyMS      float64 `json:"average_analysis_latency_ms"`
	AverageSynthesisLatencyMS     float64 `json:"average_synthesis_latency_ms"`
}

func LoadFinanceRetrievalSuite(path string) (FinanceRetrievalSuite, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return FinanceRetrievalSuite{}, fmt.Errorf("open finance retrieval eval suite: %w", err)
	}
	var suite FinanceRetrievalSuite
	decoder := yaml.NewDecoder(bytes.NewReader(data))
	decoder.KnownFields(true)
	if err := decoder.Decode(&suite); err != nil {
		return FinanceRetrievalSuite{}, fmt.Errorf("decode finance retrieval eval suite: %w", err)
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		if err == nil {
			return FinanceRetrievalSuite{}, errors.New("decode finance retrieval eval suite: multiple YAML documents are not supported")
		}
		return FinanceRetrievalSuite{}, fmt.Errorf("decode finance retrieval eval suite: %w", err)
	}
	suite.Source = path
	suite.SourceSHA256 = fmt.Sprintf("%x", sha256.Sum256(data))
	if err := suite.Validate(); err != nil {
		return FinanceRetrievalSuite{}, err
	}
	return suite, nil
}

func (s FinanceRetrievalSuite) Validate() error {
	if s.Version != SuiteVersion {
		return fmt.Errorf("finance retrieval eval suite version must be %d", SuiteVersion)
	}
	if strings.TrimSpace(s.Name) == "" || strings.TrimSpace(s.Dataset) == "" {
		return errors.New("finance retrieval suite name and dataset are required")
	}
	if len(s.SourceLockSHA256) != sha256.Size*2 {
		return errors.New("finance retrieval source_lock_sha256 must contain 64 hexadecimal characters")
	}
	if _, err := hex.DecodeString(s.SourceLockSHA256); err != nil {
		return errors.New("finance retrieval source_lock_sha256 must contain 64 hexadecimal characters")
	}
	if len(s.Modes) == 0 {
		return errors.New("finance retrieval suite modes are required")
	}
	seenModes := make(map[string]struct{}, len(s.Modes))
	for _, mode := range s.Modes {
		if !isFinanceRetrievalMode(mode) {
			return fmt.Errorf("unsupported finance retrieval mode %q", mode)
		}
		if _, exists := seenModes[mode]; exists {
			return fmt.Errorf("duplicate finance retrieval mode %q", mode)
		}
		seenModes[mode] = struct{}{}
	}
	seenTreatments := make(map[string]string)
	for group, modes := range map[string][]string{
		"primary_modes":    s.PrimaryModes,
		"diagnostic_modes": s.DiagnosticModes,
		"ablation_modes":   s.AblationModes,
	} {
		for _, mode := range modes {
			if _, exists := seenModes[mode]; !exists {
				return fmt.Errorf("finance retrieval %s contains undeclared mode %q", group, mode)
			}
			if previous := seenTreatments[mode]; previous != "" {
				return fmt.Errorf("finance retrieval mode %q appears in both %s and %s", mode, previous, group)
			}
			seenTreatments[mode] = group
		}
	}
	if len(s.PrimaryModes) > 0 && s.RandomizationSeed == 0 {
		return errors.New("finance retrieval primary modes require a non-zero randomization_seed")
	}
	if len(s.AblationModes) > 0 && strings.TrimSpace(s.Defaults.CapacityMatchedModel) == "" {
		return errors.New("finance retrieval ablation modes require defaults.capacity_matched_model")
	}
	if s.Study != "" {
		if s.Status != "draft" && s.Status != "frozen" {
			return errors.New("finance retrieval formal study status must be draft or frozen")
		}
		if s.Status == "frozen" && len(s.FormalFreezeBlockers) > 0 {
			return errors.New("finance retrieval frozen study cannot retain formal_freeze_blockers")
		}
		if s.PromptVersion == "" || s.GraderVersion == "" || s.PricingDate == "" || len(s.ModelAllocation) == 0 {
			return errors.New("finance retrieval formal study requires prompt, grader, pricing, and model metadata")
		}
		if len(s.ExecutionControls) == 0 {
			return errors.New("finance retrieval formal study requires execution_controls")
		}
	}
	if strings.TrimSpace(s.Defaults.CoordinatorAgentID) == "" ||
		strings.TrimSpace(s.Defaults.SoloAgentID) == "" ||
		strings.TrimSpace(s.Defaults.RetrieverAgentID) == "" {
		return errors.New("finance retrieval coordinator, solo, and retriever agent IDs are required")
	}
	if len(s.Defaults.Analysts) < 2 {
		return errors.New("finance retrieval suite requires at least two analyst agents")
	}
	seenAgents := map[string]struct{}{}
	for _, agentID := range []string{s.Defaults.CoordinatorAgentID, s.Defaults.SoloAgentID, s.Defaults.RetrieverAgentID} {
		seenAgents[agentID] = struct{}{}
	}
	for index, analyst := range s.Defaults.Analysts {
		if strings.TrimSpace(analyst.AgentID) == "" || strings.TrimSpace(analyst.Perspective) == "" || strings.TrimSpace(analyst.Instruction) == "" {
			return fmt.Errorf("finance retrieval analyst %d requires agent_id, perspective, and instruction", index+1)
		}
		if _, exists := seenAgents[analyst.AgentID]; exists {
			return fmt.Errorf("duplicate finance retrieval agent ID %q", analyst.AgentID)
		}
		seenAgents[analyst.AgentID] = struct{}{}
	}
	if s.Defaults.Repetitions < 0 || s.Defaults.Timeout.Value() < 0 {
		return errors.New("finance retrieval default repetitions and timeout cannot be negative")
	}
	for label, value := range map[string]float64{
		"min_retrieval_recall":      s.Defaults.MinRetrievalRecall,
		"min_summary_retention":     s.Defaults.MinSummaryRetention,
		"min_final_evidence_recall": s.Defaults.MinFinalEvidenceRecall,
	} {
		if value < 0 || value > 1 {
			return fmt.Errorf("finance retrieval default %s must be between 0 and 1", label)
		}
	}
	if len(s.Cases) == 0 {
		return errors.New("finance retrieval suite must contain at least one case")
	}
	seenCases := make(map[string]struct{}, len(s.Cases))
	for index := range s.Cases {
		if err := validateFinanceRetrievalCase(s.Cases[index], seenCases); err != nil {
			return err
		}
		if s.Status == "frozen" && s.Cases[index].TaskFamily == "point_in_time" && !s.Cases[index].AcceptedAtVerified {
			return fmt.Errorf("finance retrieval frozen point-in-time case %q requires accepted_at verification", s.Cases[index].ID)
		}
	}
	for model, pricing := range s.Pricing {
		if strings.TrimSpace(model) == "" || pricing.InputPerMillion < 0 || pricing.OutputPerMillion < 0 || pricing.CacheReadPerMillion < 0 || pricing.CacheWritePerMillion < 0 {
			return fmt.Errorf("invalid finance retrieval pricing for model %q", model)
		}
	}
	return nil
}

func validateFinanceRetrievalCase(evalCase FinanceRetrievalCase, seenCases map[string]struct{}) error {
	if strings.TrimSpace(evalCase.ID) == "" || strings.TrimSpace(evalCase.Question) == "" || strings.TrimSpace(evalCase.AnalysisProtocol) == "" {
		return errors.New("finance retrieval case id, question, and analysis protocol are required")
	}
	if _, exists := seenCases[evalCase.ID]; exists {
		return fmt.Errorf("duplicate finance retrieval case %q", evalCase.ID)
	}
	seenCases[evalCase.ID] = struct{}{}
	if evalCase.ClusterID != "" && (strings.TrimSpace(evalCase.Company) == "" || strings.TrimSpace(evalCase.TaskFamily) == "") {
		return fmt.Errorf("finance retrieval case %q cluster_id requires company and task_family", evalCase.ID)
	}
	if evalCase.TaskFamily == "point_in_time" && evalCase.AsOfTimestamp != "" {
		asOf, err := time.Parse(time.RFC3339, evalCase.AsOfTimestamp)
		if err != nil {
			return fmt.Errorf("finance retrieval case %q has invalid as_of_timestamp", evalCase.ID)
		}
		if evalCase.AcceptedAtVerified {
			for _, record := range evalCase.Records {
				acceptedAt, parseErr := time.Parse(time.RFC3339, record.AcceptedAt)
				if parseErr != nil || acceptedAt.After(asOf) {
					return fmt.Errorf("finance retrieval case %q has unverified or future accepted_at", evalCase.ID)
				}
			}
		}
	}
	switch evalCase.CorpusLoad {
	case "small", "medium", "large":
	default:
		return fmt.Errorf("finance retrieval case %q has invalid corpus_load %q", evalCase.ID, evalCase.CorpusLoad)
	}
	if evalCase.Repetitions < 0 || evalCase.Timeout.Value() < 0 {
		return fmt.Errorf("finance retrieval case %q repetitions and timeout cannot be negative", evalCase.ID)
	}
	if len(evalCase.Records) == 0 || len(evalCase.GoldRecordIDs) == 0 || len(evalCase.Milestones) == 0 || strings.TrimSpace(evalCase.OracleEvidence) == "" {
		return fmt.Errorf("finance retrieval case %q requires records, gold records, oracle evidence, and milestones", evalCase.ID)
	}
	records := make(map[string]struct{}, len(evalCase.Records))
	corpusBytes := 0
	for _, record := range evalCase.Records {
		if strings.TrimSpace(record.ID) == "" || strings.TrimSpace(record.SourceID) == "" || strings.TrimSpace(record.Text) == "" || len(record.SourceSHA256) != sha256.Size*2 {
			return fmt.Errorf("finance retrieval case %q contains an invalid corpus record", evalCase.ID)
		}
		if _, err := hex.DecodeString(record.SourceSHA256); err != nil {
			return fmt.Errorf("finance retrieval case %q record %q has an invalid source SHA-256", evalCase.ID, record.ID)
		}
		if _, exists := records[record.ID]; exists {
			return fmt.Errorf("finance retrieval case %q has duplicate record %q", evalCase.ID, record.ID)
		}
		records[record.ID] = struct{}{}
		corpusBytes += len(record.Text)
	}
	if corpusBytes > 2<<20 {
		return fmt.Errorf("finance retrieval case %q corpus exceeds 2 MiB", evalCase.ID)
	}
	gold := make(map[string]struct{}, len(evalCase.GoldRecordIDs))
	for _, recordID := range evalCase.GoldRecordIDs {
		if _, exists := records[recordID]; !exists {
			return fmt.Errorf("finance retrieval case %q gold record %q is absent from corpus", evalCase.ID, recordID)
		}
		if _, exists := gold[recordID]; exists {
			return fmt.Errorf("finance retrieval case %q has duplicate gold record %q", evalCase.ID, recordID)
		}
		gold[recordID] = struct{}{}
	}
	for groupIndex, group := range evalCase.GoldRecordGroups {
		if len(group) == 0 {
			return fmt.Errorf("finance retrieval case %q gold record group %d is empty", evalCase.ID, groupIndex)
		}
		seen := make(map[string]struct{}, len(group))
		for _, recordID := range group {
			if _, exists := records[recordID]; !exists {
				return fmt.Errorf("finance retrieval case %q gold record group %d references absent record %q", evalCase.ID, groupIndex, recordID)
			}
			if _, exists := seen[recordID]; exists {
				return fmt.Errorf("finance retrieval case %q gold record group %d duplicates record %q", evalCase.ID, groupIndex, recordID)
			}
			seen[recordID] = struct{}{}
		}
	}
	for _, value := range []float64{evalCase.MinRetrievalRecall, evalCase.MinSummaryRetention, evalCase.MinFinalEvidenceRecall, evalCase.MinGroundingAccuracy} {
		if value < 0 || value > 1 {
			return fmt.Errorf("finance retrieval case %q stage thresholds must be between 0 and 1", evalCase.ID)
		}
	}
	for _, value := range evalCase.AuthorizedNumericValues {
		if _, ok := canonicalNumericValue(value, "", ""); !ok {
			return fmt.Errorf("finance retrieval case %q has invalid authorized numeric value %q", evalCase.ID, value)
		}
	}
	return nil
}

func isFinanceRetrievalMode(mode string) bool {
	switch mode {
	case FinanceRetrievalModeSoloMonolithic,
		FinanceRetrievalModeSoloStaged,
		FinanceRetrievalModeTeamShared,
		FinanceRetrievalModeTeamRawContext,
		FinanceRetrievalModeOracleEvidence,
		FinanceRetrievalModeTeamSharedAllPro:
		return true
	default:
		return false
	}
}

func (r FinanceRetrievalRunner) Run(ctx context.Context, suite FinanceRetrievalSuite) (FinanceRetrievalReport, error) {
	if r.Executor == nil {
		return FinanceRetrievalReport{}, errors.New("finance retrieval eval executor is required")
	}
	if err := suite.Validate(); err != nil {
		return FinanceRetrievalReport{}, err
	}
	selectedCases, err := selectFinanceRetrievalCases(suite.Cases, r.Options.CaseIDs)
	if err != nil {
		return FinanceRetrievalReport{}, err
	}
	selectedModes, err := selectFinanceRetrievalModes(suite, r.Options.Modes)
	if err != nil {
		return FinanceRetrievalReport{}, err
	}
	startedAt := time.Now()
	runID := fmt.Sprintf("finance-retrieval-%d-%d", startedAt.UnixNano(), runSequence.Add(1))
	randomizationSeed := r.Options.RandomizationSeed
	if randomizationSeed == 0 {
		randomizationSeed = suite.RandomizationSeed
	}
	report := FinanceRetrievalReport{
		Version:           suite.Version,
		Study:             suite.Study,
		Status:            suite.Status,
		RandomizationSeed: randomizationSeed,
		Suite:             suite.Name,
		Description:       suite.Description,
		Dataset:           suite.Dataset,
		Source:            suite.Source,
		SourceSHA256:      suite.SourceSHA256,
		SourceLockSHA256:  suite.SourceLockSHA256,
		StartedAt:         startedAt,
		Cases:             make([]FinanceRetrievalCaseResult, 0, len(selectedCases)),
	}
	for _, evalCase := range selectedCases {
		caseResult := FinanceRetrievalCaseResult{
			ID:          evalCase.ID,
			Company:     evalCase.Company,
			TaskFamily:  evalCase.TaskFamily,
			ClusterID:   evalCase.ClusterID,
			Description: evalCase.Description,
			CorpusLoad:  evalCase.CorpusLoad,
			Tags:        append([]string(nil), evalCase.Tags...),
		}
		repetitions := firstPositive(r.Options.Repetitions, evalCase.Repetitions, suite.Defaults.Repetitions, 1)
		for attempt := 1; attempt <= repetitions; attempt++ {
			order := financeRetrievalExecutionOrder(suite, selectedModes, evalCase.ID, attempt, randomizationSeed)
			if len(order) == 0 {
				continue
			}
			pairID := financeRetrievalPairID(evalCase, attempt)
			attemptResult := FinanceRetrievalAttemptResult{
				Attempt:       attempt,
				PairID:        pairID,
				RealizedOrder: append([]string(nil), order...),
			}
			for index, mode := range order {
				attemptResult.Modes = append(attemptResult.Modes, r.runMode(ctx, suite, evalCase, mode, attempt, runID, pairID, index+1))
			}
			caseResult.Attempts = append(caseResult.Attempts, attemptResult)
		}
		report.Cases = append(report.Cases, caseResult)
	}
	report.FinishedAt = time.Now()
	report.DurationMS = milliseconds(report.FinishedAt.Sub(startedAt))
	report.Metrics = calculateFinanceRetrievalMetrics(report.Cases)
	return report, nil
}

func financeRetrievalPairID(evalCase FinanceRetrievalCase, repetition int) string {
	if evalCase.Company != "" && evalCase.TaskFamily != "" && evalCase.CorpusLoad != "" {
		return strings.Join([]string{
			"company=" + evalCase.Company,
			"task_family=" + evalCase.TaskFamily,
			"corpus_load=" + evalCase.CorpusLoad,
			"repetition=" + strconv.Itoa(repetition),
		}, "|")
	}
	return evalCase.ID + "|rep=" + strconv.Itoa(repetition)
}

func selectFinanceRetrievalModes(suite FinanceRetrievalSuite, requestedModes []string) ([]string, error) {
	if len(requestedModes) == 0 {
		if len(suite.PrimaryModes)+len(suite.DiagnosticModes) > 0 {
			selected := append([]string(nil), suite.PrimaryModes...)
			return append(selected, suite.DiagnosticModes...), nil
		}
		return suite.Modes, nil
	}
	requested := make(map[string]struct{}, len(requestedModes))
	for _, mode := range requestedModes {
		if mode = strings.TrimSpace(mode); mode != "" {
			requested[mode] = struct{}{}
		}
	}
	selected := make([]string, 0, len(requested))
	for _, mode := range suite.Modes {
		if _, exists := requested[mode]; exists {
			selected = append(selected, mode)
			delete(requested, mode)
		}
	}
	if len(requested) > 0 {
		missing := make([]string, 0, len(requested))
		for mode := range requested {
			missing = append(missing, mode)
		}
		sort.Strings(missing)
		return nil, fmt.Errorf("finance retrieval modes not found in suite: %s", strings.Join(missing, ", "))
	}
	return selected, nil
}

func financeRetrievalExecutionOrder(
	suite FinanceRetrievalSuite,
	selectedModes []string,
	caseID string,
	attempt int,
	seed int64,
) []string {
	if len(suite.PrimaryModes)+len(suite.DiagnosticModes)+len(suite.AblationModes) == 0 {
		return append([]string(nil), selectedModes...)
	}
	selected := make(map[string]struct{}, len(selectedModes))
	for _, mode := range selectedModes {
		selected[mode] = struct{}{}
	}
	primary := selectedFinanceModes(suite.PrimaryModes, selected)
	if len(primary) > 1 {
		digest := sha256.Sum256([]byte(fmt.Sprintf("%d|%s|%d", seed, caseID, attempt)))
		blockSeed := int64(binary.LittleEndian.Uint64(digest[:8]))
		random := rand.New(rand.NewSource(blockSeed))
		random.Shuffle(len(primary), func(left, right int) {
			primary[left], primary[right] = primary[right], primary[left]
		})
	}
	order := primary
	if attempt == 1 {
		order = append(order, selectedFinanceModes(suite.DiagnosticModes, selected)...)
	}
	if len(suite.AblationCaseIDs) == 0 || stringSliceContains(suite.AblationCaseIDs, caseID) {
		order = append(order, selectedFinanceModes(suite.AblationModes, selected)...)
	}
	return order
}

func selectedFinanceModes(configured []string, selected map[string]struct{}) []string {
	result := make([]string, 0, len(configured))
	for _, mode := range configured {
		if _, exists := selected[mode]; exists {
			result = append(result, mode)
		}
	}
	return result
}

func stringSliceContains(values []string, expected string) bool {
	for _, value := range values {
		if value == expected {
			return true
		}
	}
	return false
}

func selectFinanceRetrievalCases(cases []FinanceRetrievalCase, requestedIDs []string) ([]FinanceRetrievalCase, error) {
	if len(requestedIDs) == 0 {
		return cases, nil
	}
	requested := make(map[string]struct{}, len(requestedIDs))
	for _, caseID := range requestedIDs {
		if caseID = strings.TrimSpace(caseID); caseID != "" {
			requested[caseID] = struct{}{}
		}
	}
	selected := make([]FinanceRetrievalCase, 0, len(requested))
	for _, evalCase := range cases {
		if _, exists := requested[evalCase.ID]; exists {
			selected = append(selected, evalCase)
			delete(requested, evalCase.ID)
		}
	}
	if len(requested) > 0 {
		missing := make([]string, 0, len(requested))
		for caseID := range requested {
			missing = append(missing, caseID)
		}
		sort.Strings(missing)
		return nil, fmt.Errorf("finance retrieval cases not found: %s", strings.Join(missing, ", "))
	}
	return selected, nil
}

func (r FinanceRetrievalRunner) runMode(
	ctx context.Context,
	suite FinanceRetrievalSuite,
	evalCase FinanceRetrievalCase,
	mode string,
	attempt int,
	runID string,
	pairID string,
	orderIndex int,
) FinanceRetrievalModeResult {
	timeout := firstPositiveDuration(r.Options.Timeout, evalCase.Timeout.Value(), suite.Defaults.Timeout.Value(), 8*time.Minute)
	modeContext, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	startedAt := time.Now()
	result := FinanceRetrievalModeResult{
		Mode:           mode,
		ObservationID:  pairID + "|mode=" + mode,
		OrderIndex:     orderIndex,
		AnalystOutputs: make(map[string]string),
		Stages: FinanceRetrievalStageMetrics{
			GoldRecords:      len(financeGoldRecordGroups(evalCase)),
			CorpusCharacters: len(renderFinanceCorpus(evalCase.Records)),
			Milestones:       len(evalCase.Milestones),
			MilestoneResults: make(map[string]bool, len(evalCase.Milestones)),
		},
	}
	sessionBase := fmt.Sprintf("%s-%s-%d-%s", runID, sanitizeSessionPart(evalCase.ID), attempt, sanitizeSessionPart(mode))
	coordinatorID := firstNonEmpty(r.Options.AgentID, suite.Defaults.CoordinatorAgentID)
	model := r.Options.Model
	if mode == FinanceRetrievalModeTeamSharedAllPro {
		model = suite.Defaults.CapacityMatchedModel
	}

	switch mode {
	case FinanceRetrievalModeSoloMonolithic:
		response, latency, err := r.executeFinanceStage(modeContext, ExecutionRequest{
			Prompt:       financeSoloMonolithicPrompt(evalCase),
			AgentID:      suite.Defaults.SoloAgentID,
			Model:        model,
			SessionKey:   sessionBase,
			IsolateTools: true,
			Pricing:      suite.Pricing,
		}, mode+"/synthesis")
		result.Stages.SynthesisLatencyMS = latency
		r.consumeFinanceResponse(&result, response)
		result.FinalOutput = response.Output
		setFinanceModeError(&result, err)
	case FinanceRetrievalModeSoloStaged:
		r.runSoloStaged(modeContext, suite, evalCase, model, sessionBase, &result)
	case FinanceRetrievalModeTeamShared, FinanceRetrievalModeTeamSharedAllPro:
		r.runTeamShared(modeContext, suite, evalCase, coordinatorID, model, sessionBase, &result)
	case FinanceRetrievalModeTeamRawContext:
		response, latency, err := r.executeFinanceStage(modeContext, ExecutionRequest{
			Prompt:                    financeTeamPrompt(evalCase, suite.Defaults.Analysts, renderFinanceCorpus(evalCase.Records), false),
			AgentID:                   coordinatorID,
			Model:                     model,
			SessionKey:                sessionBase,
			IsolateTools:              false,
			Pricing:                   suite.Pricing,
			SubAgentMaxCalls:          len(suite.Defaults.Analysts),
			SubAgentMaxCallsPerTarget: 1,
		}, mode+"/collaboration")
		result.Stages.CollaborationLatencyMS = latency
		r.consumeFinanceResponse(&result, response)
		setFinanceTeamStageLatencies(&result.Stages, response.ModelCalls, coordinatorID)
		result.FinalOutput = response.Output
		result.Trace = response.Trace
		result.AnalystOutputs = financeAnalystOutputs(response.Trace, suite.Defaults.Analysts)
		setFinanceModeError(&result, err)
	case FinanceRetrievalModeOracleEvidence:
		response, latency, err := r.executeFinanceStage(modeContext, ExecutionRequest{
			Prompt:       financeOraclePrompt(evalCase),
			AgentID:      suite.Defaults.SoloAgentID,
			Model:        model,
			SessionKey:   sessionBase,
			IsolateTools: true,
			Pricing:      suite.Pricing,
		}, mode+"/synthesis")
		result.Stages.SynthesisLatencyMS = latency
		r.consumeFinanceResponse(&result, response)
		result.FinalOutput = response.Output
		setFinanceModeError(&result, err)
	}

	result.LatencyMS = milliseconds(time.Since(startedAt))
	if result.Error == "" {
		evaluateFinanceRetrievalMode(suite, evalCase, &result)
	}
	return result
}

func (r FinanceRetrievalRunner) runSoloStaged(ctx context.Context, suite FinanceRetrievalSuite, evalCase FinanceRetrievalCase, model, sessionBase string, result *FinanceRetrievalModeResult) {
	retrieval, latency, err := r.executeFinanceStage(ctx, ExecutionRequest{
		Prompt:       financeRetrievalPrompt(evalCase),
		AgentID:      suite.Defaults.SoloAgentID,
		Model:        model,
		SessionKey:   sessionBase + "-retrieval",
		IsolateTools: true,
		Pricing:      suite.Pricing,
	}, result.Mode+"/retrieval")
	result.Stages.RetrievalLatencyMS = latency
	r.consumeFinanceResponse(result, retrieval)
	result.RetrievalOutput = retrieval.Output
	if err != nil {
		setFinanceModeError(result, fmt.Errorf("retrieval stage: %w", err))
		return
	}
	analysisStarted := time.Now()
	for _, analyst := range suite.Defaults.Analysts {
		response, _, stageErr := r.executeFinanceStage(ctx, ExecutionRequest{
			Prompt:       financeAnalystPrompt(evalCase, analyst, retrieval.Output),
			AgentID:      suite.Defaults.SoloAgentID,
			Model:        model,
			SessionKey:   sessionBase + "-" + sanitizeSessionPart(analyst.Perspective),
			IsolateTools: true,
			Pricing:      suite.Pricing,
		}, result.Mode+"/analysis/"+sanitizeSessionPart(analyst.Perspective))
		r.consumeFinanceResponse(result, response)
		if stageErr != nil {
			setFinanceModeError(result, fmt.Errorf("%s analysis stage: %w", analyst.Perspective, stageErr))
			return
		}
		result.AnalystOutputs[analyst.Perspective] = response.Output
	}
	result.Stages.AnalysisLatencyMS = milliseconds(time.Since(analysisStarted))
	synthesis, latency, err := r.executeFinanceStage(ctx, ExecutionRequest{
		Prompt:       financeSynthesisPrompt(evalCase, result.AnalystOutputs),
		AgentID:      suite.Defaults.SoloAgentID,
		Model:        model,
		SessionKey:   sessionBase + "-synthesis",
		IsolateTools: true,
		Pricing:      suite.Pricing,
	}, result.Mode+"/synthesis")
	result.Stages.SynthesisLatencyMS = latency
	r.consumeFinanceResponse(result, synthesis)
	result.FinalOutput = synthesis.Output
	setFinanceModeError(result, err)
}

func (r FinanceRetrievalRunner) runTeamShared(ctx context.Context, suite FinanceRetrievalSuite, evalCase FinanceRetrievalCase, coordinatorID, model, sessionBase string, result *FinanceRetrievalModeResult) {
	retrieval, latency, err := r.executeFinanceStage(ctx, ExecutionRequest{
		Prompt:       financeRetrievalPrompt(evalCase),
		AgentID:      suite.Defaults.RetrieverAgentID,
		Model:        model,
		SessionKey:   sessionBase + "-retrieval",
		IsolateTools: true,
		Pricing:      suite.Pricing,
	}, result.Mode+"/retrieval")
	result.Stages.RetrievalLatencyMS = latency
	r.consumeFinanceResponse(result, retrieval)
	result.RetrievalOutput = retrieval.Output
	if err != nil {
		setFinanceModeError(result, fmt.Errorf("retrieval stage: %w", err))
		return
	}
	response, latency, err := r.executeFinanceStage(ctx, ExecutionRequest{
		Prompt:                    financeTeamPrompt(evalCase, suite.Defaults.Analysts, retrieval.Output, true),
		AgentID:                   coordinatorID,
		Model:                     model,
		SessionKey:                sessionBase + "-coordination",
		IsolateTools:              false,
		Pricing:                   suite.Pricing,
		SubAgentMaxCalls:          len(suite.Defaults.Analysts),
		SubAgentMaxCallsPerTarget: 1,
	}, result.Mode+"/collaboration")
	result.Stages.CollaborationLatencyMS = latency
	r.consumeFinanceResponse(result, response)
	setFinanceTeamStageLatencies(&result.Stages, response.ModelCalls, coordinatorID)
	result.FinalOutput = response.Output
	result.Trace = response.Trace
	result.AnalystOutputs = financeAnalystOutputs(response.Trace, suite.Defaults.Analysts)
	setFinanceModeError(result, err)
}

func (r FinanceRetrievalRunner) executeFinanceStage(ctx context.Context, request ExecutionRequest, phase string) (ExecutionResponse, float64, error) {
	startedAt := time.Now()
	response, err := r.Executor.Execute(ctx, request)
	latency := milliseconds(time.Since(startedAt))
	response.ModelCalls = appendModelCallPhase(nil, response.ModelCalls, phase)
	if err == nil && strings.TrimSpace(response.Output) == "" {
		err = errors.New("model returned empty output")
	}
	return response, latency, err
}

func (r FinanceRetrievalRunner) consumeFinanceResponse(result *FinanceRetrievalModeResult, response ExecutionResponse) {
	result.Usage = addUsage(result.Usage, response.Usage)
	result.ModelCalls = append(result.ModelCalls, response.ModelCalls...)
}

func setFinanceTeamStageLatencies(stages *FinanceRetrievalStageMetrics, calls []ModelCallUsage, coordinatorID string) {
	lastCoordinator := -1
	for index, call := range calls {
		if call.AgentID == coordinatorID {
			lastCoordinator = index
		}
	}
	for index, call := range calls {
		switch {
		case call.AgentID == coordinatorID && index == lastCoordinator:
			stages.SynthesisLatencyMS += call.LatencyMS
		case call.AgentID == coordinatorID:
			stages.CoordinationLatencyMS += call.LatencyMS
		case call.Role == "subagent":
			stages.AnalysisLatencyMS += call.LatencyMS
		}
	}
}

func setFinanceModeError(result *FinanceRetrievalModeResult, err error) {
	if err != nil && result.Error == "" {
		result.Error = err.Error()
	}
}

func evaluateFinanceRetrievalMode(suite FinanceRetrievalSuite, evalCase FinanceRetrievalCase, result *FinanceRetrievalModeResult) {
	recordIDs := financeRecordIDs(evalCase.Records)
	goldGroups := financeGoldRecordGroups(evalCase)
	relevantRecords := make(map[string]struct{})
	for _, group := range goldGroups {
		for _, recordID := range group {
			relevantRecords[recordID] = struct{}{}
		}
	}
	stages := &result.Stages
	if strings.TrimSpace(result.RetrievalOutput) != "" {
		stages.RetrievalEvaluated = true
		retrieved := mentionedFinanceRecords(result.RetrievalOutput, recordIDs)
		stages.RetrievedTotal = len(retrieved)
		stages.RetrievedRelevant = len(matchedFinanceGoldGroups(retrieved, goldGroups))
		stages.RetrievalRecall = safeRatio(stages.RetrievedRelevant, len(goldGroups))
		stages.RetrievalPrecision = safeRatio(intersectionSize(retrieved, relevantRecords), stages.RetrievedTotal)
		stages.RetrievalCharacters = len(result.RetrievalOutput)
		if stages.RetrievalCharacters > 0 {
			stages.EvidenceCompressionRatio = float64(stages.CorpusCharacters) / float64(stages.RetrievalCharacters)
		}
	}
	summaries := strings.Join(sortedMapValues(result.AnalystOutputs), "\n")
	summaryRecords := mentionedFinanceRecords(summaries, recordIDs)
	summaryGroups := matchedFinanceGoldGroups(summaryRecords, goldGroups)
	stages.SummaryRelevant = len(summaryGroups)
	if stages.RetrievedRelevant > 0 {
		retrievedGroups := matchedFinanceGoldGroups(mentionedFinanceRecords(result.RetrievalOutput, recordIDs), goldGroups)
		stages.SummaryRetention = float64(intersectionIntSize(summaryGroups, retrievedGroups)) / float64(stages.RetrievedRelevant)
	}
	finalRecords := mentionedFinanceRecords(result.FinalOutput, recordIDs)
	finalGroups := matchedFinanceGoldGroups(finalRecords, goldGroups)
	stages.FinalRelevant = len(finalGroups)
	stages.FinalEvidenceRecall = safeRatio(stages.FinalRelevant, len(goldGroups))
	if stages.SummaryRelevant > 0 {
		stages.SynthesisRetention = float64(intersectionIntSize(finalGroups, summaryGroups)) / float64(stages.SummaryRelevant)
	}
	for _, milestone := range evalCase.Milestones {
		passed := containsAllAssertions(result.FinalOutput, milestone.Values)
		stages.MilestoneResults[milestone.ID] = passed
		if passed {
			stages.PassedMilestones++
		}
	}
	for _, forbidden := range evalCase.ForbiddenOutputValues {
		if containsForbiddenAssertion(result.FinalOutput, forbidden) {
			stages.UnsupportedClaims++
		}
	}
	stages.GroundingAssertions, stages.GroundingViolations = evaluateCaseGrounding(result.FinalOutput, MultiAgentCase{
		ForbiddenOutputValues:   evalCase.ForbiddenOutputValues,
		AuthorizedNumericValues: evalCase.AuthorizedNumericValues,
	})
	_, stages.GroundingViolationValues = evaluateNumericGroundingDetails(result.FinalOutput, evalCase.AuthorizedNumericValues)
	if result.Mode == FinanceRetrievalModeTeamShared || result.Mode == FinanceRetrievalModeTeamSharedAllPro || result.Mode == FinanceRetrievalModeTeamRawContext {
		evaluateFinanceDelegations(result.Trace, suite.Defaults.Analysts, stages)
	}
	minRetrieval := financeThreshold(evalCase.MinRetrievalRecall, suite.Defaults.MinRetrievalRecall)
	minSummary := financeThreshold(evalCase.MinSummaryRetention, suite.Defaults.MinSummaryRetention)
	minFinal := financeThreshold(evalCase.MinFinalEvidenceRecall, suite.Defaults.MinFinalEvidenceRecall)
	minGrounding := financeThreshold(evalCase.MinGroundingAccuracy, suite.Defaults.MinGroundingAccuracy)
	passed := stages.PassedMilestones == stages.Milestones && stages.UnsupportedClaims == 0 && safeGroundingAccuracy(stages.GroundingAssertions, stages.GroundingViolations) >= minGrounding && stages.FinalEvidenceRecall >= minFinal
	switch result.Mode {
	case FinanceRetrievalModeSoloStaged, FinanceRetrievalModeTeamShared, FinanceRetrievalModeTeamSharedAllPro:
		passed = passed && stages.RetrievalRecall >= minRetrieval && stages.SummaryRetention >= minSummary
	case FinanceRetrievalModeTeamRawContext:
		passed = passed && stages.DelegationPrecision == 1 && stages.DelegationRecall == 1
	}
	if result.Mode == FinanceRetrievalModeTeamShared || result.Mode == FinanceRetrievalModeTeamSharedAllPro {
		passed = passed && stages.DelegationPrecision == 1 && stages.DelegationRecall == 1
	}
	result.Passed = passed
}

func financeGoldRecordGroups(evalCase FinanceRetrievalCase) [][]string {
	if len(evalCase.GoldRecordGroups) > 0 {
		return evalCase.GoldRecordGroups
	}
	groups := make([][]string, 0, len(evalCase.GoldRecordIDs))
	for _, recordID := range evalCase.GoldRecordIDs {
		groups = append(groups, []string{recordID})
	}
	return groups
}

func matchedFinanceGoldGroups(mentioned map[string]struct{}, groups [][]string) map[int]struct{} {
	matched := make(map[int]struct{}, len(groups))
	for index, group := range groups {
		for _, recordID := range group {
			if _, exists := mentioned[recordID]; exists {
				matched[index] = struct{}{}
				break
			}
		}
	}
	return matched
}

func intersectionIntSize(left, right map[int]struct{}) int {
	count := 0
	for value := range left {
		if _, exists := right[value]; exists {
			count++
		}
	}
	return count
}

func evaluateFinanceDelegations(trace []TraceEvent, analysts []FinanceRetrievalAnalyst, stages *FinanceRetrievalStageMetrics) {
	expected := make(map[string]struct{}, len(analysts))
	for _, analyst := range analysts {
		expected[analyst.AgentID] = struct{}{}
	}
	valid := make(map[string]struct{}, len(analysts))
	delegations := multiAgentDelegations(trace)
	stages.ExpectedDelegations = len(expected)
	stages.TotalDelegations = len(delegations)
	for _, delegation := range delegations {
		if _, exists := expected[delegation.AgentID]; exists {
			valid[delegation.AgentID] = struct{}{}
		}
	}
	stages.ValidDelegations = len(valid)
	stages.DelegationRecall = safeRatio(len(valid), len(expected))
	if len(delegations) > 0 {
		validCalls := 0
		for _, delegation := range delegations {
			if _, exists := expected[delegation.AgentID]; exists {
				validCalls++
			}
		}
		stages.DelegationPrecision = float64(validCalls) / float64(len(delegations))
	}
	statuses := financeDelegationStatuses(trace)
	if len(statuses) > 0 {
		stages.DelegationStatusCounts = make(map[string]int)
	}
	for _, agentStatuses := range statuses {
		for _, status := range agentStatuses {
			stages.DelegationStatusCounts[status]++
		}
		if agentStatuses[0] == "success" {
			stages.FirstAttemptSuccesses++
			continue
		}
		for _, status := range agentStatuses[1:] {
			if status == "success" {
				stages.RecoverySuccesses++
				break
			}
		}
	}
}

func financeDelegationStatuses(trace []TraceEvent) map[string][]string {
	agentsByCallID := make(map[string][]string)
	statuses := make(map[string][]string)
	for _, event := range trace {
		if event.Type == "tool_call" && event.Name == "spawn_subagent" && event.ID != "" {
			var arguments struct {
				AgentID     string `json:"agentId"`
				Delegations []struct {
					AgentID string `json:"agentId"`
				} `json:"delegations"`
			}
			if json.Unmarshal([]byte(event.Arguments), &arguments) == nil {
				if arguments.AgentID != "" {
					agentsByCallID[event.ID] = []string{arguments.AgentID}
				} else {
					for _, delegation := range arguments.Delegations {
						agentsByCallID[event.ID] = append(agentsByCallID[event.ID], delegation.AgentID)
					}
				}
			}
			continue
		}
		if event.Type != "tool_result" || event.Name != "spawn_subagent" || event.ID == "" {
			continue
		}
		agentIDs := agentsByCallID[event.ID]
		if len(agentIDs) == 1 {
			var item struct {
				AgentID string `json:"agentId"`
				Status  string `json:"status"`
			}
			if json.Unmarshal([]byte(event.Result), &item) == nil && item.Status != "" {
				agentID := item.AgentID
				if agentID == "" {
					agentID = agentIDs[0]
				}
				statuses[agentID] = append(statuses[agentID], item.Status)
			}
			continue
		}
		if len(agentIDs) > 1 {
			var batch struct {
				Results []struct {
					AgentID string `json:"agentId"`
					Status  string `json:"status"`
				} `json:"results"`
			}
			if json.Unmarshal([]byte(event.Result), &batch) == nil {
				for _, item := range batch.Results {
					if item.AgentID != "" && item.Status != "" {
						statuses[item.AgentID] = append(statuses[item.AgentID], item.Status)
					}
				}
			}
		}
	}
	return statuses
}

func financeAnalystOutputs(trace []TraceEvent, analysts []FinanceRetrievalAnalyst) map[string]string {
	byAgent, _ := multiAgentDelegationResults(trace)
	outputs := make(map[string]string, len(analysts))
	for _, analyst := range analysts {
		outputs[analyst.Perspective] = strings.Join(byAgent[analyst.AgentID], "\n")
	}
	return outputs
}

func financeThreshold(caseValue, defaultValue float64) float64 {
	if caseValue > 0 {
		return caseValue
	}
	if defaultValue > 0 {
		return defaultValue
	}
	return financeRetrievalDefaultMinStageRecall
}

func renderFinanceCorpus(records []FinanceRetrievalRecord) string {
	var builder strings.Builder
	for _, record := range records {
		fmt.Fprintf(&builder, "[%s]\nsource_id: %s\nsource_sha256: %s\ncompany: %s (%s)\nfiled_at: %s\naccession: %s\nlocator: %s\ntext: %s\n\n", record.ID, record.SourceID, record.SourceSHA256, record.Company, record.Symbol, record.FiledAt, record.Accession, record.Locator, record.Text)
	}
	return builder.String()
}

func financeRetrievalPrompt(evalCase FinanceRetrievalCase) string {
	return fmt.Sprintf(`You are the retrieval stage of a point-in-time financial research pipeline.
Select only corpus records needed to answer the research question. Do not use
outside knowledge, calculate ratios, decide the investment state, or make a
trading recommendation. Return a compact Evidence Bundle. Every retained fact
must cite its bracketed record ID, source ID, filing date, period/basis if
present, and exact source wording. Omit distractors but preserve conflicting
records instead of resolving them.

Research question:
%s

Common analysis protocol (task requirements, not source evidence):
%s

Locked SEC corpus:
%s`, evalCase.Question, evalCase.AnalysisProtocol, renderFinanceCorpus(evalCase.Records))
}

func financeSoloMonolithicPrompt(evalCase FinanceRetrievalCase) string {
	return fmt.Sprintf(`Complete this financial research task as one monolithic agent. You must
retrieve relevant records from the locked corpus, check period and accounting
basis, perform only justified calculations, assess risks, and synthesize the
final research-state decision. Use no outside knowledge. Cite every material
claim with bracketed corpus record IDs. Distinguish verified facts, derived
calculations, and bounded research decisions. Do not recommend or authorize a
trade. Return Retrieved Evidence, Trend Analysis, Accounting and Period Audit,
Risk and Governance, Final Decision, and Limitations sections.

Research question:
%s

Common analysis protocol (task requirements, not source evidence):
%s

Locked SEC corpus:
%s`, evalCase.Question, evalCase.AnalysisProtocol, renderFinanceCorpus(evalCase.Records))
}

func financeAnalystPrompt(evalCase FinanceRetrievalCase, analyst FinanceRetrievalAnalyst, evidenceBundle string) string {
	return fmt.Sprintf(`Analyze the supplied Evidence Bundle from the %s perspective.
%s
Use only the bundle, cite bracketed record IDs for every material claim, expose
missing or conflicting evidence, and do not make a trading recommendation.

Research question:
%s

Common analysis protocol (task requirements, not source evidence):
%s

Evidence Bundle:
%s`, analyst.Perspective, analyst.Instruction, evalCase.Question, evalCase.AnalysisProtocol, evidenceBundle)
}

func financeSynthesisPrompt(evalCase FinanceRetrievalCase, analystOutputs map[string]string) string {
	var builder strings.Builder
	for _, perspective := range sortedMapKeys(analystOutputs) {
		fmt.Fprintf(&builder, "## %s\n%s\n\n", perspective, analystOutputs[perspective])
	}
	return fmt.Sprintf(`Synthesize the analyst reports into one auditable answer to the research
question. Use no facts absent from the reports. Preserve bracketed record IDs,
separate verified facts from calculations and research-state judgments, state
material uncertainty, and do not recommend or authorize a trade. Return
Chronology, Evidence Reconciliation, Calculation Audit, Risk and Governance,
Final Decision, and Limitations sections.

Research question:
%s

Common analysis protocol (task requirements, not source evidence):
%s

Analyst reports:
%s`, evalCase.Question, evalCase.AnalysisProtocol, builder.String())
}

func financeTeamPrompt(evalCase FinanceRetrievalCase, analysts []FinanceRetrievalAnalyst, evidence string, compressed bool) string {
	contextLabel := "Raw locked SEC corpus"
	if compressed {
		contextLabel = "Shared retriever Evidence Bundle"
	}
	var roles strings.Builder
	for _, analyst := range analysts {
		fmt.Fprintf(&roles, "- %s (%s): %s\n", analyst.AgentID, analyst.Perspective, analyst.Instruction)
	}
	return fmt.Sprintf(`Coordinate a financial research team. Issue exactly one batch spawn_subagent
call: put the research question, common analysis protocol, and supplied evidence
in sharedContext once, and put one concise agentId/task item containing only the
assigned perspective in delegations. The runtime will append sharedContext to
every focused task and execute distinct targets concurrently. Do not copy any
shared material into individual tasks.
Then synthesize their reports. Use no outside knowledge, preserve
bracketed record IDs, distinguish facts from calculations and decisions, state
uncertainty, and do not recommend or authorize a trade. Return Chronology,
Evidence Reconciliation, Calculation Audit, Risk and Governance, Final
Decision, and Limitations sections.

Research question:
%s

Common analysis protocol (task requirements, not source evidence):
%s

Specialists:
%s
%s:
%s`, evalCase.Question, evalCase.AnalysisProtocol, roles.String(), contextLabel, evidence)
}

func financeOraclePrompt(evalCase FinanceRetrievalCase) string {
	return fmt.Sprintf(`Answer the financial research question from the oracle evidence packet.
Retrieval has already been completed perfectly. Use no outside knowledge,
preserve every bracketed record ID, distinguish facts from calculations and
research-state judgments, and do not recommend or authorize a trade. Return
Chronology, Evidence Reconciliation, Calculation Audit, Risk and Governance,
Final Decision, and Limitations sections.

Research question:
%s

Common analysis protocol (task requirements, not source evidence):
%s

Oracle evidence packet:
%s`, evalCase.Question, evalCase.AnalysisProtocol, evalCase.OracleEvidence)
}

func calculateFinanceRetrievalMetrics(cases []FinanceRetrievalCaseResult) FinanceRetrievalMetrics {
	metrics := FinanceRetrievalMetrics{TotalCases: len(cases), Modes: make(map[string]FinanceRetrievalModeMetrics)}
	latencies := make(map[string][]float64)
	retrievalEvaluated := make(map[string]int)
	summaryEvaluated := make(map[string]int)
	synthesisEvaluated := make(map[string]int)
	pricedCalls := make(map[string]int)
	totalCalls := make(map[string]int)
	for _, evalCase := range cases {
		for _, attempt := range evalCase.Attempts {
			for _, result := range attempt.Modes {
				mode := metrics.Modes[result.Mode]
				mode.Attempts++
				mode.PromptTokens += result.Usage.PromptTokens
				mode.CompletionTokens += result.Usage.CompletionTokens
				mode.TotalTokens += result.Usage.TotalTokens
				for _, call := range result.ModelCalls {
					mode.EstimatedCostUSD += call.EstimatedCostUSD
					totalCalls[result.Mode]++
					if call.Priced {
						pricedCalls[result.Mode]++
					}
				}
				if result.Error != "" {
					mode.Errored++
					metrics.Modes[result.Mode] = mode
					continue
				}
				mode.Evaluated++
				if result.Passed {
					mode.Passed++
				}
				latencies[result.Mode] = append(latencies[result.Mode], result.LatencyMS)
				mode.AverageFinalEvidenceRecall += result.Stages.FinalEvidenceRecall
				mode.AverageRetrievalLatencyMS += result.Stages.RetrievalLatencyMS
				mode.AverageCollaborationLatencyMS += result.Stages.CollaborationLatencyMS
				mode.AverageCoordinationLatencyMS += result.Stages.CoordinationLatencyMS
				mode.AverageAnalysisLatencyMS += result.Stages.AnalysisLatencyMS
				mode.AverageSynthesisLatencyMS += result.Stages.SynthesisLatencyMS
				if result.Stages.RetrievalEvaluated {
					retrievalEvaluated[result.Mode]++
					mode.AverageRetrievalRecall += result.Stages.RetrievalRecall
					mode.AverageRetrievalPrecision += result.Stages.RetrievalPrecision
					mode.AverageCompressionRatio += result.Stages.EvidenceCompressionRatio
				}
				if result.Stages.SummaryRelevant > 0 || len(result.AnalystOutputs) > 0 {
					summaryEvaluated[result.Mode]++
					mode.AverageSummaryRetention += result.Stages.SummaryRetention
				}
				if result.Stages.SummaryRelevant > 0 {
					synthesisEvaluated[result.Mode]++
					mode.AverageSynthesisRetention += result.Stages.SynthesisRetention
				}
				mode.MilestoneAccuracy += safeRatio(result.Stages.PassedMilestones, result.Stages.Milestones)
				mode.DelegationPrecision += result.Stages.DelegationPrecision
				mode.DelegationRecall += result.Stages.DelegationRecall
				mode.GroundingAccuracy += safeGroundingAccuracy(result.Stages.GroundingAssertions, result.Stages.GroundingViolations)
				metrics.Modes[result.Mode] = mode
			}
		}
	}
	for name, mode := range metrics.Modes {
		if mode.Evaluated > 0 {
			denominator := float64(mode.Evaluated)
			mode.SuccessRate = float64(mode.Passed) / denominator
			mode.AverageFinalEvidenceRecall /= denominator
			mode.MilestoneAccuracy /= denominator
			mode.AverageRetrievalLatencyMS /= denominator
			mode.AverageCollaborationLatencyMS /= denominator
			mode.AverageCoordinationLatencyMS /= denominator
			mode.AverageAnalysisLatencyMS /= denominator
			mode.AverageSynthesisLatencyMS /= denominator
			mode.DelegationPrecision /= denominator
			mode.DelegationRecall /= denominator
			mode.GroundingAccuracy /= denominator
		}
		if retrievalEvaluated[name] > 0 {
			denominator := float64(retrievalEvaluated[name])
			mode.AverageRetrievalRecall /= denominator
			mode.AverageRetrievalPrecision /= denominator
			mode.AverageCompressionRatio /= denominator
		}
		if summaryEvaluated[name] > 0 {
			mode.AverageSummaryRetention /= float64(summaryEvaluated[name])
		}
		if synthesisEvaluated[name] > 0 {
			mode.AverageSynthesisRetention /= float64(synthesisEvaluated[name])
		}
		sort.Float64s(latencies[name])
		mode.LatencyP50MS = percentile(latencies[name], 0.50)
		mode.LatencyP95MS = percentile(latencies[name], 0.95)
		if totalCalls[name] > 0 {
			mode.PricingCoverage = float64(pricedCalls[name]) / float64(totalCalls[name])
		}
		metrics.Modes[name] = mode
	}
	return metrics
}

func WriteFinanceRetrievalJSON(writer io.Writer, report FinanceRetrievalReport) error {
	encoder := json.NewEncoder(writer)
	encoder.SetIndent("", "  ")
	return encoder.Encode(report)
}

func WriteFinanceRetrievalText(writer io.Writer, report FinanceRetrievalReport) error {
	if _, err := fmt.Fprintf(writer, "Finance retrieval suite: %s\nStudy/status: %s / %s\nRandomization seed: %d\nDataset: %s\nSuite SHA-256: %s\nSource-lock SHA-256: %s\n", report.Suite, report.Study, report.Status, report.RandomizationSeed, report.Dataset, report.SourceSHA256, report.SourceLockSHA256); err != nil {
		return err
	}
	for _, modeName := range []string{FinanceRetrievalModeSoloMonolithic, FinanceRetrievalModeSoloStaged, FinanceRetrievalModeTeamShared, FinanceRetrievalModeTeamRawContext, FinanceRetrievalModeOracleEvidence} {
		mode, exists := report.Metrics.Modes[modeName]
		if !exists {
			continue
		}
		if _, err := fmt.Fprintf(writer, "%s: valid %d | errors %d | success %.1f%% | retrieval R/P %.1f/%.1f%% | summary retention %.1f%% | final evidence %.1f%% | milestones %.1f%% | grounding %.1f%% | tokens %d | cost $%.4f | p50/p95 %.1f/%.1f ms\n", modeName, mode.Evaluated, mode.Errored, mode.SuccessRate*100, mode.AverageRetrievalRecall*100, mode.AverageRetrievalPrecision*100, mode.AverageSummaryRetention*100, mode.AverageFinalEvidenceRecall*100, mode.MilestoneAccuracy*100, mode.GroundingAccuracy*100, mode.TotalTokens, mode.EstimatedCostUSD, mode.LatencyP50MS, mode.LatencyP95MS); err != nil {
			return err
		}
	}
	for _, evalCase := range report.Cases {
		if _, err := fmt.Fprintf(writer, "\n%s [%s]\n", evalCase.ID, evalCase.CorpusLoad); err != nil {
			return err
		}
		for _, attempt := range evalCase.Attempts {
			if _, err := fmt.Fprintf(writer, "  pair %s | order %s\n", attempt.PairID, strings.Join(attempt.RealizedOrder, ", ")); err != nil {
				return err
			}
			for _, mode := range attempt.Modes {
				status := "PASS"
				if mode.Error != "" {
					status = "ERROR"
				} else if !mode.Passed {
					status = "FAIL"
				}
				if _, err := fmt.Fprintf(writer, "  %s %-23s %.1f ms | retrieval %.1f%% | summary %.1f%% | final %.1f%%", status, mode.Mode, mode.LatencyMS, mode.Stages.RetrievalRecall*100, mode.Stages.SummaryRetention*100, mode.Stages.FinalEvidenceRecall*100); err != nil {
					return err
				}
				if mode.Error != "" {
					if _, err := fmt.Fprintf(writer, " | %s", mode.Error); err != nil {
						return err
					}
				}
				if _, err := fmt.Fprintln(writer); err != nil {
					return err
				}
			}
		}
	}
	return nil
}

func financeRecordIDs(records []FinanceRetrievalRecord) []string {
	ids := make([]string, 0, len(records))
	for _, record := range records {
		ids = append(ids, record.ID)
	}
	return ids
}

func mentionedFinanceRecords(output string, recordIDs []string) map[string]struct{} {
	mentioned := make(map[string]struct{})
	lowered := strings.ToLower(output)
	for _, recordID := range recordIDs {
		if strings.Contains(lowered, strings.ToLower(recordID)) {
			mentioned[recordID] = struct{}{}
		}
	}
	return mentioned
}

func stringSet(values []string) map[string]struct{} {
	result := make(map[string]struct{}, len(values))
	for _, value := range values {
		result[value] = struct{}{}
	}
	return result
}

func intersectionSet(left, right map[string]struct{}) map[string]struct{} {
	result := make(map[string]struct{})
	for value := range left {
		if _, exists := right[value]; exists {
			result[value] = struct{}{}
		}
	}
	return result
}

func intersectionSize(left, right map[string]struct{}) int {
	return len(intersectionSet(left, right))
}

func safeRatio(numerator, denominator int) float64 {
	if denominator == 0 {
		return 0
	}
	return float64(numerator) / float64(denominator)
}

func safeGroundingAccuracy(assertions, violations int) float64 {
	if assertions == 0 {
		return 1
	}
	return 1 - float64(violations)/float64(assertions)
}

func sortedMapKeys(values map[string]string) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func sortedMapValues(values map[string]string) []string {
	result := make([]string, 0, len(values))
	for _, key := range sortedMapKeys(values) {
		result = append(result, values[key])
	}
	return result
}

func firstPositive(values ...int) int {
	for _, value := range values {
		if value > 0 {
			return value
		}
	}
	return 0
}

func firstPositiveDuration(values ...time.Duration) time.Duration {
	for _, value := range values {
		if value > 0 {
			return value
		}
	}
	return 0
}
