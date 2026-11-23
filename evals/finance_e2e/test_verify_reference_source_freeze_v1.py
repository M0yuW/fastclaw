"""Freeze manifest must fail closed on packet or sheet drift."""

import json
import tempfile
import unittest
from pathlib import Path

from verify_reference_source_freeze_v1 import MANIFEST, verify


class ReferenceSourceFreezeTests(unittest.TestCase):
    def test_frozen_source_and_case_sheet_verify(self):
        result = verify()
        self.assertEqual(result["counts"]["issuers"], 30)
        self.assertEqual(result["counts"]["comparable_rows"], 523)
        self.assertFalse(result["paid_run_authorized"])

    def test_packet_hash_and_case_sheet_hash_mutations_rejected(self):
        original = json.loads(MANIFEST.read_text())
        for field, entry in (("packets", "WAL"), ("files", "case_sheet")):
            altered = json.loads(json.dumps(original))
            altered[field][entry]["sha256"] = "0" * 64
            with tempfile.TemporaryDirectory() as temporary:
                changed = Path(temporary) / "changed.json"
                changed.write_text(json.dumps(altered))
                with self.assertRaises(ValueError):
                    verify(changed)

    def test_paid_authorization_cannot_be_smuggled_into_source_freeze(self):
        altered = json.loads(MANIFEST.read_text())
        altered["paid_run_authorized"] = True
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "authorized.json"
            changed.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, "freeze status invalid"):
                verify(changed)


if __name__ == "__main__":
    unittest.main()
