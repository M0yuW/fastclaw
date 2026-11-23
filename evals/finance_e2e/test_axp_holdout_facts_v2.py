import copy
import json
import unittest

import audit_axp_holdout_facts_v2 as subject
from selected_fact_delta_guard_v1 import derive


class AxpHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())

    def test_selected_rows_and_distinct_units(self):
        result = subject.audit(self.packet, self.lock)
        self.assertEqual(12, result["selected_facts"])
        self.assertEqual("570", result["comparisons"]["gaap_total_revenues_net_of_interest_expense"])
        self.assertEqual("0.06", result["comparisons"]["gaap_diluted_eps"])
        self.assertEqual("percentage_points", result["ratio_delta_unit"])
        self.assertEqual("USD_billion", derive(self.packet)["rows"]["reported_billed_business"]["delta_unit"])

    def test_wrong_value_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 999
        with self.assertRaisesRegex(ValueError, "SEC value or unit differs"):
            subject.audit(changed, self.lock)

    def test_wrong_metric_unit_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][3]["unit"] = "USD_million_rounded"
        with self.assertRaisesRegex(ValueError, "SEC value or unit differs"):
            subject.audit(changed, self.lock)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source differs from lock"):
            subject.audit(changed, self.lock)


if __name__ == "__main__":
    unittest.main()
