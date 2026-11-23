package policy

import "testing"

func TestFinanceWorkflowPilotPolicy(t *testing.T) {
	engine := NewEngine(LoadPreset("finance-workflow-pilot"))
	for _, name := range []string{
		"finance-tools__screen_stocks", "finance-tools__portfolio_risk",
		"finance-tools__portfolio_policy_bound",
		"finance-tools__thesis_save", "finance-tools__thesis_record_review",
		"finance-tools__alert_update",
	} {
		if err := engine.CheckTool(name); err != nil {
			t.Errorf("%s should be allowed: %v", name, err)
		}
	}
	for _, name := range []string{
		"exec", "read_file", "spawn_subagent", "finance-tools__event_alert_ingest",
		"finance-tools__stock_snapshot", "finance-tools__market_events",
	} {
		if err := engine.CheckTool(name); err == nil {
			t.Errorf("%s should be denied", name)
		}
	}
	if engine.Policy().Network.Mode != "none" {
		t.Fatal("pilot agent must have no network access")
	}
}
