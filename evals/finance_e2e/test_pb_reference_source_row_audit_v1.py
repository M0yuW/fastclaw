"""Prosperity Bancshares quarterly earnings versus mixed-basis credit tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE, ROOT
from verify_reference_source_row_packet_v1 import cells_for, verify


PACKET = HERE / "pb_reference_source_row_audit_v1.json"


class PBSourceRowAuditTests(unittest.TestCase):
    def test_twenty_five_rows_verify_against_frozen_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "PB")
        self.assertEqual(result["checked_rows"], 25)
        self.assertIsNone(result["quality_pass"])

    def test_income_and_nonperforming_asset_bridges(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gaap_net_interest_income"),
                             value("gaap_total_interest_income")
                             - value("gaap_total_interest_expense"))
            self.assertEqual(value("gaap_pretax_income"),
                             value("gaap_net_interest_income")
                             + value("gaap_total_noninterest_income")
                             - value("gaap_total_noninterest_expense"))
            self.assertEqual(value("gaap_net_income_common"),
                             value("gaap_pretax_income")
                             - value("gaap_income_tax_provision"))
            self.assertEqual(value("credit_nonperforming_loans"),
                             value("credit_nonaccrual_loans")
                             + value("credit_accruing_90_plus_days_past_due"))
            self.assertEqual(value("credit_nonperforming_assets"),
                             value("credit_nonperforming_loans")
                             + value("credit_repossessed_assets")
                             + value("credit_other_real_estate"))
        self.assertGreater(Decimal(rows["gaap_net_income_common"]["delta_value"]), 0)
        self.assertGreater(Decimal(rows["credit_nonperforming_assets"]["delta_value"]), 0)
        self.assertGreater(Decimal(rows["credit_quarter_net_chargeoffs"]["delta_value"]), 0)
        self.assertLess(Decimal(rows["credit_allowance_for_loan_losses"]["delta_value"]), 0)
        self.assertEqual(rows["credit_quarter_net_chargeoffs"]["basis"],
                         "company_reported_quarter_net_chargeoffs_in_Net_chargeoffs_section")

    def test_chargeoff_total_is_within_its_section_not_npa_total(self):
        selection = json.loads((HERE / "results/2026-10-25-reference-source-pair-selection-v1/SOURCE-PAIRS.json").read_text())
        pair = next(item for item in selection["pairs"] if item["symbol"] == "PB")
        for period, table_index in (("CY2025_Q2", 15), ("CY2025_Q3", 14)):
            path = ROOT / pair["periods"][period]["local_path"]
            _, section = cells_for(path, table_index, 22)
            _, total = cells_for(path, table_index, 29)
            self.assertIn("Net charge-offs (recoveries):", section)
            self.assertIn("Total", total)

    def test_ytd_column_cannot_replace_quarter(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["numeric_value_index_by_period"] = {
            "CY2025_Q2": 0, "CY2025_Q3": 5}
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-pb-ytd.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)

    def test_wrong_asset_quality_period_header_is_rejected(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][11]["period_headers_by_period"]["CY2025_Q3"] = ["Dec 31, 2025"]
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-pb-period.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "period header absent"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
