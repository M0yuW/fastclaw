import copy
import json
import unittest

import audit_schw_holdout_facts_v2 as subject
from fetch_sources import ROOT, verify_local_lock
from sec_html_rows import extract_rows
from selected_fact_delta_guard_v1 import decompose_change, derive


class SchwHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_gaap_source_and_revenue_common_bridges(self):
        verify_local_lock(subject.MANIFEST, subject.LOCK)
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(30, result["selected_facts"])
        self.assertEqual(12, result["q2_cross_filing_comparators"])
        delta = derive(self.packet)
        mix = decompose_change(delta, "gaap_total_net_revenues",
                               list(subject.REVENUE_COMPONENTS))
        self.assertEqual("0", mix["unlisted_residual_usd_million"])
        self.assertEqual("300", delta["rows"]["gaap_net_income_available_to_common"]["delta_value"])
        self.assertEqual("234", delta["rows"]["non_gaap_adjusted_net_income"]["delta_value"])

    def test_yoy_headline_cannot_replace_sequential_revenue(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "gaap_total_net_revenues")["value"] = 27
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_adjusted_income_cannot_replace_gaap_net_income(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "gaap_net_income")["value"] = 2456
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_q3_exhibit_q2_comparator_change_is_rejected(self):
        rows = extract_rows(ROOT / ".cache/sources/HOLDOUT-SCHW-EVENT-v1.htm")
        rows[67] = ["5,850" if cell == "5,851" else cell for cell in rows[67]]
        with self.assertRaisesRegex(ValueError, "Q2 comparator"):
            subject._cross_filing_q2(rows)

    def test_wrong_source_hash_is_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["event"]["source_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)


if __name__ == "__main__":
    unittest.main()
