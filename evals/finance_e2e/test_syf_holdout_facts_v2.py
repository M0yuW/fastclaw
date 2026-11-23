import copy
import json
import unittest

import audit_syf_holdout_facts_v2 as subject
from fetch_sources import verify_local_lock
from selected_fact_delta_guard_v1 import derive


class SyfHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_locked_narrative_cells_match_and_units_remain_distinct(self):
        verify_local_lock(subject.MANIFEST, subject.LOCK)
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(16, result["selected_facts"])
        rows = derive(self.packet)["rows"]
        self.assertEqual("-0.1", rows["reported_purchase_volume"]["delta_value"])
        self.assertEqual("million_accounts", rows["reported_average_active_accounts"]["delta_unit"])
        self.assertEqual("percentage_points",
                         rows["reported_30_plus_delinquency_period_end_ratio"]["delta_unit"])
        self.assertEqual("0.21", rows["reported_30_plus_delinquency_period_end_ratio"]["delta_value"])
        self.assertEqual("-0.54", rows["reported_net_charge_off_average_receivables_ratio"]["delta_value"])

    def test_sequential_purchase_level_cannot_be_replaced_by_year_over_year_growth(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "reported_purchase_volume")["value"] = 2
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_credit_rate_denominators_cannot_be_swapped(self):
        packet = copy.deepcopy(self.packet)
        next(f for f in packet["event"]["facts"]
             if f["metric"] == "reported_net_charge_off_average_receivables_ratio"
             )["source_row"] = "Loans 30+ days past due as a percentage of total period-end loan receivables"
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)

    def test_ambiguous_narrative_block_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            subject._source_number(
                ["•Purchase volume decreased 2% to $46.1 billion"] * 2,
                "•Purchase volume", subject.EXPECTED["reported_purchase_volume"][5])

    def test_source_hash_change_is_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["baseline"]["source_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            subject.audit(packet, self.lock, self.manifest)


if __name__ == "__main__":
    unittest.main()
