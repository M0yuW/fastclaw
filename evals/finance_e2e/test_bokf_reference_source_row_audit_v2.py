"""Unified HTML-locator audit for BOKF without changing the v1 packet."""

import json
import unittest
from decimal import Decimal

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "bokf_reference_source_row_audit_v2.json"


class BOKFUnifiedSourceRowAuditTests(unittest.TestCase):
    def test_six_rows_verify_against_both_frozen_sec_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "BOKF")
        self.assertEqual(result["checked_rows"], 6)
        self.assertIsNone(result["quality_pass"])

    def test_tax_equivalent_interest_bridge_reconciles(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            number = lambda key: Decimal(rows[key][field])
            self.assertEqual(number("reported_net_interest_income"),
                             number("reported_total_interest_revenue")
                             - number("reported_total_interest_expense")
                             - number("reported_tax_equivalent_adjustment"))


if __name__ == "__main__":
    unittest.main()
