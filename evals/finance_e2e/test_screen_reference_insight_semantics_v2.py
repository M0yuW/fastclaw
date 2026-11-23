"""Regression checks for conservative reference-insight red flags."""

import json
import unittest

from run_reference_insight_development_flash_v1 import catalog_for
from screen_reference_insight_semantics_v2 import screen
from run_thesis_event_panel import HERE


RESULTS = HERE / "results/2026-10-25-reference-insight-development-flash-v1"


class SemanticScreenTests(unittest.TestCase):
    def recorded(self, symbol, repetition):
        paths = list(RESULTS.glob(f"{symbol}-*-r{repetition}/result.json"))
        self.assertEqual(len(paths), 1)
        result = json.loads(paths[0].read_text())
        try:
            candidate = json.loads(result["turns"][-1]["response"]["choices"][0]["message"]["content"])
        except json.JSONDecodeError:
            candidate = None
        return screen(catalog_for(symbol), candidate, result["state"])

    def test_recorded_affirmative_beat_without_benchmark_is_flagged(self):
        self.assertIn("unsupported_benchmark_language",
                      self.recorded("FITB", 1)["alerts"])

    def test_recorded_tax_direction_error_is_flagged(self):
        self.assertIn("tax_direction_contradiction",
                      self.recorded("RELY", 2)["alerts"])

    def test_recorded_profit_role_conflict_is_flagged(self):
        self.assertIn("profit_reference_role_conflict",
                      self.recorded("VRSK", 1)["alerts"])

    def test_nonalerted_record_does_not_become_quality_pass(self):
        result = self.recorded("VRSK", 2)
        self.assertEqual(result["alerts"], [])
        self.assertIsNone(result["quality_pass"])

    def test_malformed_final_remains_a_red_flag(self):
        self.assertEqual(self.recorded("TFC", 2)["alerts"],
                         ["candidate_not_object"])


if __name__ == "__main__":
    unittest.main()
