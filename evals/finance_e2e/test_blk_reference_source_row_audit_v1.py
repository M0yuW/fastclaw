"""BlackRock GAAP versus AUM source-audit regression tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "blk_reference_source_row_audit_v1.json"


class BLKSourceRowAuditTests(unittest.TestCase):
    def test_twenty_one_comparable_and_one_event_only_row_verify(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "BLK")
        self.assertEqual(result["checked_rows"], 21)
        self.assertEqual(result["event_only_checked_rows"], 1)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_income_and_parent_bridges(self):
        packet = json.loads(PACKET.read_text())
        rows = {row["id"]: row for row in packet["rows"]}
        subco = Decimal(packet["event_only_rows"][0]["event_value"])
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gaap_combined_advisory_lending_revenue"),
                             value("gaap_investment_advisory_administration_fees")
                             + value("gaap_securities_lending_revenue"))
            self.assertEqual(value("gaap_total_revenue"),
                             sum(value(key) for key in
                                 ("gaap_combined_advisory_lending_revenue", "gaap_performance_fees",
                                  "gaap_technology_subscription_revenue", "gaap_distribution_fees",
                                  "gaap_advisory_other_revenue")))
            self.assertEqual(value("gaap_operating_income"),
                             value("gaap_total_revenue") - value("gaap_total_expense"))
            self.assertEqual(value("gaap_pretax_income"),
                             value("gaap_operating_income") + value("gaap_total_nonoperating_income"))
            self.assertEqual(value("gaap_consolidated_net_income"),
                             value("gaap_pretax_income") - value("gaap_income_tax_expense"))
        self.assertEqual(Decimal(rows["gaap_net_income_attributable_blackrock"]["baseline_value"]),
                         Decimal(rows["gaap_consolidated_net_income"]["baseline_value"])
                         - Decimal(rows["gaap_nci_cip_income"]["baseline_value"]))
        self.assertEqual(Decimal(rows["gaap_net_income_attributable_blackrock"]["event_value"]),
                         Decimal(rows["gaap_consolidated_net_income"]["event_value"])
                         - Decimal(rows["gaap_nci_cip_income"]["event_value"]) - subco)
        self.assertEqual(rows["assets_under_management_end_period"]["basis"],
                         "company_reported_point_in_time_assets_under_management")

    def test_prior_quarter_column_cannot_replace_current_quarter(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["numeric_value_index"] = 3
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-blk-column.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
