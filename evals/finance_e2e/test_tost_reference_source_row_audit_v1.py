"""Toast quarterly GAAP-versus-GPV source audit regression tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "tost_reference_source_row_audit_v1.json"


class ToastSourceRowAuditTests(unittest.TestCase):
    def test_fourteen_selected_rows_verify_against_frozen_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "TOST")
        self.assertEqual(result["checked_rows"], 14)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_bridges_and_gpv_unit(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gaap_total_revenue"),
                             value("gaap_subscription_services_revenue")
                             + value("gaap_financial_technology_solutions_revenue")
                             + value("gaap_hardware_professional_services_revenue"))
            self.assertEqual(value("gaap_gross_profit"),
                             value("gaap_total_revenue") - value("gaap_total_costs_of_revenue"))
            self.assertEqual(value("gaap_operating_income"),
                             value("gaap_gross_profit") - value("gaap_total_operating_expenses"))
            self.assertEqual(value("gaap_pretax_income"),
                             value("gaap_operating_income") + value("gaap_interest_income_net")
                             + value("gaap_warrant_fair_value_change"))
            self.assertEqual(value("gaap_net_income"),
                             value("gaap_pretax_income")
                             + value("gaap_income_tax_expense_benefit"))
        self.assertEqual(rows["gross_payment_volume"]["unit"], "USD_billion")
        self.assertLess(value("gaap_hardware_professional_services_revenue"), 0)

    def test_cumulative_column_cannot_replace_quarterly_column(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["numeric_value_index"] = 2
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-tost-period.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
