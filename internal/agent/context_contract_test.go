package agent

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

type countingIdentityStore struct {
	mu    sync.Mutex
	files map[string][]byte
	reads map[string]int
	err   error
}

func (store *countingIdentityStore) GetMemory(context.Context, string, string) (string, error) {
	return "", nil
}

func (store *countingIdentityStore) SaveMemory(context.Context, string, string, string) error {
	return nil
}

func (store *countingIdentityStore) GetWorkspaceFile(_ context.Context, _, _, filename string) ([]byte, error) {
	store.mu.Lock()
	defer store.mu.Unlock()
	store.reads[filename]++
	if store.err != nil {
		return nil, store.err
	}
	return append([]byte(nil), store.files[filename]...), nil
}

func (store *countingIdentityStore) SaveWorkspaceFile(context.Context, string, string, string, []byte) error {
	return nil
}

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
	prompt, err := builder.BuildSystemPrompt()
	if err != nil {
		t.Fatal(err)
	}
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

func TestContextBuilderReusesValidatedIdentityRevision(t *testing.T) {
	store := &countingIdentityStore{
		files: map[string][]byte{"SOUL.md": []byte("fixed evidence")},
		reads: make(map[string]int),
	}
	builder := NewContextBuilder("", NewMemory(""), "")
	builder.store = store
	builder.agentID = "agent-1"
	builder.userID = "user-1"
	builder.SetRequiredIdentityFiles([]string{"SOUL.md"})

	revision, err := builder.ValidateRequiredIdentityFiles()
	if err != nil {
		t.Fatal(err)
	}
	prompt, err := builder.buildSystemPrompt(revision, map[string]string{"SOUL.md": "fixed evidence"})
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(prompt, "Identity revision: "+revision) {
		t.Fatalf("prompt missing validated revision %q", revision)
	}
	if reads := store.reads["SOUL.md"]; reads != 1 {
		t.Fatalf("SOUL.md reads = %d, want one validated snapshot read", reads)
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

func TestContextBuilderPreservesRequiredIdentityStoreError(t *testing.T) {
	store := &countingIdentityStore{
		files: map[string][]byte{},
		reads: make(map[string]int),
		err:   errors.New("database is locked"),
	}
	builder := NewContextBuilder("", NewMemory(""), "")
	builder.store = store
	builder.agentID = "agent-1"
	builder.userID = "user-1"
	builder.SetRequiredIdentityFiles([]string{"SOUL.md"})

	_, err := builder.ValidateRequiredIdentityFiles()
	if err == nil || !strings.Contains(err.Error(), "database is locked") {
		t.Fatalf("required identity error = %v", err)
	}
	if strings.Contains(err.Error(), "missing or empty") {
		t.Fatalf("store failure was misreported as missing identity: %v", err)
	}
}

func TestContextBuilderDoesNotFallbackAfterStoreFailure(t *testing.T) {
	home := t.TempDir()
	if err := os.WriteFile(filepath.Join(home, "SOUL.md"), []byte("stale identity"), 0o600); err != nil {
		t.Fatal(err)
	}
	store := &countingIdentityStore{
		files: map[string][]byte{},
		reads: make(map[string]int),
		err:   errors.New("database is locked"),
	}
	builder := NewContextBuilder(home, NewMemory(home), "")
	builder.store = store
	builder.agentID = "agent-1"
	builder.userID = "user-1"
	builder.SetRequiredIdentityFiles([]string{"SOUL.md"})

	if _, err := builder.BuildSystemPrompt(); err == nil || !strings.Contains(err.Error(), "database is locked") {
		t.Fatalf("BuildSystemPrompt error = %v", err)
	}
}
