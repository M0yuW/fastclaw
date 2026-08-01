package agent

import (
	"context"
	"math"
	"testing"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

func TestModelUsageCollectorPricesCachedTokensWithoutDoubleCounting(t *testing.T) {
	collector := NewModelUsageCollector("coordinator", map[string]ModelPricing{
		"model": {
			InputPerMillion:     1,
			OutputPerMillion:    2,
			CacheReadPerMillion: 0.1,
		},
	})
	ctx := ContextWithModelUsageCollector(context.Background(), collector)
	RecordModelCall(ctx, "coordinator", "provider/model", provider.Usage{
		PromptTokens:              100,
		CompletionTokens:          10,
		CacheReadTokens:           40,
		CacheReadIncludedInPrompt: true,
	}, 125*time.Millisecond, nil)

	calls := collector.Snapshot()
	if len(calls) != 1 {
		t.Fatalf("calls = %+v", calls)
	}
	call := calls[0]
	if !call.Priced ||
		call.Role != "coordinator" ||
		call.TotalTokens != 110 ||
		call.LatencyMS != 125 ||
		math.Abs(call.EstimatedCostUSD-0.000084) > 1e-12 {
		t.Fatalf("call = %+v", call)
	}
}

func TestModelUsageCollectorMarksUnknownPricing(t *testing.T) {
	collector := NewModelUsageCollector("coordinator", nil)
	ctx := ContextWithModelUsageCollector(t.Context(), collector)
	RecordModelCall(ctx, "worker", "unknown/model", provider.Usage{
		PromptTokens:     10,
		CompletionTokens: 5,
	}, time.Millisecond, nil)

	call := collector.Snapshot()[0]
	if call.Priced || call.EstimatedCostUSD != 0 || call.Role != "subagent" {
		t.Fatalf("call = %+v", call)
	}
}

func TestModelUsageCollectorOrdersCallsByStartSequence(t *testing.T) {
	collector := NewModelUsageCollector("coordinator", nil)
	ctx := ContextWithModelUsageCollector(t.Context(), collector)
	firstSequence := BeginModelCall(ctx)
	secondSequence := BeginModelCall(ctx)

	RecordModelCallWithSequence(
		ctx,
		secondSequence,
		"worker-2",
		"model",
		provider.Usage{},
		10*time.Millisecond,
		nil,
	)
	RecordModelCallWithSequence(
		ctx,
		firstSequence,
		"worker-1",
		"model",
		provider.Usage{},
		20*time.Millisecond,
		nil,
	)

	calls := collector.Snapshot()
	if len(calls) != 2 ||
		calls[0].Sequence != firstSequence || calls[0].AgentID != "worker-1" ||
		calls[1].Sequence != secondSequence || calls[1].AgentID != "worker-2" {
		t.Fatalf("calls = %+v", calls)
	}
}
