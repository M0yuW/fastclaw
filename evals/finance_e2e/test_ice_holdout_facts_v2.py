import copy
import json
import unittest

import audit_ice_holdout_facts_v2 as subject


class IceHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_standalone_quarter_rows_and_bridges(self):
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(16, result["selected_facts"])
        self.assertEqual(-255, result["gross_revenue_delta_usd_million"])
        self.assertEqual(-132, result["net_revenue_delta_usd_million"])

    def test_ytd_value_cannot_replace_current_quarter(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 6118
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_wrong_source_row_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["source_row"] = "Adjusted operating income"
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "filing/source differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_standalone_parser_requires_four_year_columns(self):
        rows = [["", "Six Months Ended June 30,", "Three Months Ended June 30,"],
                ["", "2025", "2024", "2024", "2025"],
                ["Exchanges", "4,257", "3,560", "2,134", "1,826"]]
        with self.assertRaisesRegex(ValueError, "year header differs"):
            subject._current_quarter_value(rows, "Exchanges", "June 30,", "Six")


if __name__ == "__main__":
    unittest.main()
