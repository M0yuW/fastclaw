"""EWBC quarterly earnings and point-in-time criticized-loan audit tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "ewbc_reference_source_row_audit_v1.json"


class EWBCSourceRowAuditTests(unittest.TestCase):
    def test_seventeen_selected_rows_verify_against_frozen_sources(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "EWBC")
        self.assertEqual(result["checked_rows"], 17)
        self.assertIsNone(result["quality_pass"])

    def test_income_and_criticized_loan_bridges(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gaap_net_interest_income_before_provision"),
                             value("gaap_interest_dividend_income")
                             - value("gaap_interest_expense"))
            self.assertEqual(value("gaap_net_interest_income_after_provision"),
                             value("gaap_net_interest_income_before_provision")
                             - value("gaap_credit_loss_provision"))
            self.assertEqual(value("gaap_total_noninterest_expense"),
                             value("gaap_total_operating_noninterest_expense")
                             + value("gaap_tax_credit_cra_amortization"))
            self.assertEqual(value("gaap_pretax_income"),
                             value("gaap_net_interest_income_after_provision")
                             + value("gaap_total_noninterest_income")
                             - value("gaap_total_noninterest_expense"))
            self.assertEqual(value("gaap_net_income"),
                             value("gaap_pretax_income") - value("gaap_income_tax_expense"))
            self.assertEqual(value("credit_total_criticized_loans"),
                             value("credit_special_mention_loans")
                             + value("credit_classified_loans"))
        self.assertLess(value("gaap_credit_loss_provision"), 0)
        self.assertGreater(value("credit_classified_loans"), 0)

    def test_wrong_credit_as_of_date_is_rejected(self):
        packet = json.loads(PACKET.read_text())
        credit = packet["rows"][-1]
        credit["period_headers_by_period"]["CY2025_Q3"] = ["December 31, 2025"]
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-ewbc-date.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "period header absent"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
