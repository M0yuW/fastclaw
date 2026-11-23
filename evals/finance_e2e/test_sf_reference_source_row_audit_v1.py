"""Stifel GAAP, non-GAAP reconciliation, client stock, and segment tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE, ROOT
from verify_reference_source_row_packet_v1 import cells_for, verify


PACKET = HERE / "sf_reference_source_row_audit_v1.json"


class SFSourceRowAuditTests(unittest.TestCase):
    def test_twenty_four_rows_verify_against_frozen_exhibits(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "SF")
        self.assertEqual(result["checked_rows"], 24)
        self.assertIsNone(result["quality_pass"])

    def test_gaap_to_adjusted_bridges(self):
        rows = {row["id"]: row for row in json.loads(PACKET.read_text())["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gaap_net_revenues"),
                             value("gaap_total_revenues") - value("gaap_interest_expense"))
            self.assertEqual(value("gaap_total_noninterest_expense"),
                             value("gaap_compensation_expense")
                             + value("gaap_noncompensation_expense"))
            self.assertEqual(value("gaap_pretax_income"),
                             value("gaap_net_revenues")
                             - value("gaap_total_noninterest_expense"))
            self.assertEqual(value("gaap_net_income"),
                             value("gaap_pretax_income")
                             - value("gaap_income_tax_provision"))
            self.assertEqual(value("gaap_net_income_common"),
                             value("gaap_net_income")
                             - value("gaap_preferred_dividends"))
            self.assertEqual(value("recon_total_adjustments"),
                             value("recon_merger_related_adjustment")
                             + value("recon_restructuring_severance_adjustment")
                             + value("recon_tax_adjustment"))
            self.assertEqual(value("adjusted_net_income_common"),
                             value("gaap_net_income_common")
                             + value("recon_total_adjustments"))
        self.assertGreater(Decimal(rows["gaap_net_income_common"]["delta_value"]),
                           Decimal(rows["adjusted_net_income_common"]["delta_value"]))
        self.assertEqual(rows["wealth_client_assets_end_period"]["basis"],
                         "company_reported_point_in_time_client_assets")

    def test_client_assets_appear_under_wealth_section(self):
        selection = json.loads((HERE / "results/2026-10-25-reference-source-pair-selection-v1/SOURCE-PAIRS.json").read_text())
        pair = next(item for item in selection["pairs"] if item["symbol"] == "SF")
        for period, table_index in (("CY2025_Q2", 10), ("CY2025_Q3", 12)):
            path = ROOT / pair["periods"][period]["local_path"]
            _, cells = cells_for(path, table_index, 37)
            self.assertTrue(any("Global Wealth Management" in cell for cell in cells))

    def test_year_to_date_column_cannot_replace_quarter(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][0]["numeric_value_index_by_period"] = {
            "CY2025_Q2": 0, "CY2025_Q3": 5}
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-sf-ytd.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
