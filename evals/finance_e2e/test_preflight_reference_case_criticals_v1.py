"""Reviewer-sheet membership and link fail-closed checks."""

import tempfile
import unittest
from pathlib import Path

from preflight_reference_case_criticals_v1 import SHEET, inspect


class ReferenceCaseCriticalsPreflightTests(unittest.TestCase):
    def test_exact_thirty_selected_issuers(self):
        result = inspect()
        self.assertEqual(result["issuer_count"], 30)
        self.assertTrue(result["source_ready"])
        self.assertIsNone(result["quality_pass"])

    def test_missing_or_duplicate_issuer_rejected(self):
        original = SHEET.read_text()
        line = next(x for x in original.splitlines() if x.startswith("| ADP |"))
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing.md"
            missing.write_text(original.replace(line + "\n", ""))
            with self.assertRaisesRegex(ValueError, "coverage differs"):
                inspect(sheet_path=missing, require_source_ready=False)
            duplicate = Path(temporary) / "duplicate.md"
            duplicate.write_text(original + "\n" + line + "\n")
            with self.assertRaisesRegex(ValueError, "duplicate issuer"):
                inspect(sheet_path=duplicate, require_source_ready=False)

    def test_wrong_packet_link_rejected(self):
        original = SHEET.read_text()
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "wrong-link.md"
            changed.write_text(original.replace("adp_reference_source_row_audit_v1.json",
                                                "pgr_reference_source_row_audit_v1.json"))
            with self.assertRaisesRegex(ValueError, "wrong or missing issuer packet link"):
                inspect(sheet_path=changed, require_source_ready=False)


if __name__ == "__main__":
    unittest.main()
