import copy
import json
import unittest

import audit_ndaq_holdout_facts_v2 as subject


class NdaqHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_gaap_gross_net_and_operating_bridges(self):
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(18, result["selected_facts"])
        self.assertEqual(-132, result["gross_delta_usd_million"])
        self.assertEqual(9, result["net_delta_usd_million"])
        self.assertEqual(-141, result["implied_transaction_expense_delta_usd_million"])

    def test_ytd_value_cannot_replace_quarter(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 1588
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_non_gaap_row_substitution_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][5]["source_row"] = "Non-GAAP revenues"
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "filing/source differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_standalone_parser_rejects_wrong_quarter(self):
        rows = [["", "Three Months Ended", "Nine Months Ended"],
                ["", "September 30,2024", "September 30,2025",
                 "September 30,2025", "September 30,2024"],
                ["Total revenues", "1,958", "1,902", "6,138", "5,370"]]
        with self.assertRaisesRegex(ValueError, "current-year column differs"):
            subject._current_quarter_value(rows, "Total revenues", "September 30,2025", "Nine")


if __name__ == "__main__":
    unittest.main()
