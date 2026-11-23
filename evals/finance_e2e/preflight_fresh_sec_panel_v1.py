#!/usr/bin/env python3
"""Read-only, no-model preflight for the forward-looking SEC case corpus."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CORPUS = HERE / "fresh_sec_panel_v1.json"
EXPECTED_CASES = {"FRESH-AAPL-TAX", "FRESH-MSFT-CLOUD", "FRESH-SBUX-TRAFFIC"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    corpus = json.loads(CORPUS.read_text())
    cases = corpus["cases"]
    assert corpus["status"] == "source_facts_frozen_before_model_runs"
    assert {case["case_id"] for case in cases} == EXPECTED_CASES
    assert len(cases) == len(EXPECTED_CASES)
    seen = set()
    sources = []
    for case in cases:
        assert case["workflow"] == "sec_event_to_thesis_review"
        assert case["precommitted_checks"]
        for period in ("baseline", "event"):
            item = case[period]
            path = HERE / item["local_path"]
            assert path.is_file(), path
            assert sha256(path) == item["source_sha256"], path
            assert item["source_url"].startswith("https://www.sec.gov/Archives/edgar/data/")
            raw = path.read_bytes().lower()
            assert b"exhibit 99.1" in raw or b"ex-99.1" in raw, path
            assert len(raw) > 100_000, path
            sources.append({"case_id": case["case_id"], "period": period,
                            "path": str(path.relative_to(HERE)),
                            "sha256": item["source_sha256"]})
            for fact in item["facts"]:
                assert fact["id"] not in seen, fact["id"]
                seen.add(fact["id"])
                assert fact["metric"] and fact["unit"] and fact["locator"]
    assert len(sources) == 6
    return {"preflight": "ok", "cases": len(cases), "raw_sources": len(sources),
            "facts": len(seen), "corpus_sha256": sha256(CORPUS), "sources": sources}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
