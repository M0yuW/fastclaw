"""Offline model-facing fixture coverage and adjudication-note isolation."""

import json
import unittest

from build_reference_source_distinct_event_fixtures_v1 import fixture, preflight
from preflight_reference_source_confirmation_v1 import SELECTION
from run_thesis_event_panel import HERE


class SourceDistinctEventFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepared = preflight()
        cls.by_symbol = {x["runtime_symbol"]: x for x in cls.prepared["fixtures"]}

    def test_thirty_cases_and_five_fresh_sessions_each(self):
        prepared = self.prepared
        self.assertEqual(prepared["issuer_cases"], 30)
        self.assertEqual(prepared["comparable_rows"], 523)
        self.assertEqual(prepared["planned_fresh_sessions"], 150)
        self.assertEqual(len(set(prepared["run_order"])), 150)
        self.assertFalse(prepared["paid_calls_authorized"])

    def test_source_references_and_no_investigator_answer_key(self):
        selection = {x["symbol"]: x for x in json.loads(SELECTION.read_text())["pairs"]}
        for symbol, item in self.by_symbol.items():
            pair = selection[symbol]
            self.assertEqual(item["seed_thesis"]["evidence"][0]["sha256"],
                             pair["periods"]["CY2025_Q2"]["sha256"])
            self.assertEqual(item["event"]["sources"][0]["sha256"],
                             pair["periods"]["CY2025_Q3"]["sha256"])
            self.assertEqual(item["event"]["as_of"],
                             pair["periods"]["CY2025_Q3"]["filing_date"])
            self.assertNotIn("Must assess in every answer", item["numeric_context"])
            self.assertNotIn("Material error or omission", item["numeric_context"])
            self.assertEqual(len(item["catalog"]["rows"]),
                             len(item["event"]["observed_metrics"])
                             - (1 if symbol in {"BLK", "DFIN", "FICO", "GDOT", "TROW", "WAL"} else 0))

    def test_single_period_facts_never_gain_invented_comparison(self):
        wal = self.by_symbol["WAL"]
        self.assertNotIn("SEQ:q3_mortgage_loan_origination_sale_gain_scope_unconfirmed",
                         wal["catalog"]["rows"])
        self.assertIn("Q2 only, no Q3 comparator", wal["numeric_context"])
        self.assertIn("Q3 only, no Q2 comparator", wal["numeric_context"])
        trow = self.by_symbol["TROW"]
        self.assertNotIn("SEQ:q3_model_delivery_assets_added", trow["catalog"]["rows"])
        self.assertIn("q3_model_delivery_assets_added", trow["event"]["observed_metrics"])

    def test_limitations_and_case_criticals_are_not_model_input(self):
        selection = {x["symbol"]: x for x in json.loads(SELECTION.read_text())["pairs"]}
        packet = json.loads((HERE / "wal_reference_source_row_audit_v1.json").read_text())
        before = fixture(selection["WAL"], packet)
        packet["limitations"] = ["PRIVATE CANARY: answer key should not leak"]
        after = fixture(selection["WAL"], packet)
        self.assertEqual(before, after)
        self.assertNotIn("PRIVATE CANARY", after["numeric_context"])


if __name__ == "__main__":
    unittest.main()
