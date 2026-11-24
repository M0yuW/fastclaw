package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/workspace"
)

// A cloud-mode agent has a workspace store wired, and the ledger must follow
// write_file into it rather than writing pod-local disk under userRoot.
func TestLedgerRoutesThroughWorkspaceStore(t *testing.T) {
	storeRoot := t.TempDir()
	userRoot := t.TempDir()
	r := NewRegistry(userRoot, userRoot)
	r.SetWorkspaceStore(workspace.NewLocalFS(storeRoot), "agent-1")

	appendLedger(t, r, `{"path":"football/ledger.json","key":["match"],"record":{"match":"A vs B"}}`)

	if _, err := os.Stat(filepath.Join(storeRoot, "agent-1", "football", "ledger.json")); err != nil {
		t.Fatalf("ledger did not land in the workspace store: %v", err)
	}
	if _, err := os.Stat(filepath.Join(userRoot, "football", "ledger.json")); err == nil {
		t.Fatal("ledger also wrote pod-local disk, bypassing the store")
	}

	out, err := r.Execute(context.Background(), "ledger_report", `{"path":"football/ledger.json"}`)
	if err != nil {
		t.Fatalf("ledger_report failed: %v", err)
	}
	if !strings.Contains(out, "A vs B") {
		t.Fatalf("store-backed report lost the entry: %s", out)
	}
}

// Sessions are separate scopes in the store, so two chats about the same
// fixture keep separate ledgers instead of overwriting one another.
func TestLedgerIsSessionScopedInWorkspaceStore(t *testing.T) {
	r := NewRegistry(t.TempDir(), t.TempDir())
	r.SetWorkspaceStore(workspace.NewLocalFS(t.TempDir()), "agent-1")

	r.SetSessionID("chat-a")
	appendLedger(t, r, `{"key":["match"],"record":{"match":"A vs B"}}`)

	r.SetSessionID("chat-b")
	out, err := r.Execute(context.Background(), "ledger_report", `{}`)
	if err != nil {
		t.Fatalf("ledger_report failed: %v", err)
	}
	if strings.Contains(out, "A vs B") {
		t.Fatalf("session chat-b saw chat-a's ledger: %s", out)
	}

	r.SetSessionID("chat-a")
	out, err = r.Execute(context.Background(), "ledger_report", `{}`)
	if err != nil {
		t.Fatalf("ledger_report failed: %v", err)
	}
	if !strings.Contains(out, "A vs B") {
		t.Fatalf("session chat-a lost its own ledger: %s", out)
	}
}

// ledgerFakeExecutor is the minimal sandbox.Executor the ledger needs: an
// in-memory file map. Reading a missing path errors, the way `cat` does.
type ledgerFakeExecutor struct {
	files     map[string]string
	readCalls int
	failWrite bool
}

func newLedgerFakeExecutor() *ledgerFakeExecutor {
	return &ledgerFakeExecutor{files: map[string]string{}}
}

func (e *ledgerFakeExecutor) Exec(context.Context, string, time.Duration) (string, error) {
	return "", fmt.Errorf("exec not supported")
}

func (e *ledgerFakeExecutor) ReadFile(_ context.Context, path string) (string, error) {
	e.readCalls++
	content, ok := e.files[path]
	if !ok {
		return "", fmt.Errorf("cat: %s: No such file or directory", path)
	}
	return content, nil
}

func (e *ledgerFakeExecutor) WriteFile(_ context.Context, path, content string) (string, error) {
	if e.failWrite {
		return "", fmt.Errorf("disk full")
	}
	e.files[path] = content
	return "Written to " + path, nil
}

func (e *ledgerFakeExecutor) ListDir(context.Context, string) (string, error) { return "", nil }
func (e *ledgerFakeExecutor) Close() error                                    { return nil }

// A sandboxed agent has no host filesystem for its workspace, so the ledger
// has to go through the executor.
func TestLedgerRoutesThroughSandboxExecutor(t *testing.T) {
	userRoot := t.TempDir()
	r := NewRegistry(userRoot, userRoot)
	ex := newLedgerFakeExecutor()
	r.SetExecutor(ex)

	appendLedger(t, r, `{"key":["match"],"record":{"match":"A vs B"}}`)
	appendLedger(t, r, `{"key":["match"],"record":{"match":"C vs D"}}`)

	stored, ok := ex.files[defaultLedgerPath]
	if !ok {
		t.Fatalf("ledger did not reach the executor; files=%v", ex.files)
	}
	var file ledgerFile
	if err := json.Unmarshal([]byte(stored), &file); err != nil {
		t.Fatalf("executor holds invalid JSON: %v", err)
	}
	// Both rows survive, so the second append read back the first through the
	// executor instead of starting from an empty ledger.
	if len(file.Entries) != 2 {
		t.Fatalf("entries = %d, want 2", len(file.Entries))
	}
	if ex.readCalls < 2 {
		t.Fatalf("executor ReadFile called %d times; the ledger was not loaded through the sandbox", ex.readCalls)
	}
	if _, err := os.Stat(filepath.Join(userRoot, defaultLedgerPath)); err == nil {
		t.Fatal("sandboxed ledger leaked onto the host filesystem")
	}
}

// A write that fails must surface as a tool error — silently reporting success
// would leave the model believing a fact was recorded when it wasn't.
func TestLedgerAppendSurfacesWriteFailure(t *testing.T) {
	r := NewRegistry(t.TempDir(), t.TempDir())
	ex := newLedgerFakeExecutor()
	ex.failWrite = true
	r.SetExecutor(ex)

	if _, err := r.Execute(context.Background(), "ledger_append",
		`{"key":["match"],"record":{"match":"A vs B"}}`); err == nil {
		t.Fatal("a failed write was reported as success")
	}
}

// A ledger file holding something this tool didn't write must fail loudly.
// Overwriting it would destroy whatever the user put there.
func TestLedgerRefusesUnrecognisedFileContents(t *testing.T) {
	root := t.TempDir()
	r := NewRegistry(root, root)
	if err := os.WriteFile(filepath.Join(root, defaultLedgerPath), []byte("not json at all"), 0o644); err != nil {
		t.Fatalf("seed file: %v", err)
	}

	_, err := r.Execute(context.Background(), "ledger_append", `{"key":["match"],"record":{"match":"x"}}`)
	if err == nil {
		t.Fatal("a non-ledger file was silently overwritten")
	}
	if !strings.Contains(err.Error(), defaultLedgerPath) {
		t.Fatalf("error does not name the file: %v", err)
	}
}
