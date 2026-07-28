package agent

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestContextBuilderNoToolContract(t *testing.T) {
	home := t.TempDir()
	if err := os.WriteFile(filepath.Join(home, "SOUL.md"), []byte("fixed evidence"), 0o600); err != nil {
		t.Fatal(err)
	}
	builder := NewContextBuilder(home, NewMemory(home), "unrelated skill")
	builder.SetRequiredIdentityFiles([]string{"SOUL.md"})
	builder.SetToolGuidance(false)

	revision, err := builder.ValidateRequiredIdentityFiles()
	if err != nil {
		t.Fatal(err)
	}
	if len(revision) != 16 {
		t.Fatalf("revision length = %d, want 16", len(revision))
	}
	prompt := builder.BuildSystemPrompt()
	for _, expected := range []string{"fixed evidence", "Required identity files loaded: SOUL.md"} {
		if !strings.Contains(prompt, expected) {
			t.Fatalf("prompt does not contain %q", expected)
		}
	}
	for _, forbidden := range []string{"File-tool routing", "# Skills", "# Workspace Self-Update"} {
		if strings.Contains(prompt, forbidden) {
			t.Fatalf("prompt unexpectedly contains %q", forbidden)
		}
	}
}

func TestContextBuilderRejectsMissingRequiredIdentity(t *testing.T) {
	home := t.TempDir()
	builder := NewContextBuilder(home, NewMemory(home), "")
	builder.SetRequiredIdentityFiles([]string{"SOUL.md"})
	if _, err := builder.ValidateRequiredIdentityFiles(); err == nil {
		t.Fatal("expected missing identity error")
	}
}
