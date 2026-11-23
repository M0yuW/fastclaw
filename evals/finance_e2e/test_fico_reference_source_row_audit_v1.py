"""FICO fiscal-calendar quarter and reconciliation source-audit regression tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "fico_reference_source_row_audit_v1.json"


class FICOSourceRowAuditTests(unittest.TestCase):
    def test_twenty_comparable_and_one_event_only_row_verify(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "FICO")
        self.assertEqual(result["checked_rows"], 20)
        self.assertEqual(result["event_only_checked_rows"], 1)
        self.assertIsNone(result["quality_pass"])

    def test_revenue_income_and_cash_bridges(self):
        packet = json.loads(PACKET.read_text())
        rows = {row["id"]: row for row in packet["rows"]}
        restructure = Decimal(packet["event_only_rows"][0]["event_value"])
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gaap_total_revenue"),
                             value("gaap_onprem_saas_revenue")
                             + value("gaap_professional_services_revenue")
                             + value("gaap_scores_revenue"))
            self.assertEqual(value("gaap_operating_income"),
                             value("gaap_total_revenue") - value("gaap_total_operating_expenses"))
            self.assertEqual(value("gaap_pretax_income"),
                             value("gaap_operating_income") + value("gaap_other_expense_net"))
            self.assertEqual(value("gaap_net_income"),
                             value("gaap_pretax_income") - value("gaap_tax_provision"))
            self.assertEqual(value("non_gaap_free_cash_flow"),
                             value("cash_flow_operating") + value("capital_expenditure_signed"))
        self.assertEqual(
            Decimal(rows["gaap_total_operating_expenses"]["baseline_value"]),
            sum(Decimal(rows[key]["baseline_value"]) for key in
                ("gaap_cost_of_revenue", "gaap_research_development", "gaap_sga_expense")))
        self.assertEqual(
            Decimal(rows["gaap_total_operating_expenses"]["event_value"]),
            sum(Decimal(rows[key]["event_value"]) for key in
                ("gaap_cost_of_revenue", "gaap_research_development", "gaap_sga_expense"))
            + restructure)
        for field, extra in (("baseline_value", Decimal(0)),
                             ("event_value", restructure)):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("non_gaap_net_income"),
                             value("gaap_net_income") + extra
                             + value("non_gaap_share_comp_adjustment")
                             + value("non_gaap_income_tax_adjustment")
                             + value("non_gaap_excess_tax_benefit_adjustment"))

    def test_full_year_column_cannot_replace_quarter(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["numeric_value_index"] = 2
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-fico-column.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
