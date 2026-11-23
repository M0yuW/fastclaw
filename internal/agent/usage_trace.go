package agent

import (
	"context"
	"strings"
	"sync"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

type ModelPricing struct {
	InputPerMillion      float64 `json:"input_per_million" yaml:"input_per_million"`
	OutputPerMillion     float64 `json:"output_per_million" yaml:"output_per_million"`
	CacheReadPerMillion  float64 `json:"cache_read_per_million,omitempty" yaml:"cache_read_per_million,omitempty"`
	CacheWritePerMillion float64 `json:"cache_write_per_million,omitempty" yaml:"cache_write_per_million,omitempty"`
}

type ModelCallUsage struct {
	Sequence            int      `json:"sequence"`
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

type ModelUsageCollector struct {
	mu          sync.Mutex
	rootAgentID string
	pricing     map[string]ModelPricing
	calls       []ModelCallUsage
}

type modelUsageCollectorKey struct{}

func NewModelUsageCollector(rootAgentID string, pricing map[string]ModelPricing) *ModelUsageCollector {
	copiedPricing := make(map[string]ModelPricing, len(pricing))
	for model, price := range pricing {
		copiedPricing[model] = price
	}
	return &ModelUsageCollector{
		rootAgentID: rootAgentID,
		pricing:     copiedPricing,
	}
}

func ContextWithModelUsageCollector(ctx context.Context, collector *ModelUsageCollector) context.Context {
	if ctx == nil {
		ctx = context.Background()
	}
	return context.WithValue(ctx, modelUsageCollectorKey{}, collector)
}

func RecordModelCall(
	ctx context.Context,
	agentID string,
	model string,
	usage provider.Usage,
	latency time.Duration,
	callErr error,
) {
	collector, _ := ctx.Value(modelUsageCollectorKey{}).(*ModelUsageCollector)
	if collector == nil {
		return
	}
	callPath := bus.InternalCallPathFromContext(ctx)
	role := "subagent"
	if agentID == collector.rootAgentID {
		role = "coordinator"
	}
	price, priced := collector.priceFor(model)
	call := ModelCallUsage{
		AgentID:             agentID,
		Role:                role,
		Model:               model,
		CallPath:            callPath,
		PromptTokens:        usage.PromptTokens,
		CompletionTokens:    usage.CompletionTokens,
		TotalTokens:         usage.TotalTokens(),
		CacheReadTokens:     usage.CacheReadTokens,
		CacheCreationTokens: usage.CacheCreationTokens,
		Priced:              priced,
		LatencyMS:           float64(latency.Microseconds()) / 1000,
	}
	if priced {
		call.EstimatedCostUSD = estimateModelCallCost(usage, price)
	}
	if callErr != nil {
		call.Error = callErr.Error()
	}
	collector.mu.Lock()
	call.Sequence = len(collector.calls) + 1
	collector.calls = append(collector.calls, call)
	collector.mu.Unlock()
}

func (c *ModelUsageCollector) Snapshot() []ModelCallUsage {
	if c == nil {
		return nil
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	result := make([]ModelCallUsage, len(c.calls))
	for index, call := range c.calls {
		result[index] = call
		result[index].CallPath = append([]string(nil), call.CallPath...)
	}
	return result
}

func (c *ModelUsageCollector) priceFor(model string) (ModelPricing, bool) {
	price, exists := c.pricing[model]
	if exists {
		return price, true
	}
	stripped := provider.StripProviderPrefix(model)
	price, exists = c.pricing[stripped]
	if exists {
		return price, true
	}
	for configuredModel, configuredPrice := range c.pricing {
		if strings.EqualFold(configuredModel, model) || strings.EqualFold(configuredModel, stripped) {
			return configuredPrice, true
		}
	}
	return ModelPricing{}, false
}

func estimateModelCallCost(usage provider.Usage, pricing ModelPricing) float64 {
	const million = 1_000_000
	promptTokens := usage.PromptTokens
	if usage.CacheReadIncludedInPrompt {
		promptTokens -= usage.CacheReadTokens
		if promptTokens < 0 {
			promptTokens = 0
		}
	}
	return float64(promptTokens)*pricing.InputPerMillion/million +
		float64(usage.CompletionTokens)*pricing.OutputPerMillion/million +
		float64(usage.CacheReadTokens)*pricing.CacheReadPerMillion/million +
		float64(usage.CacheCreationTokens)*pricing.CacheWritePerMillion/million
}
