import copy
import json
import unittest

import audit_stt_holdout_facts_v2 as subject


class SttHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_selected_rows_comparators_and_residual(self):
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(12, result["selected_facts"])
        self.assertEqual(6, result["q2_cross_filing_comparators"])
        self.assertEqual(1, result["revenue_mix_unlisted_residual_usd_million"])

    def test_wrong_selected_value_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["value"] = 2828
        with self.assertRaisesRegex(ValueError, "selected definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_wrong_row_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["source_row"] = "Net interest income"
        with self.assertRaisesRegex(ValueError, "selected definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "filing/source differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_summary_parser_rejects_wrong_period(self):
        rows = [["(Table presents summary results, dollars in millions)", "3Q24", "2Q24"],
                ["Total revenue", "3,545", "3,448", "3,259"]]
        with self.assertRaisesRegex(ValueError, "summary quarter header differs"):
            subject._summary_cells(rows, "Total revenue", "3Q25", "2Q25")


if __name__ == "__main__":
    unittest.main()
