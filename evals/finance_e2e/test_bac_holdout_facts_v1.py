import copy
import json
import unittest

import audit_bac_holdout_facts_v1 as subject


class BacHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text(encoding="utf-8"))
        cls.lock = json.loads(subject.LOCK.read_text(encoding="utf-8"))

    def test_selected_rows_comparators_and_accounting_bridge(self):
        result = subject.audit(self.packet, self.lock)
        self.assertEqual(20, result["selected_facts"])
        self.assertEqual(10, result["cross_filing_comparator_checks"])
        self.assertEqual(1625, result["comparisons"]["gaap_total_revenue_net_of_interest_expense"])
        self.assertEqual(1215, result["comparisons"]["gaap_net_income_applicable_to_common"])

    def test_wrong_fact_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 1
        with self.assertRaisesRegex(ValueError, "selected SEC row differs"):
            subject.audit(changed, self.lock)

    def test_wrong_unit_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["facts"][0]["unit"] = "USD_thousand"
        with self.assertRaisesRegex(ValueError, "selected-fact unit differs"):
            subject.audit(changed, self.lock)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source differs from lock"):
            subject.audit(changed, self.lock)

    def test_bridge_rejects_bad_component(self):
        values = {
            "Net interest income": 15233, "Noninterest income": 12855,
            "Total revenue, net of interest expense": 28088,
            "Provision for credit losses": 1295, "Noninterest expense": 17337,
            "Income before income taxes": 9456, "Income tax expense": 987,
            "Net income": 8469, "Preferred stock dividends": 429,
            "Net income applicable to common shareholders": 8040,
        }
        values["Income tax expense"] += 1
        with self.assertRaisesRegex(ValueError, "net income does not reconcile"):
            subject.bridge(values)


if __name__ == "__main__":
    unittest.main()
