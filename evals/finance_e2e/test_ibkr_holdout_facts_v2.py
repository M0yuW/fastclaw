import copy
import json
import unittest
from decimal import Decimal

import audit_ibkr_holdout_facts_v2 as subject
from fetch_sources import ROOT, verify_local_lock
from sec_html_rows import extract_rows
from selected_fact_delta_guard_v1 import decompose_change, derive


class IbkrHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_consolidated_to_common_source_bridge(self):
        verify_local_lock(subject.MANIFEST, subject.LOCK)
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(26, result["selected_facts"])
        self.assertEqual(180, result["consolidated_net_delta_usd_million"])
        self.assertEqual(39, result["common_available_delta_usd_million"])
        delta = derive(self.packet)
        self.assertEqual("0", decompose_change(
            delta, "gaap_total_net_revenues",
            list(subject.REVENUE_COMPONENTS))["unlisted_residual_usd_million"])
        self.assertEqual("0", decompose_change(
            delta, "gaap_total_noninterest_income",
            list(subject.NONINTEREST_COMPONENTS))["unlisted_residual_usd_million"])

    def test_consolidated_net_cannot_replace_common_available_income(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "gaap_net_income_available_common")["value"] = 1186
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_ytd_total_cannot_replace_standalone_quarter(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "gaap_total_net_revenues")["value"] = 4562
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_q2_one_time_credit_disclosure_is_checked(self):
        rows = extract_rows(ROOT / ".cache/sources/HOLDOUT-IBKR-BASELINE-v1.htm")
        self.assertIn("approximately $26 million one-time credit", rows[1][1])
        self.assertEqual(Decimal(860), subject._current_cell(rows, "Total net interest income", "statement", "June 30,"))

    def test_wrong_source_hash_is_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["event"]["source_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)


if __name__ == "__main__":
    unittest.main()
