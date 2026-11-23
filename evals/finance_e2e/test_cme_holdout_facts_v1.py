import copy
import json
import unittest

import audit_cme_holdout_facts_v1 as subject


class CmeHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text(encoding="utf-8"))
        cls.lock = json.loads(subject.LOCK.read_text(encoding="utf-8"))

    def test_selected_decimal_rows_and_comparisons(self):
        result = subject.audit(self.packet, self.lock)
        self.assertEqual(result["selected_facts"], 12)
        self.assertEqual(result["comparisons_usd_million_displayed"]["gaap_total_revenues"],
                         "-154.4")
        self.assertEqual(result["comparisons_usd_million_displayed"]["gaap_market_data_and_information_services"],
                         "4.4")

    def test_wrong_displayed_fact_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = "1227.8"
        with self.assertRaisesRegex(ValueError, "selected SEC decimal row differs"):
            subject.audit(changed, self.lock)

    def test_false_precision_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["facts"][0]["value"] = "1388.00"
        with self.assertRaisesRegex(ValueError, "selected SEC decimal row differs"):
            subject.audit(changed, self.lock)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source differs from lock"):
            subject.audit(changed, self.lock)


if __name__ == "__main__":
    unittest.main()
