#!/usr/bin/env python3
"""No-provider development checks for source-arithmetic publication alerts."""

import unittest

from screen_reference_insight_semantics_v3 import screen


def row(metric, before, after):
    change = after - before
    return {"metric": metric, "baseline_value": str(before),
            "event_value": str(after), "delta_value": str(change),
            "direction": "increase" if change > 0 else
                         "decrease" if change < 0 else "flat"}


def candidate(text):
    return {"interpretation": {"implication": text, "counterevidence": ""},
            "selected_comparisons": {"support": [], "counterevidence": []}}


class ArithmeticScreenTests(unittest.TestCase):
    def test_tax_rate_is_distinct_from_absolute_tax_expense(self):
        aciw = {"rows": {
            "SEQ:gaap_income_tax_expense": row("gaap_income_tax_expense", 5670, 26872),
            "SEQ:gaap_income_before_income_taxes": row(
                "gaap_income_before_income_taxes", 17872, 118122)}}
        self.assertIn("effective_tax_rate_decline_denied", screen(
            aciw, candidate("The effective tax rate did not decline."), {})["alerts"])
        self.assertIn("effective_tax_rate_decline_denied", screen(
            aciw, candidate("After-tax growth was not tax-assisted."), {})["alerts"])
        self.assertEqual([], screen(
            aciw, candidate("Tax expense rose, but the effective tax rate fell."),
            {})["alerts"])

    def test_ambiguous_absolute_tax_burden_language_is_not_flagged(self):
        ssb = {"rows": {
            "SEQ:gaap_income_tax_expense": row("gaap_income_tax_expense", 66975, 74715),
            "SEQ:gaap_pretax_income": row("gaap_pretax_income", 282199, 321356)}}
        self.assertEqual([], screen(ssb, candidate(
            "The higher tax provision is not evidence of a reduced tax burden."),
            {})["alerts"])

    def test_no_rate_alert_when_pretax_is_negative(self):
        loss = {"rows": {
            "SEQ:gaap_income_tax_expense": row("gaap_income_tax_expense", 206, 498),
            "SEQ:gaap_pretax_income_loss": row(
                "gaap_pretax_income_loss", -441, -3126)}}
        self.assertEqual([], screen(loss, candidate(
            "No conclusion about a reduced tax burden follows from loss periods."),
            {})["alerts"])

    def test_absolute_bridge_contradiction_and_correct_nonalert(self):
        blk = {"rows": {
            "SEQ:gaap_total_revenue": row("gaap_total_revenue", 5423, 6509),
            "SEQ:gaap_total_expense": row("gaap_total_expense", 3692, 4554),
            "SEQ:gaap_operating_income": row("gaap_operating_income", 1731, 1955)}}
        self.assertIn("expense_revenue_increment_reversed", screen(
            blk, candidate("Total expense grew by more than total revenue."),
            {})["alerts"])
        self.assertEqual([], screen(blk, candidate(
            "Revenue rose by more than expense, so operating income increased."),
            {})["alerts"])

    def test_operating_increment_contradiction(self):
        jkhy = {"rows": {
            "SEQ:gaap_revenue": row("gaap_revenue", 615372, 644738),
            "SEQ:gaap_total_expenses": row("gaap_total_expenses", 459675, 460673),
            "SEQ:gaap_operating_income": row(
                "gaap_operating_income", 155697, 184065)}}
        self.assertIn("operating_revenue_increment_reversed", screen(
            jkhy, candidate("Operating income rose by more than revenue."),
            {})["alerts"])
        self.assertIn("operating_revenue_increment_reversed", screen(
            jkhy, candidate("Operating and pretax profit rose by more than revenue."),
            {})["alerts"])
        self.assertIn("operating_revenue_increment_reversed", screen(
            jkhy, candidate("Operating income and pretax income rose by more than revenue."),
            {})["alerts"])

    def test_saved_review_is_in_scope(self):
        blk = {"rows": {
            "SEQ:gaap_total_revenue": row("gaap_total_revenue", 5423, 6509),
            "SEQ:gaap_total_expense": row("gaap_total_expense", 3692, 4554)}}
        state = {"theses": [{"reviews": [{"rationale":
            "The revenue increase was accompanied by a larger increase in total expense."}]}]}
        self.assertIn("expense_revenue_increment_reversed", screen(
            blk, candidate("The quarter was mixed."), state)["alerts"])


if __name__ == "__main__":
    unittest.main()
