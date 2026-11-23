import unittest

import audit_postcorrection_v4_state_claims as subject


class V4StateClaimDiagnosticTests(unittest.TestCase):
    def example(self):
        return {
            "turns": [{"response": {"choices": [{"message": {
                "content": "Review tr_" + "a" * 20
                           + " persisted with both source records attached. "
                           + "next_review_at 2026-01-31. Alert acknowledged."
            }}]}}],
            "state": {"theses": [{"thesis": {"next_review_at": None},
                                  "reviews": [{"id": "tr_" + "a" * 20,
                                               "event": {"sources": [{"id": "event"}]},
                                               "evidence": [],
                                               "rationale": 'review text", "evidence": [{"id":"baseline"}]'}]}],
                      "alerts": [{"status": "acknowledged"}]},
        }

    def test_detects_persisted_argument_and_final_state_mismatches(self):
        flags = subject.inspect(self.example())
        self.assertEqual({item["code"] for item in flags}, {
            "serialized_sibling_fields_inside_rationale",
            "claimed_both_sources_attached_but_absent",
            "claimed_next_review_date_differs",
        })

    def test_does_not_flag_consistent_state(self):
        item = self.example()
        review = item["state"]["theses"][0]["reviews"][0]
        review["evidence"] = [{"id": "baseline"}]
        review["rationale"] = "review text"
        item["state"]["theses"][0]["thesis"]["next_review_at"] = "2026-01-31"
        self.assertEqual(subject.inspect(item), [])


if __name__ == "__main__":
    unittest.main()
