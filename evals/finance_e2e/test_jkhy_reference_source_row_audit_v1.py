"""JKHY full-earnings-exhibit period and accounting-row checks."""

import json
import tempfile
import unittest
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "jkhy_reference_source_row_audit_v1.json"


class JKHYSourceRowAuditTests(unittest.TestCase):
    def test_ten_gaap_quarter_rows_verify_across_different_table_indexes(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "JKHY")
        self.assertEqual(result["checked_rows"], 10)
        self.assertIsNone(result["quality_pass"])

    def test_statement_bridges_reconcile_for_both_quarters_and_difference(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            number = lambda key: int(rows[key][field])
            self.assertEqual(number("gaap_total_expenses"), sum(number(key) for key in (
                "gaap_cost_of_revenue", "gaap_research_development",
                "gaap_selling_general_admin")))
            self.assertEqual(number("gaap_operating_income"),
                             number("gaap_revenue") - number("gaap_total_expenses"))
            self.assertEqual(number("gaap_net_income"),
                             number("gaap_income_before_taxes")
                             - number("gaap_income_tax_provision"))

    def test_wrong_event_table_locator_is_rejected(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["table_index_by_period"]["CY2025_Q3"] = 19
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "wrong-event-table.json"
            path.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                verify(path)


if __name__ == "__main__":
    unittest.main()
