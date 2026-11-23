"""F.N.B. quarter-flow and point-in-time credit-quality source tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "fnb_reference_source_row_audit_v1.json"


class FNBSourceRowAuditTests(unittest.TestCase):
    def test_twenty_three_rows_verify_against_frozen_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "FNB")
        self.assertEqual(result["checked_rows"], 23)
        self.assertEqual(result["event_only_checked_rows"], 0)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_and_credit_quality_bridges(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gaap_net_interest_income"),
                             value("gaap_total_interest_income")
                             - value("gaap_total_interest_expense"))
            self.assertEqual(value("gaap_net_interest_after_provision"),
                             value("gaap_net_interest_income")
                             - value("gaap_credit_loss_provision"))
            self.assertEqual(value("gaap_pretax_income"),
                             value("gaap_net_interest_after_provision")
                             + value("gaap_total_noninterest_income")
                             - value("gaap_total_noninterest_expense"))
            self.assertEqual(value("gaap_net_income"),
                             value("gaap_pretax_income") - value("gaap_tax_expense"))
            self.assertEqual(value("gaap_net_income_common"), value("gaap_net_income"))
            self.assertEqual(value("credit_nonperforming_assets"),
                             value("credit_nonperforming_loans")
                             + value("credit_other_real_estate_owned"))
        self.assertLess(Decimal(rows["gaap_credit_loss_provision"]["delta_value"]), 0)
        self.assertGreater(Decimal(rows["credit_nonperforming_loans"]["delta_value"]), 0)
        self.assertGreater(Decimal(rows["credit_past_due_and_nonaccrual_loans"]["delta_value"]), 0)
        self.assertEqual(rows["credit_nonperforming_loans"]["basis"],
                         "company_reported_point_in_time_asset_quality")

    def test_prior_quarter_numeric_column_is_rejected(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["numeric_value_index_by_period"] = {
            "CY2025_Q2": 0, "CY2025_Q3": 1}
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-fnb-column.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)

    def test_income_header_cannot_authorize_credit_row(self):
        packet = json.loads(PACKET.read_text())
        del packet["rows"][15]["period_headers_by_period"]
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-fnb-credit-header.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "period header absent"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
