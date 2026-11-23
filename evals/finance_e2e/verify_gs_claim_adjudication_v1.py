#!/usr/bin/env python3
"""Verify frozen GS source, numeric and state evidence for diagnostic review."""

from __future__ import annotations

import hashlib
import json
import re

import audit_gs_holdout_facts_v1 as source_audit
from rank_prospective_cross_workflow_v1 import FRAME, SEED_SOURCE, rank
from verify_prospective_source_discovery_v1 import DISCOVERY
from verify_mco_claim_adjudication_v1 import RESULTS, _frozen_hashes


LEVELS = ("14583", "15184", "3723", "4098", "9241", "9453",
          "384", "339", "4733", "3868", "2194", "2659")


def verify_result(result: dict, packet: dict, relative: str, repeat: int) -> None:
    if (result["status"] != "mechanical_pass" or not all(result["checks"].values())
            or result["error"] is not None
            or not result["runtime_audit"]["clean_completion"]):
        raise ValueError(f"GS workflow completion differs: {relative}")
    state = result["state"]
    if len(state["alerts"]) != 1 or len(state["theses"]) != 1:
        raise ValueError(f"GS ledger cardinality differs: {relative}")
    alert, thesis_record = state["alerts"][0], state["theses"][0]
    thesis, reviews = thesis_record["thesis"], thesis_record["reviews"]
    if len(reviews) != 1:
        raise ValueError(f"GS review cardinality differs: {relative}")
    review = reviews[0]
    if (review["alert_id"] != alert["id"] or review["thesis_id"] != thesis["id"]
            or review["decision"] != "maintain"
            or review["event"]["sources"] != alert["event"]["sources"]
            or alert["event"]["sources"][0]["sha256"] != packet["event"]["source_sha256"]
            or thesis["status"] != "active" or thesis["conviction"] != 3
            or thesis["decision_hold"] or thesis["actionability"] != "available"
            or thesis["version"] != 2 or alert["status"] != "acknowledged"
            or alert["version"] != 2):
        raise ValueError(f"GS persisted state differs: {relative}")
    final = result["turns"][-1]["response"]["choices"][0]["message"]["content"]
    for identifier in (thesis["id"], alert["id"], review["id"]):
        if identifier not in final:
            raise ValueError(f"GS final record ID differs: {relative}")
    normalized = final.replace(",", "")
    for number in LEVELS:
        if not re.search(r"(?<!\d)" + number + r"(?!\d)", normalized):
            raise ValueError(f"GS final selected level missing: {number} in {relative}")
    if any("trade" in name.lower() or "order" in name.lower()
           for turn in result["turns"] for name in turn["tool_calls"]):
        raise ValueError(f"GS trading tool called: {relative}")
    wrong_absolute = "earnings increase exceeded the revenue increase in absolute terms"
    if repeat == 5 and wrong_absolute not in review["rationale"]:
        raise ValueError("GS-r5 persisted absolute comparison changed")


def verify() -> dict:
    packet = json.loads(source_audit.PACKET.read_text())
    frame = json.loads(FRAME.read_text())
    rank(frame, SEED_SOURCE.read_bytes())
    source_audit.audit(packet, frame, json.loads(DISCOVERY.read_text()))
    frozen = _frozen_hashes()
    for repeat in range(1, 6):
        relative = f"GS-2025-Q3-EARNINGS-TRANSITION-r{repeat}/result.json"
        path = RESULTS / relative
        if relative not in frozen or hashlib.sha256(path.read_bytes()).hexdigest() != frozen[relative]:
            raise ValueError(f"GS raw result hash differs: {relative}")
        verify_result(json.loads(path.read_text()), packet, relative, repeat)
    return {"status": "gs_five_raw_hashes_source_rows_numeric_claims_and_state_verified",
            "observations_checked": 5, "critical_error_observation": "GS-r5",
            "quality_scores_assigned_by_script": 0, "model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
