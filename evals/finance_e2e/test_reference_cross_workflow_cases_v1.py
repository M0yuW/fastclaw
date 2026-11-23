"""Regression checks for the frozen source-disjoint development packets."""

from __future__ import annotations

import json
import unittest

from build_reference_cross_workflow_cases_v1 import build


class ReferenceCrossWorkflowCasesTests(unittest.TestCase):
    def test_packets_are_disjoint_and_screen_oracle_is_complete(self):
        result = build()
        cases = result["case_packets"]
        self.assertEqual(len(cases), 10)
        symbols = [symbol for case in cases for symbol in case["screen"]["symbols"]]
        self.assertEqual(len(symbols), len(set(symbols)))
        for case in cases:
            screen = case["screen"]
            self.assertEqual(set(screen["expected_retained"]) |
                             set(screen["expected_rejected"]), set(screen["symbols"]))
            self.assertFalse(set(screen["expected_retained"]) &
                             set(screen["expected_rejected"]))
            self.assertIn("require_complete=false", screen["prompt"])
            self.assertEqual(case["portfolio"]["expected_overlap_status"],
                             "indeterminate")

    def test_saved_artifact_matches_builder(self):
        from pathlib import Path
        from run_thesis_event_panel import HERE
        path = HERE / "results/2026-10-26-reference-cross-workflow-cases-v1/CASES.json"
        self.assertEqual(json.loads(path.read_text()), build())


if __name__ == "__main__":
    unittest.main()
