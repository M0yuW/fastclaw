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
            root = Path(temporary)
            result = prepare(DEFAULT_EVIDENCE, DEFAULT_OUTPUT, root)
            self.assertEqual(44, result["source"])
            self.assertEqual(17, result["oracle_calculation"])
            self.assertEqual(37, result["evidence_groups"])
            self.assertEqual(98, result["tasks"])
            with (root / "audit-tasks.csv").open(newline="", encoding="utf-8") as handle:
                tasks = list(csv.DictReader(handle))
            source = next(row for row in tasks if row["audit_type"] == "source")
            calculation = next(row for row in tasks if row["audit_type"] == "oracle_calculation")
            group = next(row for row in tasks if row["audit_type"] == "evidence_equivalence_group")
            self.assertTrue(source["claimed_excerpt"])
            self.assertIn("fact_id", calculation["input_facts"])
            self.assertNotIn("expected", calculation["calculation_spec"])
            self.assertIn("text_preview", group["record_previews"])
            with (root / "reviewer-a.csv").open(newline="", encoding="utf-8") as handle:
                self.assertIn("independent_result", next(csv.DictReader(handle)))
            review_html = (root / "review.html").read_text(encoding="utf-8")
            self.assertNotIn("__STAGE2_REVIEW_TASKS__", review_html)
            self.assertIn(source["audit_id"], review_html)
            self.assertIn(source["claimed_excerpt"], review_html)
            self.assertIn("Expected results remain hidden", review_html)

    def test_analysis_requires_complete_independent_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare(DEFAULT_EVIDENCE, DEFAULT_OUTPUT, root)
            for name in ("reviewer-a.csv", "reviewer-b.csv"):
                path = root / name
                with path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                with path.open("w", newline="", encoding="utf-8") as handle:
                    reviewer_fields = ["audit_id", "verdict", "independent_result", "notes"]
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=reviewer_fields,
                        lineterminator="\n",
                    )
                    writer.writeheader()
                    for row in rows:
                        row["verdict"] = "PASS"
                        row["independent_result"] = "independently verified"
                        writer.writerow({field: row.get(field, "") for field in reviewer_fields})
            result = analyze(root / "audit-tasks.csv", root / "reviewer-a.csv", root / "reviewer-b.csv", root / "analysis")
            self.assertTrue(result["freeze_audit_passed"])
            self.assertEqual(1, result["raw_agreement"])

    def test_analysis_rejects_missing_independent_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare(DEFAULT_EVIDENCE, DEFAULT_OUTPUT, root)
            for name in ("reviewer-a.csv", "reviewer-b.csv"):
                path = root / name
                with path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                with path.open("w", newline="", encoding="utf-8") as handle:
                    reviewer_fields = ["audit_id", "verdict", "independent_result", "notes"]
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=reviewer_fields,
                        lineterminator="\n",
                    )
                    writer.writeheader()
                    for row in rows:
                        row["verdict"] = "PASS"
                        writer.writerow({field: row.get(field, "") for field in reviewer_fields})
            with self.assertRaisesRegex(ValueError, "independent_result"):
                analyze(
                    root / "audit-tasks.csv",
                    root / "reviewer-a.csv",
                    root / "reviewer-b.csv",
                    root / "analysis",
                )


if __name__ == "__main__":
    unittest.main()
