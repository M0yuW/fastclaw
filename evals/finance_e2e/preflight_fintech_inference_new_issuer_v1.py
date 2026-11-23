#!/usr/bin/env python3
"""Fail-closed raw-source preflight for the new FinTech issuer panel."""

import hashlib
import json
from pathlib import Path

import audit_fintech_inference_sources_v1 as source_audit
from validate_fintech_inference_packet_v1 import CORPUS, HERE, validate


FROZEN_STATUS = "source_facts_frozen_before_model_runs"
EXPECTED_URLS = {
    ("AFRM-FISCAL-COST", "baseline"): "https://www.sec.gov/Archives/edgar/data/1820953/000182095324000033/afrm-q424shareholderlett.htm",
    ("AFRM-FISCAL-COST", "event"): "https://www.sec.gov/Archives/edgar/data/1820953/000182095324000058/afrm-q125shareholderlett.htm",
    ("SOFI-REVENUE-BRIDGE", "baseline"): "https://www.sec.gov/Archives/edgar/data/1818874/000181887424000169/q22024earningsrelease.htm",
    ("SOFI-REVENUE-BRIDGE", "event"): "https://www.sec.gov/Archives/edgar/data/1818874/000181887424000229/q32024earningsrelease.htm",
    ("UPST-MIXED-BASIS", "baseline"): "https://www.sec.gov/Archives/edgar/data/1647639/000164763924000032/upst991prq22024.htm",
    ("UPST-MIXED-BASIS", "event"): "https://www.sec.gov/Archives/edgar/data/1647639/000164763924000045/upst991prq32024.htm",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify():
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    if corpus.get("status") != FROZEN_STATUS:
        raise RuntimeError("panel is not source-frozen; no model run is permitted")
    packet = validate()
    sources = []
    for case in corpus["cases"]:
        for period in ("baseline", "event"):
            item = case[period]
            if item["source_url"] != EXPECTED_URLS[(case["case_id"], period)]:
                raise RuntimeError(f"unexpected SEC exhibit URL: {case['case_id']} {period}")
            path = (HERE / item["local_path"]).resolve()
            if not path.is_relative_to(HERE.resolve()):
                raise RuntimeError(f"source path escapes study directory: {path}")
            # The two genuine Affirm EX-99.1 HTML exhibits are 69–79 KB.
            # Exact pinned SHA-256 and exhibit identity are the decisive checks;
            # this lower bound only catches empty/error-body downloads.
            if not path.is_file() or path.stat().st_size <= 20_000:
                raise RuntimeError(f"missing or implausibly short SEC exhibit: {path}")
            if sha256(path) != item["source_sha256"]:
                raise RuntimeError(f"SEC exhibit hash mismatch: {path}")
            raw = path.read_bytes().lower()
            if b"exhibit 99.1" not in raw and b"ex-99.1" not in raw:
                raise RuntimeError(f"EX-99.1 identity not found: {path}")
            sources.append({"case_id": case["case_id"], "period": period,
                            "bytes": path.stat().st_size, "sha256": item["source_sha256"]})
    if len(sources) != 6:
        raise RuntimeError("expected exactly six baseline/event SEC exhibits")
    selected_fact_audit = source_audit.verify()
    return {"preflight": "raw_source_hashes_and_packet_arithmetic_ok",
            "facts": packet["facts"], "sources": sources,
            "selected_fact_audit": selected_fact_audit,
            "corpus_sha256": sha256(CORPUS),
            "note": "Selected fact row anchors were checked against the pinned raw SEC bytes; this is not a full-filing audit."}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
