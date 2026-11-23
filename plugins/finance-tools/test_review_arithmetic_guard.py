import json
import tempfile
import unittest
from pathlib import Path

from review_arithmetic_guard import GuardCatalogError, ReviewArithmeticGuard


class ReviewArithmeticGuardTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.baseline_hash = "a" * 64
        self.event_hash = "b" * 64
        self.catalog_path = Path(self.temp.name) / "catalog.json"
        self.catalog_path.write_text(json.dumps({
            "version": "review-arithmetic-guard-catalog-v1",
            "cases": [{
                "symbol": "EXAMPLE",
                "baseline_source_sha256": self.baseline_hash,
                "event_source_sha256": self.event_hash,
                "rows": {
                    "SEQ:gaap_total_revenue": {
                        "delta_value": "29.366", "unit": "USD_million",
                    },
                    "SEQ:gaap_operating_income": {
                        "delta_value": "28.368", "unit": "USD_million",
                    },
                    "SEQ:gaap_total_operating_expenses": {
                        "delta_value": "0.998", "unit": "USD_million",
                    },
                    "SEQ:gaap_income_tax_expense_benefit": {
                        "baseline_value": "-3", "event_value": "1",
                        "delta_value": "4", "unit": "USD_million",
                        "basis": "GAAP_quarter_signed_contribution_to_net_income",
                    },
                },
            }],
        }), encoding="utf-8")
        self.guard = ReviewArithmeticGuard(self.catalog_path)
        self.thesis = {"symbol": "EXAMPLE", "evidence": [
            {"sha256": self.baseline_hash}]}
        self.event = {"sources": [{"sha256": self.event_hash}]}

    def test_reversing_explicit_operating_bridge_is_rejected(self):
        self.assertEqual(
            ["operating_revenue_increment_reversed"],
            self.guard.check(self.thesis, self.event,
                             "Operating income rose by more than revenue."),
        )

    def test_correct_or_unrelated_claim_is_not_vetoed(self):
        self.assertEqual([], self.guard.check(
            self.thesis, self.event,
            "Revenue grew more than operating income; demand drivers need review."))

    def test_reversed_signed_tax_claim_is_rejected(self):
        self.assertEqual(
            ["signed_tax_contribution_reversed"],
            self.guard.check(self.thesis, self.event,
                             "The signed income tax line is a larger tax charge."),
        )

    def test_correct_signed_tax_claim_is_not_vetoed(self):
        self.assertEqual([], self.guard.check(
            self.thesis, self.event,
            "The signed income tax line improved by 4 million, adding to net income."))
        self.assertEqual([], self.guard.check(
            self.thesis, self.event,
            "The signed income tax line is not a larger tax charge."))

    def test_loss_alias_and_signed_expense_tax_are_checked(self):
        data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        rows = data["cases"][0]["rows"]
        rows["SEQ:gaap_operating_income_loss"] = rows.pop(
            "SEQ:gaap_operating_income")
        rows["SEQ:gaap_income_tax_expense_benefit"] = {
            "delta_value": "-30.3", "unit": "USD_million",
            "basis": "GAAP_quarter_signed_expense_negative_value_is_benefit",
        }
        self.catalog_path.write_text(json.dumps(data), encoding="utf-8")
        guard = ReviewArithmeticGuard(self.catalog_path)
        self.assertEqual(
            ["operating_revenue_increment_reversed"],
            guard.check(self.thesis, self.event,
                        "Operating profit rose by more than revenue."),
        )
        self.assertEqual(
            ["signed_tax_contribution_reversed"],
            guard.check(self.thesis, self.event,
                        "The tax expense created a larger tax drag."),
        )
        self.assertEqual([], guard.check(
            self.thesis, self.event,
            "The tax expense did not create a larger tax drag."))

    def test_positive_tax_benefit_alias_is_checked(self):
        data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        rows = data["cases"][0]["rows"]
        rows["SEQ:gaap_income_tax_benefit"] = rows.pop(
            "SEQ:gaap_income_tax_expense_benefit")
        self.catalog_path.write_text(json.dumps(data), encoding="utf-8")
        guard = ReviewArithmeticGuard(self.catalog_path)
        self.assertEqual(
            ["signed_tax_contribution_reversed"],
            guard.check(self.thesis, self.event,
                        "The tax expense created a larger tax drag."),
        )

    def test_false_hold_assurance_is_rejected(self):
        self.assertEqual(
            ["claimed_hold_not_in_ledger"],
            self.guard.check(self.thesis, self.event,
                             "The research hold is preserved pending more evidence.",
                             "maintain"),
        )

    def test_existing_hold_does_not_trigger_false_assurance(self):
        self.thesis["decision_hold"] = True
        self.assertEqual([], self.guard.check(
            self.thesis, self.event,
            "The research hold is preserved pending more evidence.",
            "maintain"))

    def test_unsigned_tax_row_is_not_interpreted_as_a_signed_contribution(self):
        data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        data["cases"][0]["rows"]["SEQ:gaap_income_tax_expense_benefit"]["basis"] = "unsigned_tax_expense"
        self.catalog_path.write_text(json.dumps(data), encoding="utf-8")
        guard = ReviewArithmeticGuard(self.catalog_path)
        self.assertEqual([], guard.check(
            self.thesis, self.event,
            "The signed income tax line is a larger tax charge."))

    def test_source_identity_mismatch_fails_closed(self):
        altered = {"sources": [{"sha256": "c" * 64}]}
        with self.assertRaises(GuardCatalogError):
            self.guard.check(self.thesis, altered,
                             "Operating income rose by more than revenue.")

    def test_duplicate_catalog_pair_is_rejected(self):
        data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        data["cases"].append(dict(data["cases"][0]))
        self.catalog_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(GuardCatalogError):
            ReviewArithmeticGuard(self.catalog_path)


if __name__ == "__main__":
    unittest.main()
