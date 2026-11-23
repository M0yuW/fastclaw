import unittest

from discover_prospective_sec_submissions_v1 import (
    earnings_candidates, matching_shards, records_from_arrays,
)


class SecSubmissionDiscoveryTests(unittest.TestCase):
    def test_array_shape_rejects_missing_or_unequal_fields(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            records_from_arrays({"form": ["8-K"]})
        arrays = {field: ["x"] for field in
                  ("accessionNumber", "filingDate", "form", "items", "primaryDocument")}
        arrays["items"] = []
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            records_from_arrays(arrays)

    def test_item_202_filter_cutoff_order_and_dedup(self):
        records = [
            {"accessionNumber": "a", "filingDate": "2025-10-14", "form": "8-K",
             "items": "2.02,7.01,9.01", "primaryDocument": "a.htm"},
            {"accessionNumber": "a", "filingDate": "2025-10-14", "form": "8-K",
             "items": "2.02,7.01,9.01", "primaryDocument": "a.htm"},
            {"accessionNumber": "b", "filingDate": "2025-07-16", "form": "8-K/A",
             "items": "2.02,9.01", "primaryDocument": "b.htm"},
            {"accessionNumber": "c", "filingDate": "2025-09-01", "form": "8-K",
             "items": "9.01", "primaryDocument": "c.htm"},
            {"accessionNumber": "d", "filingDate": "2026-01-01", "form": "8-K",
             "items": "2.02", "primaryDocument": "d.htm"},
        ]
        result = earnings_candidates(records, "2025-01-01", "2025-12-31")
        self.assertEqual([entry["accessionNumber"] for entry in result], ["a", "b"])

    def test_historical_shards_cover_requested_window_only(self):
        root = {"filings": {"files": [
            {"name": "one.json", "filingFrom": "2025-08-01", "filingTo": "2025-10-20"},
            {"name": "two.json", "filingFrom": "2024-12-01", "filingTo": "2025-02-01"},
            {"name": "old.json", "filingFrom": "2024-01-01", "filingTo": "2024-11-30"},
        ]}}
        self.assertEqual(matching_shards(root, "2025-01-01", "2025-12-31"),
                         ["one.json", "two.json"])


if __name__ == "__main__":
    unittest.main()
