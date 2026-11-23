import tempfile
import unittest
from pathlib import Path

import discover_postcorrection_sec_sources_v2 as subject


class PostcorrectionSourceDiscoveryTests(unittest.TestCase):
    def test_targets_are_only_selected_issuers_without_archived_sources(self):
        targets = subject.selected_targets()
        self.assertEqual(set(subject.TARGETS), set(targets))
        self.assertEqual("0000072971", targets["WFC"])

    def test_contact_and_rate_are_checked_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "new"
            with self.assertRaisesRegex(ValueError, "contact identifier"):
                subject.discover(target, "")
            with self.assertRaisesRegex(ValueError, "interval"):
                subject.discover(target, "Researcher contact@example.com", 0.01)
            self.assertFalse(target.exists())

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            (target / "existing.txt").write_text("preserve")
            with self.assertRaisesRegex(ValueError, "refusing overwrite"):
                subject.discover(target, "Researcher contact@example.com")
            self.assertEqual("preserve", (target / "existing.txt").read_text())


if __name__ == "__main__":
    unittest.main()
