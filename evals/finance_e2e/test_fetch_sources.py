from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from evals.finance_e2e.fetch_sources import load_manifest, verify_local_lock


class SourceManifestTest(unittest.TestCase):
    def test_repository_manifest_is_valid_and_complete(self) -> None:
        manifest = Path(__file__).with_name("sources.json")
        payload, sources = load_manifest(manifest)

        filing_sources = [source for source in sources if source.kind == "filing_artifact"]
        cross_checks = [source for source in sources if source.kind == "companyfacts"]
        self.assertEqual("fastclaw-finance-e2e-v1", payload["dataset"])
        self.assertEqual(12, len(filing_sources))
        self.assertEqual(4, len(cross_checks))
        self.assertEqual({"NVDA", "AMD", "INTC", "NKE"}, {source.symbol for source in sources})
        for symbol in {source.symbol for source in filing_sources}:
            episodes = sorted(source.episode for source in filing_sources if source.symbol == symbol)
            self.assertEqual([1, 2, 3], episodes)

    def test_manifest_rejects_non_sec_sources(self) -> None:
        payload = {
            "version": 1,
            "sources": [
                {
                    "id": "bad",
                    "company": "Example",
                    "symbol": "BAD",
                    "cik": "0000000001",
                    "episode": 1,
                    "filed_at": "2024-01-01",
                    "accession": "0000000001-24-000001",
                    "artifact": "release.htm",
                    "url": "https://example.com/release.htm",
                }
            ],
            "cross_checks": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "official SEC"):
                load_manifest(path)

    def test_verifies_cached_source_against_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "sources.json"
            payload = {
                "version": 1,
                "dataset": "fastclaw-finance-e2e-v1",
                "sources": [
                    {
                        "id": "example-episode",
                        "company": "Example Corp.",
                        "symbol": "EXM",
                        "cik": "0000000001",
                        "episode": 1,
                        "filed_at": "2024-01-01",
                        "accession": "0000000001-24-000001",
                        "artifact": "release.htm",
                        "form": "8-K",
                        "document_type": "EX-99.1",
                        "url": "https://www.sec.gov/Archives/edgar/data/1/000000000124000001/release.htm",
                    }
                ],
                "cross_checks": [],
            }
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            source_file = root / ".cache" / "sources" / "example-episode.htm"
            source_file.parent.mkdir(parents=True)
            source_file.write_bytes(b"verified source")
            lock = root / "source-lock.json"
            lock.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "dataset": "fastclaw-finance-e2e-v1",
                        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                        "entries": [
                            {
                                "id": "example-episode",
                                "kind": "filing_artifact",
                                "url": payload["sources"][0]["url"],
                                "local_path": ".cache/sources/example-episode.htm",
                                "bytes": source_file.stat().st_size,
                                "sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            verify_local_lock(manifest, lock, root)
            source_file.write_bytes(b"tampered source")
            with self.assertRaisesRegex(RuntimeError, "byte count changed|SHA-256 changed"):
                verify_local_lock(manifest, lock, root)


if __name__ == "__main__":
    unittest.main()
