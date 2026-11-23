import importlib.util
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).parent
ROOT = HERE.parents[1]
PLUGIN = ROOT / "plugins" / "finance-tools" / "plugin.py"


class PortfolioPolicyBoundTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("portfolio_policy_bound_plugin", PLUGIN)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.temp = tempfile.TemporaryDirectory(prefix="portfolio-policy-bound-")
        self.finance = module.FinanceToolsPlugin()
        self.finance.initialize({"stateDbPath": str(Path(self.temp.name) / "ledger.db"),
                                 "evaluationFixture": True})

    def tearDown(self):
        self.temp.cleanup()

    def bound(self, known, remainder, overlap, limit=50):
        return self.finance.execute("portfolio_policy_bound", {
            "known_holdings_percent": known,
            "unknown_remainder_percent": remainder,
            "unknown_may_overlap_known": overlap,
            "limit_percent": limit,
        })

    def test_distinct_residual_proves_no_breach_without_exact_risk(self):
        result = self.bound({"COIN": 40, "HOOD": 30}, 30, False)
        self.assertTrue(result["ok"])
        self.assertEqual("no_breach_proven", result["data"]["policy_status"])
        self.assertEqual({"min_percent": 40, "max_percent": 40},
                         result["data"]["known_issuer_bounds_percent"]["COIN"])
        self.assertEqual(30, result["data"]["unidentified_new_issuer_max_percent"])
        self.assertFalse(result["data"]["exact_hhi_available"])
        self.assertFalse(result["data"]["portfolio_risk_calculated"])
        self.assertEqual(0.7, result["quality"]["completeness"])

    def test_possible_overlap_is_indeterminate(self):
        result = self.bound({"COIN": 40, "HOOD": 30}, 30, True)
        self.assertEqual("indeterminate", result["data"]["policy_status"])
        self.assertEqual({"min_percent": 40, "max_percent": 70},
                         result["data"]["known_issuer_bounds_percent"]["COIN"])
        self.assertEqual({"min_percent": 30, "max_percent": 60},
                         result["data"]["known_issuer_bounds_percent"]["HOOD"])

    def test_known_breach_remains_proven_and_strict_boundary(self):
        self.assertEqual("breach_proven",
                         self.bound({"COIN": 55, "HOOD": 25}, 20, True)["data"]["policy_status"])
        self.assertEqual("no_breach_proven",
                         self.bound({"COIN": 50, "HOOD": 30}, 20, False)["data"]["policy_status"])

    def test_rejects_missing_semantics_and_invalid_denominator(self):
        missing = self.finance.execute("portfolio_policy_bound", {
            "known_holdings_percent": {"COIN": 40}, "unknown_remainder_percent": 60})
        self.assertFalse(missing["ok"])
        self.assertEqual("invalid_input", missing["errors"][0]["code"])
        invalid = self.bound({"COIN": 40, "HOOD": 30}, 20, False)
        self.assertFalse(invalid["ok"])
        self.assertEqual("invalid_input", invalid["errors"][0]["code"])
        collision = self.bound({"COIN": 40, "coin": 30}, 30, False)
        self.assertFalse(collision["ok"])

    def test_existing_exact_risk_guard_is_unchanged(self):
        refused = self.finance.execute("portfolio_risk", {
            "holdings": {"COIN": 40, "HOOD": 30}, "holdings_complete": False,
            "weight_unit": "percent", "view": "concentration"})
        self.assertFalse(refused["ok"])
        self.assertEqual("portfolio_incomplete", refused["errors"][0]["code"])


if __name__ == "__main__":
    unittest.main()
