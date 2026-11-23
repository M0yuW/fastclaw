"""Ameriprise GAAP/adjusted divergence and AWM flow source checks."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "amp_reference_source_row_audit_v1.json"


class AMPSourceRowAuditTests(unittest.TestCase):
    def test_twenty_two_rows_verify_without_quality_claim(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "AMP")
        self.assertEqual(result["checked_rows"], 22)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_awm_segment_and_wrap_bridges(self):
        rows = {r["id"]: r for r in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            val = lambda key: Decimal(rows[key][field])
            self.assertEqual(val("net_revenues"),
                             val("total_revenues") - val("banking_deposit_interest_expense"))
            self.assertEqual(val("pretax_income"),
                             val("net_revenues") - val("total_expenses"))
            self.assertEqual(val("gaap_net_income"),
                             val("pretax_income") - val("income_tax_provision"))
            self.assertEqual(val("awm_segment_pretax_adjusted_earnings"),
                             val("awm_segment_adjusted_net_revenues")
                             - val("awm_segment_adjusted_expenses"))
            self.assertEqual(val("wrap_ending_assets"),
                             val("wrap_beginning_assets") + val("wrap_net_flows")
                             + val("wrap_market_other"))
        self.assertEqual(Decimal(rows["wrap_beginning_assets"]["event_value"]),
                         Decimal(rows["wrap_ending_assets"]["baseline_value"]))
        self.assertLess(Decimal(rows["gaap_net_income"]["delta_value"]), 0)
        self.assertGreater(Decimal(rows["adjusted_operating_earnings"]["delta_value"]), 0)

    def test_prior_year_column_and_wrong_wrap_row_rejected(self):
        packet = json.loads(PACKET.read_text())
        by_id = {r["id"]: r for r in packet["rows"]}
        by_id["gaap_net_income"]["numeric_value_index"] = 1
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "prior-year.json"
            changed.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(changed)
        packet = json.loads(PACKET.read_text())
        by_id = {r["id"]: r for r in packet["rows"]}
        by_id["wrap_net_flows"]["row_index"] = 6
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "total-instead-of-wrap-flow.json"
            changed.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(changed)


if __name__ == "__main__":
    unittest.main()
