#!/usr/bin/env python3
"""Read-only integrity check of the remaining 16 issuer SEC discovery cache."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from verify_postcorrection_unseen_candidates_v4 import verify


HERE = Path(__file__).parent
ROOT = HERE / "results/2026-10-24-postcorrection-v4-remaining16-discovery"
MANIFEST = ROOT / "manifest.json"
EXISTING = {"HBAN", "PAYO", "VRSK", "NTRS"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_path(relative: str, digest: str) -> None:
    path = (ROOT / relative).resolve()
    if ROOT.resolve() not in path.parents or not path.is_file():
        raise ValueError(f"discovery raw path missing or escaped: {relative}")
    if sha(path) != digest:
        raise ValueError(f"discovery raw SHA-256 differs: {relative}")


def verify_discovery() -> dict:
    expected = {symbol for group in verify()["selected_by_stratum"].values()
                for symbol in group} - EXISTING
    data = json.loads(MANIFEST.read_text())
    if (data.get("version") != 4 or data.get("model_observations") != 0
            or not expected or len(data.get("issuers", [])) != len(expected)):
        raise ValueError("unexpected discovery manifest")
    seen = set()
    unique_exhibit = 0
    exception = []
    checked_files = 0
    for issuer in data["issuers"]:
        symbol = issuer["symbol"]
        if symbol in seen or symbol not in expected:
            raise ValueError("discovery issuer set differs")
        seen.add(symbol)
        check_path(issuer["submissions_path"], issuer["submissions_sha256"])
        checked_files += 1
        for shard in issuer["shards"]:
            check_path(shard["path"], shard["sha256"])
            checked_files += 1
        if len(issuer["candidate_filings"]) != 4:
            raise ValueError(f"{symbol} did not retain four filings")
        for filing in issuer["candidate_filings"]:
            check_path(filing["index_path"], filing["index_sha256"])
            checked_files += 1
            if filing["status"] == "one_ex99_1":
                if len(filing["ex99_1_urls"]) != 1:
                    raise ValueError("one-exhibit status disagrees with URLs")
                unique_exhibit += 1
            elif filing["status"] == "no_ex99_1" and not filing["ex99_1_urls"]:
                exception.append([symbol, filing["accession"]])
            else:
                raise ValueError("ambiguous or invalid EX-99.1 status")
            for url in filing["ex99_1_urls"]:
                parsed = urlparse(url)
                fragment = (f"/Archives/edgar/data/{int(issuer['cik'])}/"
                            f"{filing['accession'].replace('-', '')}/")
                if (parsed.scheme != "https" or parsed.hostname != "www.sec.gov"
                        or not parsed.path.startswith(fragment)):
                    raise ValueError("exhibit URL does not match filing identity")
    if seen != expected or len(exception) != 2 or any(row[0] != "SPGI" for row in exception):
        raise ValueError("discovery coverage or expected exceptions differ")
    return {"status": "v4_remaining16_public_sec_indexes_hash_verified_only",
            "issuers": len(seen), "filing_indexes": 64,
            "raw_files_verified": checked_files,
            "single_ex99_1_filings": unique_exhibit,
            "spgi_no_ex99_1_filings": exception,
            "model_observations": 0}


if __name__ == "__main__":
    print(json.dumps(verify_discovery(), indent=2))
