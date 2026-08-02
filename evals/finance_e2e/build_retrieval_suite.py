#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.finance_e2e.audit_evidence import (
    fact_is_present,
    matching_windows,
    value_candidates,
    visible_text,
)
from evals.finance_e2e.build_suite import (
    DEFAULT_EVIDENCE,
    DEFAULT_SOURCES,
    authorized_numeric_values,
    read_json,
    verify_evidence,
    write_json,
)
from evals.finance_e2e.fetch_sources import DEFAULT_LOCK, ROOT as EVAL_ROOT, load_manifest, verify_local_lock


DEFAULT_OUTPUT = ROOT / "evals" / "finance-retrieval-sec.json"
LOADS = ("small", "medium", "large")
SYMBOLS = ("NVDA", "AMD", "INTC", "NKE")
WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9-]{2,}")
NUMBER_PATTERN = re.compile(r"[-−–]?\d[\d,]*(?:\.\d+)?")
NEGATIVE_CONTEXT_PATTERN = re.compile(
    r"(?:decline|declined|decrease|decreased|down|fell|fall|loss|negative)"
    r"(?:\s+(?:first|initially|then|and|by|of|was|were|is|at|usd))*\s*$",
    re.IGNORECASE,
)


def normalized_words(value: str) -> set[str]:
    return {word.lower() for word in WORD_PATTERN.findall(value)}


def best_source_window(source_text: str, fact: dict[str, Any], radius: int = 650) -> str:
    present, _ = fact_is_present(source_text, fact)
    if not present:
        raise ValueError(f"{fact['id']}: fact is absent from the locked source")
    windows = matching_windows(source_text, value_candidates(fact), radius=radius)
    if not windows:
        raise ValueError(f"{fact['id']}: no source window found")
    excerpt_words = normalized_words(str(fact["excerpt"]))

    def score(window: str) -> tuple[int, int]:
        overlap = len(excerpt_words & normalized_words(window))
        return overlap, -len(window)

    selected = max(windows, key=score).strip()
    selected = re.sub(r"\s+", " ", selected)
    if len(selected) > radius * 2:
        selected = selected[: radius * 2].rstrip()
    return selected


def record_id(symbol: str, sequence: int, fact_index: int) -> str:
    return f"REC-{symbol}-{sequence:02d}-{fact_index:02d}"


def build_records(
    evidence: dict[str, Any],
    sources_path: Path,
    lock_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, dict[str, Any]]]:
    _, source_records = load_manifest(sources_path)
    sources = {source.id: source for source in source_records if source.kind == "filing_artifact"}
    lock = read_json(lock_path)
    locked = {entry["id"]: entry for entry in lock["entries"]}
    records: list[dict[str, Any]] = []
    fact_to_record: dict[str, str] = {}
    fact_index: dict[str, dict[str, Any]] = {}
    source_texts: dict[str, str] = {}
    for episode in evidence["episodes"]:
        source = sources[episode["source_id"]]
        entry = locked[source.id]
        if source.id not in source_texts:
            source_texts[source.id] = visible_text(EVAL_ROOT / entry["local_path"])
        for index, fact in enumerate(episode["facts"], start=1):
            current_record_id = record_id(episode["symbol"], episode["sequence"], index)
            fact_to_record[fact["id"]] = current_record_id
            fact_index[fact["id"]] = fact
            records.append(
                {
                    "id": current_record_id,
                    "source_id": source.id,
                    "source_sha256": entry["sha256"],
                    "company": source.company,
                    "symbol": source.symbol,
                    "filed_at": source.filed_at,
                    "accession": source.accession,
                    "locator": fact["locator"],
                    "text": best_source_window(source_texts[source.id], fact),
                    "_fact_id": fact["id"],
                    "_sequence": episode["sequence"],
                }
            )
    return records, fact_to_record, fact_index


def required_fact_ids(episodes: list[dict[str, Any]], task_type: str) -> list[str]:
    selected = episodes if task_type == "longitudinal" else [episodes[-1]]
    required: set[str] = set()
    for episode in selected:
        required.update(
            evidence_id
            for evidence_id in episode["research_state"]["basis_evidence_ids"]
            if not evidence_id.startswith("CALC-")
        )
        for comparison in episode.get("comparisons", []):
            required.add(comparison["from_fact"])
            required.add(comparison["to_fact"])
        for calculation in episode.get("calculations", []):
            required.add(calculation["numerator_fact"])
            required.add(calculation["denominator_fact"])
    return sorted(required)


def calculation_assertions(episodes: list[dict[str, Any]]) -> list[str]:
    assertions: list[str] = []
    for episode in episodes:
        for comparison in episode.get("comparisons", []):
            expected = str(comparison["expected"])
            if comparison["unit"] == "percentage_point":
                assertions.append(f"{expected} percentage points || {expected} pp")
            else:
                assertions.append(f"{expected} percent || {expected}%")
        for calculation in episode.get("calculations", []):
            expected = str(calculation["expected"])
            assertions.append(f"{expected} percent || {expected}%")
    return assertions


def version_transition_assertions(episodes: list[dict[str, Any]]) -> list[str]:
    assertions: list[str] = []
    for episode in episodes:
        state = episode["research_state"]
        expected = state["expected_version"]
        next_version = state["next_version"]
        assertions.append(
            f"version {expected} to {next_version} || version {expected} → {next_version} || "
            f"expected_version {expected} next_version {next_version} || {expected} → {next_version}"
        )
    return assertions


def task_milestones(episodes: list[dict[str, Any]], task_type: str) -> list[dict[str, Any]]:
    selected = episodes if task_type == "longitudinal" else [episodes[-1]]
    final_state = episodes[-1]["research_state"]
    state_values = [final_state["decision"], final_state["status"], "trade action is none || no trade"]
    if task_type == "longitudinal":
        state_values.extend(episode["research_state"]["decision"] for episode in episodes[:-1])
        state_values.extend(version_transition_assertions(episodes))
    milestones = [{"id": "bounded-research-state", "values": state_values}]
    calculations = calculation_assertions(selected)
    if calculations:
        milestones.append({"id": "declared-calculations", "values": calculations})
    milestones.append(
        {
            "id": "evidence-separation",
            "values": [
                "Chronology",
                "Evidence Reconciliation",
                "Calculation Audit",
                "Limitations",
            ],
        }
    )
    return milestones


def analysis_protocol(episodes: list[dict[str, Any]], task_type: str) -> str:
    selected = episodes if task_type == "longitudinal" else [episodes[-1]]
    lines = [
        "This is a predeclared experimental policy, not SEC evidence. Every evaluated mode receives the same policy.",
        "Retrieve and cite the source metrics needed by each formula; compute results rather than treating policy text as a fact.",
        "Report only requested rounded calculation results and source numbers quoted verbatim; omit intermediate arithmetic, unrounded values, unit-converted duplicates, and additional derived metrics.",
        "Required deterministic calculations (expected results are intentionally withheld):",
    ]
    calculations = 0
    for episode in selected:
        for comparison in episode.get("comparisons", []):
            calculations += 1
            lines.append(
                f"- {episode['id']} comparison {calculations}: {comparison['operation']} from "
                f"{comparison['from_fact']} to {comparison['to_fact']}, reported in {comparison['unit']} "
                f"with rounding {comparison['rounding']}."
            )
        for calculation in episode.get("calculations", []):
            calculations += 1
            lines.append(
                f"- {calculation['id']}: {calculation['operation']} using {calculation['numerator_fact']} "
                f"and {calculation['denominator_fact']}, reported in {calculation['unit']} with rounding "
                f"{calculation['rounding']}."
            )
    if calculations == 0:
        lines.append("- No arithmetic is required.")
    lines.append("Bounded research-state transition policy:")
    for episode in selected:
        state = episode["research_state"]
        lines.append(
            f"- {episode['id']}: only when the required source metrics and calculations for this observation are "
            f"verified, apply expected_version {state['expected_version']} -> next_version {state['next_version']}, "
            f"decision {state['decision']}, status {state['status']}, and trade action {state['trade_action']}; "
            "otherwise report insufficient evidence and do not advance the state."
        )
    lines.append("Keep source facts, derived calculations, and policy-driven state judgments in separate sections.")
    return "\n".join(lines)


def research_question(symbol: str, episodes: list[dict[str, Any]], task_type: str) -> str:
    if task_type == "point":
        return (
            f"For {symbol}, update the bounded research state at the final locked observation. "
            f"Answer: {episodes[-1]['question']} Use earlier observations only when a declared comparison requires them. "
            "Identify the decisive verified facts, check period and accounting basis, reproduce only justified "
            "calculations, report unresolved risks, and authorize no trade."
        )
    return (
        f"For {symbol}, reconstruct the complete three-observation research-state chain from the locked SEC corpus. "
        "Determine how operating trends, accounting basis, and downside evidence changed; verify every declared "
        "cross-observation calculation and the contiguous version transition; reconcile conflicting signals; "
        "select the final bounded research state; and authorize no trade."
    )


def corpus_for_load(
    all_records: list[dict[str, Any]],
    symbol: str,
    gold_record_ids: set[str],
    load: str,
) -> list[dict[str, Any]]:
    own = [record for record in all_records if record["symbol"] == symbol]
    others = [record for record in all_records if record["symbol"] != symbol]
    if load == "small":
        selected = own
    elif load == "medium":
        selected = own + others[: min(12, len(others))]
    elif load == "large":
        selected = all_records
    else:
        raise ValueError(f"unsupported corpus load: {load}")
    if not gold_record_ids.issubset({record["id"] for record in selected}):
        raise ValueError(f"{symbol}/{load}: corpus omitted a gold record")
    return sorted(selected, key=lambda record: hashlib.sha256(f"{symbol}:{load}:{record['id']}".encode()).hexdigest())


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if not key.startswith("_")}


def gold_record_groups(
    records: list[dict[str, Any]],
    symbol: str,
    required_fact_ids: list[str],
    fact_index: dict[str, dict[str, Any]],
) -> list[list[str]]:
    groups: list[list[str]] = []
    for fact_id in required_fact_ids:
        fact = fact_index[fact_id]
        alternatives = [
            record["id"]
            for record in records
            if record["symbol"] == symbol and fact_is_present(record["text"], fact)[0]
        ]
        if not alternatives:
            raise ValueError(f"{symbol}: no record covers required fact {fact_id}")
        groups.append(sorted(alternatives))
    return groups


def oracle_packet(
    records: list[dict[str, Any]],
    gold_record_ids: set[str],
    episodes: list[dict[str, Any]],
    task_type: str,
) -> str:
    lines = ["Perfect-retrieval SEC records:"]
    for record in records:
        if record["id"] not in gold_record_ids:
            continue
        lines.append(
            f"[{record['id']}] {record['source_id']} filed {record['filed_at']} locator {record['locator']}: {record['text']}"
        )
    return "\n".join(lines)


def numeric_values(records: list[dict[str, Any]], episodes: list[dict[str, Any]]) -> list[str]:
    values: set[str] = set()
    for record in records:
        source_text = f"{record['filed_at']} {record['text']}"
        for match in NUMBER_PATTERN.finditer(source_text):
            normalized = match.group().replace(",", "").replace("−", "-").replace("–", "-")
            try:
                values.add(format(Decimal(normalized), "f"))
                if not normalized.startswith("-") and NEGATIVE_CONTEXT_PATTERN.search(source_text[max(0, match.start() - 64):match.start()]):
                    values.add(format(-Decimal(normalized), "f"))
            except InvalidOperation:
                continue
    for episode in episodes:
        values.update(authorized_numeric_values(episode))
    return sorted(values, key=lambda value: (Decimal(value), value))


def build_suite(evidence_path: Path, sources_path: Path, lock_path: Path) -> dict[str, Any]:
    verify_local_lock(sources_path, lock_path)
    evidence = verify_evidence(evidence_path, sources_path)
    all_records, fact_to_record, fact_index = build_records(evidence, sources_path, lock_path)
    by_symbol: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in SYMBOLS}
    for episode in evidence["episodes"]:
        by_symbol[episode["symbol"]].append(episode)
    for episodes in by_symbol.values():
        episodes.sort(key=lambda episode: episode["sequence"])

    cases: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        episodes = by_symbol[symbol]
        for task_type in ("point", "longitudinal"):
            required = required_fact_ids(episodes, task_type)
            gold_record_ids = {fact_to_record[fact_id] for fact_id in required}
            for load in LOADS:
                records = corpus_for_load(all_records, symbol, gold_record_ids, load)
                case_id = f"FRET-{symbol}-{'POINT' if task_type == 'point' else 'LONG'}-{load.upper()}"
                cases.append(
                    {
                        "id": case_id,
                        "description": (
                            f"{symbol} {task_type} financial retrieval and synthesis task with {load} locked-corpus load."
                        ),
                        "question": research_question(symbol, episodes, task_type),
                        "analysis_protocol": analysis_protocol(episodes, task_type),
                        "corpus_load": load,
                        "tags": ["finance", "sec", "retrieval", task_type, load, symbol.lower()],
                        "records": [public_record(record) for record in records],
                        "gold_record_ids": sorted(gold_record_ids),
                        "gold_record_groups": gold_record_groups(records, symbol, required, fact_index),
                        "oracle_evidence": oracle_packet(records, gold_record_ids, episodes, task_type),
                        "milestones": task_milestones(episodes, task_type),
                        "forbidden_output_values": [
                            "trade is authorized",
                            "execute a trade",
                            "buy recommendation",
                            "sell recommendation",
                            "target price is",
                            "source data was estimated",
                        ],
                        "authorized_numeric_values": numeric_values(records, episodes),
                    }
                )

    return {
        "version": 1,
        "name": "finance-sec-retrieval-context-v1",
        "description": (
            "End-to-end comparison of monolithic, compute-matched staged, shared-retrieval team, raw-context team, "
            "and oracle-evidence financial research pipelines over SHA-256-locked SEC filing excerpts."
        ),
        "dataset": evidence["dataset"],
        "source_lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
        "defaults": {
            "coordinator_agent_id": "finance-coordinator",
            "solo_agent_id": "finance-solo",
            "retriever_agent_id": "finance-retriever",
            "analysts": [
                {
                    "agent_id": "finance-trend",
                    "perspective": "trend and chronology",
                    "instruction": (
                        "Reconstruct the observation sequence and assess growth, segment, and channel direction "
                        "without changing period labels."
                    ),
                },
                {
                    "agent_id": "finance-accounting",
                    "perspective": "accounting and period audit",
                    "instruction": (
                        "Separate GAAP, segment, channel, quarterly, and annual measures and show only "
                        "calculations justified by cited records."
                    ),
                },
                {
                    "agent_id": "finance-risk",
                    "perspective": "risk and governance",
                    "instruction": (
                        "Identify downside evidence and contradictions, then apply only supplied bounded "
                        "research-state rules without authorizing a trade."
                    ),
                },
            ],
            "repetitions": 1,
            "timeout": "10m",
            "min_retrieval_recall": 0.75,
            "min_summary_retention": 0.75,
            "min_final_evidence_recall": 0.60,
            "min_grounding_accuracy": 0.95,
        },
        "modes": [
            "solo_monolithic",
            "solo_staged",
            "team_shared_retrieval",
            "team_raw_context",
            "oracle_evidence",
        ],
        "pricing": {
            "deepseek/deepseek-v4-flash": {
                "input_per_million": 0.14,
                "output_per_million": 0.28,
                "cache_read_per_million": 0.0028,
            },
            "deepseek/deepseek-v4-pro": {
                "input_per_million": 0.435,
                "output_per_million": 0.87,
                "cache_read_per_million": 0.003625,
            },
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the locked-SEC financial retrieval/context suite.")
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    suite = build_suite(args.evidence, args.sources, args.lock)
    if args.check:
        if not args.output.exists() or read_json(args.output) != suite:
            raise RuntimeError(f"generated artifact is stale: {args.output}")
        print("finance retrieval suite is valid and current")
        return 0
    write_json(args.output, suite)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
