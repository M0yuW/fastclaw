import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import audit_postcorrection_v4_source_identity as auditor  # noqa: E402


class V4SourceIdentityTests(unittest.TestCase):
    def wex_baseline(self):
        entry = next(x for x in json.loads((auditor.WEX /
            "manifest.json").read_text())["entries"] if x["role"] == "baseline")
        return {**entry, "symbol_cik": "0001309108"}

    def test_complete_twenty_pair_coverage(self):
        result = auditor.audit()
        self.assertEqual(result["issuer_pairs"], 20)
        self.assertEqual(result["primary_exhibits"], 40)
        self.assertEqual(result["navi_detailed_exhibits"], 2)
        self.assertEqual(result["numeric_row_audits_complete"], 20)
        self.assertEqual(result["numeric_row_audited_symbols"],
                         ["C", "CPAY", "EVTC", "FDS", "FITB", "FLYW", "HBAN", "LPLA", "MKTX", "NAVI", "NTRS", "RELY", "RKT", "SEIC", "SPGI", "TFC", "TRU", "USB", "VRSK", "WEX"])
        self.assertEqual(result["model_observations"], 0)

    def test_wrong_source_hash_rejected(self):
        entry = self.wex_baseline()
        entry["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source byte identity differs"):
            auditor.audit_source(entry, auditor.WEX, "Second Quarter")

    def test_wrong_quarter_title_rejected(self):
        entry = self.wex_baseline()
        with self.assertRaisesRegex(ValueError, "expected quarterly title absent"):
            auditor.audit_source(entry, auditor.WEX,
                                 r"Third Quarter 2025 Financial Results")


if __name__ == "__main__":
    unittest.main()
