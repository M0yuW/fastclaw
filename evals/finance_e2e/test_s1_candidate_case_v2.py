import importlib.util
import tempfile
import unittest
from pathlib import Path

from evals.finance_e2e.s1_candidate_case_v2 import FIXTURES, prompt, score


class S1CandidateCaseV2Test(unittest.TestCase):
    def test_fixture_retains_only_complete_candidate_with_provenance(self):
        plugin_path = Path(__file__).resolve().parents[2] / "plugins" / "finance-tools" / "plugin.py"
        spec = importlib.util.spec_from_file_location("s1_v2_finance_plugin", plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp_root:
            finance = module.FinanceToolsPlugin()
            finance.initialize({"finskillsPath": str(FIXTURES),
                                "stateDbPath": str(Path(temp_root) / "ledger.db"),
                                "evaluationFixture": True})
            result = finance.execute("screen_stocks", {
                "market": "US", "symbols": ["FICC", "FICD"],
                "require_complete": True})
        self.assertTrue(result["ok"])
        self.assertEqual(["FICC"], [item["symbol"] for item in result["data"]["results"]])
        self.assertEqual(["FICD"], [item["symbol"] for item in result["data"]["rejected"]])
        retained = result["data"]["results"][0]
        self.assertEqual("FY2025", retained["period"])
        self.assertEqual("USD_million", retained["cash_flow"]["unit"])
        self.assertEqual("local_evaluation_fixture", result["sources"][0]["name"])

    def test_prompt_defines_sandbox_record_not_real_investment_thesis(self):
        text = prompt().lower()
        self.assertIn("sandbox-only", text)
        self.assertIn("synthetic preliminary", text)
        self.assertNotIn("ficc is the winner", text)

    def test_oracle_requires_labeled_record_and_exact_metrics(self):
        state = {"theses": [{"thesis": {
            "symbol": "FICC", "title": "SYNTHETIC PRELIMINARY candidate",
            "thesis": "SYNTHETIC PRELIMINARY FY2025 note: P/E 16.5, free cash flow 310 USD million, ROIC 13%.",
        }}], "alerts": []}
        checks = score(state, ["finance-tools__screen_stocks", "finance-tools__thesis_save"])
        self.assertTrue(all(checks.values()))
        state["theses"][0]["thesis"]["title"] = "Candidate"
        state["theses"][0]["thesis"]["thesis"] = "FY2025 P/E 16.5, FCF 310 USD_million, ROIC 0.13."
        self.assertFalse(score(state, ["finance-tools__screen_stocks"])["sandbox_label"])


if __name__ == "__main__":
    unittest.main()
