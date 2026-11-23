"""Regression checks for provisional source-pair and row selection."""

from __future__ import annotations

import json
import unittest

from build_reference_cross_workflow_expansion_pair_candidates_v1 import (
    ARCHIVE, pair_and_rows,
)
from build_reference_cross_workflow_expansion_frame_v1 import FIRST_SELECTION
from run_thesis_event_panel import HERE


class ExpansionPairCandidatesTests(unittest.TestCase):
    def test_selection_is_source_disjoint_and_earliest(self):
        pairs, rows = pair_and_rows()
        used = {item["symbol"] for item in json.loads(FIRST_SELECTION.read_text())["pairs"]}
        symbols = {item["symbol"] for item in pairs["pairs"]}
        self.assertEqual(len(symbols), 30)
        self.assertFalse(symbols & used)
        self.assertNotIn("INTU", symbols)
        self.assertNotIn("OZK", symbols)
        self.assertIn("ALIT", symbols)
        self.assertIn("RF", symbols)
        self.assertEqual(len(rows["issuers"]), 30)
        self.assertGreater(sum(item["shared_label_count"] for item in rows["issuers"]), 3000)
        archive = json.loads((ARCHIVE / "manifest.json").read_text())
        by_key = {}
        for item in archive["artifacts"]:
            by_key.setdefault((item["symbol"], item["period_window"]), []).append(item)
        for pair in pairs["pairs"]:
            for period, chosen in pair["periods"].items():
                first = min(by_key[(pair["symbol"], period)],
                            key=lambda item: (item["filing_date"], item["accession"]))
                self.assertEqual(chosen["accession"], first["accession"])
                self.assertEqual(chosen["sha256"], first["sha256"])
                self.assertEqual(chosen["period_identity_review"],
                                 "pending_manual_confirmation")

    def test_saved_selection_matches_builder(self):
        path = HERE / "results/2026-10-26-reference-cross-workflow-expansion-pair-candidates-v1/SOURCE-PAIR-CANDIDATES.json"
        self.assertEqual(json.loads(path.read_text()), pair_and_rows()[0])


if __name__ == "__main__":
    unittest.main()
