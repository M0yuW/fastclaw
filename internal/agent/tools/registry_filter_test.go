package tools

import (
	"context"
	"encoding/json"
	"testing"
)

func stubTool(_ context.Context, _ json.RawMessage) (string, error) { return "ok", nil }

func definitionNames(r *Registry) map[string]bool {
	names := make(map[string]bool)
	for _, def := range r.Definitions() {
		names[def.Function.Name] = true
	}
	return names
}

func TestFilterKeepsOnlyAllowedTools(t *testing.T) {
	r := NewEmptyRegistry()
	for _, name := range []string{"spawn_subagent", "exec", "web_fetch"} {
		r.Register(name, name+" desc", map[string]any{"type": "object"}, stubTool)
	}

	filtered := r.Filter(func(name string) bool { return name == "spawn_subagent" })

	got := definitionNames(filtered)
	if !got["spawn_subagent"] {
		t.Fatal("spawn_subagent missing from filtered definitions")
	}
	for _, name := range []string{"exec", "web_fetch"} {
		if got[name] {
			t.Fatalf("filtered registry still advertises %q", name)
		}
	}
}

// Filtering must also block execution, not just hide the definition — a model
// can emit a call for a tool it was never offered.
func TestFilteredRegistryRefusesToExecuteDeniedTool(t *testing.T) {
	r := NewEmptyRegistry()
	r.Register("exec", "exec desc", map[string]any{"type": "object"}, stubTool)
	r.Register("spawn_subagent", "spawn desc", map[string]any{"type": "object"}, stubTool)

	filtered := r.Filter(func(name string) bool { return name == "spawn_subagent" })

	if _, err := filtered.Execute(context.Background(), "exec", "{}"); err == nil {
		t.Fatal("filtered registry executed a denied tool")
	}
	if filtered.GetFunc("exec") != nil {
		t.Fatal("filtered registry still exposes the denied tool func")
	}
	if _, err := filtered.Execute(context.Background(), "spawn_subagent", "{}"); err != nil {
		t.Fatalf("allowed tool must still run: %v", err)
	}
}

func TestFilterLeavesOriginalRegistryUntouched(t *testing.T) {
	r := NewEmptyRegistry()
	r.Register("exec", "exec desc", map[string]any{"type": "object"}, stubTool)

	_ = r.Filter(func(string) bool { return false })

	if !definitionNames(r)["exec"] {
		t.Fatal("Filter mutated the shared registry")
	}
	if _, err := r.Execute(context.Background(), "exec", "{}"); err != nil {
		t.Fatalf("shared registry lost its tool func: %v", err)
	}
}

func TestFilterNilAllowIsIdentity(t *testing.T) {
	r := NewEmptyRegistry()
	r.Register("exec", "exec desc", map[string]any{"type": "object"}, stubTool)
	if filtered := r.Filter(nil); filtered != r {
		t.Fatal("Filter(nil) must return the receiver unchanged")
	}
}
