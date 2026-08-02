#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.finance_e2e.build_suite import (
    DEFAULT_EVIDENCE,
    DEFAULT_SOURCES,
    SPECIALIST_IDS,
    authorized_numeric_values,
    decimal_value,
    read_json,
    specialist_reports,
    verify_evidence,
    write_json,
)
from evals.finance_e2e.fetch_sources import load_manifest


EVAL_ROOT = Path(__file__).resolve().parent
DEFAULT_HARD_SUITE = ROOT / "evals" / "multiagent-finance-sec-hard.json"
DEFAULT_HARD_AGENT_PACK = EVAL_ROOT / "runtime-agent-evidence-hard.json"

HARD_CASES = {
    "NVDA": {
        "id": "FHARD-NVDA-01",
        "question": (
            "Reconstruct the three-observation NVIDIA research-state chain, determine whether growth remains "
            "strong while the margin-risk flag remains active, and reject the stale control candidate."
        ),
        "stale_id": "STALE-NVDA-03",
        "stale_decision": "clear_margin_risk",
        "control": "The sampled Q2-to-Q4 change is not quarter-over-quarter.",
    },
    "AMD": {
        "id": "FHARD-AMD-01",
        "question": (
            "Reconstruct AMD's three-observation state chain, reconcile improving revenue and margin with the "
            "remaining segment-mix risk, and reject the stale control candidate."
        ),
        "stale_id": "STALE-AMD-03",
        "stale_decision": "clear_segment_mix_risk",
        "control": "Do not confuse quarterly observations with full-year figures.",
    },
    "INTC": {
        "id": "FHARD-INTC-01",
        "question": (
            "Reconstruct Intel's three-observation risk-state chain, reconcile the revenue change with the "
            "profitability, restructuring, impairment, workforce, and dividend evidence, and reject the stale candidate."
        ),
        "stale_id": "STALE-INTC-03",
        "stale_decision": "downgrade_to_needs_review",
        "control": "Revenue growth does not override restructuring and impairment evidence.",
    },
    "NKE": {
        "id": "FHARD-NKE-01",
        "question": (
            "Reconstruct NIKE's three-observation channel-and-margin state chain, distinguish the initial margin "
            "improvement from subsequent deterioration, and reject the stale control candidate."
        ),
        "stale_id": "STALE-NKE-03",
        "stale_decision": "resolve_digital_risk",
        "control": "Keep GAAP margin evidence distinct from reported-channel evidence.",
    },
}


def version_chain_values(symbol: str) -> str:
    return (
        "version 0 to 1 to 2 to 3 || version 0 → 1 → 2 → 3 || "
        "state chain 0 to 1 to 2 to 3 || state chain 0 → 1 → 2 → 3 || "
        f"{symbol} state versions 0 1 2 3"
    )


def build_hard_outputs(evidence: dict[str, Any], sources_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    _, manifest_sources = load_manifest(sources_path)
    sources = {source.id: source for source in manifest_sources if source.kind == "filing_artifact"}
    episodes_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for episode in evidence["episodes"]:
        episodes_by_symbol.setdefault(episode["symbol"], []).append(episode)
    for episodes in episodes_by_symbol.values():
        episodes.sort(key=lambda item: item["sequence"])

    cases = []
    agent_evidence: dict[str, dict[str, str]] = {agent_id: {} for agent_id in SPECIALIST_IDS}
    for symbol in ("NVDA", "AMD", "INTC", "NKE"):
        spec = HARD_CASES[symbol]
        episodes = episodes_by_symbol[symbol]
        reports = [specialist_reports(episode, sources[episode["source_id"]]) for episode in episodes]
        final_state = episodes[-1]["research_state"]

        source_id = f"LONG-SRC-{symbol}-01"
        methodology_id = f"LONG-CALC-{symbol}-01"
        governance_id = f"LONG-STATE-{symbol}-01"
        source_response = (
            f"{source_id}: Three locked SEC observations, in accepted sequence: "
            + " ".join(report["finance-source"]["response"] for report in reports)
        )
        methodology_response = (
            f"{methodology_id}: Declared calculations and period controls, in accepted sequence: "
            + " ".join(report["finance-methodology"]["response"] for report in reports)
            + f" {spec['control']} No other arithmetic is authorized."
        )
        state_steps = " ".join(report["finance-governance"]["response"] for report in reports)
        governance_response = (
            f"{governance_id}: Accepted version chain: {state_steps} "
            f"{spec['stale_id']} is a rejected candidate: decision {spec['stale_decision']} at expected_version 1 "
            "does not match the accepted prior next_version 2. "
            f"Apply only STATE-{symbol}-03 with decision {final_state['decision']}, next_version 3, "
            f"status {final_state['status']}, and trade action none."
        )

        source_values = [source_id]
        methodology_values = [methodology_id]
        governance_values = [
            governance_id,
            *[f"STATE-{episode['id'].removeprefix('FSEC-')}" for episode in episodes],
            final_state["decision"],
            version_chain_values(symbol),
            spec["stale_id"],
            (
                f"reject {spec['stale_id']} || rejected {spec['stale_id']} || "
                f"{spec['stale_id']} is a rejected candidate || reject the stale control candidate"
            ),
            "trade action is none || no trade || trade authorization none",
        ]
        numeric_values: set[str] = set()
        for episode, report in zip(episodes, reports):
            source_values.extend(report["finance-source"]["values"])
            methodology_values.extend(report["finance-methodology"]["values"])
            numeric_values.update(authorized_numeric_values(episode))

        responses = {
            "finance-source": source_response,
            "finance-methodology": methodology_response,
            "finance-governance": governance_response,
        }
        values = {
            "finance-source": source_values,
            "finance-methodology": methodology_values + [spec["control"]],
            "finance-governance": governance_values,
        }
        roles = {
            "finance-source": "Reconstruct the locked three-filing fact chronology without calculations.",
            "finance-methodology": "Audit only declared cross-observation calculations and period labels.",
            "finance-governance": "Validate the contiguous state chain and reject stale control candidates.",
        }
        agents = []
        for agent_id in SPECIALIST_IDS:
            agent_evidence[agent_id][spec["id"]] = responses[agent_id]
            agents.append(
                {
                    "id": agent_id,
                    "role": roles[agent_id],
                    "response": responses[agent_id],
                    "task_values": [spec["id"]],
                    "contribution_values": values[agent_id],
                }
            )

        authorized = sorted(
            numeric_values,
            key=lambda value: (decimal_value(value, "hard authorized numeric value"), value),
        )
        cases.append(
            {
                "id": spec["id"],
                "description": (
                    f"{episodes[0]['company']} three-observation SEC chronology, methodology, and state-conflict adjudication."
                ),
                "execution_mode": "runtime",
                "tags": ["finance", "sec", "hard", "longitudinal", "state-conflict", symbol.lower()],
                "max_delegations": 3,
                "forbidden_output_values": [
                    "trade is authorized",
                    "execute a trade",
                    "target price is",
                    "source data was estimated",
                    (
                        f"final decision {spec['stale_decision']} || "
                        f"persisted decision {spec['stale_decision']}"
                    ),
                ],
                "authorized_numeric_values": authorized,
                "prompt": (
                    f"[{spec['id']}] {spec['question']} Delegate exactly once to finance-source, "
                    "finance-methodology, and finance-governance. Build the chronology before selecting the final "
                    "state: verify all three SEC observations, reproduce only declared calculations, enforce the "
                    "contiguous 0-to-1-to-2-to-3 version chain, and explicitly reject the stale candidate. Preserve "
                    "every SEC, CALC, STATE, LONG, and STALE evidence ID. Do not use outside knowledge, recommend or "
                    "authorize a trade, relabel sampled observations, or emit undeclared arithmetic. The only "
                    f"authorized numeric values are: {', '.join(authorized)}. Return Chronology, Decision, Evidence "
                    "Reconciliation, Calculation Audit, Conflict Resolution, and State Update sections."
                ),
                "agents": agents,
                "milestones": [
                    {"id": "three-filing-chronology", "values": source_values},
                    {"id": "declared-calculation-audit", "values": methodology_values + [spec["control"]]},
                    {"id": "state-conflict-resolution", "values": governance_values},
                ],
            }
        )

    suite = {
        "version": 1,
        "name": "finance-sec-hard-longitudinal-runtime-v1",
        "description": (
            "Four evidence-matched hard tasks combining three locked SEC observations, declared calculations, "
            "contiguous research-state transitions, and an explicitly stale control candidate."
        ),
        "defaults": {"agent_id": "bench-coordinator", "repetitions": 1, "timeout": "8m"},
        "baselines": ["solo_open_book", "solo_two_pass", "team", "oracle_team"],
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
    evidence_bytes = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
    sources_bytes = json.dumps(read_json(sources_path), sort_keys=True, separators=(",", ":")).encode()
    spec_bytes = json.dumps(HARD_CASES, sort_keys=True, separators=(",", ":")).encode()
    agent_pack = {
        "version": 1,
        "dataset": "fastclaw-finance-e2e-hard-v1",
        "suite": "evals/multiagent-finance-sec-hard.json",
        "evidence_sha256": hashlib.sha256(evidence_bytes + b"\n" + sources_bytes + b"\n" + spec_bytes).hexdigest(),
        "agents": agent_evidence,
    }
    return suite, agent_pack


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the hard longitudinal finance runtime suite.")
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--suite", type=Path, default=DEFAULT_HARD_SUITE)
    parser.add_argument("--agent-pack", type=Path, default=DEFAULT_HARD_AGENT_PACK)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    evidence = verify_evidence(args.evidence, args.sources)
    suite, agent_pack = build_hard_outputs(evidence, args.sources)
    if args.check:
        for path, payload in ((args.suite, suite), (args.agent_pack, agent_pack)):
            if not path.exists() or read_json(path) != payload:
                raise RuntimeError(f"generated artifact is stale: {path}")
        print("hard finance suite and runtime evidence pack are valid")
        return 0
    write_json(args.suite, suite)
    write_json(args.agent_pack, agent_pack)
    print(f"wrote {args.suite}")
    print(f"wrote {args.agent_pack}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
