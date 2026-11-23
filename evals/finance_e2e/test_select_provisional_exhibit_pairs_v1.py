import json
import unittest

from select_provisional_exhibit_pairs_v1 import EXHIBITS, choose_pair, select


class ProvisionalPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exhibits = json.loads(EXHIBITS.read_text(encoding="utf-8"))

    def test_all_twenty_get_a_provisional_pair(self):
        result = select(self.exhibits)
        self.assertEqual(len(result["issuers"]), 20)

    def test_four_skips_missing_q2_ex991(self):
        result = select(self.exhibits)
        four = next(item for item in result["issuers"] if item["ticker"] == "FOUR")
        self.assertEqual((four["baseline"]["filed_at"], four["event"]["filed_at"]),
                         ("2025-02-18", "2025-04-29"))

    def test_no_usable_pair_fails(self):
        with self.assertRaisesRegex(ValueError, "no EX-99.1 filing pair"):
            choose_pair([{"filing_date": "2025-08-05", "accession": "x", "ex99_1_urls": []}])


if __name__ == "__main__":
    unittest.main()
