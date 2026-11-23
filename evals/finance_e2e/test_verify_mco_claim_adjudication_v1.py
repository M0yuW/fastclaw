import copy
import json
import unittest

import verify_mco_claim_adjudication_v1 as subject
import audit_mco_holdout_facts_v1 as source_audit


class McoClaimAdjudicationVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(source_audit.PACKET.read_text())
        cls.relative = "MCO-2025-Q3-SEGMENT-MIX-r1/result.json"
        cls.raw = json.loads((subject.RESULTS / cls.relative).read_text())

    def test_five_frozen_records_verified(self):
        self.assertEqual(5, subject.verify()["observations_checked"])

    def test_false_final_record_id_is_rejected(self):
        changed = copy.deepcopy(self.raw)
        final = changed["turns"][-1]["response"]["choices"][0]["message"]
        final["content"] = final["content"].replace(
            changed["state"]["theses"][0]["reviews"][0]["id"], "wrong-review")
        with self.assertRaisesRegex(ValueError, "final record ID differs"):
            subject.verify_result(changed, self.packet, self.relative)

    def test_unblocked_hold_is_rejected(self):
        changed = copy.deepcopy(self.raw)
        changed["state"]["theses"][0]["thesis"]["actionability"] = "blocked"
        with self.assertRaisesRegex(ValueError, "persisted state differs"):
            subject.verify_result(changed, self.packet, self.relative)

    def test_missing_reported_number_is_rejected(self):
        changed = copy.deepcopy(self.raw)
        final = changed["turns"][-1]["response"]["choices"][0]["message"]
        final["content"] = final["content"].replace("1898", "XXXX")
        with self.assertRaisesRegex(ValueError, "selected number missing"):
            subject.verify_result(changed, self.packet, self.relative)


if __name__ == "__main__":
    unittest.main()
