#!/usr/bin/env python3
"""Check the reproducible source/numeric/state substrate of MCO self-review.

This does not assign inference or utility scores. Those remain explicit human-
readable diagnostic judgments in MCO-CLAIM-ADJUDICATION-v1.md.
"""

from __future__ import annotations

import hashlib
import json
import re

import audit_mco_holdout_facts_v1 as source_audit
from fetch_sources import ROOT, verify_local_lock


RESULTS = ROOT / "results/2026-10-23-prospective-event-batch1-flash-v1"
NUMBERS = ("1898", "2007", "1080", "1090", "818", "917", "578", "646")


def _frozen_hashes() -> dict[str, str]:
    entries = {}
    for line in (RESULTS / "RESULT-SHA256.txt").read_text().splitlines():
        digest, relative = line.split(None, 1)
        entries[relative.strip()] = digest
    return entries


def verify_result(result: dict, source: dict, relative: str) -> None:
    if result["status"] != "mechanical_pass" or not all(result["checks"].values()):
        raise ValueError(f"MCO workflow checks differ: {relative}")
    if result["error"] is not None or not result["runtime_audit"]["clean_completion"]:
        raise ValueError(f"MCO runtime completion differs: {relative}")
    state = result["state"]
    if len(state["alerts"]) != 1 or len(state["theses"]) != 1:
        raise ValueError(f"MCO ledger cardinality differs: {relative}")
    alert, thesis_record = state["alerts"][0], state["theses"][0]
    thesis, reviews = thesis_record["thesis"], thesis_record["reviews"]
    if len(reviews) != 1:
        raise ValueError(f"MCO review cardinality differs: {relative}")
    review = reviews[0]
    if (review["alert_id"] != alert["id"] or review["thesis_id"] != thesis["id"]
            or review["decision"] != "maintain"
            or review["event"]["sources"] != alert["event"]["sources"]
            or alert["event"]["sources"][0]["sha256"] != source["event"]["source_sha256"]
            or thesis["status"] != "active" or thesis["conviction"] != 3
            or thesis["decision_hold"] or thesis["actionability"] != "available"
            or thesis["version"] != 2 or alert["status"] != "acknowledged"
            or alert["version"] != 2):
        raise ValueError(f"MCO persisted state differs: {relative}")
    final = result["turns"][-1]["response"]["choices"][0]["message"]["content"]
    for identifier in (thesis["id"], alert["id"], review["id"]):
        if identifier not in final:
            raise ValueError(f"MCO final record ID differs: {relative}")
    for number in NUMBERS:
        if not re.search(r"(?<!\d)" + number + r"(?!\d)", final):
            raise ValueError(f"MCO final selected number missing: {number} in {relative}")
    if not re.search(r"19\s*%", final):
        raise ValueError(f"MCO final segment counterpoint missing: {relative}")
    if any("trade" in name.lower() or "order" in name.lower()
           for turn in result["turns"] for name in turn["tool_calls"]):
        raise ValueError(f"MCO trading tool called: {relative}")


def verify() -> dict:
    verify_local_lock(source_audit.MANIFEST, source_audit.LOCK)
    packet = json.loads(source_audit.PACKET.read_text())
    lock = json.loads(source_audit.LOCK.read_text())
    source_audit.audit(packet, lock)
    frozen = _frozen_hashes()
    checked = []
    for repeat in range(1, 6):
        relative = f"MCO-2025-Q3-SEGMENT-MIX-r{repeat}/result.json"
        path = RESULTS / relative
        if relative not in frozen or hashlib.sha256(path.read_bytes()).hexdigest() != frozen[relative]:
            raise ValueError(f"MCO raw result hash differs: {relative}")
        verify_result(json.loads(path.read_text()), packet, relative)
        checked.append(relative)
    return {"status": "mco_five_raw_hashes_source_rows_numeric_claims_and_state_verified",
            "observations_checked": len(checked), "quality_scores_assigned_by_script": 0,
            "model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
