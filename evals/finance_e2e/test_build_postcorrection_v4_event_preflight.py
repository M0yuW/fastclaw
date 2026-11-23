import json
import unittest

import build_postcorrection_v4_event_preflight as subject


class V4EventPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepared = subject.preflight()
        cls.by_symbol = {item["runtime_symbol"]: item
                         for item in cls.prepared["fixtures"]}

    def test_all_source_distinct_fixtures_without_model_calls(self):
        self.assertEqual(self.prepared["ready_cases"], 20)
        self.assertEqual(self.prepared["rendered_signed_bridges"], 94)
        self.assertEqual(self.prepared["model_observations"], 0)
        self.assertFalse(self.prepared["paid_calls_authorized"])
        self.assertEqual(len(self.by_symbol), 20)
        for item in self.prepared["fixtures"]:
            self.assertNotEqual(item["seed_thesis"]["evidence"],
                                item["event"]["sources"])
            self.assertIn("sha256", item["event"]["sources"][0])
            self.assertNotIn("precommitted_interpretation_checks",
                             json.dumps(item))
            self.assertEqual(item["seed_thesis"]["required_event_metrics"],
                             sorted(item["event"]["observed_metrics"]))

    def test_fiscal_case_is_not_mislabeled_calendar_q3_minus_q2(self):
        item = self.by_symbol["FDS"]
        self.assertIn("FY2025 Q4", item["numeric_context"])
        self.assertIn("FY2026 Q1", item["numeric_context"])
        self.assertNotIn("Q3-minus-Q2", item["numeric_context"])
        self.assertIn("event-minus-baseline change", item["numeric_context"])

    def test_rkt_and_lpla_signed_bridges_reach_prompt(self):
        for symbol, metric in (("RKT", "gaap_net"),
                               ("LPLA", "adjusted_ebitda")):
            item = self.by_symbol[symbol]
            prompt = subject.review_prompt(item, "thesis-test", "alert-test")
            self.assertIn(f"{metric} change", prompt)
            self.assertIn("accounting identities from causal drivers", prompt)
            self.assertIn("thesis-test", prompt)

    def test_navi_uses_detailed_exhibit_from_same_sec_filing(self):
        item = self.by_symbol["NAVI"]
        self.assertTrue(item["event"]["sources"][0]["id"].endswith("-DETAIL"))
        self.assertIn("dex992.htm", item["event"]["sources"][0]["url"])

    def test_incompatible_quarterly_units_rejected(self):
        packet = json.loads(subject.DECLARED_PACKETS["LPLA"].read_text())
        item = next(x for x in packet["event"]["facts"] if x["metric"] == "revenue")
        item["unit"] = "USD_million"
        with self.assertRaisesRegex(ValueError, "quarterly fact basis/unit changed"):
            subject.fixture("LPLA", packet, subject._source_index())

    def test_single_letter_ticker_uses_searchable_company_keyword(self):
        self.assertEqual(subject.watchlist_keyword("C"), "Citigroup")
        self.assertIn("Citigroup", self.by_symbol["C"]["event"]["summary"])
        self.assertEqual(subject.watchlist_keyword("WEX"), "WEX")


if __name__ == "__main__":
    unittest.main()
