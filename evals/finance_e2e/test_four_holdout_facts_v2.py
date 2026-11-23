import copy
import json
import unittest
from decimal import Decimal

import audit_four_holdout_facts_v2 as subject
from fetch_sources import ROOT, verify_local_lock
from financial_evidence_bundle_v1 import check_adjacent_quarters
from sec_html_blocks import extract_blocks
from selected_fact_delta_guard_v1 import derive


class FourHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_adjacent_cross_year_appendices_and_bridges(self):
        verify_local_lock(subject.MANIFEST, subject.LOCK)
        check_adjacent_quarters(self.packet["baseline"]["period"],
                                self.packet["event"]["period"])
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(26, result["selected_facts"])
        self.assertTrue(result["adjusted_income_definition_change_checked"])
        rows = derive(self.packet)["rows"]
        self.assertEqual("-38.7", rows["gaap_gross_revenue"]["delta_value"])
        self.assertEqual("-36.5", rows["non_gaap_gross_revenue_less_network_fees"]["delta_value"])
        self.assertEqual("-99.3", rows["gaap_net_income_attributable_to_shift4"]["delta_value"])

    def test_old_and_revised_adjusted_net_income_are_not_same_basis(self):
        old = subject._one_block(
            extract_blocks(ROOT / ".cache/sources/HOLDOUT-FOUR-BASELINE-v1.htm"),
            "Fourth Quarter of 2024 Reconciliations of Net Income to")
        new = subject._one_block(
            extract_blocks(ROOT / ".cache/sources/HOLDOUT-FOUR-EVENT-v1.htm"),
            "First Quarter of 2025 Reconciliations of Net Income to")
        self.assertEqual(Decimal("123.4"),
                         subject._adjusted_last(old, "ADJUSTED NET INCOME")[-1])
        self.assertEqual([Decimal("154.4"), Decimal("98.6")],
                         subject._adjusted_last(new, "ADJUSTED NET INCOME")[-2:])
        self.assertNotIn("non_gaap_adjusted_net_income",
                         {fact["metric"] for fact in self.packet["event"]["facts"]})

    def test_annual_revenue_cannot_replace_standalone_quarter(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["baseline"]["facts"]
             if f["metric"] == "gaap_gross_revenue")["value"] = 3330.6
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_non_gaap_grlnf_cannot_replace_gaap_gross_revenue(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "gaap_gross_revenue")["value"] = 368.5
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_source_hash_change_is_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["event"]["source_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)


if __name__ == "__main__":
    unittest.main()
