import unittest

from evals.finance_e2e.build_hard_suite import DEFAULT_EVIDENCE, DEFAULT_SOURCES, build_hard_outputs
from evals.finance_e2e.build_suite import read_json, verify_evidence


class HardFinanceSuiteTest(unittest.TestCase):
    def test_builds_four_evidence_matched_longitudinal_cases(self) -> None:
        evidence = verify_evidence(DEFAULT_EVIDENCE, DEFAULT_SOURCES)
        suite, agent_pack = build_hard_outputs(evidence, DEFAULT_SOURCES)

        self.assertEqual("finance-sec-hard-longitudinal-runtime-v1", suite["name"])
        self.assertEqual(4, len(suite["cases"]))
        self.assertEqual(
            ["solo_open_book", "solo_two_pass", "team", "oracle_team"],
            suite["baselines"],
        )
        self.assertEqual(
            {"finance-source", "finance-methodology", "finance-governance"},
            set(agent_pack["agents"]),
        )
        self.assertEqual("evals/multiagent-finance-sec-hard.json", agent_pack["suite"])
        for case in suite["cases"]:
            self.assertEqual("runtime", case["execution_mode"])
            self.assertEqual(3, len(case["agents"]))
            self.assertEqual(3, len(case["milestones"]))
            self.assertIn("state-conflict", case["tags"])
            self.assertIn("explicitly reject the stale candidate", case["prompt"])
            self.assertTrue(all(case["id"] in cases for cases in agent_pack["agents"].values()))

    def test_intel_case_requires_categorical_and_impairment_evidence(self) -> None:
        suite, _ = build_hard_outputs(read_json(DEFAULT_EVIDENCE), DEFAULT_SOURCES)
        intel = next(case for case in suite["cases"] if case["id"] == "FHARD-INTC-01")
        source_values = intel["milestones"][0]["values"]
        self.assertIn("INTC-Q2-DIVIDEND", source_values)
        self.assertIn("INTC-Q3-IMPAIR", source_values)
        self.assertTrue(
            any("downgrade_to_needs_review" in value for value in intel["forbidden_output_values"])
        )


if __name__ == "__main__":
    unittest.main()
