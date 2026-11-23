"""UMB Financial quarterly GAAP, adjusted earnings, and credit-source checks."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "umbf_reference_source_row_audit_v1.json"


class UMBFSourceRowAuditTests(unittest.TestCase):
    def test_twenty_one_source_rows_verify_without_quality_claim(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "UMBF")
        self.assertEqual(result["checked_rows"], 21)
        self.assertEqual(result["event_only_checked_rows"], 0)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_and_adjusted_bridges_both_quarters_and_delta(self):
        rows = {r["id"]: r for r in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("net_interest_income"),
                             value("interest_income") - value("interest_expense"))
            self.assertEqual(value("net_interest_after_provision"),
                             value("net_interest_income") - value("provision"))
            self.assertEqual(value("pretax_income"),
                             value("net_interest_after_provision")
                             + value("noninterest_income") - value("noninterest_expense"))
            self.assertEqual(value("net_income"),
                             value("pretax_income") - value("income_tax_expense"))
            self.assertEqual(value("common_net_income"),
                             value("net_income") - value("preferred_dividends"))
            self.assertEqual(value("operating_common_net_income"),
                             value("common_net_income") + value("net_adjustments_after_tax"))

    def test_first_quarter_column_and_credit_row_cannot_be_substituted(self):
        packet = json.loads(PACKET.read_text())
        by_id = {r["id"]: r for r in packet["rows"]}
        by_id["net_income"]["numeric_value_index"] = 1
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "wrong-income-column.json"
            changed.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(changed)
        packet = json.loads(PACKET.read_text())
        by_id = {r["id"]: r for r in packet["rows"]}
        by_id["nonaccrual_restructured"]["row_index"] = 7
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "wrong-credit-row.json"
            changed.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(changed)


if __name__ == "__main__":
    unittest.main()
