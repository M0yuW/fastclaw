package main

import (
	"testing"

	"github.com/fastclaw-ai/fastclaw/internal/config"
)

func TestDefaultGatewayConfigEnablesOpenAIEndpoints(t *testing.T) {
	cfg := defaultGatewayConfig(&config.EnvConfig{
		Gateway: config.EnvGateway{Bind: "all"},
	}, 19000)

	if cfg.Port != 19000 {
		t.Fatalf("port = %d, want 19000", cfg.Port)
	}
	if cfg.Bind != "all" {
		t.Fatalf("bind = %q, want all", cfg.Bind)
	}
	if !cfg.HTTP.Endpoints.ChatCompletions.Enabled {
		t.Fatal("chat completions endpoint is disabled")
	}
	if !cfg.HTTP.Endpoints.Agents.Enabled {
		t.Fatal("agents endpoint is disabled")
	}
}
