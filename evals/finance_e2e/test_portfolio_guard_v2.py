import importlib.util
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).parent
ROOT = HERE.parents[1]
PLUGIN = ROOT / "plugins" / "finance-tools" / "plugin.py"
FIXTURES = HERE / "workflow_fixtures_v2"


class PortfolioGuardV2Test(unittest.TestCase):
    def test_real_fixture_rejects_partial_and_preserves_boundaries(self):
        spec = importlib.util.spec_from_file_location("portfolio_guard_plugin", PLUGIN)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="portfolio-guard-v2-") as temp_root:
            finance = module.FinanceToolsPlugin()
            finance.initialize({"finskillsPath": str(FIXTURES),
                                "stateDbPath": str(Path(temp_root) / "ledger.db"),
                                "evaluationFixture": True})
            partial = finance.execute("portfolio_risk", {
                "holdings": {"FICA": 45, "FICB": 30}, "view": "concentration"})
            self.assertFalse(partial["ok"])
            self.assertEqual("portfolio_incomplete", partial["errors"][0]["code"])
            for largest, other, expected_breach in ((45, (30, 25), False),
                                                     (50, (30, 20), False),
                                                     (65, (20, 15), True)):
                result = finance.execute("portfolio_risk", {
                    "holdings": {"FICA": largest, "FICB": other[0], "FICC": other[1]},
                    "view": "concentration"})
                self.assertTrue(result["ok"])
                self.assertEqual(float(largest), result["data"]["largest_weight_pct"])
                self.assertEqual(expected_breach, result["data"]["limit_breached"])


if __name__ == "__main__":
    unittest.main()
