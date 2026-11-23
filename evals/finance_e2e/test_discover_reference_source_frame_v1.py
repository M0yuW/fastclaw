"""No-network checks for frozen-frame SEC candidate selection."""

import json
import unittest

from discover_reference_source_frame_v1 import (
    FRAME, MAX_INDEXES_PER_WINDOW, discover, earnings_exhibit_urls,
    first_reserve_for, planned, select_candidates,
)


def filing(date, accession, items="2.02"):
    return {"filingDate": date, "accessionNumber": accession,
            "form": "8-K", "items": items, "primaryDocument": "x.htm"}


class ReferenceSourceDiscoveryTests(unittest.TestCase):
    def test_frozen_frame_has_thirty_distinct_planned_issuers(self):
        frame = json.loads(FRAME.read_text())
        self.assertEqual(frame["planned_issuers"], 30)
        self.assertEqual(len(planned(frame)), 30)
        self.assertEqual(set(planned(frame)), {
            item["ticker"] for group in frame["strata"].values()
            for item in group["planned"]})

    def test_windows_only_select_earnings_filings_and_mark_truncation(self):
        records = [filing("2025-07-17", "a"),
                   filing("2025-08-01", "b"),
                   filing("2025-10-17", "c"),
                   filing("2025-10-20", "d"),
                   filing("2025-10-21", "e"),
                   filing("2025-10-22", "f"),
                   filing("2025-10-23", "g", "5.02")]
        selected = select_candidates(records)
        self.assertEqual(selected["CY2025_Q2"]["total_item_2_02_filings_in_window"], 2)
        self.assertEqual(selected["CY2025_Q3"]["total_item_2_02_filings_in_window"], 4)
        self.assertEqual(len(selected["CY2025_Q3"]["selected_filings"]),
                         MAX_INDEXES_PER_WINDOW)
        self.assertTrue(selected["CY2025_Q3"]["truncated"])
        self.assertFalse(selected["CY2025_Q2"]["truncated"])

    def test_rejects_symbol_outside_frozen_planned_frame_before_network(self):
        with self.assertRaisesRegex(ValueError, "planned frame issuers"):
            discover(FRAME.parent / "not-used", ["NOT_IN_FRAME"],
                     "Research contact example@example.com")

    def test_both_sec_exhibit_type_conventions(self):
        accession = "0000008670-25-000026"
        prefix = "/Archives/edgar/data/8670/000000867025000026/"
        source = (
            '<tr><td>EXHIBIT 99</td><td><a href="' + prefix +
            'q4fy25exhibit99.htm">release</a></td><td>EX-99</td></tr>'
            '<tr><td>EX-99.1</td><td><a href="' + prefix +
            'other.htm">release</a></td><td>EX-99.1</td></tr>'
            '<tr><td>EX-99</td><td><a href="https://evil.example/other.htm">'
            'wrong host</a></td><td>EX-99</td></tr>'
        )
        urls = earnings_exhibit_urls(source, accession, "8670")
        self.assertEqual(urls, ["https://www.sec.gov" + prefix + name
                                for name in ("other.htm", "q4fy25exhibit99.htm")])

    def test_payx_replacement_is_first_same_stratum_reserve(self):
        frame = json.loads(FRAME.read_text())
        stratum, entry = first_reserve_for(frame, "PAYX")
        self.assertEqual(stratum, "payments_and_fintech")
        self.assertEqual(entry["ticker"], "BILL")
        with self.assertRaisesRegex(ValueError, "next frozen"):
            discover(FRAME.parent / "not-used", ["EEFT"],
                     "Research contact example@example.com", reserve_for="PAYX")


if __name__ == "__main__":
    unittest.main()
