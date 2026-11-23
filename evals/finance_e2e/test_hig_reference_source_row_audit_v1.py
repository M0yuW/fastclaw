"""Hartford consolidated GAAP and mixed insurance-segment signal tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "hig_reference_source_row_audit_v1.json"


class HIGSourceRowAuditTests(unittest.TestCase):
    def test_twenty_four_rows_verify_against_frozen_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "HIG")
        self.assertEqual(result["checked_rows"], 24)
        self.assertIsNone(result["quality_pass"])

    def test_consolidated_bridges_and_opposing_segment_signals(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("consolidated_pretax_income"),
                             value("consolidated_total_revenues")
                             - value("consolidated_total_expenses"))
            self.assertEqual(value("consolidated_net_income"),
                             value("consolidated_pretax_income")
                             - value("consolidated_tax_expense"))
            self.assertEqual(value("consolidated_common_net_income"),
                             value("consolidated_net_income")
                             - value("consolidated_preferred_dividends"))
        delta = lambda key: Decimal(rows[key]["delta_value"])
        self.assertGreater(delta("consolidated_common_net_income"), 0)
        self.assertLess(delta("business_written_premiums"), 0)
        self.assertLess(delta("business_underwriting_gain"), 0)
        self.assertGreater(delta("business_combined_ratio"), 0)
        self.assertGreater(delta("personal_underwriting_gain"), 0)
        self.assertLess(delta("personal_underlying_underwriting_gain"), 0)
        self.assertLess(delta("personal_combined_ratio"), 0)
        self.assertGreater(delta("personal_underlying_combined_ratio"), 0)
        self.assertLess(delta("personal_current_accident_catastrophe_ratio"), 0)
        self.assertEqual(rows["consolidated_core_earnings"]["basis"],
                         "company_defined_non_GAAP_consolidated_quarter")

    def test_prior_year_column_cannot_replace_current_quarter(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][9]["numeric_value_index_by_period"] = {
            "CY2025_Q2": 0, "CY2025_Q3": 1}
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-hig-prior-year.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)

    def test_business_segment_cannot_be_substituted_with_personal(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][9]["table_index"] = 2
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-hig-segment.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "source row label absent|transcribed row differs"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
