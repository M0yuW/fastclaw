import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_postcorrection_signed_bridge_fixture_v4 as v4  # noqa: E402
from selected_fact_delta_guard_v1 import derive  # noqa: E402


class BridgeFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = v4.prepare()

    def test_all_source_audits_and_bridges_pass_without_model(self):
        self.assertEqual(self.result["source_cases"], 20)
        self.assertEqual(self.result["bridge_cases"], 11)
        self.assertEqual(self.result["checked_bridges"], 22)
        self.assertEqual(self.result["model_observations"], 0)

    def test_ally_prompt_shows_exact_signed_bridge_and_boundary(self):
        ally = next(item for item in self.result["fixtures"]
                    if item["runtime_symbol"] == "ALLY")
        context = ally["numeric_context"]
        self.assertIn("+86 −31 +22 = 77 USD_million", context)
        self.assertIn("baseline, event, and change residuals are all 0", context)
        self.assertIn("not an economic/causal driver", context)
        self.assertNotIn("precommitted_interpretation_checks", context)

    def test_bad_formula_refuses_to_render(self):
        packet = json.loads(v4.v2.READY["ALLY"][1].read_text())
        with self.assertRaisesRegex(ValueError, "does not fully reconcile"):
            v4.render_bridge("wrong", derive(packet), "gaap_pre_tax_income",
                             {"gaap_total_net_revenue": 1,
                              "gaap_provision_for_credit_losses": -1})


if __name__ == "__main__":
    unittest.main()
