"""Free end-to-end ledger replay using BILL's frozen SEC-source discrepancy."""

import json
import tempfile
import unittest
from pathlib import Path

from run_thesis_event_panel import HERE
from test_thesis_event_integration import load_plugin
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "bill_reference_source_row_audit_v1.json"


class BILLSourceConflictIntegrationTests(unittest.TestCase):
    def test_one_source_two_disagreeing_statement_rows_hold_thesis(self):
        self.assertEqual(verify(PACKET)["checked_rows"], 9)
        packet = json.loads(PACKET.read_text())
        selection = json.loads((HERE / packet["source_pair_selection"]).read_text())
        pair = next(item for item in selection["pairs"] if item["symbol"] == "BILL")
        source = pair["periods"]["CY2025_Q2"]
        discrepancy = packet["source_internal_discrepancy"]
        tenant = {"userId": "bill-source-conflict", "agentId": "research-agent",
                  "sessionId": "offline-real-source-replay"}

        with tempfile.TemporaryDirectory() as directory:
            finance = load_plugin().FinanceToolsPlugin()
            finance.initialize({"stateDbPath": str(Path(directory) / "ledger.db")})

            def call(name, args):
                result = finance.execute(name, args, tenant)
                self.assertTrue(result["ok"], (name, result.get("errors")))
                return result["data"]

            thesis = call("thesis_save", {
                "market": "US", "symbol": "BILL", "status": "active",
                "conviction": 3,
                "thesis": "Revenue quality and operating loss need ongoing review.",
            })["thesis"]
            call("watchlist_save", {
                "market": "US", "symbol": "BILL", "thesis_id": thesis["id"],
                "event_types": ["earnings"], "keywords": ["BILL"],
                "min_match_score": 1,
            })
            source_claims = [
                {"metric": "gaap_net_income", "period": "2025-06-30",
                 "value": discrepancy[value_field], "unit": discrepancy["unit"],
                 "fact_id": fact_id, "source_sha256": source["sha256"]}
                for value_field, fact_id in (
                    ("statement_of_operations_value", "BILL-JUNE-OPS-NET"),
                    ("cash_flow_value", "BILL-JUNE-CF-NET"),
                )
            ]
            alert = call("event_alert_ingest", {
                "market": "US", "symbol": "BILL", "event": {
                    "external_id": source["accession"], "type": "earnings",
                    "summary": "BILL June-quarter source prints conflicting net-income rows.",
                    "as_of": "2025-06-30",
                    "sources": [{"id": source["accession"], "url": source["url"],
                                 "sha256": source["sha256"]}],
                    "source_claims": source_claims,
                },
            })["results"][0]["alert"]
            conflicts = alert["event"]["unresolved_conflicts"]
            self.assertEqual(len(conflicts), 1)
            self.assertEqual({item["value"] for item in conflicts[0]["claims"]},
                             {"-7074", "-7072"})
            self.assertEqual({item["source_sha256"] for item in conflicts[0]["claims"]},
                             {source["sha256"]})
            held = call("thesis_get", {"thesis_id": thesis["id"]})["thesis"]
            self.assertEqual(held["actionability"], "blocked")
            self.assertEqual(held["conviction"], 3)
            substantive = {
                "thesis_id": thesis["id"], "alert_id": alert["id"],
                "expected_version": held["version"],
                "event": {"summary": "Model copy is not the trusted event."},
                "impact": "positive", "decision": "upgrade",
                "rationale": "Cannot resolve conflicting source values.",
                "new_conviction": 4,
            }
            rejected = finance.execute("thesis_record_review", substantive, tenant)
            self.assertFalse(rejected["ok"])
            accepted = call("thesis_record_review", {
                **substantive, "impact": "mixed", "decision": "needs_review",
                "new_conviction": 3,
            })
            self.assertEqual(accepted["review"]["decision"], "needs_review")
            self.assertEqual(accepted["thesis"]["actionability"], "blocked")
            self.assertEqual(accepted["thesis"]["conviction"], 3)
            self.assertEqual(len(accepted["review"]["unresolved_conflicts"]), 1)


if __name__ == "__main__":
    unittest.main()
