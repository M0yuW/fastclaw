#!/usr/bin/env python3
"""Prepare order/outcome-masked SEC event answer packets for later adjudication.

This is a read-only transform of frozen observations. It does not score answers,
contact a model, or alter raw results. The private mapping stays separate from
the answer packets and should not be shown to a qualitative judge initially.
"""

from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path

import build_postcorrection_event_preflight_v2 as source_batch
from aggregate_postcorrection_judgments_v2 import verify_frozen_results
from run_thesis_event_panel import sha256


RUNTIME_METADATA_KEYS = {"created_at", "updated_at", "first_seen_at",
                         "last_seen_at", "last_review_at", "created_in_session_id",
                         "session_id", "agent_id", "created_by_agent_id",
                         "elapsed_ms", "started_at", "finished_at"}


def new_masked_id() -> str:
    return "J-" + secrets.token_hex(8)


def final_text(result: dict) -> str | None:
    turns = result.get("turns") or []
    if not turns:
        return None
    response = turns[-1].get("response") or {}
    return (((response.get("choices") or [{}])[0].get("message") or {})
            .get("content"))


def tool_evidence(result: dict) -> list[dict]:
    evidence = []
    for turn in result.get("turns") or []:
        trace = ((turn.get("response") or {}).get("fastclaw") or {}).get("trace") or []
        evidence.extend(item for item in trace if item.get("type") in
                        ("tool_call", "tool_result", "error", "terminal"))
    return evidence


def mask_runtime_metadata(value):
    """Drop chronology/session markers, retaining decision and evidence fields."""
    if isinstance(value, dict):
        return {key: mask_runtime_metadata(item) for key, item in value.items()
                if key not in RUNTIME_METADATA_KEYS}
    if isinstance(value, list):
        return [mask_runtime_metadata(item) for item in value]
    return value


def packet_for_judge(result: dict, source_packet: dict, mask: str | None = None) -> dict:
    state = result.get("state") or {}
    theses, alerts = state.get("theses") or [], state.get("alerts") or []
    # A qualitative judge sees the actual persisted state and tool record, but
    # not the runner's mechanical verdict, status, cost, repetition or run order.
    source = {key: value for key, value in source_packet.items()
              if key != "precommitted_interpretation_checks"}
    return {
        "masked_id": mask or new_masked_id(),
        "workflow": result.get("workflow"),
        "source_packet": source,
        "model_prompt": (result.get("turns") or [{}])[-1].get("prompt"),
        "final_answer": final_text(result),
        "persisted_theses_and_reviews": mask_runtime_metadata(theses),
        "persisted_alerts": mask_runtime_metadata(alerts),
        "tool_evidence": mask_runtime_metadata(tool_evidence(result)),
    }


def prepare(results_dir: Path, output_dir: Path) -> dict:
    if output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    verify_frozen_results(results_dir)
    packet_by_case = {}
    for _, path in source_batch.READY.values():
        packet = json.loads(path.read_text())
        packet_by_case[packet["case_id"]] = packet
    result_paths = sorted(results_dir.glob("*/result.json"))
    if not result_paths:
        raise ValueError("no frozen observation results found")
    results = [json.loads(path.read_text()) for path in result_paths]
    ids = [result["observation_id"] for result in results]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate observation ID")
    if any(result["case_id"] not in packet_by_case for result in results):
        raise ValueError("observation references a non-frozen case")
    output_dir.mkdir(parents=True)
    packets_dir = output_dir / "masked_packets"
    packets_dir.mkdir()
    scores_dir = output_dir / "scores"
    scores_dir.mkdir()
    private_mapping = []
    used_masks = set()
    for path, result in zip(result_paths, results):
        mask = new_masked_id()
        if mask in used_masks:
            raise ValueError("masked ID collision")
        used_masks.add(mask)
        item = packet_for_judge(result, packet_by_case[result["case_id"]], mask)
        mask = item["masked_id"]
        (packets_dir / f"{mask}.json").write_text(
            json.dumps(item, indent=2, ensure_ascii=False) + "\n")
        score_template = {
            "masked_id": mask, "reviewer": "",
            "coverage": {"final_answer": False, "persisted_review": False},
            "scores": {name: None for name in ("F", "I", "R", "S", "U")},
            "claim_adjudications": [], "critical_errors": [],
            "assessable_implication": False, "notes": "",
        }
        (scores_dir / f"{mask}.json").write_text(
            json.dumps(score_template, indent=2, ensure_ascii=False) + "\n")
        private_mapping.append({"masked_id": mask,
                                "observation_id": result["observation_id"],
                                "raw_result_path": str(path.resolve()),
                                "raw_result_sha256": sha256(path),
                                "mechanical_status": result.get("status"),
                                "runtime_error": result.get("error"),
                                "estimated_cost_usd": result.get("estimated_cost_usd")})
    (output_dir / "PRIVATE-MAPPING.json").write_text(
        json.dumps(private_mapping, indent=2, ensure_ascii=False) + "\n")
    hashes = [(path.relative_to(output_dir), sha256(path)) for path in
              sorted(packets_dir.glob("*.json"))]
    (output_dir / "MASKED-PACKET-SHA256.txt").write_text(
        "".join(f"{digest}  {path}\n" for path, digest in hashes))
    return {"status": "masked_judgment_inputs_prepared_no_scores",
            "packets": len(hashes), "raw_results_changed": False,
            "model_calls": 0, "source_cases": len({r["case_id"] for r in results})}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.results_dir, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
