import copy
import json
import unittest

import audit_jpm_holdout_facts_v2 as subject


class JpmHoldoutFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(subject.PACKET.read_text())
        cls.lock = json.loads(subject.LOCK.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_firmwide_rows_and_q2_cross_filing_comparators(self):
        result = subject.audit(self.packet, self.lock, self.manifest)
        self.assertEqual(12, result["selected_facts"])
        self.assertEqual(6, result["q2_cross_filing_comparators"])
        self.assertEqual(1515, result["reported_revenue_delta_usd_million"])
        self.assertEqual(-594, result["net_income_delta_usd_million"])

    def test_managed_revenue_cannot_replace_reported_revenue(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][0]["source_row"] = "Net revenue - managed"
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_wrong_eps_unit_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["event"]["facts"][-1]["unit"] = "USD_million_rounded"
        with self.assertRaisesRegex(ValueError, "selected fact definition differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_wrong_source_hash_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["baseline"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "filing/source differs"):
            subject.audit(changed, self.lock, self.manifest)

    def test_header_parser_rejects_reversed_quarters(self):
        rows = [["Results for JPM"],
                ["($ millions, except per share data)", "2Q25", "3Q25"],
                ["Net revenue - reported", "46,427", "44,912", "42,654"]]
        with self.assertRaisesRegex(ValueError, "current/prior quarter header differs"):
            subject._firmwide_cells(rows, "Net revenue - reported", "3Q25", "2Q25")


if __name__ == "__main__":
    unittest.main()
