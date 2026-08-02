package eval

import (
	"context"
	"errors"
	"strings"
	"testing"
)

type financeRetrievalExecutorStub struct {
	requests []ExecutionRequest
	failOn   string
}

func (s *financeRetrievalExecutorStub) Execute(_ context.Context, request ExecutionRequest) (ExecutionResponse, error) {
	s.requests = append(s.requests, request)
	if s.failOn != "" && strings.Contains(request.SessionKey, s.failOn) {
		return ExecutionResponse{}, errors.New("injected stage failure")
	}
	response := ExecutionResponse{
		Model: "provider/model",
		Usage: Usage{PromptTokens: 10, CompletionTokens: 5, TotalTokens: 15},
		ModelCalls: []ModelCallUsage{{
			AgentID:          request.AgentID,
			Role:             "coordinator",
			Model:            "provider/model",
			PromptTokens:     10,
			CompletionTokens: 5,
			TotalTokens:      15,
			Priced:           true,
			EstimatedCostUSD: 0.01,
			LatencyMS:        2,
		}},
	}
	switch {
	case strings.Contains(request.Prompt, "retrieval stage"):
		response.Output = "Evidence Bundle: [REC-A] revenue evidence; [REC-B] margin evidence."
	case strings.Contains(request.Prompt, "Analyze the supplied Evidence Bundle"):
		response.Output = "Verified fact [REC-A] and [REC-B]. Calculation is bounded; limitation is explicit."
	case strings.Contains(request.Prompt, "Coordinate a financial research team"):
		response.Output = financeRetrievalPassingOutput()
		response.Trace = []TraceEvent{
			{Type: "tool_call", ID: "call-trend", Name: "spawn_subagent", Arguments: `{"agentId":"finance-trend","task":"CASE trend"}`},
			{Type: "tool_result", ID: "call-trend", Name: "spawn_subagent", Result: "Verified fact [REC-A] and [REC-B]."},
			{Type: "tool_call", ID: "call-risk", Name: "spawn_subagent", Arguments: `{"agentId":"finance-risk","task":"CASE risk"}`},
			{Type: "tool_result", ID: "call-risk", Name: "spawn_subagent", Result: "Calculation and limitation from [REC-A] and [REC-B]."},
		}
	default:
		response.Output = financeRetrievalPassingOutput()
	}
	return response, nil
}

func financeRetrievalPassingOutput() string {
	return "Verified fact [REC-A] and [REC-B]. The calculation supports decision hold. Trade action is none. Limitation remains explicit."
}

func financeRetrievalTestSuite() FinanceRetrievalSuite {
	return FinanceRetrievalSuite{
		Version:          SuiteVersion,
		Name:             "finance-retrieval-test",
		Dataset:          "locked-test-data",
		SourceLockSHA256: strings.Repeat("a", 64),
		Defaults: FinanceRetrievalDefaults{
			CoordinatorAgentID:     "bench-coordinator",
			SoloAgentID:            "finance-solo",
			RetrieverAgentID:       "finance-retriever",
			Repetitions:            1,
			Timeout:                Duration(60_000_000_000),
			MinRetrievalRecall:     1,
			MinSummaryRetention:    1,
			MinFinalEvidenceRecall: 1,
			Analysts: []FinanceRetrievalAnalyst{
				{AgentID: "finance-trend", Perspective: "trend", Instruction: "analyze chronology"},
				{AgentID: "finance-risk", Perspective: "risk", Instruction: "analyze risk"},
			},
		},
		Modes: []string{
			FinanceRetrievalModeSoloMonolithic,
			FinanceRetrievalModeSoloStaged,
			FinanceRetrievalModeTeamShared,
			FinanceRetrievalModeTeamRawContext,
			FinanceRetrievalModeOracleEvidence,
		},
		Pricing: map[string]ModelPricing{"provider/model": {InputPerMillion: 1, OutputPerMillion: 1}},
		Cases: []FinanceRetrievalCase{{
			ID:               "CASE",
			Question:         "Assess the locked evidence.",
			AnalysisProtocol: "Compute the declared comparison and apply decision hold when evidence is complete.",
			CorpusLoad:       "small",
			GoldRecordIDs:    []string{"REC-A", "REC-B"},
			OracleEvidence:   "[REC-A] revenue; [REC-B] margin",
			Records: []FinanceRetrievalRecord{
				{ID: "REC-A", SourceID: "source-a", SourceSHA256: strings.Repeat("b", 64), Company: "A", Symbol: "A", FiledAt: "2024-01-01", Accession: "0000000000-24-000001", Locator: "Revenue", Text: "Revenue evidence."},
				{ID: "REC-B", SourceID: "source-b", SourceSHA256: strings.Repeat("c", 64), Company: "A", Symbol: "A", FiledAt: "2024-04-01", Accession: "0000000000-24-000002", Locator: "Margin", Text: "Margin evidence."},
			},
			Milestones: []MultiAgentMilestone{
				{ID: "decision", Values: []string{"decision hold", "trade action is none"}},
				{ID: "separation", Values: []string{"verified fact", "calculation", "limitation"}},
			},
			ForbiddenOutputValues: []string{"trade is authorized"},
		}},
	}
}

func TestFinanceRetrievalRunnerExecutesFairPipelines(t *testing.T) {
	executor := &financeRetrievalExecutorStub{}
	report, err := (FinanceRetrievalRunner{Executor: executor}).Run(t.Context(), financeRetrievalTestSuite())
	if err != nil {
		t.Fatal(err)
	}
	if len(executor.requests) != 9 {
		t.Fatalf("requests = %d, want 9", len(executor.requests))
	}
	if len(report.Cases) != 1 || len(report.Cases[0].Attempts) != 1 || len(report.Cases[0].Attempts[0].Modes) != 5 {
		t.Fatalf("report shape = %+v", report.Cases)
	}
	for _, mode := range report.Cases[0].Attempts[0].Modes {
		if !mode.Passed || mode.Error != "" {
			t.Fatalf("mode %s = %+v", mode.Mode, mode)
		}
		if mode.Stages.FinalEvidenceRecall != 1 || mode.Stages.PassedMilestones != 2 {
			t.Fatalf("mode %s stages = %+v", mode.Mode, mode.Stages)
		}
	}
	team := report.Metrics.Modes[FinanceRetrievalModeTeamShared]
	if team.SuccessRate != 1 || team.AverageRetrievalRecall != 1 || team.DelegationRecall != 1 {
		t.Fatalf("team metrics = %+v", team)
	}
	if team.AverageCollaborationLatencyMS <= 0 || team.AverageSynthesisLatencyMS <= 0 {
		t.Fatalf("team stage latencies = %+v", team)
	}
	staged := report.Metrics.Modes[FinanceRetrievalModeSoloStaged]
	if staged.TotalTokens != 60 {
		t.Fatalf("staged tokens = %d, want 60", staged.TotalTokens)
	}
}

func TestFinanceRetrievalRunnerExcludesErroredModesFromSuccessDenominator(t *testing.T) {
	suite := financeRetrievalTestSuite()
	suite.Modes = []string{FinanceRetrievalModeTeamShared}
	executor := &financeRetrievalExecutorStub{failOn: "team-shared-retrieval-retrieval"}
	report, err := (FinanceRetrievalRunner{Executor: executor}).Run(t.Context(), suite)
	if err != nil {
		t.Fatal(err)
	}
	team := report.Metrics.Modes[FinanceRetrievalModeTeamShared]
	if team.Attempts != 1 || team.Errored != 1 || team.Evaluated != 0 || team.SuccessRate != 0 {
		t.Fatalf("team metrics = %+v", team)
	}
}

func TestFinanceRetrievalRunnerSelectsRequestedModes(t *testing.T) {
	executor := &financeRetrievalExecutorStub{}
	report, err := (FinanceRetrievalRunner{
		Executor: executor,
		Options:  RunOptions{Modes: []string{FinanceRetrievalModeOracleEvidence}},
	}).Run(t.Context(), financeRetrievalTestSuite())
	if err != nil {
		t.Fatal(err)
	}
	if len(executor.requests) != 1 || len(report.Cases[0].Attempts[0].Modes) != 1 {
		t.Fatalf("requests=%d report=%+v", len(executor.requests), report.Cases)
	}
}

func TestLoadGeneratedFinanceRetrievalSuite(t *testing.T) {
	suite, err := LoadFinanceRetrievalSuite("../../evals/finance-retrieval-sec.json")
	if err != nil {
		t.Fatal(err)
	}
	if len(suite.Cases) != 24 || len(suite.Modes) != 5 {
		t.Fatalf("suite cases=%d modes=%d", len(suite.Cases), len(suite.Modes))
	}
}
