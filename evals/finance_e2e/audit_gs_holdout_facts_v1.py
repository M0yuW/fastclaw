#!/usr/bin/env python3
"""Check selected GS facts against both frozen SEC exhibit tables before any model run."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from financial_evidence_bundle_v1 import build_bundle
from sec_exhibit_text import extract_lines
from verify_prospective_source_discovery_v1 import DISCOVERY, ROOT, verify as verify_discovery
from rank_prospective_cross_workflow_v1 import FRAME, SEED_SOURCE, rank


PACKET = ROOT / "gs_holdout_fact_packet_v1.json"
TABLE_ANCHOR = "Consolidated Statements of Earnings (unaudited)"


def number(cell: str) -> int:
    cleaned = re.sub(r"[^0-9-]", "", cell)
    if not re.fullmatch(r"-?\d+", cleaned):
        raise ValueError(f"not a plain table number: {cell!r}")
    return int(cleaned)


def table_values(path: Path, row: str, current_column: str) -> tuple[int, int, int]:
    lines = extract_lines(path)
    starts = [i for i, text in enumerate(lines) if TABLE_ANCHOR in text]
    if not starts:
        raise ValueError(f"consolidated earnings table missing: {path}")
    start = starts[0]
    header = re.sub(r"[^a-z0-9]+", " ", " ".join(lines[start:start + 20]).lower()).strip()
    if current_column.lower() not in header:
        raise ValueError(f"source table has a different current-quarter column: {path}")
    stop = next((i for i in range(start + 1, len(lines))
                 if TABLE_ANCHOR in lines[i] or "NINE MONTHS ENDED" in lines[i]
                 or "Balance Sheets" in lines[i]), len(lines))
    matches = [i for i in range(start, stop) if lines[i] == row]
    if len(matches) != 1:
        raise ValueError(f"earnings row missing or ambiguous: {row}")
    i = matches[0]
    return tuple(number(cell) for cell in lines[i + 1:i + 4])


def audit(packet: dict, frame: dict, discovery: dict) -> dict:
    verify_discovery(frame, discovery)
    if packet.get("version") != 1 or packet.get("symbol") != "GS":
        raise ValueError("unexpected fact packet")
    found = discovery["issuers"][0]
    sources = found["sources"]
    if len(sources) != 2:
        raise ValueError("expected two frozen SEC exhibits")
    values_by_period: dict[str, dict[str, int]] = {}
    for period, source in zip(("baseline", "event"), sources):
        section = packet[period]
        if section["source_url"] != source["url"] or section["source_sha256"] != source["sha256"]:
            raise ValueError(f"fact packet points to different source: {period}")
        if section["local_path"] != source["local_path"]:
            raise ValueError(f"fact packet points to different local source: {period}")
        path = ROOT / section["local_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != section["source_sha256"]:
            raise ValueError(f"raw source changed: {period}")
        values_by_period[period] = {}
        for fact in section["facts"]:
            if fact["unit"] != "USD_million_rounded":
                raise ValueError("selected GS table is in displayed USD millions")
            current, prior, prior_year = table_values(path, fact["source_row"],
                                                     fact["source_column"])
            if fact["value"] != current:
                raise ValueError(f"fact differs from SEC current-quarter cell: {fact['id']}")
            if fact["metric"] in values_by_period[period]:
                raise ValueError(f"duplicate metric in {period}")
            values_by_period[period][fact["metric"]] = current
            if period == "event":
                expected_prior = values_by_period["baseline"].get(fact["metric"])
                if prior != expected_prior:
                    raise ValueError(f"Q3 source's Q2 comparator disagrees: {fact['id']}")
    bundle = build_bundle(packet)
    if len(bundle["comparisons"]) != 6:
        raise ValueError("expected six declared metric comparisons")
    return {"status": "selected_source_rows_and_cross_filing_comparators_match",
            "source_files": 2, "selected_facts": 12,
            "comparisons": {item["metric"]: {"delta_usd_million_displayed":
                             str(int(item["delta_usd_thousand"]) // 1000),
                             "precision": item["precision"]}
                            for item in bundle["comparisons"]},
            "model_observations": 0}


if __name__ == "__main__":
    frame = json.loads(FRAME.read_text(encoding="utf-8"))
    rank(frame, SEED_SOURCE.read_bytes())
    discovery = json.loads(DISCOVERY.read_text(encoding="utf-8"))
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    print(json.dumps(audit(packet, frame, discovery), indent=2))
