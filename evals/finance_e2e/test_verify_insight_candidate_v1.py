"""Free regression checks for typed-answer and ledger-state publication gating."""

import json
import copy
import unittest
from pathlib import Path

import build_postcorrection_v4_event_preflight as v4
from verify_insight_candidate_v1 import canonical_state, render_review_card, verify_candidate


HERE = Path(__file__).resolve().parent
FITB_RESULT = HERE / "results/2026-10-25-postcorrection-v4-event-holdout" / (
    "FITB-2025-Q3-GAAP-INTEREST-CREDIT-INCOME-BRIDGE-r1/result.json")


class InsightCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        packet = json.loads(v4.DECLARED_PACKETS["FITB"].read_text())
        cls.facts = v4._normalize("FITB", packet)["facts"]
        cls.raw_state = json.loads(FITB_RESULT.read_text())["state"]
        cls.state = copy.deepcopy(cls.raw_state)
        cls.state["theses"][0]["reviews"][0]["rationale"] = (
            "Reported improvement is bounded by a higher provision; investigate its composition."
        )

    def candidate(self):
        return {
            "claims": [{"op": "delta", "metric": "gaap_pretax_income",
                        "value": "29", "unit": "USD_million", "basis": "GAAP"}],
            "interpretation": {
                "implication": "Reported improvement is bounded by credit cost.",
                "counterevidence": "The provision increased.",
                "uncertainty": "Provision composition needs further research.",
            },
            "asserted_state": canonical_state(self.state),
        }

    def test_correct_typed_candidate_is_not_an_automatic_quality_pass(self):
        result = verify_candidate(self.facts, self.candidate(), self.state)
        self.assertEqual(result["status"], "candidate_for_qualitative_review")
        self.assertIsNone(result["quality_pass"])

    def test_wrong_number_and_claimed_unsaved_date_are_held(self):
        candidate = self.candidate()
        candidate["claims"][0]["value"] = "30"
        candidate["asserted_state"]["next_review_at"] = "2026-11-30"
        result = verify_candidate(self.facts, candidate, self.state)
        self.assertEqual(result["status"], "held")
        self.assertIn("numeric_claims_unverified_or_uncovered", result["issues"])
        self.assertIn("state_claim_contradicted_by_ledger", result["issues"])

    def test_missing_coverage_and_extra_freeform_field_are_held(self):
        candidate = self.candidate()
        candidate["claims"] = []
        candidate["final_prose"] = "Unchecked numerical claims could hide here."
        result = verify_candidate(self.facts, candidate, self.state)
        self.assertEqual(result["status"], "held")
        self.assertIn("numeric_claims_unverified_or_uncovered", result["issues"])
        self.assertIn("candidate_schema_mismatch", result["issues"])

    def test_asserted_source_attachment_must_match_actual_review(self):
        candidate = self.candidate()
        candidate["asserted_state"]["evidence_ids"] = ["HOLDOUT-V4-FITB-BASELINE",
                                                        "HOLDOUT-V4-FITB-EVENT"]
        result = verify_candidate(self.facts, candidate, self.state)
        self.assertIn("state_claim_contradicted_by_ledger", result["issues"])

    def test_evidence_id_order_does_not_change_state_identity(self):
        state = copy.deepcopy(self.state)
        state["theses"][0]["reviews"][0]["evidence"] = [
            {"id": "HOLDOUT-V4-FITB-BASELINE"},
            {"id": "HOLDOUT-V4-FITB-EVENT"},
        ]
        candidate = self.candidate()
        candidate["asserted_state"] = canonical_state(state)
        ids = candidate["asserted_state"]["evidence_ids"]
        candidate["asserted_state"]["evidence_ids"] = list(reversed(ids))
        result = verify_candidate(self.facts, candidate, state)
        self.assertEqual(result["status"], "candidate_for_qualitative_review")

    def test_unchecked_numeric_prose_is_held(self):
        candidate = self.candidate()
        candidate["interpretation"]["implication"] = "Pretax income improved by 30 USD million."
        result = verify_candidate(self.facts, candidate, self.state)
        self.assertIn("unstructured_numeric_prose", result["issues"])
        self.assertEqual(render_review_card(self.facts, candidate, self.state)["status"],
                         "held")

    def test_review_card_uses_source_result_and_actual_state(self):
        candidate = self.candidate()
        card = render_review_card(self.facts, candidate, self.state)
        self.assertEqual(card["source_derived_assertions"][0]["verified_result"], "29")
        self.assertEqual(card["canonical_state"], canonical_state(self.state))
        self.assertIsNone(card["quality_pass"])

    def test_numeric_saved_rationale_requires_separate_coverage(self):
        candidate = self.candidate()
        result = verify_candidate(self.facts, candidate, self.raw_state)
        self.assertEqual(result["status"], "held")
        self.assertIn("unstructured_numeric_saved_rationale", result["issues"])


if __name__ == "__main__":
    unittest.main()
