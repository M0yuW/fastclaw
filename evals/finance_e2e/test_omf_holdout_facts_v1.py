import copy
import json
import unittest

import audit_omf_holdout_facts_v1 as subject


class OneMainHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text(encoding="utf-8"))
        cls.lock = json.loads(subject.LOCK.read_text(encoding="utf-8"))

    def test_selected_rows_and_comparisons(self):
        result = subject.audit(self.packet, self.lock)
        self.assertEqual(result["selected_facts"], 14)
        self.assertEqual(result["monetary_deltas_usd_million"]["gaap_net_income"], 32)
        self.assertEqual(result["ratio_deltas_percentage_points"]["ci_consumer_30_plus_delinquency_ratio"], "0.38")

    def test_wrong_monetary_fact_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 1
        with self.assertRaisesRegex(ValueError, "selected GAAP row differs"):
            subject.audit(changed, self.lock)

    def test_wrong_ratio_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][-1]["value"] = 1
        with self.assertRaisesRegex(ValueError, "selected credit-ratio row differs"):
            subject.audit(changed, self.lock)

    def test_wrong_expense_normalization_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        expense = next(f for f in changed["baseline"]["facts"]
                       if f["metric"] == "gaap_provision_expense_magnitude")
        expense.pop("normalization")
        with self.assertRaisesRegex(ValueError, "selected GAAP row differs"):
            subject.audit(changed, self.lock)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source differs from lock"):
            subject.audit(changed, self.lock)


if __name__ == "__main__":
    unittest.main()
