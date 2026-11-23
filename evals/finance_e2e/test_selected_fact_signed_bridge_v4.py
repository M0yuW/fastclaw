import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from selected_fact_delta_guard_v1 import derive  # noqa: E402
from selected_fact_signed_bridge_v4 import signed_bridge  # noqa: E402


HERE = Path(__file__).parent
ALLY_COMPONENTS = {
    "gaap_net_financing_revenue": 1,
    "gaap_other_revenue": 1,
    "gaap_provision_for_credit_losses": -1,
    "gaap_noninterest_expense": -1,
}


class SignedBridgeTests(unittest.TestCase):
    def bundle(self):
        packet = json.loads((HERE / "ally_holdout_fact_packet_v2.json").read_text())
        return derive(packet)

    def test_ally_source_row_formula_reconciles_both_quarters(self):
        result = signed_bridge(self.bundle(), "gaap_pre_tax_income", ALLY_COMPONENTS)
        self.assertTrue(result["fully_reconciles_both_periods"])
        self.assertEqual(result["delta_residual"], "0")
        self.assertEqual(result["baseline_residual"], "0")
        self.assertEqual(result["event_residual"], "0")

    def test_missing_component_exposes_residual(self):
        components = dict(ALLY_COMPONENTS)
        del components["gaap_noninterest_expense"]
        result = signed_bridge(self.bundle(), "gaap_pre_tax_income", components)
        self.assertFalse(result["fully_reconciles_both_periods"])
        self.assertEqual(result["delta_residual"], "22")

    def test_bad_sign_and_unit_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid"):
            signed_bridge(self.bundle(), "gaap_pre_tax_income",
                          {"gaap_net_financing_revenue": 2})
        with self.assertRaisesRegex(ValueError, "currency"):
            signed_bridge(self.bundle(), "gaap_pre_tax_income", {"gaap_eps": 1})


if __name__ == "__main__":
    unittest.main()
