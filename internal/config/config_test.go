package config

import "testing"

func TestMergedAgentConfigAppliesFileThinkingOverride(t *testing.T) {
	originalLoader := AgentFileConfigLoader
	t.Cleanup(func() { AgentFileConfigLoader = originalLoader })
	AgentFileConfigLoader = func(_, _ string) (AgentFileConfig, bool) {
		return AgentFileConfig{Thinking: "off"}, true
	}
	cfg := &Config{Agents: AgentsConfig{Defaults: AgentDefaults{
		Model:             "provider/model",
		MaxTokens:         100,
		MaxToolIterations: 2,
		Thinking:          "high",
	}}}
	resolved := cfg.MergedAgentConfig(AgentEntry{ID: "agent"})
	if resolved.Thinking != "off" {
		t.Fatalf("thinking = %q, want off", resolved.Thinking)
	}
}
