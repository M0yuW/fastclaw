"""Lincoln GAAP/non-GAAP reconciliation and mixed-column source tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "lnc_reference_source_row_audit_v1.json"


class LNCSourceRowAuditTests(unittest.TestCase):
    def test_sixteen_rows_verify_against_frozen_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "LNC")
        self.assertEqual(result["checked_rows"], 16)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_adjusted_and_common_shareholder_bridges(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        components = (
            "recon_annuity_product_features", "recon_life_product_features",
            "recon_credit_loss_adjustments", "recon_investment_gains_losses",
            "recon_fair_value_reinsurance_related", "recon_other_items",
            "recon_tax_on_adjustments")
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("recon_total_adjustments"),
                             sum(value(key) for key in components))
            self.assertEqual(value("adjusted_income_operations"),
                             value("gaap_net_income") - value("recon_total_adjustments"))
            self.assertEqual(value("gaap_common_diluted_net_income"),
                             value("gaap_net_income") + value("gaap_preferred_dividends_signed"))
            self.assertEqual(value("adjusted_common_income_operations"),
                             value("adjusted_income_operations")
                             + value("gaap_preferred_dividends_signed"))
        self.assertGreater(Decimal(rows["gaap_revenues"]["delta_value"]), 0)
        self.assertLess(Decimal(rows["gaap_net_income"]["delta_value"]), 0)
        self.assertLess(Decimal(rows["adjusted_income_operations"]["delta_value"]), 0)
        self.assertEqual(rows["adjusted_income_operations"]["basis"],
                         "company_defined_non_GAAP_quarter")

    def test_headline_prior_year_column_is_rejected(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["numeric_value_index"] = 0
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-lnc-headline-column.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)

    def test_appendix_prior_year_column_is_rejected(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][6]["numeric_value_index"] = 1
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-lnc-appendix-column.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
