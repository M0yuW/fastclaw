"""Marqeta quarterly GAAP, non-GAAP and TPV source-audit regression tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "mq_reference_source_row_audit_v1.json"


class MQSourceRowAuditTests(unittest.TestCase):
    def test_fifteen_selected_rows_verify_against_frozen_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "MQ")
        self.assertEqual(result["checked_rows"], 15)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_bridges_and_non_gaap_separation(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gaap_gross_profit"),
                             value("gaap_net_revenue") - value("gaap_costs_of_revenue"))
            self.assertEqual(value("gaap_operating_income_loss"),
                             value("gaap_gross_profit") - value("gaap_total_operating_expenses"))
            self.assertEqual(value("gaap_pretax_income_loss"),
                             value("gaap_operating_income_loss") + value("gaap_other_income_net"))
            self.assertEqual(value("gaap_net_income_loss"),
                             value("gaap_pretax_income_loss") - value("gaap_income_tax_expense"))
        self.assertEqual(rows["company_total_processing_volume"]["unit"], "USD_million")
        self.assertEqual(rows["gaap_net_revenue"]["unit"], "USD_thousand")
        self.assertGreater(value("non_gaap_adjusted_ebitda"), 0)
        self.assertLess(value("gaap_net_income_loss"), 0)

    def test_cumulative_column_cannot_replace_quarter(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["numeric_value_index"] = 2
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-mq-period.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
