"""Development regression probes using eight known v4 numeric error classes."""

import json
import unittest

import build_postcorrection_v4_event_preflight as v4
from validate_structured_financial_claims_v1 import validate_claim, validate_claims


def rows(symbol):
    packet = json.loads((v4.FIRST_PACKETS.get(symbol)
                         or v4.DECLARED_PACKETS[symbol]).read_text())
    return v4._normalize(symbol, packet)["facts"]


class StructuredClaimValidationTests(unittest.TestCase):
    def test_eight_known_wrong_numeric_claims_are_rejected(self):
        wrong = {
            "EVTC": {"op": "delta", "metric": "cash_interest_signed",
                     "value": "1122", "unit": "USD_thousand", "basis": "non_GAAP"},
            "FITB": {"op": "ratio_direction", "numerator_metric": "gaap_income_tax_expense",
                     "denominator_metric": "gaap_pretax_income", "relation": "lt"},
            "MKTX": {"op": "delta_share_percent", "numerator_metric": "total_other_income_signed",
                     "denominator_metric": "operating_income", "value": "66.7"},
            "NTRS": {"op": "compare_delta", "left_metric": "gaap_provision_for_credit_losses_signed",
                     "right_metric": "gaap_net_income", "magnitudes": True, "relation": "gt"},
            "RELY": {"op": "delta", "metric": "non_gaap_integration_addback",
                     "value": "2040", "unit": "USD_thousand", "basis": "non_GAAP"},
            "SEIC": {"op": "compare_delta", "left_metric": "pretax_income",
                     "right_metric": "gain_on_sale_of_business", "magnitudes": True,
                     "relation": "gt"},
            "USB": {"op": "signed_delta_identity", "total_metric": "gaap_net_income_attributable",
                    "terms": [{"metric": "gaap_net_income", "sign": 1},
                              {"metric": "noncontrolling_income_signed", "sign": -1}],
                    "value": "186"},
            "VRSK": {"op": "gap_direction", "left_metric": "non_gaap_adjusted_net_income",
                     "right_metric": "gaap_net_income", "cross_basis_explicit": True,
                     "relation": "lt"},
        }
        for symbol, claim in wrong.items():
            with self.subTest(symbol=symbol):
                self.assertEqual(validate_claim(rows(symbol), claim)["status"],
                                 "contradicted")

    def test_corrected_counterparts_verify(self):
        correct = {
            "EVTC": {"op": "delta", "metric": "cash_interest_signed",
                     "value": "992", "unit": "USD_thousand", "basis": "non_GAAP"},
            "FITB": {"op": "ratio_direction", "numerator_metric": "gaap_income_tax_expense",
                     "denominator_metric": "gaap_pretax_income", "relation": "gt"},
            "MKTX": {"op": "delta_share_percent", "numerator_metric": "total_other_income_signed",
                     "denominator_metric": "operating_income", "value": "39.9"},
            "NTRS": {"op": "compare_delta", "left_metric": "gaap_provision_for_credit_losses_signed",
                     "right_metric": "gaap_net_income", "magnitudes": True, "relation": "lt"},
            "RELY": {"op": "delta", "metric": "non_gaap_integration_addback",
                     "value": "-2040", "unit": "USD_thousand", "basis": "non_GAAP"},
            "SEIC": {"op": "compare_delta", "left_metric": "pretax_income",
                     "right_metric": "gain_on_sale_of_business", "magnitudes": True,
                     "relation": "lt"},
            "USB": {"op": "signed_delta_identity", "total_metric": "gaap_net_income_attributable",
                    "terms": [{"metric": "gaap_net_income", "sign": 1},
                              {"metric": "noncontrolling_income_signed", "sign": 1}],
                    "value": "186"},
            "VRSK": {"op": "gap_direction", "left_metric": "non_gaap_adjusted_net_income",
                     "right_metric": "gaap_net_income", "cross_basis_explicit": True,
                     "relation": "gt"},
        }
        for symbol, claim in correct.items():
            with self.subTest(symbol=symbol):
                self.assertEqual(validate_claim(rows(symbol), claim)["status"],
                                 "verified")

    def test_unsubmitted_claims_cannot_be_called_a_quality_pass(self):
        self.assertEqual(validate_claims(rows("FITB"), []),
                         {"status": "no_coverage", "items": [], "quality_pass": None})
        self.assertEqual(validate_claim(rows("FITB"), {"op": "unknown"})["status"],
                         "invalid_or_unassessable")
        self.assertEqual(validate_claim(rows("FITB"), {
            "op": "ratio_direction", "numerator_metric": "gaap_income_tax_expense",
            "denominator_metric": "gaap_pretax_income", "relation": "higher",
        })["status"], "invalid_or_unassessable")

    def test_reported_delta_pair_is_checked_not_silently_ignored(self):
        claim = {"op": "compare_delta", "left_metric": "gaap_noninterest_income",
                 "right_metric": "gaap_net_interest_income", "relation": "gt",
                 "magnitudes": [31, 25]}
        self.assertEqual(validate_claim(rows("FITB"), claim)["status"], "verified")
        claim["magnitudes"] = [32, 25]
        result = validate_claim(rows("FITB"), claim)
        self.assertEqual(result["status"], "invalid_or_unassessable")
        self.assertIn("reported delta pair differs", result["error"])
        claim["magnitudes"] = {"left": 31, "right": 25}
        self.assertEqual(validate_claim(rows("FITB"), claim)["status"], "verified")
        claim["magnitudes"] = "31 versus 25"
        self.assertEqual(validate_claim(rows("FITB"), claim)["status"],
                         "invalid_or_unassessable")


if __name__ == "__main__":
    unittest.main()
