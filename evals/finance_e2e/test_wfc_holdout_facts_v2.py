import copy
import json
import unittest

import audit_wfc_holdout_facts_v2 as subject


class WfcHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())

    def test_selected_rows_and_cross_filing_comparators(self):
        result = subject.audit(self.packet, self.lock)
        self.assertEqual(18, result["selected_facts"])
        self.assertEqual(9, result["cross_filing_comparator_checks"])
        self.assertEqual("-0.07", result["comparisons"]["fte_net_interest_margin"])
        self.assertEqual("0", result["revenue_mix_residual_usd_million"])

    def test_wrong_value_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 1
        with self.assertRaisesRegex(ValueError, "selected SEC row differs"):
            subject.audit(changed, self.lock)

    def test_wrong_basis_unit_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][-1]["unit"] = "USD_million_rounded"
        with self.assertRaisesRegex(ValueError, "selected-fact unit differs"):
            subject.audit(changed, self.lock)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source differs from lock"):
            subject.audit(changed, self.lock)


if __name__ == "__main__":
    unittest.main()
