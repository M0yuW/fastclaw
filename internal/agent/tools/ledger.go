package tools

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/workspace"
)

// The ledger is an append-or-update record file an agent maintains across
// turns: one row per real-world subject, identified by a caller-declared
// composite key. It exists so an orchestrator can keep durable bookkeeping
// without being handed `exec` — writing a ledger through a shell is what
// forces a locked-down coordinator to reopen a general-purpose tool face,
// and a general-purpose tool face is what lets it skip its specialists.
//
// Structured rather than free-form because the failure mode of "write JSON
// with write_file" is a second row for the same subject every time the user
// asks again. Here the key is stored in the file, so the second write is an
// update by construction.
const (
	defaultLedgerPath = "ledger.json"
	ledgerVersion     = 1
	maxLedgerEntries  = 5000
)

// defaultLedgerKey is used when a ledger has no recorded key yet and the
// caller didn't declare one.
var defaultLedgerKey = []string{"subject", "date"}

// ledgerFile is the on-disk envelope. The key lives in the file so every
// later append identifies rows the same way, even across agent restarts and
// model context resets.
type ledgerFile struct {
	Version int           `json:"version"`
	Key     []string      `json:"key"`
	Entries []ledgerEntry `json:"entries"`
}

// ledgerEntry is one row: the identity string, the bookkeeping the tool owns,
// and the caller's opaque record.
type ledgerEntry struct {
	Key       string         `json:"key"`
	Revision  int            `json:"revision"`
	CreatedAt time.Time      `json:"created_at"`
	UpdatedAt time.Time      `json:"updated_at"`
	Record    map[string]any `json:"record"`
}

type ledgerAppendArgs struct {
	Path   string         `json:"path,omitempty"`
	Key    []string       `json:"key,omitempty"`
	Record map[string]any `json:"record"`
}

type ledgerReportArgs struct {
	Path   string         `json:"path,omitempty"`
	Filter map[string]any `json:"filter,omitempty"`
	Limit  int            `json:"limit,omitempty"`
}

// ledgerLocks serialises the read-modify-write cycle per resolved ledger path.
// Two concurrent tool calls in the same turn would otherwise each load the
// same snapshot and the second save would drop the first row. Keyed by path
// rather than one global lock so unrelated ledgers don't contend.
var ledgerLocks sync.Map // map[string]*sync.Mutex

func ledgerLock(key string) *sync.Mutex {
	actual, _ := ledgerLocks.LoadOrStore(key, &sync.Mutex{})
	return actual.(*sync.Mutex)
}

// RegisterLedger registers the ledger_append / ledger_report tools. Both
// operate on a JSON file resolved the same way write_file resolves a path:
// through the workspace store when one is configured, otherwise on disk under
// the agent's workspace root.
func RegisterLedger(r *Registry) {
	r.Register("ledger_append", "Record one entry in a durable JSON ledger, keyed by identity fields so a repeat write updates the existing row instead of duplicating it. Use this for bookkeeping you must be able to re-read in a later turn.", map[string]interface{}{
		"type": "object",
		"properties": map[string]interface{}{
			"path": map[string]interface{}{
				"type":        "string",
				"description": "Ledger file path relative to your workspace (default \"ledger.json\")",
			},
			"key": map[string]interface{}{
				"type":        "array",
				"items":       map[string]interface{}{"type": "string"},
				"description": "Record field names that together identify one row, e.g. [\"competition\",\"season\",\"date\",\"match\"]. Set on first write and reused afterwards; omit to reuse the ledger's existing key.",
			},
			"record": map[string]interface{}{
				"type":        "object",
				"description": "The entry itself. Must contain a non-empty value for every key field.",
			},
		},
		"required": []string{"record"},
	}, makeLedgerAppend(r))

	r.Register("ledger_report", "Read back entries from a JSON ledger written by ledger_append, optionally filtered by record fields.", map[string]interface{}{
		"type": "object",
		"properties": map[string]interface{}{
			"path": map[string]interface{}{
				"type":        "string",
				"description": "Ledger file path relative to your workspace (default \"ledger.json\")",
			},
			"filter": map[string]interface{}{
				"type":        "object",
				"description": "Return only entries whose record fields equal these values (case-insensitive string compare)",
			},
			"limit": map[string]interface{}{
				"type":        "integer",
				"description": "Maximum entries to return, most recently updated first (default 50)",
			},
		},
	}, makeLedgerReport(r))
}

// ledgerScalar renders a record value as the string used for identity and
// filtering. Only scalars are meaningful in a key; anything else is rejected
// by identityFor so a nested object can't silently become "map[...]".
func ledgerScalar(v any) (string, bool) {
	switch typed := v.(type) {
	case string:
		return strings.TrimSpace(typed), true
	case bool:
		return fmt.Sprintf("%t", typed), true
	case float64:
		// JSON numbers arrive as float64; render integers without ".0" so
		// 2026 keys as "2026" and matches a later string "2026".
		if typed == float64(int64(typed)) {
			return fmt.Sprintf("%d", int64(typed)), true
		}
		return fmt.Sprintf("%g", typed), true
	case json.Number:
		return typed.String(), true
	case nil:
		return "", true
	default:
		return "", false
	}
}

// identityFor builds the row identity from the key fields. Every key field
// must be present and non-empty: a ledger row whose identity is partly blank
// would collide with every other partly-blank row, which is worse than an
// error the model can correct.
func identityFor(record map[string]any, key []string) (string, error) {
	parts := make([]string, 0, len(key))
	for _, field := range key {
		raw, present := record[field]
		if !present {
			return "", fmt.Errorf("record is missing key field %q (key is %s)", field, strings.Join(key, " + "))
		}
		text, ok := ledgerScalar(raw)
		if !ok {
			return "", fmt.Errorf("key field %q must be a string, number or boolean", field)
		}
		if text == "" {
			return "", fmt.Errorf("key field %q is empty", field)
		}
		parts = append(parts, strings.ToLower(text))
	}
	return strings.Join(parts, "|"), nil
}

// resolveLedgerPath normalises the caller's path. The ledger is a workspace
// artifact, so absolute paths and escapes are refused outright — that keeps
// the tool safe to hand to an agent whose whole point is that it has no
// general filesystem access. Identity files and the `skills/` subtree are
// refused too: both are routed elsewhere by the file tools, and accepting them
// here would make the ledger's storage location depend on its name.
func resolveLedgerPath(path string) (string, error) {
	if strings.TrimSpace(path) == "" {
		return defaultLedgerPath, nil
	}
	if filepath.IsAbs(path) {
		return "", fmt.Errorf("ledger path must be relative to your workspace, got %q", path)
	}
	clean := filepath.Clean(filepath.FromSlash(path))
	if clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("ledger path must stay inside your workspace, got %q", path)
	}
	if isSingleSegmentSystemFile(clean) {
		return "", fmt.Errorf("%q is an identity file, not a ledger", clean)
	}
	if clean == "skills" || strings.HasPrefix(clean, "skills"+string(filepath.Separator)) {
		return "", fmt.Errorf("ledger path must not live under skills/, got %q", path)
	}
	return clean, nil
}

// readLedger loads the ledger, mirroring write_file's storage routing so the
// ledger lands wherever that agent's other artifacts do. resolveLedgerPath has
// already refused every path the file tools would send somewhere else
// (absolute, identity file, skills/), so a ledger is always workspace-scoped
// and needs no isWorkspacePath check. A missing file is not an error — it's an
// empty ledger.
func (r *Registry) readLedger(ctx context.Context, path string) (*ledgerFile, error) {
	var data []byte

	switch {
	case r.workspaceStore != nil && r.agentID != "":
		rc, err := r.workspaceStore.Get(ctx, r.agentID, r.sessionID, path)
		if err != nil {
			if errors.Is(err, workspace.ErrNotFound) {
				return &ledgerFile{}, nil
			}
			return nil, fmt.Errorf("workspace get: %w", err)
		}
		defer rc.Close()
		if data, err = io.ReadAll(rc); err != nil {
			return nil, fmt.Errorf("workspace read: %w", err)
		}
	case r.executor != nil:
		text, err := r.executor.ReadFile(ctx, path)
		if err != nil {
			// The executor has no typed not-found; an unreadable ledger and a
			// missing one are indistinguishable, so treat both as empty and
			// let the save surface a real write failure.
			return &ledgerFile{}, nil
		}
		data = []byte(text)
	default:
		full, err := resolvePathSandboxed(r.userRoot, r.sandboxRoot, path)
		if err != nil {
			return nil, err
		}
		if data, err = os.ReadFile(full); err != nil {
			if os.IsNotExist(err) {
				return &ledgerFile{}, nil
			}
			return nil, fmt.Errorf("read ledger: %w", err)
		}
	}

	return parseLedger(data, path)
}

// parseLedger accepts both the current envelope and a bare JSON array, which
// is what the file looks like when it was seeded by hand or written by an
// earlier free-form flow.
func parseLedger(data []byte, path string) (*ledgerFile, error) {
	trimmed := strings.TrimSpace(string(data))
	if trimmed == "" || trimmed == "null" {
		return &ledgerFile{}, nil
	}
	if strings.HasPrefix(trimmed, "[") {
		var entries []ledgerEntry
		if err := json.Unmarshal([]byte(trimmed), &entries); err != nil {
			return nil, fmt.Errorf("%s holds a JSON array this tool can't read: %w", path, err)
		}
		return &ledgerFile{Entries: entries}, nil
	}
	var file ledgerFile
	if err := json.Unmarshal([]byte(trimmed), &file); err != nil {
		return nil, fmt.Errorf("%s is not a ledger this tool wrote: %w", path, err)
	}
	return &file, nil
}

// writeLedger persists the ledger through the same routing readLedger uses.
func (r *Registry) writeLedger(ctx context.Context, path string, file *ledgerFile) error {
	data, err := json.MarshalIndent(file, "", "  ")
	if err != nil {
		return fmt.Errorf("encode ledger: %w", err)
	}
	data = append(data, '\n')

	switch {
	case r.workspaceStore != nil && r.agentID != "":
		if err := r.workspaceStore.Put(ctx, r.agentID, r.sessionID, path,
			strings.NewReader(string(data)), int64(len(data)), "application/json"); err != nil {
			return fmt.Errorf("workspace put: %w", err)
		}
	case r.executor != nil:
		if _, err := r.executor.WriteFile(ctx, path, string(data)); err != nil {
			return fmt.Errorf("write ledger: %w", err)
		}
	default:
		full, err := resolvePathSandboxed(r.userRoot, r.sandboxRoot, path)
		if err != nil {
			return err
		}
		if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
			return fmt.Errorf("create ledger directory: %w", err)
		}
		if err := os.WriteFile(full, data, 0o644); err != nil {
			return fmt.Errorf("write ledger: %w", err)
		}
	}
	return nil
}

func makeLedgerAppend(r *Registry) ToolFunc {
	return func(ctx context.Context, rawArgs json.RawMessage) (string, error) {
		var args ledgerAppendArgs
		if err := json.Unmarshal(rawArgs, &args); err != nil {
			return "", fmt.Errorf("parse args: %w", err)
		}
		if len(args.Record) == 0 {
			return "", fmt.Errorf("record is required and must not be empty")
		}
		path, err := resolveLedgerPath(args.Path)
		if err != nil {
			return "", err
		}

		// Hold the lock across load → merge → save. Without it two calls in
		// the same turn both write a one-row file and one row is lost.
		lock := ledgerLock(r.ledgerLockKey(path))
		lock.Lock()
		defer lock.Unlock()

		file, err := r.readLedger(ctx, path)
		if err != nil {
			return "", err
		}

		// Key precedence: what the caller declares this call, else what the
		// ledger already uses, else the generic default. A caller that
		// changes the key on an existing ledger would silently re-identify
		// every row, so that's refused.
		key := args.Key
		switch {
		case len(key) == 0:
			key = file.Key
			if len(key) == 0 {
				key = defaultLedgerKey
			}
		case len(file.Key) > 0 && !sameKey(key, file.Key):
			return "", fmt.Errorf("%s is keyed by [%s]; refusing to re-key it as [%s] because existing rows would change identity",
				path, strings.Join(file.Key, " "), strings.Join(key, " "))
		}

		identity, err := identityFor(args.Record, key)
		if err != nil {
			return "", err
		}

		now := time.Now().UTC()
		for i := range file.Entries {
			if file.Entries[i].Key != identity {
				continue
			}
			existing := file.Entries[i]
			file.Entries[i] = ledgerEntry{
				Key:       identity,
				Revision:  existing.Revision + 1,
				CreatedAt: existing.CreatedAt,
				UpdatedAt: now,
				Record:    args.Record,
			}
			if file.Entries[i].CreatedAt.IsZero() {
				file.Entries[i].CreatedAt = now
			}
			file.Version = ledgerVersion
			file.Key = key
			if err := r.writeLedger(ctx, path, file); err != nil {
				return "", err
			}
			return fmt.Sprintf("Updated %s (revision %d of %d entries): %s",
				path, file.Entries[i].Revision, len(file.Entries), identity), nil
		}

		if len(file.Entries) >= maxLedgerEntries {
			return "", fmt.Errorf("%s already holds %d entries; archive it before adding more", path, len(file.Entries))
		}
		file.Version = ledgerVersion
		file.Key = key
		file.Entries = append(file.Entries, ledgerEntry{
			Key:       identity,
			Revision:  1,
			CreatedAt: now,
			UpdatedAt: now,
			Record:    args.Record,
		})
		if err := r.writeLedger(ctx, path, file); err != nil {
			return "", err
		}
		return fmt.Sprintf("Appended to %s (%d entries): %s", path, len(file.Entries), identity), nil
	}
}

func makeLedgerReport(r *Registry) ToolFunc {
	return func(ctx context.Context, rawArgs json.RawMessage) (string, error) {
		var args ledgerReportArgs
		// An empty argument object is legitimate here — report the default
		// ledger — so only a malformed payload is an error.
		if len(rawArgs) > 0 && string(rawArgs) != "null" {
			if err := json.Unmarshal(rawArgs, &args); err != nil {
				return "", fmt.Errorf("parse args: %w", err)
			}
		}
		path, err := resolveLedgerPath(args.Path)
		if err != nil {
			return "", err
		}
		limit := args.Limit
		if limit <= 0 {
			limit = 50
		}

		file, err := r.readLedger(ctx, path)
		if err != nil {
			return "", err
		}

		matched := make([]ledgerEntry, 0, len(file.Entries))
		for _, entry := range file.Entries {
			if matchesFilter(entry.Record, args.Filter) {
				matched = append(matched, entry)
			}
		}
		// Most recently updated first: the entries a caller wants to reconcile
		// against are the ones it just touched.
		sort.SliceStable(matched, func(i, j int) bool {
			return matched[i].UpdatedAt.After(matched[j].UpdatedAt)
		})
		total := len(matched)
		truncated := false
		if total > limit {
			matched = matched[:limit]
			truncated = true
		}

		key := file.Key
		if len(key) == 0 {
			key = defaultLedgerKey
		}
		out := struct {
			Path      string        `json:"path"`
			Key       []string      `json:"key"`
			Total     int           `json:"total"`
			Returned  int           `json:"returned"`
			Truncated bool          `json:"truncated,omitempty"`
			Entries   []ledgerEntry `json:"entries"`
		}{path, key, total, len(matched), truncated, matched}

		data, err := json.MarshalIndent(out, "", "  ")
		if err != nil {
			return "", fmt.Errorf("encode report: %w", err)
		}
		return string(data), nil
	}
}

// ledgerLockKey namespaces the mutex by storage scope so two agents (or two
// sessions) writing "ledger.json" don't serialise against each other.
func (r *Registry) ledgerLockKey(path string) string {
	return strings.Join([]string{r.agentID, r.sessionID, r.userRoot, path}, "\x00")
}

func sameKey(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if !strings.EqualFold(strings.TrimSpace(a[i]), strings.TrimSpace(b[i])) {
			return false
		}
	}
	return true
}

// matchesFilter compares filter values against record values as strings, so a
// caller filtering season "2026" matches a record that stored the number 2026.
func matchesFilter(record map[string]any, filter map[string]any) bool {
	for field, want := range filter {
		wantText, ok := ledgerScalar(want)
		if !ok {
			return false
		}
		gotText, ok := ledgerScalar(record[field])
		if !ok || !strings.EqualFold(strings.TrimSpace(gotText), strings.TrimSpace(wantText)) {
			return false
		}
	}
	return true
}
