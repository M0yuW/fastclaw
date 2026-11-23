"""ALL quarter, scope, and GAAP result source audit regression tests."""

import json
import unittest
from decimal import Decimal

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "all_reference_source_row_audit_v1.json"


class ALLSourceRowAuditTests(unittest.TestCase):
    def test_fifteen_selected_rows_verify_against_frozen_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "ALL")
        self.assertEqual(result["checked_rows"], 15)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_income_bridges_and_ratio_scope(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            number = lambda key: Decimal(rows[key][field])
            self.assertEqual(number("gaap_pretax_income"),
                             number("gaap_total_revenues")
                             - number("gaap_total_costs_expenses")
                             + number("gaap_gain_disposition_operations"))
            self.assertEqual(number("gaap_net_income"),
                             number("gaap_pretax_income")
                             - number("gaap_income_tax_expense"))
        self.assertEqual(rows["non_gaap_underlying_combined_ratio"]["basis"],
                         "company_defined_underlying_non_gaap")
        self.assertLess(number("reported_catastrophe_losses"), 0)


if __name__ == "__main__":
    unittest.main()
