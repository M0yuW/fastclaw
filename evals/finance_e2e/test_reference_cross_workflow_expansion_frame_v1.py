"""No-overlap and frozen-order regressions for the additional issuer frame."""

from __future__ import annotations

import json
import unittest

from build_reference_cross_workflow_expansion_frame_v1 import (
    FIRST_SELECTION, POOL, QUOTAS, frame, previous_observed,
)
from run_thesis_event_panel import HERE


class CrossWorkflowExpansionFrameTests(unittest.TestCase):
    def test_quotas_reserves_and_prior_exclusion(self):
        current = frame()
        self.assertEqual(current["planned_issuers"], 30)
        used = {item["symbol"] for item in json.loads(FIRST_SELECTION.read_text())["pairs"]}
        excluded = used | previous_observed()
        chosen = []
        for stratum, group in current["strata"].items():
            self.assertEqual(len(group["planned"]), QUOTAS[stratum])
            self.assertGreater(len(group["reserves_in_order"]), 0)
            self.assertEqual(len(group["planned"] + group["reserves_in_order"]),
                             len(POOL[stratum].split()))
            self.assertEqual(group["planned"] + group["reserves_in_order"],
                             sorted(group["planned"] + group["reserves_in_order"],
                                    key=lambda entry: entry["rank_sha256"]))
            chosen.extend(entry["ticker"] for entry in
                          group["planned"] + group["reserves_in_order"])
        self.assertEqual(len(chosen), len(set(chosen)))
        self.assertFalse(set(chosen) & excluded)

    def test_saved_frame_matches_builder(self):
        path = HERE / "results/2026-10-26-reference-cross-workflow-expansion-frame-v1/FRAME.json"
        self.assertEqual(json.loads(path.read_text()), frame())


if __name__ == "__main__":
    unittest.main()
