import unittest

from evals.finance_e2e.audit_evidence import fact_is_present, value_candidates


class FinanceEvidenceAuditTest(unittest.TestCase):
    def test_builds_decimal_and_rounded_billion_candidates(self) -> None:
        fact = {"value": "22600", "unit": "USD_million", "precision": "rounded_to_100_million"}
        self.assertEqual({"22.6", "22600", "22,600"}, value_candidates(fact))

    def test_requires_negative_context_for_negative_values(self) -> None:
        fact = {"value": "-10", "unit": "percent", "precision": "exact"}
        self.assertEqual((False, ["10"]), fact_is_present("Digital increased 10 percent.", fact))
        self.assertEqual((True, ["10"]), fact_is_present("Digital declined 10 percent.", fact))

    def test_numeric_candidates_do_not_match_inside_other_numbers(self) -> None:
        integer_fact = {"value": 10, "unit": "percent", "precision": "exact"}
        decimal_fact = {"value": 2.8, "unit": "percent", "precision": "exact"}
        self.assertEqual((False, ["10"]), fact_is_present("Margin increased 110 basis points.", integer_fact))
        self.assertEqual((False, ["2.8"]), fact_is_present("Revenue was 12.8 billion.", decimal_fact))

    def test_matches_categorical_filing_actions(self) -> None:
        fact = {"value": "suspending dividend", "unit": "categorical", "precision": "exact"}
        self.assertEqual(
            (True, ["suspending dividend"]),
            fact_is_present("The company is suspending dividend starting in the fourth quarter.", fact),
        )


if __name__ == "__main__":
    unittest.main()
