"""Offline regression of the actual source-locked NVDA packet omission."""

import tempfile
import unittest
from pathlib import Path

from .test_thesis_event_integration import load_plugin, locked_episode


class MissingEvidenceGuardTest(unittest.TestCase):
    def test_nvda_omitted_margin_requires_needs_review(self):
        q1, q1_source = locked_episode("FSEC-NVDA-01")
        q2, q2_source = locked_episode("FSEC-NVDA-02")
        q2_facts = {fact["metric"]: fact for fact in q2["facts"]}
        tenant = {"userId": "source-locked-user", "agentId": "finance-coordinator", "sessionId": "case"}
        with tempfile.TemporaryDirectory() as folder:
            finance = load_plugin().FinanceToolsPlugin()
            finance.initialize({"stateDbPath": str(Path(folder) / "ledger.db")})

            def call(name, args):
                result = finance.execute(name, args, tenant)
                self.assertTrue(result["ok"], result.get("errors"))
                return result["data"]

            thesis = call("thesis_save", {
                "market": "US", "symbol": "NVDA", "title": "Revenue with margin resilience",
                "thesis": "Q1 revenue and Data Center growth require current GAAP margin verification.",
                "status": "active", "conviction": 3,
                "required_event_metrics": ["quarterly_revenue", "data_center_revenue", "gross_margin"],
                "evidence": [{"id": q1_source["id"], "sha256": q1_source["sha256"]}],
            })["thesis"]
            call("watchlist_save", {"market": "US", "symbol": "NVDA",
                                    "thesis_id": thesis["id"], "event_types": ["earnings"],
                                    "keywords": ["NVDA"], "min_match_score": 1})
            packet_metrics = {
                metric: {"value": fact["value"], "unit": fact["unit"], "fact_id": fact["id"]}
                for metric, fact in q2_facts.items() if metric != "gross_margin"
            }
            self.assertIn("gross_margin", q2_facts)  # omitted only from the packet
            alert = call("event_alert_ingest", {
                "market": "US", "symbol": "NVDA", "event": {
                    "external_id": q2["source_id"], "type": "earnings",
                    "summary": "NVDA Q2 revenue and Data Center grew; packet does not provide GAAP margin.",
                    "as_of": q2["observed_at"],
                    "sources": [{"id": q2_source["id"], "url": q2_source["url"],
                                 "sha256": q2_source["sha256"]}],
                    "observed_metrics": packet_metrics,
                },
            })["results"][0]["alert"]
            held = call("thesis_get", {"thesis_id": thesis["id"]})["thesis"]
            self.assertTrue(held["decision_hold"])
            self.assertEqual("blocked", held["actionability"])
            review = {
                "thesis_id": thesis["id"], "alert_id": alert["id"],
                "expected_version": held["version"],
                "event": {"summary": "The model cannot fill in the missing packet field."},
                "impact": "mixed", "decision": "maintain",
                "rationale": "Growth observed but margin remains unverified.",
            }
            blocked = finance.execute("thesis_record_review", review, tenant)
            self.assertFalse(blocked["ok"])
            self.assertEqual("decision_on_hold", blocked["errors"][0]["code"])
            self.assertEqual(alert["id"], blocked["errors"][0]["details"]["alert_id"])
            self.assertEqual([], call("thesis_get", {"thesis_id": thesis["id"]})["reviews"])

            accepted = call("thesis_record_review", {**review, "decision": "needs_review"})
            self.assertEqual("needs_review", accepted["review"]["decision"])
            self.assertEqual(["gross_margin"], accepted["review"]["missing_metrics"])
            self.assertEqual(3, accepted["thesis"]["version"])
            self.assertEqual("active", accepted["thesis"]["status"])
            self.assertEqual(3, accepted["thesis"]["conviction"])
            self.assertTrue(accepted["thesis"]["decision_hold"])
            self.assertEqual("blocked", accepted["thesis"]["actionability"])


if __name__ == "__main__":
    unittest.main()
