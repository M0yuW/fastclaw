from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from evals.finance_e2e.build_retrieval_suite import DEFAULT_EVIDENCE
from evals.finance_e2e.build_stage2_suite import DEFAULT_OUTPUT
from evals.finance_e2e.stage2_freeze_audit import analyze, prepare


class Stage2FreezeAuditTest(unittest.TestCase):
    def test_prepare_has_frozen_source_oracle_and_group_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = prepare(DEFAULT_EVIDENCE, DEFAULT_OUTPUT, Path(temporary))
            self.assertEqual(44, result["source"])
            self.assertEqual(17, result["oracle_calculation"])
            self.assertEqual(37, result["evidence_groups"])
            self.assertEqual(98, result["tasks"])

    def test_analysis_requires_complete_independent_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare(DEFAULT_EVIDENCE, DEFAULT_OUTPUT, root)
            for name in ("reviewer-a.csv", "reviewer-b.csv"):
                path = root / name
                with path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["audit_id", "verdict", "notes"])
                    writer.writeheader()
                    for row in rows:
                        row["verdict"] = "PASS"
                        writer.writerow(row)
            result = analyze(root / "audit-tasks.csv", root / "reviewer-a.csv", root / "reviewer-b.csv", root / "analysis")
            self.assertTrue(result["freeze_audit_passed"])
            self.assertEqual(1, result["raw_agreement"])


if __name__ == "__main__":
    unittest.main()
