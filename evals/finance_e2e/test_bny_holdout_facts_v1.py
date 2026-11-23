import copy
import json
import unittest

import audit_bny_holdout_facts_v1 as subject


class BnyHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text(encoding="utf-8"))
        cls.lock = json.loads(subject.LOCK.read_text(encoding="utf-8"))

    def test_selected_rows_and_comparisons(self):
        result = subject.audit(self.packet, self.lock)
        self.assertEqual(result["selected_facts"], 10)
        self.assertEqual(result["comparisons"]["gaap_total_revenue"], 53)
        self.assertEqual(result["comparisons"]["gaap_net_income_applicable_to_common"], -52)

    def test_wrong_fact_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 1
        with self.assertRaisesRegex(ValueError, "selected SEC row differs"):
            subject.audit(changed, self.lock)

    def test_wrong_unit_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["facts"][0]["unit"] = "USD_thousand"
        with self.assertRaisesRegex(ValueError, "wrong selected-fact unit"):
            subject.audit(changed, self.lock)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source differs from lock"):
            subject.audit(changed, self.lock)


if __name__ == "__main__":
    unittest.main()
