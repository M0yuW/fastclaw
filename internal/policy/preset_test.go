package policy

import "testing"

func TestLoadPresetResolvesDelegateOnly(t *testing.T) {
	p := LoadPreset("delegate-only")
	if p.Name != "delegate-only" {
		t.Fatalf("got preset %q, want delegate-only", p.Name)
	}
	if p := LoadPreset("Delegate-Only"); p.Name != "delegate-only" {
		t.Fatalf("preset lookup is case-sensitive: got %q", p.Name)
	}
}

func TestLoadPresetResolvesNoTools(t *testing.T) {
	if p := LoadPreset("no-tools"); p.Name != "no-tools" {
		t.Fatalf("got preset %q, want no-tools", p.Name)
	}
}

func TestLoadPresetUnknownFallsBackToPermissive(t *testing.T) {
	p := LoadPreset("not-a-preset")
	if p.Name != "permissive" {
		t.Fatalf("got preset %q, want permissive", p.Name)
	}
	// An empty preset must stay permissive: every existing agent has no
	// `policy` key in its config, and silently locking them down would break
	// them all.
	if p := LoadPreset(""); p.Name != "permissive" {
		t.Fatalf("empty preset resolved to %q, want permissive", p.Name)
	}
}

func TestDelegateOnlyAllowsOnlySpawnSubagent(t *testing.T) {
	e := NewEngine(DelegateOnlyPolicy())
	if err := e.CheckTool("spawn_subagent"); err != nil {
		t.Fatalf("spawn_subagent must be allowed: %v", err)
	}
	for _, name := range []string{"exec", "web_fetch", "write_file", "read_file", "list_dir", "send_message"} {
		if err := e.CheckTool(name); err == nil {
			t.Fatalf("tool %q must be denied under delegate-only", name)
		}
	}
}

func TestNoToolsDeniesEverything(t *testing.T) {
	e := NewEngine(NoToolsPolicy())
	for _, name := range []string{"spawn_subagent", "exec", "read_file"} {
		if err := e.CheckTool(name); err == nil {
			t.Fatalf("tool %q must be denied under no-tools", name)
		}
	}
}

func TestPermissivePresetAllowsEverything(t *testing.T) {
	e := NewEngine(LoadPreset(""))
	for _, name := range []string{"spawn_subagent", "exec", "web_fetch", "write_file"} {
		if err := e.CheckTool(name); err != nil {
			t.Fatalf("tool %q must be allowed by default: %v", name, err)
		}
	}
}
