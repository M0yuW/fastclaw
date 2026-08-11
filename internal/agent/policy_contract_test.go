package agent

import (
	"context"
	"strings"
	"testing"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
	"github.com/fastclaw-ai/fastclaw/internal/config"
)

type recordingSpawner struct{ calls int }

func (r *recordingSpawner) SpawnSubAgent(context.Context, string, bus.InboundMessage) (string, error) {
	r.calls++
	return "specialist reply", nil
}

// newPolicyTestAgent builds an agent with the given preset and the
// spawn_subagent tool wired, mirroring what loadUserSpace does at boot.
func newPolicyTestAgent(t *testing.T, preset string) (*Agent, *recordingSpawner) {
	t.Helper()
	home := t.TempDir()
	ag := NewAgent(config.ResolvedAgent{
		ID:                "coordinator",
		Home:              home,
		Workspace:         home,
		Model:             "fake/model",
		MaxTokens:         128,
		MaxToolIterations: 4,
		PolicyPreset:      preset,
	}, nil, nil, home)
	spawner := &recordingSpawner{}
	ag.SetSubAgentSpawner(spawner)
	return ag, spawner
}

func toolNameSet(names []string) map[string]bool {
	set := make(map[string]bool, len(names))
	for _, n := range names {
		set[n] = true
	}
	return set
}

// A delegate-only coordinator must be offered spawn_subagent plus its own
// ledger, and nothing that lets it gather evidence itself. This is the
// contract that turns the SOUL instruction "always call the specialists" from
// advice into an invariant.
func TestDelegateOnlyCoordinatorAdvertisesOnlySpawnSubagent(t *testing.T) {
	ag, _ := newPolicyTestAgent(t, "delegate-only")

	if got := ag.PolicyName(); got != "delegate-only" {
		t.Fatalf("policy name = %q, want delegate-only", got)
	}
	allowed := toolNameSet(ag.AllowedToolNames())
	for _, needed := range []string{"spawn_subagent", "ledger_append", "ledger_report"} {
		if !allowed[needed] {
			t.Fatalf("coordinator was not offered %q; allowed=%v", needed, ag.AllowedToolNames())
		}
	}
	for _, banned := range []string{"exec", "web_fetch", "write_file", "read_file", "list_dir"} {
		if allowed[banned] {
			t.Fatalf("delegate-only coordinator was offered %q", banned)
		}
	}
	if len(allowed) != 3 {
		t.Fatalf("delegate-only tool face = %v, want spawn_subagent + ledger tools only", ag.AllowedToolNames())
	}
}

// The definition filter alone is not a security boundary: a model can emit a
// call for a tool it was never shown. Execution must go through the same
// filtered registry.
func TestDelegateOnlyRejectsForgedExecCall(t *testing.T) {
	ag, _ := newPolicyTestAgent(t, "delegate-only")

	registry := ag.allowedRegistry()
	if _, err := registry.Execute(context.Background(), "exec", `{"command":"id"}`); err == nil {
		t.Fatal("forged exec call was executed under delegate-only")
	} else if !strings.Contains(err.Error(), "unknown tool") {
		t.Fatalf("unexpected error for forged exec: %v", err)
	}
	if _, err := registry.Execute(context.Background(), "web_fetch", `{"url":"https://example.com"}`); err == nil {
		t.Fatal("forged web_fetch call was executed under delegate-only")
	}
}

// Specialists keep their full tool face — the lockdown targets orchestrators.
func TestSpecialistWithoutPresetKeepsFullToolFace(t *testing.T) {
	ag, _ := newPolicyTestAgent(t, "")

	if got := ag.PolicyName(); got != "permissive" {
		t.Fatalf("policy name = %q, want permissive", got)
	}
	allowed := toolNameSet(ag.AllowedToolNames())
	for _, needed := range []string{"exec", "web_fetch", "read_file", "write_file", "spawn_subagent"} {
		if !allowed[needed] {
			t.Fatalf("specialist lost %q; allowed=%v", needed, ag.AllowedToolNames())
		}
	}
}

// UpdateConfig is how the gateway hot-reloads an agent after an admin edit.
// The policy must follow, or a lockdown silently reverts on the next reload.
func TestUpdateConfigReloadsPolicyPreset(t *testing.T) {
	ag, _ := newPolicyTestAgent(t, "")
	if toolNameSet(ag.AllowedToolNames())["exec"] == false {
		t.Fatal("precondition failed: permissive agent has no exec")
	}

	ag.UpdateConfig(config.ResolvedAgent{
		ID:                "coordinator",
		Home:              ag.HomePath(),
		Workspace:         ag.WorkspacePath(),
		Model:             "fake/model",
		MaxTokens:         128,
		MaxToolIterations: 4,
		PolicyPreset:      "delegate-only",
	})

	if got := ag.PolicyName(); got != "delegate-only" {
		t.Fatalf("policy name after UpdateConfig = %q, want delegate-only", got)
	}
	if toolNameSet(ag.AllowedToolNames())["exec"] {
		t.Fatal("exec survived the switch to delegate-only")
	}
}

// Filtering must not sever the spawn wiring: the coordinator's one remaining
// tool has to actually reach the spawner.
func TestDelegateOnlySpawnSubagentStillExecutes(t *testing.T) {
	ag, spawner := newPolicyTestAgent(t, "delegate-only")

	out, err := ag.allowedRegistry().Execute(
		context.Background(),
		"spawn_subagent",
		`{"agentId":"data-analyst","task":"confirm fixture identity"}`,
	)
	if err != nil {
		t.Fatalf("spawn_subagent failed under delegate-only: %v", err)
	}
	if out != "specialist reply" {
		t.Fatalf("spawn_subagent returned %q", out)
	}
	if spawner.calls != 1 {
		t.Fatalf("spawner called %d times, want 1", spawner.calls)
	}
}

// The coordinator's bookkeeping has to survive the lockdown too: without a
// working ledger under delegate-only it would need write_file or exec back.
func TestDelegateOnlyLedgerRoundTrips(t *testing.T) {
	ag, _ := newPolicyTestAgent(t, "delegate-only")
	registry := ag.allowedRegistry()

	if _, err := registry.Execute(context.Background(), "ledger_append",
		`{"path":"football/ledger.json","key":["competition","season","date","match"],
		  "record":{"competition":"UCL","season":"2026","date":"2026-08-12","match":"A vs B","lean":"draw"}}`,
	); err != nil {
		t.Fatalf("ledger_append failed under delegate-only: %v", err)
	}

	out, err := registry.Execute(context.Background(), "ledger_report",
		`{"path":"football/ledger.json","filter":{"competition":"UCL"}}`)
	if err != nil {
		t.Fatalf("ledger_report failed under delegate-only: %v", err)
	}
	if !strings.Contains(out, "A vs B") {
		t.Fatalf("report lost the appended entry: %s", out)
	}
}
