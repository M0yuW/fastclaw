"""Raymond James GAAP, client assets/flows, and bank-credit source tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "rjf_reference_source_row_audit_v1.json"


class RJFSourceRowAuditTests(unittest.TestCase):
    def test_twenty_four_rows_verify_against_frozen_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "RJF")
        self.assertEqual(result["checked_rows"], 24)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_bridges_and_client_stock_flow_distinction(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gaap_net_revenues"),
                             value("gaap_total_revenues")
                             + value("gaap_interest_expense_signed"))
            self.assertEqual(value("gaap_pretax_income"),
                             value("gaap_net_revenues")
                             - value("gaap_total_noninterest_expense"))
            self.assertEqual(value("gaap_net_income"),
                             value("gaap_pretax_income")
                             - value("gaap_income_tax_provision"))
            self.assertEqual(value("gaap_net_income_common"),
                             value("gaap_net_income")
                             - value("gaap_preferred_dividends"))
        self.assertEqual(rows["wealth_client_assets_under_administration"]["unit"],
                         "USD_billion")
        self.assertEqual(rows["wealth_domestic_pcg_net_new_assets"]["unit"],
                         "USD_million")
        self.assertNotEqual(Decimal(rows["wealth_client_assets_under_administration"]["delta_value"])
                            * 1000,
                            Decimal(rows["wealth_domestic_pcg_net_new_assets"]["event_value"]))
        self.assertLess(Decimal(rows["bank_nonperforming_assets"]["delta_value"]), 0)
        self.assertGreater(Decimal(rows["bank_criticized_loans"]["delta_value"]), 0)
        self.assertGreater(Decimal(rows["bank_quarter_net_chargeoffs"]["delta_value"]), 0)
        self.assertLess(Decimal(rows["bank_loan_allowance"]["delta_value"]), 0)

    def test_prior_year_column_cannot_replace_current_quarter(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["numeric_value_index"] = 1
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-rjf-year.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)

    def test_net_new_asset_ytd_column_cannot_replace_quarter(self):
        packet = json.loads(PACKET.read_text())
        row = next(row for row in packet["rows"] if row["id"] == "wealth_domestic_pcg_net_new_assets")
        row["numeric_value_index_by_period"] = {"CY2025_Q2": 0, "CY2025_Q3": 3}
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-rjf-ytd.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
