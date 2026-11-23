import copy
import json
import unittest

import audit_ally_holdout_facts_v2 as subject


class AllyHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_selected_rows_comparators_and_gaap_bridges(self):
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(16, result["selected_facts"])
        self.assertEqual(8, result["q2_cross_filing_comparators"])
        self.assertEqual(86, result["revenue_delta_usd_million"])
        self.assertEqual(77, result["pretax_delta_usd_million"])

    def test_wrong_selected_value_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 2169
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_wrong_unit_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][-1]["unit"] = "USD_million_rounded"
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_non_gaap_row_substitution_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["source_row"] = "Adjusted Total Net Revenue1"
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source/filing identity differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_source_row_parser_requires_quarter_header(self):
        rows = [["($ millions except per share data)", "2024"],
                ["GAAP Total Net Revenue", "$", "2,168", "$", "2,082", "$", "2,135"]]
        with self.assertRaisesRegex(ValueError, "quarter header mismatch"):
            subject._first_three_cells(rows, "GAAP Total Net Revenue", "3Q 25", "2Q 25")


if __name__ == "__main__":
    unittest.main()
