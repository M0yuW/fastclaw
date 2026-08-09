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


if __name__ == "__main__":
    unittest.main()
