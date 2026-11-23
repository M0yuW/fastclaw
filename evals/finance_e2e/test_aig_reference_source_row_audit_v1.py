"""AIG 2025-quarter column and reporting-basis source-audit regression tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "aig_reference_source_row_audit_v1.json"


class AIGSourceRowAuditTests(unittest.TestCase):
    def test_selected_2025_rows_verify_against_frozen_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "AIG")
        self.assertEqual(result["checked_rows"], 16)
        self.assertIsNone(result["quality_pass"])

    def test_prior_year_column_cannot_replace_2025_column(self):
        packet = json.loads(PACKET.read_text())
        self.assertTrue(all(row["numeric_value_index"] == 1 for row in packet["rows"]))
        packet["rows"][0]["numeric_value_index"] = 0
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-aig-column.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)

    def test_adjusted_segment_bridges_and_mixed_signal(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gi_adjusted_pretax_income"),
                             value("gi_underwriting_income") + value("gi_net_investment_income"))
            self.assertEqual(value("total_adjusted_pretax_income"),
                             value("general_insurance_adjusted_pretax_income")
                             + value("other_operations_adjusted_pretax_income"))
        self.assertLess(Decimal(rows["gi_net_premiums_written"]["delta_value"]), 0)
        self.assertGreater(Decimal(rows["gi_underwriting_income"]["delta_value"]), 0)
        self.assertLess(Decimal(rows["gaap_net_income_common"]["delta_value"]), 0)
        self.assertEqual(rows["gi_adjusted_accident_year_combined_ratio"]["unit"], "percent")


if __name__ == "__main__":
    unittest.main()
