import copy
import json
import unittest

import audit_fisv_holdout_facts_v1 as subject


class FiservHoldoutFactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text(encoding="utf-8"))
        cls.lock = json.loads(subject.LOCK.read_text(encoding="utf-8"))

    def test_selected_rows_and_oracle(self):
        result = subject.audit(self.packet, self.lock)
        self.assertEqual(result["selected_facts"], 8)
        self.assertEqual(result["comparisons"]["gaap_total_revenue"], -253)

    def test_wrong_fact_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 5260
        with self.assertRaisesRegex(ValueError, "selected SEC row differs"):
            subject.audit(changed, self.lock)

    def test_wrong_accounting_basis_label_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["facts"][0]["section_anchor"] = "Reconciliation of GAAP to"
        with self.assertRaisesRegex(ValueError, "source row missing or ambiguous"):
            subject.audit(changed, self.lock)

    def test_missing_guidance_reset_anchor_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["qualitative_source_signal"]["anchor_phrases"][0] = "unreported guidance increase"
        with self.assertRaisesRegex(ValueError, "management-statement anchor missing"):
            subject.audit(changed, self.lock)


if __name__ == "__main__":
    unittest.main()
