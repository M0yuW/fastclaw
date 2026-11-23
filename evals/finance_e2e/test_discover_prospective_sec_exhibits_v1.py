import unittest

from discover_prospective_sec_exhibits_v1 import exhibit_urls
from rank_prospective_cross_workflow_v1 import ROOT


class SecExhibitDiscoveryTests(unittest.TestCase):
    def test_actual_gs_filing_index_identifies_ex991(self):
        source = (ROOT / "source_snapshots/gs-2025-q3-filing-index.html").read_text()
        self.assertEqual(exhibit_urls(source, "0001193125-25-238058", "0000886982"), [
            "https://www.sec.gov/Archives/edgar/data/886982/000119312525238058/d899312dex991.htm"])

    def test_mismatched_accession_cannot_be_accepted(self):
        source = (ROOT / "source_snapshots/gs-2025-q3-filing-index.html").read_text()
        self.assertEqual(exhibit_urls(source, "0001193125-25-159560", "0000886982"), [])

    def test_non_sec_link_cannot_be_accepted(self):
        source = '<tr><td>EX-99.1</td><td><a href="https://elsewhere.test/file.htm">x</a></td></tr>'
        self.assertEqual(exhibit_urls(source, "0001193125-25-238058", "0000886982"), [])


if __name__ == "__main__":
    unittest.main()
