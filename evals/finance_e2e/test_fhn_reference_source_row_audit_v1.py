"""First Horizon rounded quarterly income and as-of credit-quality source tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "fhn_reference_source_row_audit_v1.json"


class FHNSourceRowAuditTests(unittest.TestCase):
    def test_twenty_one_rows_verify_against_both_frozen_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "FHN")
        self.assertEqual(result["checked_rows"], 21)
        self.assertEqual(result["event_only_checked_rows"], 0)
        self.assertIsNone(result["quality_pass"])

    def test_rounded_income_and_credit_bridges(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            close = lambda actual, expected: self.assertLessEqual(abs(actual - expected), Decimal(1))
            self.assertEqual(value("gaap_total_revenue"), value("gaap_net_interest_income")
                             + value("gaap_total_noninterest_income"))
            close(value("gaap_pretax_income"), value("gaap_total_revenue")
                  - value("gaap_total_noninterest_expense")
                  - value("gaap_credit_loss_provision"))
            close(value("gaap_net_income"), value("gaap_pretax_income")
                  - value("gaap_income_tax_provision"))
            self.assertEqual(value("gaap_controlling_interest_income"),
                             value("gaap_net_income") - value("gaap_noncontrolling_interest_income"))
            close(value("gaap_net_income_common"),
                  value("gaap_controlling_interest_income") - value("gaap_preferred_dividends"))
            close(value("npl_total"), sum(value(key) for key in (
                "npl_commercial_industrial", "npl_commercial_real_estate",
                "npl_consumer_real_estate", "npl_credit_card_other")))
        self.assertLess(Decimal(rows["gaap_credit_loss_provision"]["event_value"]), 0)
        self.assertGreater(Decimal(rows["npl_total"]["delta_value"]), 0)
        self.assertGreater(Decimal(rows["npl_commercial_real_estate"]["delta_value"]), 0)
        self.assertEqual(rows["npl_total"]["basis"],
                         "company_reported_point_in_time_nonperforming_loans")

    def test_prior_quarter_numeric_column_is_rejected(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["numeric_value_index_by_period"] = {
            "CY2025_Q2": 0, "CY2025_Q3": 1}
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-fhn-column.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)

    def test_income_header_cannot_authorize_point_in_time_row(self):
        packet = json.loads(PACKET.read_text())
        del packet["rows"][-2]["period_headers_by_period"]
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-fhn-as-of-header.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "period header absent"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
