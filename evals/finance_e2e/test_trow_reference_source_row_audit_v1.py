"""T. Rowe Price GAAP and AUM scope-adjustment source checks."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "trow_reference_source_row_audit_v1.json"


class TROWSourceRowAuditTests(unittest.TestCase):
    def test_twenty_one_comparable_and_one_q3_only_row(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "TROW")
        self.assertEqual(result["checked_rows"], 21)
        self.assertEqual(result["event_only_checked_rows"], 1)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_and_aum_bridges_separate_flow_from_scope_addition(self):
        packet = json.loads(PACKET.read_text())
        rows = {r["id"]: r for r in packet["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            val = lambda key: Decimal(rows[key][field])
            self.assertEqual(val("net_revenues"),
                             val("investment_advisory_fees")
                             + val("performance_advisory_fees")
                             + val("capital_allocation_income")
                             + val("administrative_other_fees"))
            self.assertEqual(val("operating_income"),
                             val("net_revenues") - val("operating_expenses"))
            self.assertEqual(val("pretax_income"),
                             val("operating_income") + val("nonoperating_income"))
            self.assertEqual(val("consolidated_net_income"),
                             val("pretax_income") - val("income_tax_provision"))
            self.assertEqual(val("parent_net_income"),
                             val("consolidated_net_income") - val("redeemable_nci_income"))
            self.assertEqual(val("ending_aum"), val("aum_end_bridge"))
        q2 = lambda key: Decimal(rows[key]["baseline_value"])
        q3 = lambda key: Decimal(rows[key]["event_value"])
        delivery = Decimal(packet["event_only_rows"][0]["event_value"])
        self.assertEqual(q2("aum_end_bridge"),
                         q2("aum_start") + q2("aum_net_cash_flows")
                         + q2("aum_market_appreciation"))
        self.assertEqual(q3("aum_end_bridge"),
                         q3("aum_start") + delivery + q3("aum_net_cash_flows")
                         + q3("aum_market_appreciation"))
        self.assertEqual(q3("aum_start"), q2("aum_end_bridge"))

    def test_model_delivery_cannot_be_turned_into_flows_or_wrong_column(self):
        packet = json.loads(PACKET.read_text())
        packet["event_only_rows"][0]["event_value"] = "0"
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "wrong-delivery.json"
            changed.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(changed)
        packet = json.loads(PACKET.read_text())
        by_id = {r["id"]: r for r in packet["rows"]}
        by_id["aum_net_cash_flows"]["numeric_value_index"] = 0
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "equity-instead-of-total.json"
            changed.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(changed)


if __name__ == "__main__":
    unittest.main()
