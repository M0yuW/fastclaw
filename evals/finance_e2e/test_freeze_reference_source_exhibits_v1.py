"""No-network checks for SEC source-artifact freeze boundaries."""

import json
import unittest

from discover_reference_source_frame_v1 import HERE
from freeze_reference_source_exhibits_v1 import validate_candidate


DISCOVERY = HERE / "results/2026-10-25-reference-source-distinct-sec-discovery-pilot-v2/manifest.json"


class ReferenceSourceFreezeTests(unittest.TestCase):
    def test_all_pilot_candidates_use_expected_sec_accession(self):
        discovery = json.loads(DISCOVERY.read_text())
        self.assertEqual(len(discovery["issuers"]), 4)
        for issuer in discovery["issuers"]:
            for period, group in issuer["windows"].items():
                with self.subTest(symbol=issuer["symbol"], period=period):
                    self.assertEqual(len(group["candidates"]), 1)
                    url, filename = validate_candidate(
                        issuer, period, group["candidates"][0])
                    self.assertTrue(url.startswith("https://www.sec.gov/Archives/"))
                    self.assertTrue(filename.endswith(".htm"))

    def test_all_remaining_candidates_have_sec_accession_bound_urls(self):
        remaining = (DISCOVERY.parent.parent
                     / "2026-10-25-reference-source-distinct-sec-discovery-remaining-v1"
                     / "manifest.json")
        discovery = json.loads(remaining.read_text())
        self.assertEqual(len(discovery["issuers"]), 26)
        for issuer in discovery["issuers"]:
            for period, group in issuer["windows"].items():
                self.assertTrue(group["candidates"])
                for candidate in group["candidates"]:
                    with self.subTest(symbol=issuer["symbol"], period=period,
                                      accession=candidate["accession"]):
                        validate_candidate(issuer, period, candidate)

    def test_rejects_non_sec_host(self):
        discovery = json.loads(DISCOVERY.read_text())
        issuer = discovery["issuers"][0]
        candidate = dict(issuer["windows"]["CY2025_Q2"]["candidates"][0])
        candidate["ex99_candidate_urls"] = [
            "https://example.com" + candidate["ex99_candidate_urls"][0].split(
                "www.sec.gov", 1)[1]]
        with self.assertRaisesRegex(ValueError, "SEC accession"):
            validate_candidate(issuer, "CY2025_Q2", candidate)


if __name__ == "__main__":
    unittest.main()
