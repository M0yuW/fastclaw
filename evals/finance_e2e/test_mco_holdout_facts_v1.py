import copy
import json
import unittest

import audit_mco_holdout_facts_v1 as subject


class MoodysHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text(encoding="utf-8"))
        cls.lock = json.loads(subject.LOCK.read_text(encoding="utf-8"))

    def test_selected_rows_and_comparisons(self):
        result = subject.audit(self.packet, self.lock)
        self.assertEqual(result["selected_facts"], 8)
        self.assertEqual(result["comparisons"]["gaap_revenue"], 109)

    def test_wrong_fact_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 2000
        with self.assertRaisesRegex(ValueError, "selected SEC row differs"):
            subject.audit(changed, self.lock)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source differs from lock"):
            subject.audit(changed, self.lock)

    def test_false_counterevidence_anchor_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["qualitative_source_signal"]["anchor_phrase"] = "transaction revenue increased by 99%"
        with self.assertRaisesRegex(ValueError, "counterevidence anchor missing"):
            subject.audit(changed, self.lock)


if __name__ == "__main__":
    unittest.main()
