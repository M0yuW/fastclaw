import json
import unittest

import audit_prospective_period_headlines_v1 as subject


class ProspectivePeriodHeadlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = json.loads(subject.LOCK.read_text(encoding="utf-8"))

    def test_twenty_source_pairs_have_expected_headline_anchors(self):
        result = subject.audit(self.lock)
        self.assertEqual(len(result["issuers"]), 20)
        four = next(item for item in result["issuers"] if item["ticker"] == "FOUR")
        self.assertEqual([p["expected_period"] for p in four["periods"]],
                         ["2024 Q4", "2025 Q1"])

    def test_wrong_quarter_does_not_match(self):
        with self.assertRaisesRegex(ValueError, "no near-headline period anchor"):
            subject.anchor(["Second Quarter 2025 results"], "2025 Q3")


if __name__ == "__main__":
    unittest.main()
