import unittest

from evals.finance_e2e.build_retrieval_suite import (
    DEFAULT_EVIDENCE,
    DEFAULT_LOCK,
    DEFAULT_SOURCES,
    build_suite,
)


class FinanceRetrievalSuiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = build_suite(DEFAULT_EVIDENCE, DEFAULT_SOURCES, DEFAULT_LOCK)

    def test_builds_two_tasks_and_three_loads_for_four_companies(self) -> None:
        self.assertEqual("finance-sec-retrieval-context-v1", self.suite["name"])
        self.assertEqual(24, len(self.suite["cases"]))
        self.assertEqual(
            [
                "solo_monolithic",
                "solo_staged",
                "team_shared_retrieval",
                "team_raw_context",
                "oracle_evidence",
            ],
            self.suite["modes"],
        )

    def test_gold_labels_are_not_embedded_in_public_corpus_records(self) -> None:
        for case in self.suite["cases"]:
            record_ids = {record["id"] for record in case["records"]}
            self.assertTrue(set(case["gold_record_ids"]).issubset(record_ids))
            self.assertTrue(all(set(group).issubset(record_ids) for group in case["gold_record_groups"]))
            for record in case["records"]:
                self.assertFalse(any(key.startswith("_") for key in record))
                self.assertEqual(64, len(record["source_sha256"]))

    def test_common_protocol_withholds_expected_calculation_results(self) -> None:
        nvda = next(case for case in self.suite["cases"] if case["id"] == "FRET-NVDA-LONG-MEDIUM")
        self.assertIn("expected results are intentionally withheld", nvda["analysis_protocol"])
        self.assertIn("finance-coordinator", self.suite["defaults"]["coordinator_agent_id"])
        self.assertEqual(0.95, self.suite["defaults"]["min_grounding_accuracy"])
        self.assertNotIn("15.3 percent", nvda["analysis_protocol"])
        self.assertNotIn("86.8 percent", nvda["analysis_protocol"])
        self.assertNotIn("Predeclared deterministic calculation ledger", nvda["oracle_evidence"])

    def test_context_loads_increase_without_changing_gold(self) -> None:
        cases = {
            case["id"]: case
            for case in self.suite["cases"]
            if case["id"].startswith("FRET-NVDA-LONG-")
        }
        small = cases["FRET-NVDA-LONG-SMALL"]
        medium = cases["FRET-NVDA-LONG-MEDIUM"]
        large = cases["FRET-NVDA-LONG-LARGE"]
        self.assertLess(len(small["records"]), len(medium["records"]))
        self.assertLess(len(medium["records"]), len(large["records"]))
        self.assertEqual(small["gold_record_ids"], medium["gold_record_ids"])
        self.assertEqual(medium["gold_record_ids"], large["gold_record_ids"])


if __name__ == "__main__":
    unittest.main()
