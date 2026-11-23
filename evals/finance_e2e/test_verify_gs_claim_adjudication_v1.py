import copy
import json
import unittest

import audit_gs_holdout_facts_v1 as source_audit
import verify_gs_claim_adjudication_v1 as subject


class GsClaimAdjudicationVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(source_audit.PACKET.read_text())
        cls.relative = "GS-2025-Q3-EARNINGS-TRANSITION-r1/result.json"
        cls.raw = json.loads((subject.RESULTS / cls.relative).read_text())

    def test_five_frozen_records_verified(self):
        self.assertEqual(5, subject.verify()["observations_checked"])

    def test_false_final_record_id_is_rejected(self):
        changed = copy.deepcopy(self.raw)
        final = changed["turns"][-1]["response"]["choices"][0]["message"]
        final["content"] = final["content"].replace(
            changed["state"]["theses"][0]["reviews"][0]["id"], "wrong-review")
        with self.assertRaisesRegex(ValueError, "final record ID differs"):
            subject.verify_result(changed, self.packet, self.relative, 1)

    def test_unexpected_state_is_rejected(self):
        changed = copy.deepcopy(self.raw)
        changed["state"]["theses"][0]["thesis"]["actionability"] = "blocked"
        with self.assertRaisesRegex(ValueError, "persisted state differs"):
            subject.verify_result(changed, self.packet, self.relative, 1)

    def test_missing_reported_number_is_rejected(self):
        changed = copy.deepcopy(self.raw)
        final = changed["turns"][-1]["response"]["choices"][0]["message"]
        final["content"] = final["content"].replace("14,583", "XXXXX")
        with self.assertRaisesRegex(ValueError, "selected level missing"):
            subject.verify_result(changed, self.packet, self.relative, 1)

    def test_wrong_persisted_absolute_comparison_is_present(self):
        relative = "GS-2025-Q3-EARNINGS-TRANSITION-r5/result.json"
        changed = json.loads((subject.RESULTS / relative).read_text())
        review = changed["state"]["theses"][0]["reviews"][0]
        review["rationale"] = review["rationale"].replace(
            "earnings increase exceeded the revenue increase in absolute terms",
            "earnings grew faster in relative percentage terms",
        )
        with self.assertRaisesRegex(ValueError, "persisted absolute comparison changed"):
            subject.verify_result(changed, self.packet, relative, 5)


if __name__ == "__main__":
    unittest.main()
