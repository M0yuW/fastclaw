import copy
import json
import unittest

import audit_cof_holdout_facts_v2 as subject
from fetch_sources import verify_local_lock
from selected_fact_delta_guard_v1 import derive


class CofHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_locked_discover_scope_and_signed_credit_measures(self):
        verify_local_lock(subject.MANIFEST, subject.LOCK)
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(22, result["selected_facts"])
        self.assertEqual("-8.660", result["signed_reserve_delta_usd_billion"])
        self.assertEqual("0.4", result["net_chargeoffs_delta_usd_billion"])
        rows = derive(self.packet)["rows"]
        self.assertEqual("-8.66", rows["reported_signed_loan_reserve_movement"]["delta_value"])
        self.assertEqual("0.4", rows["reported_net_charge_offs"]["delta_value"])
        self.assertEqual("13.41", rows["gaap_diluted_eps"]["delta_value"])
        self.assertEqual("0.47", rows["non_gaap_adjusted_diluted_eps"]["delta_value"])

    def test_reserve_release_cannot_be_called_a_build(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "reported_signed_loan_reserve_movement")["value"] = 0.760
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_net_chargeoffs_cannot_be_replaced_by_provision(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "reported_net_charge_offs")["value"] = 2.7
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_adjusted_eps_cannot_replace_negative_gaap_eps(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["baseline"]["facts"]
             if f["metric"] == "gaap_diluted_eps")["value"] = 5.48
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_source_hash_change_is_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["event"]["source_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)


if __name__ == "__main__":
    unittest.main()
