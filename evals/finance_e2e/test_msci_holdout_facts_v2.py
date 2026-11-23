import copy
import json
import unittest

import audit_msci_holdout_facts_v2 as subject
from selected_fact_delta_guard_v1 import decompose_change, derive


class MsciHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_standalone_quarter_rows_and_income_bridges(self):
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(18, result["selected_facts"])
        self.assertEqual(20747, result["revenue_delta_usd_thousand"])
        self.assertEqual(21736, result["net_income_delta_usd_thousand"])

    def test_unit_guard_preserves_thousands_and_per_share(self):
        rows = derive(self.packet)["rows"]
        self.assertEqual("USD_thousand", rows["gaap_operating_revenues"]["delta_unit"])
        self.assertEqual("thousand_shares", rows["diluted_weighted_average_shares"]["delta_unit"])
        self.assertEqual("USD_per_share", rows["gaap_diluted_eps"]["delta_unit"])
        with self.assertRaisesRegex(ValueError, "needs USD million levels"):
            decompose_change(derive(self.packet), "gaap_operating_income",
                             ["gaap_operating_revenues"])

    def test_ytd_value_cannot_replace_current_quarter(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 2311931
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_million_unit_cannot_replace_thousand_unit(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["unit"] = "USD_million_rounded"
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "filing/source differs"):
            subject.audit(changed, self.lock, self.manifest)


if __name__ == "__main__":
    unittest.main()
