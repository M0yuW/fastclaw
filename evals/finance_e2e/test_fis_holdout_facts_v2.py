import copy
import json
import unittest

import audit_fis_holdout_facts_v2 as subject
from selected_fact_delta_guard_v1 import derive


class FisHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_signed_gaap_and_adjusted_paths_are_distinct(self):
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(22, result["selected_facts"])
        self.assertEqual(734, result["gaap_attributable_delta_usd_million"])
        self.assertEqual(575, result["equity_method_delta_usd_million"])
        self.assertEqual(73, result["non_gaap_adjusted_delta_usd_million"])
        rows = derive(self.packet)["rows"]
        self.assertIsNone(rows["gaap_net_earnings_attributable_to_fis"]["relative_percent_of_baseline"])

    def test_negative_equity_loss_sign_cannot_be_reversed(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["facts"][7]["value"] = 598
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_adjusted_non_gaap_row_cannot_replace_gaap_net(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][9]["source_row"] = "Adjusted Net Earnings"
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "filing/source differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_parenthesized_loss_parsing(self):
        self.assertEqual(-598, subject._signed("(598)"))
        self.assertEqual(264, subject._signed("264"))


if __name__ == "__main__":
    unittest.main()
