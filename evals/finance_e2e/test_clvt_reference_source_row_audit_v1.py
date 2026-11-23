"""Clarivate quarter-column, mixed-result and cash-flow source checks."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "clvt_reference_source_row_audit_v1.json"


class CLVTSourceRowAuditTests(unittest.TestCase):
    def test_twenty_four_rows_verify_without_model_claim(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "CLVT")
        self.assertEqual(result["checked_rows"], 24)
        self.assertIsNone(result["quality_pass"])

    def test_revenue_expense_net_income_and_cash_bridges(self):
        rows = {r["id"]: r for r in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            val = lambda name: Decimal(rows[name][field])
            self.assertEqual(val("recurring_revenues"),
                             val("subscription_revenue") + val("reoccurring_revenue"))
            self.assertEqual(val("revenue"),
                             val("recurring_revenues") + val("transactional_revenue"))
            self.assertEqual(val("revenue"),
                             val("academia_government_revenue")
                             + val("intellectual_property_revenue")
                             + val("life_sciences_revenue"))
            self.assertEqual(val("operating_expenses"),
                             val("cost_of_revenues") + val("sga")
                             + val("depreciation_amortization")
                             + val("restructuring_impairments")
                             + val("other_operating_expense"))
            self.assertEqual(val("operating_income"),
                             val("revenue") - val("operating_expenses"))
            self.assertEqual(val("pretax_income"),
                             val("operating_income") - val("interest_expense"))
            self.assertEqual(val("net_income"),
                             val("pretax_income") - val("income_tax_provision"))
            self.assertEqual(val("free_cash_flow"),
                             val("operating_cash_flow") + val("capital_expenditures"))

    def test_adjacent_prior_year_column_and_wrong_segment_header_rejected(self):
        packet = json.loads(PACKET.read_text())
        by_id = {r["id"]: r for r in packet["rows"]}
        by_id["revenue"]["numeric_value_index"] = 1
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "prior-year.json"
            changed.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(changed)
        packet = json.loads(PACKET.read_text())
        by_id = {r["id"]: r for r in packet["rows"]}
        by_id["academia_government_revenue"]["period_headers_by_period"] = {
            "CY2025_Q2": ["Nine Months Ended September 30,"],
            "CY2025_Q3": ["Nine Months Ended September 30,"]
        }
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "wrong-segment-header.json"
            changed.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(changed)


if __name__ == "__main__":
    unittest.main()
