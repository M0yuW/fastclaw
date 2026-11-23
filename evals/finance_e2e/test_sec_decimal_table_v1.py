import unittest
from decimal import Decimal

from sec_decimal_table import first_decimal_column


class SecDecimalTableTests(unittest.TestCase):
    def test_current_column_preserves_one_decimal(self):
        lines = ["Consolidated Statements of Income", "Quarter Ended",
                 "September 30,", "2025 2024 2025 2024",
                 "Total Revenues $ 1,537.6 $ 1,584.4 $ 4,871.9 $ 4,604.8",
                 "Reconciliation of adjusted results"]
        value = first_decimal_column(
            lines, start_anchor="Consolidated Statements of Income",
            end_anchor="Reconciliation of ", row_label="Total Revenues",
            header_fragments=("Quarter Ended", "September 30", "2025 2024 2025 2024"))
        self.assertEqual(value, Decimal("1537.6"))

    def test_wrong_period_is_rejected(self):
        lines = ["Consolidated Statements of Income", "Quarter Ended",
                 "June 30,", "2025 2024 2025 2024",
                 "Total Revenues 1,692.0 1,532.5 3,334.3 3,020.4",
                 "Reconciliation of adjusted results"]
        with self.assertRaisesRegex(ValueError, "header mismatch"):
            first_decimal_column(
                lines, start_anchor="Consolidated Statements of Income",
                end_anchor="Reconciliation of ", row_label="Total Revenues",
                header_fragments=("Quarter Ended", "September 30"))


if __name__ == "__main__":
    unittest.main()
