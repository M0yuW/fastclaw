from __future__ import annotations

import unittest

from evals.finance_e2e.build_provenance import DEFAULT_EVIDENCE, DEFAULT_LOCK, DEFAULT_SOURCES, build


class BuildProvenanceTest(unittest.TestCase):
    def test_complete_locked_oracle(self) -> None:
        facts, derived = build(DEFAULT_EVIDENCE, DEFAULT_SOURCES, DEFAULT_LOCK)
        self.assertEqual(44, len(facts["facts"]))
        self.assertEqual(17, len(derived["derived_values"]))
        self.assertEqual(44, len({row["fact_id"] for row in facts["facts"]}))
        self.assertTrue(all(len(row["source_sha256"]) == 64 for row in facts["facts"]))

    def test_accepted_at_is_locked_and_unknown_scope_is_not_inferred(self) -> None:
        facts, _ = build(DEFAULT_EVIDENCE, DEFAULT_SOURCES, DEFAULT_LOCK)
        self.assertTrue(all(row["accepted_at"].endswith("Z") for row in facts["facts"]))
        for row in facts["facts"]:
            if not row["scope"]:
                self.assertIn("scope not explicitly stated", row["missing_reason"])

    def test_derived_values_keep_formula_inputs_and_rounding(self) -> None:
        _, derived = build(DEFAULT_EVIDENCE, DEFAULT_SOURCES, DEFAULT_LOCK)
        for row in derived["derived_values"]:
            self.assertEqual(2, len(row["input_fact_ids"]))
            self.assertTrue(row["formula"])
            self.assertTrue(row["rounding_rule"])
            self.assertNotEqual("", row["expected_result"])


if __name__ == "__main__":
    unittest.main()
