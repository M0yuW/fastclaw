import unittest
from pathlib import Path

from sec_exhibit_text import extract_lines
from sec_inline_table import first_column_value, numeric_cell


ROOT = Path(__file__).resolve().parent


class SecInlineTableTests(unittest.TestCase):
    def test_parenthesized_cell_is_negative(self):
        self.assertEqual(numeric_cell("(1,234)"), -1234)

    def test_actual_fiserv_current_quarter_revenue(self):
        lines = extract_lines(ROOT / ".cache/sources/HOLDOUT-FISV-EVENT-v1.htm")
        self.assertEqual(first_column_value(
            lines, start_anchor="Condensed Consolidated Statements of Income",
            end_anchor="Reconciliation of GAAP to", row_label="Total revenue",
            header_fragments=("Three Months Ended September 30", "2025"), min_columns=4), 5263)

    def test_actual_moodys_current_quarter_revenue(self):
        lines = extract_lines(ROOT / ".cache/sources/HOLDOUT-MCO-EVENT-v1.htm")
        self.assertEqual(first_column_value(
            lines, start_anchor="Amounts in millions, except per share amounts",
            end_anchor="Table 2 - Condensed Consolidated Balance Sheet Data",
            row_label="Revenue", header_fragments=("Three Months EndedSeptember 30", "2025"),
            min_columns=4), 2007)

    def test_wrong_header_rejected(self):
        lines = extract_lines(ROOT / ".cache/sources/HOLDOUT-FISV-EVENT-v1.htm")
        with self.assertRaisesRegex(ValueError, "column header mismatch"):
            first_column_value(lines, start_anchor="Condensed Consolidated Statements of Income",
                               end_anchor="Reconciliation of GAAP to", row_label="Total revenue",
                               header_fragments=("Three Months Ended June 30",), min_columns=4)


if __name__ == "__main__":
    unittest.main()
