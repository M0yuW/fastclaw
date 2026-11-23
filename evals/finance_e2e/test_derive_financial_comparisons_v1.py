"""Checks signed arithmetic and unit/basis safeguards on frozen SEC facts."""

import json
import unittest

from derive_financial_comparisons_v1 import compare, reconcile
from verify_fintech_inference_answer_v1 import CORPUS


CASES = {case["case_id"]: case for case in json.loads(CORPUS.read_text())["cases"]}


def fact(case_id, period, fact_id):
    return next(item for item in CASES[case_id][period]["facts"] if item["id"] == fact_id)


class ComparisonTests(unittest.TestCase):
    def test_afrm_revenue_delta_and_percent_are_computed_not_approximated(self):
        output = compare(fact("AFRM-FISCAL-COST", "event", "AFRM-FQ1-REV"),
                         fact("AFRM-FISCAL-COST", "baseline", "AFRM-FQ4-REV"),
                         "sequential")
        self.assertEqual(output["delta_usd_thousand"], "39294")
        self.assertEqual(output["percent_change_of_baseline"], "5.96")
        self.assertEqual(output["direction"], "increased")

    def test_sofi_reconciliation_adds_signed_adjustments_once(self):
        case = "SOFI-REVENUE-BRIDGE"
        output = reconcile(fact(case, "event", "SOFI-Q3-GAAP-REV"),
                           [fact(case, "event", item) for item in
                            ("SOFI-Q3-SERVICING", "SOFI-Q3-RESIDUAL", "SOFI-Q3-DEBTGAIN")],
                           fact(case, "event", "SOFI-Q3-ADJ-REV"))
        self.assertTrue(output["reconciled"])
        self.assertEqual(output["computed_usd_thousand"], "689445")
        self.assertEqual(output["residual_usd_thousand"], "0")

    def test_upst_loss_direction_and_rounded_conversion(self):
        case = "UPST-MIXED-BASIS"
        q2 = fact(case, "baseline", "UPST-Q2-ADJ-NETLOSS")
        q3 = fact(case, "event", "UPST-Q3-ADJ-NETLOSS")
        sequential = compare(q3, q2, "sequential")
        self.assertEqual(sequential["delta_usd_thousand"], "9982.0")
        self.assertEqual(sequential["direction"], "loss_narrowed")
        self.assertEqual(sequential["precision"], "approximate_rounded_input")
        self.assertIsNone(sequential["percent_change_of_baseline"])
        prior = fact(case, "event", "UPST-Q3-PRIOR-ADJ-NETLOSS")
        year_over_year = compare(q3, prior, "year_over_year")
        self.assertEqual(year_over_year["direction"], "loss_widened")
        self.assertEqual(year_over_year["delta_usd_thousand"], "-1400.0")

    def test_mismatched_metrics_and_unsupported_units_fail(self):
        case = "AFRM-FISCAL-COST"
        with self.assertRaisesRegex(ValueError, "metrics differ"):
            compare(fact(case, "event", "AFRM-FQ1-REV"),
                    fact(case, "baseline", "AFRM-FQ4-RLTC"), "sequential")
        changed = {**fact(case, "event", "AFRM-FQ1-REV"), "unit": "shares"}
        with self.assertRaisesRegex(ValueError, "unsupported comparison unit"):
            compare(changed, fact(case, "baseline", "AFRM-FQ4-REV"), "sequential")


if __name__ == "__main__":
    unittest.main()
