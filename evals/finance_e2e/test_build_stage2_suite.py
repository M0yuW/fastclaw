from __future__ import annotations

import unittest

from evals.finance_e2e.build_retrieval_suite import DEFAULT_EVIDENCE, DEFAULT_LOCK, DEFAULT_SOURCES
from evals.finance_e2e.build_stage2_suite import ABLATION_MODE, build_stage2_suite


class BuildStage2SuiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = build_stage2_suite(DEFAULT_EVIDENCE, DEFAULT_SOURCES, DEFAULT_LOCK)

    def test_stage2_matrix_and_thresholds(self) -> None:
        self.assertEqual("draft", self.suite["status"])
        self.assertEqual(24, len(self.suite["cases"]))
        self.assertEqual(8, len({case["cluster_id"] for case in self.suite["cases"]}))
        self.assertEqual(3, self.suite["defaults"]["repetitions"])
        self.assertEqual(0.90, self.suite["defaults"]["min_final_evidence_recall"])
        self.assertEqual("off", self.suite["execution_controls"]["thinking_mode"])
        self.assertEqual(0.1, self.suite["execution_controls"]["temperature"])

    def test_capacity_matched_ablation_is_prespecified(self) -> None:
        self.assertIn(ABLATION_MODE, self.suite["ablation_modes"])
        self.assertEqual(8, len(self.suite["ablation_case_ids"]))
        for case_id in self.suite["ablation_case_ids"]:
            self.assertTrue(case_id.endswith("LONG-MEDIUM") or case_id.endswith("POINT-LARGE"))

    def test_point_in_time_temporal_gate_is_explicitly_blocked(self) -> None:
        point_cases = [case for case in self.suite["cases"] if case["task_family"] == "point_in_time"]
        self.assertEqual(12, len(point_cases))
        self.assertTrue(all(case["as_of_timestamp"].endswith("Z") for case in point_cases))
        self.assertTrue(all(case["accepted_at_verified"] is True for case in point_cases))
        self.assertTrue(all("Verified" in case["temporal_verification_note"] for case in point_cases))
        self.assertTrue(any(case["excluded_future_source_ids"] for case in point_cases))
        for case in point_cases:
            self.assertTrue(all(record["accepted_at"] <= case["as_of_timestamp"] for record in case["records"]))
        self.assertTrue(self.suite["formal_freeze_blockers"])


if __name__ == "__main__":
    unittest.main()
