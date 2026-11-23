import copy
import json
import unittest

from fetch_sources import ROOT
from selected_fact_delta_guard_v1 import (
    decompose_change, derive, render_trusted_numeric_context,
)


def packet(symbol):
    return json.loads((ROOT / f"{symbol.lower()}_holdout_fact_packet_v1.json").read_text())


class SelectedFactDeltaGuardTests(unittest.TestCase):
    def test_all_seven_audited_packets_have_comparable_deltas(self):
        for symbol in ("GS", "BNY", "FISV", "MCO", "OMF", "CME", "BAC"):
            with self.subTest(symbol=symbol):
                source = packet(symbol)
                result = derive(source)
                self.assertEqual(len(source["baseline"]["facts"]), len(result["rows"]))
                self.assertEqual(source["event"]["source_sha256"],
                                 result["event_source_sha256"])

    def test_bny_incomplete_revenue_mix_cannot_be_called_entire(self):
        result = decompose_change(derive(packet("BNY")), "gaap_total_revenue",
                                  ["gaap_net_interest_income", "gaap_fee_revenue"])
        self.assertEqual("53", result["total_delta_usd_million"])
        self.assertEqual("33", result["components_delta_usd_million"]["gaap_net_interest_income"])
        self.assertEqual("24", result["unlisted_residual_usd_million"])
        self.assertFalse(result["fully_accounted_by_listed_components"])

    def test_gs_mix_requires_large_unlisted_revenue_residual(self):
        bundle = derive(packet("GS"))
        self.assertEqual("375", bundle["rows"]["reported_net_earnings"]["delta_value"])
        self.assertEqual("601", bundle["rows"]["reported_total_net_revenues"]["delta_value"])
        result = decompose_change(bundle, "reported_total_net_revenues",
                                  ["reported_market_making_revenues",
                                   "reported_investment_banking_revenues"])
        self.assertEqual("1001", result["unlisted_residual_usd_million"])
        self.assertFalse(result["fully_accounted_by_listed_components"])

    def test_bac_revenue_mix_fully_reconciles(self):
        result = decompose_change(
            derive(packet("BAC")), "gaap_total_revenue_net_of_interest_expense",
            ["gaap_net_interest_income", "gaap_noninterest_income"])
        self.assertEqual("0", result["unlisted_residual_usd_million"])
        self.assertTrue(result["fully_accounted_by_listed_components"])

    def test_ratio_changes_are_percentage_points(self):
        rows = derive(packet("OMF"))["rows"]
        self.assertEqual("0.38", rows["ci_consumer_30_plus_delinquency_ratio"]["delta_value"])
        self.assertEqual("percentage_points",
                         rows["ci_consumer_30_plus_delinquency_ratio"]["delta_unit"])

    def test_axp_mixed_units_remain_distinct(self):
        source = json.loads((ROOT / "axp_holdout_fact_packet_v2.json").read_text())
        rows = derive(source)["rows"]
        self.assertEqual("USD_billion", rows["reported_billed_business"]["delta_unit"])
        self.assertEqual("USD_per_share", rows["gaap_diluted_eps"]["delta_unit"])
        self.assertEqual("million_shares", rows["reported_average_diluted_common_shares"]["delta_unit"])
        self.assertEqual("percentage_points", rows["reported_principal_only_net_write_off_rate"]["delta_unit"])
        with self.assertRaisesRegex(ValueError, "needs USD million levels"):
            decompose_change(derive(source), "gaap_total_revenues_net_of_interest_expense",
                             ["reported_billed_business"])

    def test_rendered_context_has_residual_and_no_hidden_oracle(self):
        source = packet("BNY")
        bundle = derive(source)
        mix = decompose_change(bundle, "gaap_total_revenue",
                               ["gaap_net_interest_income", "gaap_fee_revenue"])
        rendered = render_trusted_numeric_context(bundle, [mix])
        self.assertIn("unlisted residual 24 USD_million", rendered)
        self.assertIn("This is not a causal explanation", rendered)
        for private_check in source["precommitted_interpretation_checks"]:
            self.assertNotIn(private_check, rendered)
        self.assertNotIn("high_within_case", rendered)

    def test_wrong_case_mix_cannot_enter_context(self):
        mix = decompose_change(derive(packet("BNY")), "gaap_total_revenue",
                               ["gaap_net_interest_income", "gaap_fee_revenue"])
        with self.assertRaisesRegex(ValueError, "another case"):
            render_trusted_numeric_context(derive(packet("GS")), [mix])

    def test_duplicate_or_mismatched_facts_are_rejected(self):
        changed = copy.deepcopy(packet("BNY"))
        changed["event"]["facts"][1]["id"] = changed["event"]["facts"][0]["id"]
        with self.assertRaisesRegex(ValueError, "duplicate fact ID"):
            derive(changed)
        changed = copy.deepcopy(packet("BNY"))
        changed["event"]["facts"][1]["unit"] = "percent"
        with self.assertRaisesRegex(ValueError, "mismatched unit"):
            derive(changed)


if __name__ == "__main__":
    unittest.main()
