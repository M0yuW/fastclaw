"""Prospective gate tests using sealed responses and counterexamples."""

import json
import unittest

from run_reference_insight_development_flash_v1 import catalog_for
from run_thesis_event_panel import HERE
from verify_reference_insight_candidate_v2 import render_reference_card_v2


RESULTS = HERE / "results/2026-10-25-reference-insight-development-flash-v1"


class ProspectiveReferenceGateTests(unittest.TestCase):
    def recorded(self, symbol, repetition):
        paths = list(RESULTS.glob(f"{symbol}-*-r{repetition}/result.json"))
        self.assertEqual(len(paths), 1)
        result = json.loads(paths[0].read_text())
        try:
            candidate = json.loads(
                result["turns"][-1]["response"]["choices"][0]["message"]["content"]
            )
        except json.JSONDecodeError:
            candidate = None
        return catalog_for(symbol), candidate, result["state"]

    def test_three_machine_accepted_but_semantically_flagged_are_held(self):
        expected = {
            ("FITB", 1): "unsupported_benchmark_language",
            ("RELY", 2): "tax_direction_contradiction",
            ("VRSK", 1): "profit_reference_role_conflict",
        }
        for (symbol, repetition), alert in expected.items():
            with self.subTest(symbol=symbol, repetition=repetition):
                card = render_reference_card_v2(
                    *self.recorded(symbol, repetition))
                self.assertEqual(card["status"], "held")
                self.assertIn(alert, card["semantic_alerts"])
                self.assertIsNone(card["quality_pass"])

    def test_nonalerted_candidate_still_needs_qualitative_review(self):
        card = render_reference_card_v2(*self.recorded("VRSK", 2))
        self.assertEqual(card["status"], "candidate_for_qualitative_review")
        self.assertEqual(card["semantic_alerts"], [])
        self.assertIsNone(card["quality_pass"])
        self.assertTrue(card["complete_host_comparison_table"])

    def test_malformed_response_is_held_without_publishing_table(self):
        card = render_reference_card_v2(*self.recorded("TFC", 2))
        self.assertEqual(card["status"], "held")
        self.assertIn("candidate_not_object", card["issues"])
        self.assertNotIn("complete_host_comparison_table", card)

    def test_new_case_without_semantic_signal_cannot_get_quality_pass(self):
        catalog, candidate, state = self.recorded("VRSK", 2)
        candidate["interpretation"]["uncertainty"] = (
            "The extract does not establish durability or full-filing context."
        )
        card = render_reference_card_v2(catalog, candidate, state)
        self.assertIsNone(card["quality_pass"])


if __name__ == "__main__":
    unittest.main()
