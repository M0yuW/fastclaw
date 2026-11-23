import json
import tempfile
import unittest
from pathlib import Path

import build_postcorrection_event_preflight_v2 as subject
from run_thesis_event_gateway import load_plugin, must_call


class PostcorrectionEventPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = subject.preflight()

    def test_twenty_ready_cases_belong_to_twenty_case_frame(self):
        self.assertEqual(20, self.result["ready_cases"])
        self.assertEqual(20, self.result["target_cases"])
        self.assertEqual("v2_source_and_numeric_preflight_complete_no_model_observations",
                         self.result["status"])
        self.assertEqual(0, self.result["model_observations"])
        self.assertFalse(self.result["paid_calls_authorized"])
        self.assertEqual({"BAC", "CME", "WFC", "AXP", "PNC", "CBOE", "ALLY", "STT", "ICE", "MSCI", "NDAQ", "JPM", "FIS", "GPN", "SYF", "WU", "SCHW", "IBKR", "COF", "FOUR"},
                         {item["runtime_symbol"] for item in self.result["fixtures"]})

    def test_prompt_contains_host_arithmetic_but_no_private_oracle(self):
        for item in self.result["fixtures"]:
            with self.subTest(item["runtime_symbol"]):
                prompt = subject.review_prompt(item, "thesis-id", "alert-id")
                self.assertIn("Displayed-value comparisons", prompt)
                self.assertIn("Baseline SEC SHA-256", prompt)
                self.assertIn("verify that any needs_review decision leaves the thesis blocked", prompt)
                self.assertEqual(set(item["seed_thesis"]["required_event_metrics"]),
                                 set(item["event"]["observed_metrics"]))
                path = subject.READY[item["runtime_symbol"]][1]
                packet = json.loads(path.read_text())
                self.assertNotIn("precommitted_interpretation_checks", prompt)
                for check in packet["precommitted_interpretation_checks"]:
                    self.assertNotIn(check, prompt)
        bny_like = {item["runtime_symbol"]: item for item in self.result["fixtures"]}
        self.assertIn("unlisted residual 0 USD_million", bny_like["BAC"]["numeric_context"])
        self.assertIn("unlisted residual 0 USD_million", bny_like["WFC"]["numeric_context"])
        self.assertIn("unlisted residual 0 USD_million", bny_like["PNC"]["numeric_context"])
        self.assertIn("unlisted residual 0 USD_million", bny_like["CBOE"]["numeric_context"])
        self.assertIn("unlisted residual 0 USD_million", bny_like["ALLY"]["numeric_context"])
        self.assertIn("unlisted residual 1 USD_million", bny_like["STT"]["numeric_context"])
        self.assertIn("unlisted residual 0 USD_million", bny_like["ICE"]["numeric_context"])
        self.assertIn("20747 USD_thousand", bny_like["MSCI"]["numeric_context"])
        self.assertIn("-917 thousand_shares", bny_like["MSCI"]["numeric_context"])
        self.assertIn("unlisted residual 0 USD_million", bny_like["NDAQ"]["numeric_context"])
        self.assertIn("1515 USD_million", bny_like["JPM"]["numeric_context"])
        self.assertIn("4.7 USD_billion", bny_like["AXP"]["numeric_context"])
        self.assertIn("unlisted residual 0 USD_million", bny_like["FIS"]["numeric_context"])
        self.assertIn("575 USD_million", bny_like["FIS"]["numeric_context"])
        self.assertIn("734 USD_million", bny_like["FIS"]["numeric_context"])
        self.assertIn("73 USD_million", bny_like["FIS"]["numeric_context"])
        self.assertIn("350808 USD_thousand", bny_like["GPN"]["numeric_context"])
        self.assertIn("-343624 USD_thousand", bny_like["GPN"]["numeric_context"])
        self.assertIn("40080 USD_thousand", bny_like["GPN"]["numeric_context"])
        self.assertIn("0.21 percentage_points", bny_like["SYF"]["numeric_context"])
        self.assertIn("-0.54 percentage_points", bny_like["SYF"]["numeric_context"])
        self.assertIn("0.2 million_accounts", bny_like["SYF"]["numeric_context"])
        self.assertIn("17.5 USD_million", bny_like["WU"]["numeric_context"])
        self.assertIn("-9.6 USD_million", bny_like["WU"]["numeric_context"])
        self.assertIn("-6.8 million_shares", bny_like["WU"]["numeric_context"])
        self.assertIn("unlisted residual 0 USD_million", bny_like["SCHW"]["numeric_context"])
        self.assertIn("300 USD_million", bny_like["SCHW"]["numeric_context"])
        self.assertIn("234 USD_million", bny_like["SCHW"]["numeric_context"])
        self.assertIn("unlisted residual 0 USD_million", bny_like["IBKR"]["numeric_context"])
        self.assertIn("180 USD_million", bny_like["IBKR"]["numeric_context"])
        self.assertIn("39 USD_million", bny_like["IBKR"]["numeric_context"])
        self.assertIn("-8.66 USD_billion", bny_like["COF"]["numeric_context"])
        self.assertIn("0.4 USD_billion", bny_like["COF"]["numeric_context"])
        self.assertIn("13.41 USD_per_share", bny_like["COF"]["numeric_context"])
        self.assertIn("unlisted residual 0 USD_million", bny_like["FOUR"]["numeric_context"])
        self.assertIn("-99.3 USD_million", bny_like["FOUR"]["numeric_context"])
        self.assertNotIn("non_gaap_adjusted_net_income", bny_like["FOUR"]["numeric_context"])

    def test_free_plugin_replay_blocks_voluntary_needs_review(self):
        for item in self.result["fixtures"]:
            with self.subTest(item["runtime_symbol"]), tempfile.TemporaryDirectory() as temp:
                plugin = load_plugin().FinanceToolsPlugin()
                plugin.initialize({"stateDbPath": str(Path(temp) / "finance-tools.db")})
                tenant = {"userId": "v2-source-preflight", "agentId": "finance-coordinator",
                          "sessionId": "v2-local-scripted-preflight"}
                thesis = must_call(plugin, "thesis_save", item["seed_thesis"], tenant)["thesis"]
                must_call(plugin, "watchlist_save", {
                    "market": "US", "symbol": item["runtime_symbol"],
                    "thesis_id": thesis["id"], "event_types": ["earnings"],
                    "keywords": [item["runtime_symbol"]], "min_match_score": 1,
                }, tenant)
                incoming = must_call(plugin, "event_alert_ingest", {
                    "market": "US", "symbol": item["runtime_symbol"],
                    "event": item["event"],
                }, tenant)
                self.assertEqual(1, incoming["created"])
                alert = incoming["results"][0]["alert"]
                self.assertEqual(item["event"]["observed_metrics"],
                                 alert["event"]["observed_metrics"])
                review = must_call(plugin, "thesis_record_review", {
                    "thesis_id": thesis["id"], "alert_id": alert["id"],
                    "expected_version": thesis["version"],
                    "event": {"summary": alert["event"]["summary"]},
                    "impact": "mixed", "decision": "needs_review",
                    "rationale": "Local deterministic fixture defers the research decision.",
                }, tenant)
                self.assertTrue(review["thesis"]["decision_hold"])
                self.assertEqual("blocked", review["thesis"]["actionability"])
                self.assertEqual(alert["id"], review["thesis"]["decision_hold_alert_id"])
                self.assertEqual(3, review["thesis"]["conviction"])
                must_call(plugin, "alert_update", {
                    "alert_id": alert["id"], "status": "acknowledged",
                    "expected_version": alert["version"],
                }, tenant)
                state = must_call(plugin, "thesis_get", {"thesis_id": thesis["id"]}, tenant)
                self.assertEqual("blocked", state["thesis"]["actionability"])


if __name__ == "__main__":
    unittest.main()
