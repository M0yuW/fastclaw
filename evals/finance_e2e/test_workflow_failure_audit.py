"""Deterministic replay of malformed finance calls and trace attribution."""

import json
import tempfile
import unittest
from pathlib import Path

from .test_thesis_event_integration import load_plugin
from .workflow_failure_audit import audit_attempt

HERE = Path(__file__).resolve().parent
FAILED_ATTEMPT = (HERE / "results/2026-10-18-finance-workflow-flash-panel-v1"
                  / "W01F-r1/result.json")


class WorkflowFailureAuditTest(unittest.TestCase):
    def test_retained_attempt_attributes_all_three_failure_layers(self):
        module = load_plugin()
        attempt = json.loads(FAILED_ATTEMPT.read_text())
        audit = audit_attempt(attempt, module.tool_definitions())
        self.assertEqual("W01F-r1", audit["attempt_id"])
        self.assertEqual(4, len(audit["missing_required_calls"]))
        self.assertTrue(all(call["missing_required"] == ["thesis_id"]
                            for call in audit["missing_required_calls"]))
        self.assertEqual({"invalid_input": 4, "alert_required": 1}, audit["error_codes"])
        self.assertTrue(audit["later_successful_retry"])
        self.assertTrue(audit["budget_exhausted"])
        self.assertFalse(audit["request_error"])
        self.assertFalse(audit["workflow_complete"])
        self.assertEqual([], audit["unpaired_calls"])

    def test_local_plugin_replay_rejects_bad_calls_then_allows_correction(self):
        module = load_plugin()
        with tempfile.TemporaryDirectory(prefix="finance-replay-") as directory:
            plugin = module.FinanceToolsPlugin()
            plugin.initialize({"stateDbPath": str(Path(directory) / "ledger.db")})
            tenant = {"userId": "replay-user", "agentId": "replay-agent",
                      "sessionId": "replay-session"}

            def call(name, args):
                return plugin.execute(name, args, tenant)

            thesis = call("thesis_save", {
                "market": "US", "symbol": "FICE", "thesis": "Frozen local replay thesis.",
                "status": "active", "conviction": 3,
                "required_event_metrics": ["quarterly_revenue"],
            })["data"]["thesis"]
            watch = call("watchlist_save", {
                "market": "US", "symbol": "FICE", "thesis_id": thesis["id"],
                "event_types": ["earnings"], "keywords": ["FICE"],
                "min_match_score": 1,
            })
            self.assertTrue(watch["ok"])
            alert = call("event_alert_ingest", {
                "market": "US", "symbol": "FICE", "event": {
                    "type": "earnings", "summary": "FICE fixture quarterly revenue 100.",
                    "sources": [{"id": "fixture", "sha256": "a" * 64}],
                    "observed_metrics": {"quarterly_revenue": {
                        "value": "100", "unit": "USD_million", "fact_id": "FICE-REV"}},
                },
            })["data"]["results"][0]["alert"]
            review = {"event": {"summary": "FICE fixture quarterly revenue 100."},
                      "impact": "neutral", "decision": "maintain",
                      "rationale": "The frozen revenue fact is 100 USD million.",
                      "expected_version": 1}
            for _ in range(4):
                rejected = call("thesis_record_review", {**review, "alert_id": alert["id"]})
                self.assertEqual("invalid_input", rejected["errors"][0]["code"])
            missing_alert = call("thesis_record_review", {**review, "thesis_id": thesis["id"]})
            self.assertEqual("alert_required", missing_alert["errors"][0]["code"])
            before = call("thesis_get", {"thesis_id": thesis["id"]})["data"]
            self.assertEqual(1, before["thesis"]["version"])
            self.assertEqual([], before["reviews"])
            corrected = call("thesis_record_review", {
                **review, "thesis_id": thesis["id"], "alert_id": alert["id"]})
            self.assertTrue(corrected["ok"], corrected.get("errors"))
            acknowledged = call("alert_update", {
                "alert_id": alert["id"], "status": "acknowledged",
                "expected_version": alert["version"],
            })
            self.assertTrue(acknowledged["ok"], acknowledged.get("errors"))
            after = call("thesis_get", {"thesis_id": thesis["id"]})["data"]
            self.assertEqual(2, after["thesis"]["version"])
            self.assertEqual(1, len(after["reviews"]))
            self.assertEqual("acknowledged", acknowledged["data"]["alert"]["status"])


if __name__ == "__main__":
    unittest.main()
