"""DFIN conflicting headline/operations source-row and pension-charge checks."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "dfin_reference_source_row_audit_v1.json"


class DFINSourceRowAuditTests(unittest.TestCase):
    def test_gaap_quarter_rows_and_event_only_pension_charge_verify(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "DFIN")
        self.assertEqual(result["checked_rows"], 15)
        self.assertEqual(result["event_only_checked_rows"], 1)
        self.assertIsNone(result["quality_pass"])

    def test_sales_pretax_and_tax_bridges(self):
        packet = json.loads(PACKET.read_text())
        rows = {row["id"]: row for row in packet["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            number = lambda key: Decimal(rows[key][field])
            self.assertEqual(number("gaap_total_net_sales"), sum(number(key) for key in (
                "gaap_software_solutions_sales", "gaap_tech_enabled_services_sales",
                "gaap_print_distribution_sales")))
            self.assertEqual(number("gaap_net_earnings_loss"),
                             number("gaap_pretax_earnings_loss")
                             - number("gaap_income_tax_expense_benefit"))
        self.assertGreater(Decimal(rows["gaap_income_from_operations"]["event_value"]), 0)
        self.assertLess(Decimal(rows["gaap_net_earnings_loss"]["event_value"]), 0)
        pension = Decimal(packet["event_only_rows"][0]["event_value"])
        self.assertEqual(pension, Decimal("82.8"))
        self.assertEqual(
            Decimal(rows["gaap_pretax_earnings_loss"]["event_value"]),
            Decimal(rows["gaap_income_from_operations"]["event_value"])
            - Decimal(rows["gaap_interest_expense_net"]["event_value"])
            - pension
            - Decimal(rows["gaap_investment_other_loss_net"]["event_value"]),
        )

    def test_wrong_event_only_pension_value_is_rejected(self):
        packet = json.loads(PACKET.read_text())
        packet["event_only_rows"][0]["event_value"] = "0"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "wrong-pension.json"
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "event-only transcribed row differs"):
                verify(path)


if __name__ == "__main__":
    unittest.main()
