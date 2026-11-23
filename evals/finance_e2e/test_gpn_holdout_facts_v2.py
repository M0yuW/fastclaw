import copy
import json
import unittest

import audit_gpn_holdout_facts_v2 as subject
from fetch_sources import verify_local_lock
from selected_fact_delta_guard_v1 import derive


class GpnHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_current_quarter_source_cells_and_signed_gaap_bridges(self):
        verify_local_lock(subject.MANIFEST, subject.LOCK)
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(22, result["selected_facts"])
        self.assertEqual(350808, result["gaap_operating_delta_usd_thousand"])
        self.assertEqual(343624, result["disposition_gain_delta_usd_thousand"])
        self.assertEqual(40080, result["non_gaap_adjusted_operating_delta_usd_thousand"])
        delta = derive(self.packet)
        self.assertEqual("USD_thousand", delta["rows"]["gaap_operating_income"]["delta_unit"])

    def test_q3_disposition_gain_sign_cannot_be_flipped(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "gaap_disposition_gain_as_negative_expense")["value"] = 343891
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_adjusted_cannot_replace_gaap_operating_income(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "gaap_operating_income")["value"] = 1092829
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_ytd_number_cannot_replace_standalone_quarter(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "gaap_revenues")["value"] = 5773071
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_wrong_source_hash_is_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["event"]["source_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)


if __name__ == "__main__":
    unittest.main()
