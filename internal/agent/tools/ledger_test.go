package tools

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

// newLedgerRegistry builds a filesystem-backed registry rooted in a temp dir,
// which is the shape a single-host agent runs in.
func newLedgerRegistry(t *testing.T) (*Registry, string) {
	t.Helper()
	root := t.TempDir()
	return NewRegistry(root, root), root
}

func appendLedger(t *testing.T, r *Registry, args string) string {
	t.Helper()
	out, err := r.Execute(context.Background(), "ledger_append", args)
	if err != nil {
		t.Fatalf("ledger_append(%s) failed: %v", args, err)
	}
	return out
}

func readLedgerFile(t *testing.T, root, rel string) ledgerFile {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(root, rel))
	if err != nil {
		t.Fatalf("read ledger file: %v", err)
	}
	var file ledgerFile
	if err := json.Unmarshal(data, &file); err != nil {
		t.Fatalf("ledger file is not valid JSON: %v\n%s", err, data)
	}
	return file
}

func TestLedgerAppendCreatesFileAndPersistsKey(t *testing.T) {
	r, root := newLedgerRegistry(t)

	appendLedger(t, r, `{"path":"football/ledger.json","key":["competition","season","date","match"],
		"record":{"competition":"UCL","season":"2026","date":"2026-08-12","match":"A vs B","lean":"home"}}`)

	file := readLedgerFile(t, root, "football/ledger.json")
	if file.Version != ledgerVersion {
		t.Fatalf("version = %d, want %d", file.Version, ledgerVersion)
	}
	// The key is stored in the file so a later turn — with a fresh model
	// context — identifies rows the same way without being told again.
	if strings.Join(file.Key, ",") != "competition,season,date,match" {
		t.Fatalf("key = %v", file.Key)
	}
	if len(file.Entries) != 1 {
		t.Fatalf("entries = %d, want 1", len(file.Entries))
	}
	if file.Entries[0].Revision != 1 {
		t.Fatalf("revision = %d, want 1", file.Entries[0].Revision)
	}
}

// The whole point of the tool: asking twice about the same match updates one
// row instead of growing the ledger.
func TestLedgerAppendUpdatesSameKeyInsteadOfDuplicating(t *testing.T) {
	r, root := newLedgerRegistry(t)
	const key = `"key":["competition","season","date","match"]`

	appendLedger(t, r, `{`+key+`,"record":{"competition":"UCL","season":"2026","date":"2026-08-12","match":"A vs B","lean":"home"}}`)
	out := appendLedger(t, r, `{`+key+`,"record":{"competition":"UCL","season":"2026","date":"2026-08-12","match":"A vs B","lean":"draw"}}`)

	if !strings.Contains(out, "Updated") {
		t.Fatalf("second write reported %q, want an update", out)
	}
	file := readLedgerFile(t, root, defaultLedgerPath)
	if len(file.Entries) != 1 {
		t.Fatalf("entries = %d, want 1 after re-writing the same match", len(file.Entries))
	}
	entry := file.Entries[0]
	if entry.Revision != 2 {
		t.Fatalf("revision = %d, want 2", entry.Revision)
	}
	if entry.Record["lean"] != "draw" {
		t.Fatalf("record was not replaced: %v", entry.Record)
	}
	if entry.CreatedAt.IsZero() || entry.UpdatedAt.Before(entry.CreatedAt) {
		t.Fatalf("timestamps are wrong: created=%v updated=%v", entry.CreatedAt, entry.UpdatedAt)
	}
}

// Identity ignores case and surrounding space, and ignores non-key fields:
// two reports of the same fixture must not become two rows because the model
// capitalised the competition differently or changed its lean.
func TestLedgerIdentityIsCaseAndWhitespaceInsensitive(t *testing.T) {
	r, root := newLedgerRegistry(t)
	const key = `"key":["competition","date"]`

	appendLedger(t, r, `{`+key+`,"record":{"competition":"UCL","date":"2026-08-12","lean":"home"}}`)
	appendLedger(t, r, `{`+key+`,"record":{"competition":" ucl ","date":"2026-08-12","lean":"away"}}`)

	if file := readLedgerFile(t, root, defaultLedgerPath); len(file.Entries) != 1 {
		t.Fatalf("entries = %d, want 1", len(file.Entries))
	}
}

// A key field the record doesn't carry means the row has no identity. Failing
// loudly lets the model correct itself; silently keying on "" would collapse
// every such row onto one.
func TestLedgerAppendRejectsMissingOrEmptyKeyField(t *testing.T) {
	r, _ := newLedgerRegistry(t)

	if _, err := r.Execute(context.Background(), "ledger_append",
		`{"key":["competition","date"],"record":{"competition":"UCL"}}`); err == nil {
		t.Fatal("missing key field was accepted")
	}
	if _, err := r.Execute(context.Background(), "ledger_append",
		`{"key":["competition","date"],"record":{"competition":"UCL","date":"   "}}`); err == nil {
		t.Fatal("blank key field was accepted")
	}
	if _, err := r.Execute(context.Background(), "ledger_append",
		`{"key":["competition"],"record":{"competition":{"nested":true}}}`); err == nil {
		t.Fatal("non-scalar key field was accepted")
	}
	if _, err := r.Execute(context.Background(), "ledger_append", `{"record":{}}`); err == nil {
		t.Fatal("empty record was accepted")
	}
}

// Numbers arrive as float64 from JSON. Season 2026 must key as "2026" so a
// later string "2026" is the same row, not a second one.
func TestLedgerNumericKeyFieldsKeyAsIntegers(t *testing.T) {
	r, root := newLedgerRegistry(t)
	const key = `"key":["competition","season"]`

	appendLedger(t, r, `{`+key+`,"record":{"competition":"UCL","season":2026,"lean":"home"}}`)
	appendLedger(t, r, `{`+key+`,"record":{"competition":"UCL","season":"2026","lean":"draw"}}`)

	file := readLedgerFile(t, root, defaultLedgerPath)
	if len(file.Entries) != 1 {
		t.Fatalf("entries = %d, want 1; numeric and string 2026 must be one row", len(file.Entries))
	}
	if got := file.Entries[0].Key; got != "ucl|2026" {
		t.Fatalf("identity = %q, want ucl|2026", got)
	}
}

// Re-keying an existing ledger would silently change what every stored row
// means, so it's refused rather than applied.
func TestLedgerAppendRefusesToRekeyExistingLedger(t *testing.T) {
	r, _ := newLedgerRegistry(t)
	appendLedger(t, r, `{"key":["competition","date"],"record":{"competition":"UCL","date":"2026-08-12"}}`)

	_, err := r.Execute(context.Background(), "ledger_append",
		`{"key":["match"],"record":{"match":"A vs B"}}`)
	if err == nil {
		t.Fatal("re-keying an existing ledger was accepted")
	}
	if !strings.Contains(err.Error(), "keyed by") {
		t.Fatalf("unexpected error: %v", err)
	}
}

// An omitted key reuses what the ledger already recorded, so a caller that
// declared the key once doesn't have to repeat it every turn.
func TestLedgerAppendReusesStoredKeyWhenOmitted(t *testing.T) {
	r, root := newLedgerRegistry(t)
	appendLedger(t, r, `{"key":["competition","date"],"record":{"competition":"UCL","date":"2026-08-12","lean":"home"}}`)

	appendLedger(t, r, `{"record":{"competition":"UCL","date":"2026-08-12","lean":"away"}}`)

	file := readLedgerFile(t, root, defaultLedgerPath)
	if len(file.Entries) != 1 || file.Entries[0].Revision != 2 {
		t.Fatalf("stored key was not reused: %+v", file.Entries)
	}
}

func TestLedgerReportFiltersAndReportsTotals(t *testing.T) {
	r, _ := newLedgerRegistry(t)
	const key = `"key":["competition","match"]`
	appendLedger(t, r, `{`+key+`,"record":{"competition":"UCL","match":"A vs B","lean":"home"}}`)
	appendLedger(t, r, `{`+key+`,"record":{"competition":"UCL","match":"C vs D","lean":"draw"}}`)
	appendLedger(t, r, `{`+key+`,"record":{"competition":"EPL","match":"E vs F","lean":"away"}}`)

	out, err := r.Execute(context.Background(), "ledger_report", `{"filter":{"competition":"ucl"}}`)
	if err != nil {
		t.Fatalf("ledger_report failed: %v", err)
	}
	var report struct {
		Total     int           `json:"total"`
		Returned  int           `json:"returned"`
		Truncated bool          `json:"truncated"`
		Key       []string      `json:"key"`
		Entries   []ledgerEntry `json:"entries"`
	}
	if err := json.Unmarshal([]byte(out), &report); err != nil {
		t.Fatalf("report is not JSON: %v\n%s", err, out)
	}
	if report.Total != 2 || report.Returned != 2 {
		t.Fatalf("total=%d returned=%d, want 2/2", report.Total, report.Returned)
	}
	if strings.Contains(out, "E vs F") {
		t.Fatalf("filter leaked a non-matching competition: %s", out)
	}
	if report.Truncated {
		t.Fatal("report claims truncation with no limit hit")
	}
}

func TestLedgerReportLimitTruncatesMostRecentFirst(t *testing.T) {
	r, _ := newLedgerRegistry(t)
	const key = `"key":["match"]`
	appendLedger(t, r, `{`+key+`,"record":{"match":"first"}}`)
	appendLedger(t, r, `{`+key+`,"record":{"match":"second"}}`)

	out, err := r.Execute(context.Background(), "ledger_report", `{"limit":1}`)
	if err != nil {
		t.Fatalf("ledger_report failed: %v", err)
	}
	var report struct {
		Total     int  `json:"total"`
		Returned  int  `json:"returned"`
		Truncated bool `json:"truncated"`
	}
	if err := json.Unmarshal([]byte(out), &report); err != nil {
		t.Fatalf("report is not JSON: %v", err)
	}
	if report.Total != 2 || report.Returned != 1 || !report.Truncated {
		t.Fatalf("total=%d returned=%d truncated=%v", report.Total, report.Returned, report.Truncated)
	}
	if !strings.Contains(out, "second") {
		t.Fatalf("truncated report dropped the newest entry: %s", out)
	}
}

// Reporting before anything was written is a normal first turn, not an error.
func TestLedgerReportOnMissingFileIsEmptyNotAnError(t *testing.T) {
	r, _ := newLedgerRegistry(t)

	out, err := r.Execute(context.Background(), "ledger_report", `{}`)
	if err != nil {
		t.Fatalf("report on a missing ledger failed: %v", err)
	}
	if !strings.Contains(out, `"total": 0`) {
		t.Fatalf("empty report = %s", out)
	}
	// The tool is also called with no arguments at all.
	if _, err := r.Execute(context.Background(), "ledger_report", ``); err != nil {
		t.Fatalf("report with empty args failed: %v", err)
	}
}

// A ledger seeded as a bare `[]` (what the provisioning script writes) must be
// readable, or the coordinator's first append would fail on its own fixture.
func TestLedgerReadsBareArrayFile(t *testing.T) {
	r, root := newLedgerRegistry(t)
	if err := os.WriteFile(filepath.Join(root, defaultLedgerPath), []byte("[]\n"), 0o644); err != nil {
		t.Fatalf("seed ledger: %v", err)
	}

	appendLedger(t, r, `{"key":["match"],"record":{"match":"A vs B"}}`)

	file := readLedgerFile(t, root, defaultLedgerPath)
	if len(file.Entries) != 1 {
		t.Fatalf("entries = %d, want 1", len(file.Entries))
	}
}

func TestLedgerRejectsAbsoluteAndEscapingPaths(t *testing.T) {
	r, _ := newLedgerRegistry(t)

	for _, path := range []string{"/etc/ledger.json", "../escape.json", "SOUL.md"} {
		args := `{"path":"` + path + `","key":["match"],"record":{"match":"x"}}`
		if _, err := r.Execute(context.Background(), "ledger_append", args); err == nil {
			t.Fatalf("path %q was accepted", path)
		}
	}
}

// Two appends racing inside one turn must both survive: the read-modify-write
// cycle is serialised per ledger.
func TestLedgerConcurrentAppendsDoNotLoseEntries(t *testing.T) {
	r, root := newLedgerRegistry(t)

	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			args := `{"key":["match"],"record":{"match":"m` + string(rune('a'+n)) + `"}}`
			if _, err := r.Execute(context.Background(), "ledger_append", args); err != nil {
				t.Errorf("concurrent append %d failed: %v", n, err)
			}
		}(i)
	}
	wg.Wait()

	if file := readLedgerFile(t, root, defaultLedgerPath); len(file.Entries) != 8 {
		t.Fatalf("entries = %d, want 8; concurrent appends lost rows", len(file.Entries))
	}
}

// The tools must be part of the default builtin face, or a permissive agent
// can't use them at all.
func TestLedgerToolsAreRegisteredAsBuiltins(t *testing.T) {
	r, _ := newLedgerRegistry(t)
	for _, name := range []string{"ledger_append", "ledger_report"} {
		if !r.HasBuiltin(name) {
			t.Fatalf("%s is not a builtin", name)
		}
	}
}
