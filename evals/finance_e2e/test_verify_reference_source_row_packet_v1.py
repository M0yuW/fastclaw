"""Regression checks for source-pinned quarterly row verification."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import number_after_label, verify


PACKET = HERE / "adp_reference_source_row_audit_v1.json"
PGR_PACKET = HERE / "pgr_reference_source_row_audit_v1.json"
EVR_PACKET = HERE / "evr_reference_source_row_audit_v1.json"
JKHY_PACKET = HERE / "jkhy_reference_source_row_audit_v1.json"


class SourceRowPacketVerifierTests(unittest.TestCase):
    def test_actual_adp_packet_checks_six_rows_without_quality_claim(self):
        result = verify(PACKET)
        self.assertEqual(result["checked_rows"], 6)
        self.assertIsNone(result["quality_pass"])

    def test_other_business_strata_use_source_pinned_rows(self):
        self.assertEqual(verify(EVR_PACKET)["checked_rows"], 6)
        self.assertEqual(verify(PGR_PACKET)["checked_rows"], 6)

    def altered(self, change):
        packet = json.loads(PACKET.read_text())
        change(packet)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "altered.json"
            path.write_text(json.dumps(packet))
            return verify(path)

    def test_wrong_transcribed_value_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "transcribed row differs"):
            self.altered(lambda packet: packet["rows"][0].__setitem__(
                "event_value", "9999"))

    def test_wrong_period_header_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "period header absent"):
            self.altered(lambda packet: packet["period_headers"]["CY2025_Q2"].append(
                "December 31,"))

    def test_per_row_period_header_override_must_be_complete_and_real(self):
        with self.assertRaisesRegex(ValueError, "per-row period headers incomplete"):
            self.altered(lambda packet: packet["rows"][0].__setitem__(
                "period_headers_by_period", {"CY2025_Q2": ["June 30,"]}))
        with self.assertRaisesRegex(ValueError, "period header absent"):
            self.altered(lambda packet: packet["rows"][0].__setitem__(
                "period_headers_by_period", {
                    "CY2025_Q2": ["December 31, 2025"],
                    "CY2025_Q3": ["September 30, 2025"]}))

    def test_header_scan_limit_must_be_bounded(self):
        with self.assertRaisesRegex(ValueError, "header row count invalid"):
            self.altered(lambda packet: packet["rows"][0].__setitem__(
                "header_row_count", -1))

    def test_wrong_numeric_column_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "transcribed row differs"):
            self.altered(lambda packet: packet["rows"][0].__setitem__(
                "numeric_value_index", 1))

    def test_pgr_month_column_cannot_replace_quarter_column(self):
        packet = json.loads(PGR_PACKET.read_text())
        packet["rows"][0]["numeric_value_index"] = 0
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "month-instead-of-quarter.json"
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "transcribed row differs"):
                verify(path)

    def test_per_period_table_locator_cannot_be_partial(self):
        packet = json.loads(JKHY_PACKET.read_text())
        packet["rows"][0]["table_index_by_period"].pop("CY2025_Q3")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "partial-locator.json"
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "per-period table_index locators incomplete"):
                verify(path)

    def test_negative_table_locator_cannot_select_from_end(self):
        with self.assertRaisesRegex(ValueError, "table_index locator invalid"):
            self.altered(lambda packet: packet["rows"][0].__setitem__(
                "table_index", -1))

    def test_split_parenthesis_negative_cell_requires_closing_cell(self):
        self.assertEqual(number_after_label(
            ["Pretax loss", "(57.9", ")", "15.4"], "Pretax loss", 0),
            Decimal("-57.9"))
        with self.assertRaisesRegex(ValueError, "numeric column out of range"):
            number_after_label(["Pretax loss", "(57.9"], "Pretax loss", 0)

    def test_currency_prefixed_numeric_cell_is_parsed_without_percent_column(self):
        self.assertEqual(number_after_label(
            ["Net income", "$1,074", "$761", "41%"], "Net income", 0),
            Decimal("1074"))
        self.assertEqual(number_after_label(
            ["Net loss", "$(11)", "$31", "NM"], "Net loss", 0),
            Decimal("-11"))
        with self.assertRaisesRegex(ValueError, "numeric column out of range"):
            number_after_label(["Net income", "$1,074", "41%"], "Net income", 1)

    def test_percent_cell_requires_explicit_row_opt_in(self):
        with self.assertRaisesRegex(ValueError, "numeric column out of range"):
            number_after_label(["Coverage", "1.31%", "1.24%"], "Coverage", 0)
        self.assertEqual(number_after_label(
            ["Coverage", "1.31%", "1.24%"], "Coverage", 0, True), Decimal("1.31"))

    def test_leading_decimal_point_in_reported_ratio(self):
        self.assertEqual(number_after_label(
            ["Annualized net charge-offs", ".32", "%", ".42", "%"],
            "Annualized net charge-offs", 0), Decimal("0.32"))
        self.assertEqual(number_after_label(
            ["Ratio", ".32%"], "Ratio", 0, True), Decimal("0.32"))

    def test_quality_pass_cannot_be_injected(self):
        with self.assertRaisesRegex(ValueError, "cannot assert model quality"):
            self.altered(lambda packet: packet.__setitem__("quality_pass", True))


if __name__ == "__main__":
    unittest.main()
