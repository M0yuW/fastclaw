import unittest

import build_insight_candidate_prompt_v1 as prompt


class CandidatePromptTests(unittest.TestCase):
    def test_contract_requests_typed_claims_without_prewriting_decision(self):
        fixture = {"case_id": "TEST", "numeric_context": "Audited selected facts."}
        text = prompt.candidate_prompt(fixture, "th_example", "al_example")
        self.assertIn("exactly three top-level keys", text)
        self.assertIn("delta_share_percent", text)
        self.assertIn("actual tool results and saved ledger state", text)
        self.assertIn("Audited selected facts.", text)
        self.assertNotIn("keep conviction at 3", text)
        self.assertNotIn("choose needs_review", text)


if __name__ == "__main__":
    unittest.main()
