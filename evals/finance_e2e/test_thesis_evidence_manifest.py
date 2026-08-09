from __future__ import annotations

import copy
import unittest

from evals.finance_e2e.thesis_evidence_manifest import ROOT, build_manifest, verify


class ThesisEvidenceManifestTest(unittest.TestCase):
    def test_current_manifest_verifies(self) -> None:
        verify(build_manifest())

    def test_hash_drift_fails(self) -> None:
        manifest = copy.deepcopy(build_manifest())
        manifest["groups"][0]["files"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash drift"):
            verify(manifest, ROOT)

    def test_status_mixing_fails(self) -> None:
        manifest = copy.deepcopy(build_manifest())
        manifest["groups"][0]["files"][0]["path"] = "calibration.json"
        with self.assertRaisesRegex(ValueError, "status mixing"):
            verify(manifest, ROOT)

    def test_missing_file_fails(self) -> None:
        manifest = copy.deepcopy(build_manifest())
        manifest["groups"][-1]["files"][0]["path"] = "evals/does-not-exist.json"
        with self.assertRaisesRegex(ValueError, "missing thesis evidence"):
            verify(manifest, ROOT)


if __name__ == "__main__":
    unittest.main()
