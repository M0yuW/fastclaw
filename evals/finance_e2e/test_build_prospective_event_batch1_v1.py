import json
import tempfile
import unittest
from pathlib import Path

import build_prospective_event_batch1_v1 as subject
from run_thesis_event_gateway import load_plugin, must_call


class ProspectiveEventBatch1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = subject.preflight()

    def test_source_bound_fixtures_and_historical_symbols(self):
        fixtures = self.result["fixtures"]
        self.assertEqual(self.result["planned_observations"], 25)
        self.assertEqual(len(fixtures), 5)
        self.assertEqual({item["case_id"] for item in fixtures},
                         set(self.result["source_packet_sha256"]))
        symbols = {item["case_id"].split("-")[0]: item["runtime_symbol"]
                   for item in fixtures}
        self.assertEqual(symbols["BNY"], "BK")
        self.assertEqual(symbols["FISV"], "FI")
        summaries = {item["case_id"].split("-")[0]: item["event"]["summary"]
                     for item in fixtures}
        self.assertIn("management statements", summaries["FISV"])
        self.assertIn("prior-year period", summaries["MCO"])
        for item in fixtures:
            self.assertEqual(set(item["seed_thesis"]["required_event_metrics"]),
                             set(item["event"]["observed_metrics"]))
            self.assertEqual(item["seed_thesis"]["symbol"], item["runtime_symbol"])
            self.assertEqual(len(item["event"]["sources"]), 1)
            self.assertEqual(len(item["seed_thesis"]["evidence"]), 1)

    def test_interpretation_oracles_are_not_in_model_inputs(self):
        for item in self.result["fixtures"]:
            packet_path = next(case["packet"] for case in
                               json.loads(subject.FRAME_PATH.read_text())["cases"]
                               if case["case_id"] == item["case_id"])
            packet = json.loads((subject.HERE / packet_path).read_text())
            content = json.dumps(item, ensure_ascii=False)
            self.assertNotIn("precommitted_interpretation_checks", content)
            for check in packet["precommitted_interpretation_checks"]:
                self.assertNotIn(check, content)

    def test_free_plugin_replay_creates_alert_without_a_model(self):
        for fixture in self.result["fixtures"]:
            with self.subTest(fixture["case_id"]), tempfile.TemporaryDirectory() as temp:
                plugin = load_plugin().FinanceToolsPlugin()
                plugin.initialize({"stateDbPath": str(Path(temp) / "finance-tools.db")})
                tenant = {"userId": "prospective-preflight-user", "agentId": "finance-coordinator",
                          "sessionId": "source-preflight"}
                saved = must_call(plugin, "thesis_save", fixture["seed_thesis"], tenant)["thesis"]
                must_call(plugin, "watchlist_save", {
                    "market": "US", "symbol": fixture["runtime_symbol"],
                    "thesis_id": saved["id"], "event_types": ["earnings"],
                    "keywords": [fixture["runtime_symbol"]], "min_match_score": 1,
                }, tenant)
                result = must_call(plugin, "event_alert_ingest", {
                    "market": "US", "symbol": fixture["runtime_symbol"],
                    "event": fixture["event"],
                }, tenant)
                self.assertEqual(result["created"], 1)
                alerts = must_call(plugin, "alert_list", {}, tenant)["alerts"]
                self.assertEqual(len(alerts), 1)
                self.assertEqual(alerts[0]["event"]["observed_metrics"],
                                 fixture["event"]["observed_metrics"])


if __name__ == "__main__":
    unittest.main()
