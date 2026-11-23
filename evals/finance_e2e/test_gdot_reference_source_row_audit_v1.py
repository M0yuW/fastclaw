"""Green Dot quarterly GAAP, segment, and event-only source-audit tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "gdot_reference_source_row_audit_v1.json"


class GDOTSourceRowAuditTests(unittest.TestCase):
    def test_twenty_one_comparable_and_one_event_only_row_verify(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "GDOT")
        self.assertEqual(result["checked_rows"], 21)
        self.assertEqual(result["event_only_checked_rows"], 1)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_and_segment_bridges_preserve_opposing_signals(self):
        packet = json.loads(PACKET.read_text())
        rows = {row["id"]: row for row in packet["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gaap_total_operating_revenue"),
                             sum(value(key) for key in
                                 ("gaap_card_revenue_fees", "gaap_cash_processing_revenue",
                                  "gaap_interchange_revenue", "gaap_interest_income_net")))
            self.assertEqual(value("gaap_operating_income_loss"),
                             value("gaap_total_operating_revenue")
                             - value("gaap_total_operating_expenses"))
            self.assertEqual(value("gaap_pretax_loss"),
                             value("gaap_operating_income_loss")
                             - value("gaap_interest_expense_net")
                             + value("gaap_other_expense_net"))
            self.assertEqual(value("gaap_net_loss"),
                             value("gaap_pretax_loss")
                             - value("gaap_income_tax_benefit_expense"))
            self.assertEqual(value("segment_total_revenues"),
                             sum(value(key) for key in
                                 ("segment_b2b_services_revenue", "segment_consumer_services_revenue",
                                  "segment_money_movement_revenue", "segment_corporate_other_revenue")))
            self.assertEqual(value("gaap_total_operating_revenue"),
                             value("segment_total_revenues")
                             + value("segment_reconciliation_commissions")
                             + value("segment_reconciliation_other_income"))
        self.assertLess(Decimal(rows["gaap_operating_income_loss"]["delta_value"]), 0)
        self.assertGreater(Decimal(rows["gaap_net_loss"]["delta_value"]), 0)

    def test_year_to_date_column_cannot_replace_quarter(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["numeric_value_index"] = 2
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-gdot-period.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
