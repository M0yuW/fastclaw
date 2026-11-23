import copy
import json
import unittest

import audit_gs_holdout_facts_v1 as subject


class GsHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text(encoding="utf-8"))
        cls.frame = json.loads(subject.FRAME.read_text(encoding="utf-8"))
        cls.discovery = json.loads(subject.DISCOVERY.read_text(encoding="utf-8"))

    def test_source_rows_and_q2_comparators(self):
        result = subject.audit(self.packet, self.frame, self.discovery)
        self.assertEqual(result["selected_facts"], 12)
        self.assertEqual(result["comparisons"]["reported_total_net_revenues"]
                         ["delta_usd_million_displayed"], "601")

    def test_wrong_transcribed_value_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 15180
        with self.assertRaisesRegex(ValueError, "fact differs from SEC"):
            subject.audit(changed, self.frame, self.discovery)

    def test_wrong_period_column_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["facts"][0]["source_column"] = "September 30 2025"
        with self.assertRaisesRegex(ValueError, "different current-quarter column"):
            subject.audit(changed, self.frame, self.discovery)

    def test_wrong_source_hash_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "different source"):
            subject.audit(changed, self.frame, self.discovery)


if __name__ == "__main__":
    unittest.main()
