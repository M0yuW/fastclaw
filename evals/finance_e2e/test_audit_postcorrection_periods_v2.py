import copy
import json
import unittest

import audit_postcorrection_periods_v2 as subject


class PostcorrectionPeriodAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = json.loads(subject.LOCK.read_text())

    def test_all_five_pairs_have_q2_q3_headline_anchors(self):
        result = subject.audit(self.lock)
        self.assertEqual(5, len(result["issuers"]))
        self.assertTrue(all([period["expected_period"] for period in issuer["periods"]]
                            == ["2025 Q2", "2025 Q3"] for issuer in result["issuers"]))

    def test_missing_pair_is_rejected(self):
        changed = copy.deepcopy(self.lock)
        changed["entries"].pop()
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            subject.audit(changed)


if __name__ == "__main__":
    unittest.main()
