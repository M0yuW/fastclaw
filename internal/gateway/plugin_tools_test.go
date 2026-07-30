package gateway

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/fastclaw-ai/fastclaw/internal/agent"
	agenttools "github.com/fastclaw-ai/fastclaw/internal/agent/tools"
	"github.com/fastclaw-ai/fastclaw/internal/bus"
	"github.com/fastclaw-ai/fastclaw/internal/config"
	"github.com/fastclaw-ai/fastclaw/internal/plugin"
)

func TestRegisterPluginToolsExposesToolToAgent(t *testing.T) {
	if _, err := exec.LookPath("python3"); err != nil {
		t.Skip("python3 is required")
	}

	pluginRoot := t.TempDir()
	pluginDir := filepath.Join(pluginRoot, "fixture-finance")
	if err := os.MkdirAll(pluginDir, 0o755); err != nil {
		t.Fatal(err)
	}
	manifest := `{
		"id": "fixture-finance",
		"name": "Fixture Finance",
		"version": "0.1.0",
		"type": "tool",
		"command": "python3 plugin.py",
		"capabilities": ["tool"]
	}`
	if err := os.WriteFile(filepath.Join(pluginDir, "plugin.json"), []byte(manifest), 0o644); err != nil {
		t.Fatal(err)
	}
	script := `import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    request_id = request.get("id")
    method = request.get("method")
    if method == "initialize":
        result = {"status": "ok"}
    elif method == "tool.list":
        result = {"tools": [{
            "name": "quote",
            "description": "Return a fixture quote.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"]
            }
        }]}
    elif method == "tool.execute":
        symbol = request["params"]["args"]["symbol"]
        call_context = request["params"].get("context", {})
        result = {"result": json.dumps({
            "symbol": symbol,
            "price": 100,
            "user": call_context.get("userId"),
            "agent": call_context.get("agentId"),
            "session": call_context.get("sessionId")
        })}
    elif method == "shutdown":
        result = {"status": "ok"}
    else:
        print(json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "unknown method"},
            "id": request_id
        }), flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "result": result, "id": request_id}), flush=True)
    if method == "shutdown":
        break
`
	if err := os.WriteFile(filepath.Join(pluginDir, "plugin.py"), []byte(script), 0o755); err != nil {
		t.Fatal(err)
	}

	manager := plugin.NewManager(nil)
	if err := manager.Discover([]string{pluginRoot}); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	if err := manager.StartAll(ctx); err != nil {
		t.Fatal(err)
	}
	defer manager.StopAll()

	agentHome := t.TempDir()
	runtimeAgent := agent.NewAgent(
		config.ResolvedAgent{
			ID:                "finance-agent",
			Home:              agentHome,
			Workspace:         agentHome,
			Model:             "fixture/model",
			MaxTokens:         100,
			MaxToolIterations: 2,
		},
		nil,
		bus.New(),
		t.TempDir(),
	)

	if err := registerPluginTools(ctx, manager, []*agent.Agent{runtimeAgent}); err != nil {
		t.Fatal(err)
	}
	toolCtx := agenttools.ContextWithExecutionScope(ctx, agenttools.ExecutionScope{
		UserID:    "user-1",
		AgentID:   "finance-agent",
		SessionID: "session-1",
	})
	result, err := runtimeAgent.ToolRegistry().Execute(
		toolCtx,
		"fixture-finance.quote",
		`{"symbol":"AAPL"}`,
	)
	if err != nil {
		t.Fatal(err)
	}
	if result != `{"symbol": "AAPL", "price": 100, "user": "user-1", "agent": "finance-agent", "session": "session-1"}` {
		t.Fatalf("unexpected plugin result: %s", result)
	}
}
