"""Western Alliance GAAP and mixed credit-quality source checks."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "wal_reference_source_row_audit_v1.json"


class WALSourceRowAuditTests(unittest.TestCase):
    def test_twenty_six_comparable_and_two_unmatched_rows_verify(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "WAL")
        self.assertEqual(result["checked_rows"], 26)
        self.assertEqual(result["baseline_only_checked_rows"], 1)
        self.assertEqual(result["event_only_checked_rows"], 1)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_bridges_and_distinct_credit_signals(self):
        rows = {r["id"]: r for r in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            val = lambda key: Decimal(rows[key][field])
            self.assertEqual(val("net_interest_income"),
                             val("interest_income") - val("interest_expense"))
            self.assertEqual(val("net_interest_after_provision"),
                             val("net_interest_income") - val("credit_loss_provision"))
            self.assertEqual(val("pretax_income"),
                             val("net_interest_after_provision")
                             + val("noninterest_income") - val("noninterest_expense"))
            self.assertEqual(val("consolidated_net_income"),
                             val("pretax_income") - val("income_tax_expense"))
            self.assertEqual(val("parent_net_income"),
                             val("consolidated_net_income") - val("nci_income"))
            self.assertEqual(val("common_net_income"),
                             val("parent_net_income") - val("preferred_dividends"))
        delta = lambda key: Decimal(rows[key]["delta_value"])
        self.assertGreater(delta("nonaccrual_loans"), 0)
        self.assertLess(delta("repossessed_assets"), 0)
        self.assertLess(delta("classified_assets"), 0)
        self.assertGreater(delta("past_due_30_89_accruing"), 0)
        self.assertGreater(delta("credit_loss_provision"), 0)

    def test_wrong_year_column_and_wrong_credit_row_rejected(self):
        packet = json.loads(PACKET.read_text())
        by_id = {r["id"]: r for r in packet["rows"]}
        by_id["common_net_income"]["numeric_value_index"] = 1
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "prior-year-common-income.json"
            changed.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(changed)
        packet = json.loads(PACKET.read_text())
        by_id = {r["id"]: r for r in packet["rows"]}
        by_id["nonaccrual_loans"]["row_index"] = 45
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "repossessed-instead-of-nonaccrual.json"
            changed.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(changed)

    def test_changed_scope_rows_cannot_be_silently_mutated(self):
        packet = json.loads(PACKET.read_text())
        packet["baseline_only_rows"][0]["baseline_value"] = "0"
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "bad-q2-loan-sale.json"
            changed.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(changed)
        packet = json.loads(PACKET.read_text())
        packet["event_only_rows"][0]["event_value"] = "0"
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "bad-q3-mortgage-sale.json"
            changed.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(changed)


if __name__ == "__main__":
    unittest.main()
