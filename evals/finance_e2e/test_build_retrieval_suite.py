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
        declared = next(item for item in nvda["milestones"] if item["id"] == "declared-calculations")
        self.assertTrue(any("percentage_point" in value for value in declared["values"]))
        self.assertTrue(any("+30.9%" in value for value in declared["values"]))

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

    def test_gold_equivalence_groups_never_cross_source_or_locator(self) -> None:
        for case in self.suite["cases"]:
            records = {record["id"]: record for record in case["records"]}
            for group in case["gold_record_groups"]:
                self.assertEqual(1, len({records[record_id]["source_id"] for record_id in group}))
                self.assertEqual(1, len({records[record_id]["locator"] for record_id in group}))

    def test_same_number_different_periods_remain_distinct(self) -> None:
        case = next(case for case in self.suite["cases"] if case["id"] == "FRET-INTC-LONG-LARGE")
        groups = [set(group) for group in case["gold_record_groups"]]
        q2_headcount = next(group for group in groups if "REC-INTC-02-04" in group)
        q3_margin = next(group for group in groups if "REC-INTC-03-02" in group)
        self.assertNotEqual(q2_headcount, q3_margin)
        self.assertNotIn("REC-INTC-03-02", q2_headcount)
        self.assertNotIn("REC-INTC-02-04", q3_margin)

    def test_intel_impairment_group_requires_full_charge_context(self) -> None:
        case = next(case for case in self.suite["cases"] if case["id"] == "FRET-INTC-LONG-LARGE")
        group = next(item for item in case["gold_fact_groups"] if item["fact_id"] == "INTC-Q3-IMPAIR")
        records = {record["id"]: record for record in case["records"]}
        self.assertTrue(group["record_ids"])
        for record_id in group["record_ids"]:
            record = records[record_id]
            self.assertIn("accelerated depreciation", record["text"].lower())
            self.assertEqual("Q3 2024 Restructuring and Impairment Charges", record["locator"])

    def test_intel_restructuring_record_uses_declared_detail_section(self) -> None:
        case = next(case for case in self.suite["cases"] if case["id"] == "FRET-INTC-LONG-LARGE")
        record = next(record for record in case["records"] if record["id"] == "REC-INTC-03-03")
        self.assertIn("recognized $2.8 billion in restructuring charges in q3 2024", record["text"].lower())


if __name__ == "__main__":
    unittest.main()
