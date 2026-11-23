"""Equifax quarterly GAAP and segment source-audit regression tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "efx_reference_source_row_audit_v1.json"


class EquifaxSourceRowAuditTests(unittest.TestCase):
    def test_nineteen_selected_rows_verify_against_frozen_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "EFX")
        self.assertEqual(result["checked_rows"], 19)
        self.assertIsNone(result["quality_pass"])

    def test_income_and_segment_bridges(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gaap_total_operating_expenses"),
                             value("gaap_cost_of_services") + value("gaap_sga_expense")
                             + value("gaap_depreciation_amortization"))
            self.assertEqual(value("gaap_operating_income"),
                             value("gaap_operating_revenue") - value("gaap_total_operating_expenses"))
            self.assertEqual(value("gaap_pretax_income"),
                             value("gaap_operating_income") + value("gaap_interest_expense")
                             + value("gaap_other_income_expense"))
            self.assertEqual(value("gaap_consolidated_net_income"),
                             value("gaap_pretax_income") + value("gaap_income_tax_provision"))
            self.assertEqual(value("gaap_net_income_attributable_equifax"),
                             value("gaap_consolidated_net_income")
                             + value("gaap_noncontrolling_interests"))
            self.assertEqual(value("segment_workforce_solutions_revenue"),
                             value("segment_verification_services_revenue")
                             + value("segment_employer_services_revenue"))
            self.assertEqual(value("segment_total_operating_revenue"),
                             value("segment_workforce_solutions_revenue")
                             + value("segment_us_information_solutions_revenue")
                             + value("segment_international_revenue"))
            self.assertEqual(value("segment_total_operating_revenue"),
                             value("gaap_operating_revenue"))

    def test_prior_year_column_cannot_replace_2025(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["numeric_value_index"] = 1
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-efx-column.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
