import copy
import json
import unittest

import audit_wu_holdout_facts_v2 as subject
from fetch_sources import verify_local_lock
from selected_fact_delta_guard_v1 import derive


class WuHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_gaap_actual_quarter_bridge_and_units(self):
        verify_local_lock(subject.MANIFEST, subject.LOCK)
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(22, result["selected_facts"])
        self.assertEqual("17.5", result["net_income_delta_usd_million"])
        rows = derive(self.packet)["rows"]
        self.assertEqual("USD_million", rows["gaap_revenues"]["delta_unit"])
        self.assertEqual("USD_per_share", rows["gaap_diluted_eps"]["delta_unit"])
        self.assertEqual("million_shares", rows["gaap_weighted_average_diluted_shares"]["delta_unit"])

    def test_full_year_outlook_cannot_replace_actual_revenue(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "gaap_revenues")["value"] = 4085
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_ytd_net_income_cannot_replace_quarter(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "gaap_net_income")["value"] = 385.2
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_signed_other_expense_cannot_be_flipped(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "gaap_total_other_expense_net_signed")["value"] = 34.3
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_wrong_source_hash_is_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["event"]["source_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)


if __name__ == "__main__":
    unittest.main()
