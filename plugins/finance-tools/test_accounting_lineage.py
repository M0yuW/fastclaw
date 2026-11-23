"""Free deterministic controls for the experimental accounting-lineage rule."""

import unittest

from accounting_lineage import ClaimValidationError, validate_causal_claims


FACTS = {
    "INTC-MFG": {"statement_line": "cost_of_sales"},
    "INTC-GOODWILL": {"statement_line": "operating_expense"},
    "INTC-TAX": {"statement_line": "income_tax"},
    "AAPL-TAX": {
        "statement_line": "income_tax",
        "source_explicit_targets": ["diluted_eps_gaap"],
    },
    "NKE-DISCOUNT": {
        "statement_line": "contra_revenue",
        "source_explicit_targets": ["gross_margin"],
    },
    "NKE-MIX": {
        "statement_line": "revenue_mix",
        "source_explicit_targets": ["gross_margin"],
    },
    "NVDA-REV": {"statement_line": "revenue"},
    "AMD-GAMING-REV": {"statement_line": "revenue"},
}


def claim(target, strength, *drivers, **extra):
    return {"target_metric": target, "strength": strength,
            "driver_fact_ids": list(drivers), **extra}


class AccountingLineageControls(unittest.TestCase):
    def test_cost_of_sales_is_consistent_with_margin_without_quantifying_share(self):
        value = claim("gross_margin", "consistent_with", "INTC-MFG")
        self.assertEqual(validate_causal_claims(FACTS, [value]), [value])

    def test_tax_and_goodwill_cannot_drive_gross_margin(self):
        for driver in ("INTC-TAX", "INTC-GOODWILL"):
            with self.subTest(driver=driver), self.assertRaises(ClaimValidationError):
                validate_causal_claims(
                    FACTS, [claim("gross_margin", "consistent_with", driver)])

    def test_mixed_bundle_cannot_be_assigned_to_gross_margin(self):
        with self.assertRaises(ClaimValidationError):
            validate_causal_claims(FACTS, [claim(
                "gross_margin", "consistent_with", "INTC-MFG", "INTC-GOODWILL", "INTC-TAX")])

    def test_source_explicit_nike_drivers_are_allowed(self):
        value = claim("gross_margin", "directly_stated", "NKE-DISCOUNT", "NKE-MIX")
        self.assertEqual(validate_causal_claims(FACTS, [value]), [value])

    def test_revenue_cooccurrence_is_not_a_margin_cause(self):
        for driver in ("NVDA-REV", "AMD-GAMING-REV"):
            with self.subTest(driver=driver), self.assertRaises(ClaimValidationError):
                validate_causal_claims(
                    FACTS, [claim("gross_margin", "consistent_with", driver)])

    def test_no_unverified_percentage_point_attribution(self):
        with self.assertRaises(ClaimValidationError):
            validate_causal_claims(FACTS, [claim(
                "gross_margin", "consistent_with", "INTC-MFG",
                attributed_change_percentage_points=20.4)])

    def test_unresolved_causality_is_allowed(self):
        value = claim("gross_margin", "unresolved", "INTC-MFG", "INTC-TAX")
        self.assertEqual(validate_causal_claims(FACTS, [value]), [value])

    def test_unresolved_causality_cannot_name_unstored_fact(self):
        with self.assertRaises(ClaimValidationError):
            validate_causal_claims(
                FACTS, [claim("gross_margin", "unresolved", "MISSING-FACT")])

    def test_unresolved_causality_rejects_nonstrings(self):
        with self.assertRaises(ClaimValidationError):
            validate_causal_claims(
                FACTS, [claim("gross_margin", "unresolved", {"fact": "INTC-MFG"})])

    def test_explicit_tax_to_gaap_eps_without_unreconciled_number(self):
        value = claim("diluted_eps_gaap", "directly_stated", "AAPL-TAX")
        self.assertEqual(validate_causal_claims(FACTS, [value]), [value])
        with self.assertRaises(ClaimValidationError):
            validate_causal_claims(
                FACTS, [claim("diluted_eps_gaap", "directly_stated", "AAPL-TAX",
                              attributed_change_percentage_points=0.67)])

    def test_direct_claim_needs_explicit_source_link(self):
        with self.assertRaises(ClaimValidationError):
            validate_causal_claims(FACTS, [claim(
                "gross_margin", "directly_stated", "INTC-MFG")])

    def test_unsupported_target_error_gives_recoverable_next_step(self):
        with self.assertRaises(ClaimValidationError) as raised:
            validate_causal_claims(FACTS, [claim(
                "global_comp_sales_growth_yoy", "directly_stated", "NVDA-REV")])
        message = str(raised.exception)
        self.assertIn("supported targets:", message)
        self.assertIn("causal_claims=[]", message)


if __name__ == "__main__":
    unittest.main()
