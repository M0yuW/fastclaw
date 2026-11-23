"""BILL quarterly transcription, accounting bridges, and source conflict."""

import json
import unittest

from run_thesis_event_panel import HERE, ROOT
from verify_reference_source_row_packet_v1 import cells_for, number_after_label, verify


PACKET = HERE / "bill_reference_source_row_audit_v1.json"


class BILLSourceRowAuditTests(unittest.TestCase):
    def test_nine_selected_rows_verify(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "BILL")
        self.assertEqual(result["checked_rows"], 9)
        self.assertIsNone(result["quality_pass"])

    def test_selected_statement_bridges(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for key in ("baseline_value", "event_value", "delta_value"):
            value = lambda name: int(rows[name][key])
            self.assertEqual(value("gaap_total_revenue"),
                             value("gaap_subscription_transaction_fees")
                             + value("gaap_interest_customer_funds"))
            self.assertEqual(value("gaap_gross_profit"),
                             value("gaap_total_revenue")
                             - value("gaap_total_cost_revenue"))
            self.assertEqual(value("gaap_operating_loss"),
                             value("gaap_gross_profit")
                             - value("gaap_total_operating_expenses"))

    def test_june_internal_net_income_discrepancy_is_explicit(self):
        packet = json.loads(PACKET.read_text())
        source_pairs = json.loads((HERE / packet["source_pair_selection"]).read_text())
        pair = next(item for item in source_pairs["pairs"] if item["symbol"] == "BILL")
        path = ROOT / pair["periods"]["CY2025_Q2"]["local_path"]
        conflict = packet["source_internal_discrepancy"]
        statement = cells_for(path, conflict["statement_of_operations_table_index"],
                              conflict["statement_of_operations_row_index"])[1]
        cash_flow = cells_for(path, conflict["cash_flow_table_index"],
                              conflict["cash_flow_row_index"])[1]
        statement_value = number_after_label(statement, conflict["metric"], 0)
        cash_flow_value = number_after_label(cash_flow, conflict["metric"], 0)
        self.assertEqual(str(statement_value), conflict["statement_of_operations_value"])
        self.assertEqual(str(cash_flow_value), conflict["cash_flow_value"])
        self.assertEqual(abs(statement_value - cash_flow_value), 2)


if __name__ == "__main__":
    unittest.main()
