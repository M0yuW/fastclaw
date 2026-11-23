import copy
import json
import unittest

import audit_cboe_holdout_facts_v2 as subject


class CboeHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())

    def test_gaap_rows_and_segment_bridge(self):
        result = subject.audit(self.packet, self.lock)
        self.assertEqual(22, result["selected_facts"])
        self.assertEqual(2, result["reconciled_quarters"])
        self.assertEqual("18.2", result["comparisons"]["gaap_net_revenue"])
        self.assertEqual("3.5", result["comparisons"]["gaap_reported_operating_margin"])
        self.assertEqual("0", result["segment_mix_residual_usd_million"])

    def test_adjusted_operating_income_cannot_replace_reported_gaap(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["facts"][2]["value"] = 374.0
        with self.assertRaisesRegex(ValueError, "selected SEC row differs"):
            subject.audit(changed, self.lock)

    def test_wrong_ratio_unit_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][3]["unit"] = "USD_million_rounded"
        with self.assertRaisesRegex(ValueError, "unit differs"):
            subject.audit(changed, self.lock)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source differs from lock"):
            subject.audit(changed, self.lock)


if __name__ == "__main__":
    unittest.main()
