package policy

import "testing"

func TestFinanceReviewOnlyPolicy(t *testing.T) {
	engine := NewEngine(LoadPreset("finance-review-only"))
	for _, name := range []string{
		"finance-tools__thesis_get",
		"finance-tools__thesis_match_event",
		"finance-tools__thesis_record_review",
		"finance-tools__alert_list",
		"finance-tools__alert_update",
	} {
		if err := engine.CheckTool(name); err != nil {
			t.Errorf("%s should be allowed: %v", name, err)
		}
	}
	for _, name := range []string{
		"exec", "read_file", "spawn_subagent", "finance-tools__thesis_save",
		"finance-tools__event_alert_ingest", "finance-tools__stock_snapshot",
	} {
		if err := engine.CheckTool(name); err == nil {
			t.Errorf("%s should be denied", name)
		}
	}
}
