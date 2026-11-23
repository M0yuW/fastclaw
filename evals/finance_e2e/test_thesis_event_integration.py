"""Source-locked SEC event to finance ledger integration smoke test.

This exercises real finance-tools state mutations without a model call. It is
not an agent-quality result; the model-in-the-loop experiment is specified in
THESIS-EVENT-INTEGRATION-PROTOCOL.md.
"""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PLUGIN_PATH = ROOT / "plugins" / "finance-tools" / "plugin.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("finance_event_plugin", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def locked_episode(episode_id):
    evidence = json.loads((HERE / "evidence.json").read_text(encoding="utf-8"))
    lock = json.loads((HERE / "source-lock.json").read_text(encoding="utf-8"))
    episode = next(item for item in evidence["episodes"] if item["id"] == episode_id)
    source = next(item for item in lock["entries"] if item["id"] == episode["source_id"])
    artifact = HERE / source["local_path"]
    actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if actual_hash != source["sha256"]:
        raise AssertionError(f"SEC source hash mismatch: {source['id']}")
    return episode, source


class ThesisEventIntegrationTest(unittest.TestCase):
    def test_amd_q3_event_review_is_persisted_once(self):
        episode, source = locked_episode("FSEC-AMD-02")
        facts = {fact["id"]: fact for fact in episode["facts"]}
        self.assertEqual("6819", facts["AMD-Q3-REV"]["value"])
        self.assertEqual("50", facts["AMD-Q3-GM"]["value"])
        self.assertEqual("462", facts["AMD-Q3-GAME"]["value"])
        event_summary = (
            "AMD Q3 2024 GAAP revenue was USD 6,819 million and gross margin "
            "was 50 percent; Gaming revenue was USD 462 million."
        )
        event = {
            "external_id": episode["source_id"],
            "type": "earnings",
            "summary": event_summary,
            "as_of": episode["observed_at"],
            "sources": [
                {
                    "id": source["id"],
                    "url": source["url"],
                    "sha256": source["sha256"],
                    "fact_ids": sorted(facts),
                }
            ],
        }
        tenant = {"userId": "eval-user", "agentId": "eval-agent", "sessionId": "eval-session"}
        other = {"userId": "other-user", "agentId": "other-agent", "sessionId": "other-session"}

        with tempfile.TemporaryDirectory() as directory:
            finance = load_plugin().FinanceToolsPlugin()
            finance.initialize({"stateDbPath": str(Path(directory) / "ledger.db")})

            def call(name, args, context=tenant):
                result = finance.execute(name, args, context)
                self.assertTrue(result["ok"], f"{name}: {result['errors']}")
                return result["data"]

            thesis = call(
                "thesis_save",
                {
                    "market": "US",
                    "symbol": "AMD",
                    "title": "Data Center growth with segment-mix risk",
                    "thesis": "Revenue growth remains relevant, but Gaming weakness must be monitored.",
                    "status": "active",
                    "conviction": 3,
                    "catalysts": ["revenue growth"],
                    "invalidations": ["Gaming weakness"],
                },
            )["thesis"]
            call(
                "watchlist_save",
                {
                    "market": "US",
                    "symbol": "AMD",
                    "thesis_id": thesis["id"],
                    "event_types": ["earnings"],
                    "keywords": ["Gaming revenue"],
                    "min_match_score": 1,
                },
            )
            matched = call(
                "thesis_match_event",
                {"market": "US", "symbol": "AMD", "event_summary": event_summary},
            )
            self.assertEqual(thesis["id"], matched["matches"][0]["thesis_id"])

            first = call("event_alert_ingest", {"market": "US", "symbol": "AMD", "event": event})
            duplicate = call("event_alert_ingest", {"market": "US", "symbol": "AMD", "event": event})
            self.assertEqual((1, 0), (first["created"], first["deduplicated"]))
            self.assertEqual((0, 1), (duplicate["created"], duplicate["deduplicated"]))
            alert = duplicate["results"][0]["alert"]
            self.assertEqual(2, alert["duplicate_count"])

            review_args = {
                "thesis_id": thesis["id"],
                "expected_version": thesis["version"],
                "event": event,
                "impact": "mixed",
                "decision": "maintain",
                "rationale": "Revenue and GAAP margin improved, but Gaming remained below Q2; keep the risk visible.",
                "evidence": event["sources"],
                "new_status": "active",
                "new_conviction": 3,
            }
            reviewed = call("thesis_record_review", review_args)
            self.assertEqual(2, reviewed["thesis"]["version"])
            self.assertEqual("active", reviewed["thesis"]["status"])
            self.assertEqual(3, reviewed["thesis"]["conviction"])

            stale = finance.execute("thesis_record_review", review_args, tenant)
            self.assertFalse(stale["ok"])
            self.assertEqual("version_conflict", stale["errors"][0]["code"])
            fetched = call("thesis_get", {"thesis_id": thesis["id"]})
            self.assertEqual(1, len(fetched["reviews"]))
            self.assertEqual(source["sha256"], fetched["reviews"][0]["event"]["sources"][0]["sha256"])

            call(
                "alert_update",
                {"alert_id": alert["id"], "status": "acknowledged", "expected_version": alert["version"]},
            )
            self.assertEqual(1, call("alert_list", {})["count"])
            self.assertEqual(0, call("alert_list", {}, other)["count"])
            self.assertEqual(0, call("thesis_list", {}, other)["count"])


if __name__ == "__main__":
    unittest.main()
