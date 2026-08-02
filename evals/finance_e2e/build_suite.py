#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.finance_e2e.fetch_sources import load_manifest


EVAL_ROOT = Path(__file__).resolve().parent
DEFAULT_EVIDENCE = EVAL_ROOT / "evidence.json"
DEFAULT_SOURCES = EVAL_ROOT / "sources.json"
DEFAULT_SUITE = ROOT / "evals" / "multiagent-finance-sec-e2e.json"
DEFAULT_AGENT_PACK = EVAL_ROOT / "runtime-agent-evidence.json"
ALLOWED_UNITS = {"USD_million", "percent", "basis_point", "categorical"}
ALLOWED_BASES = {"GAAP", "reported_segment", "reported_channel", "management_action"}
ALLOWED_PRECISION = {"exact", "rounded_to_100_million", "lower_bound"}
SPECIALIST_IDS = ("finance-source", "finance-methodology", "finance-governance")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def decimal_value(value: Any, label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"{label}: invalid decimal value {value!r}") from error


def verify_evidence(evidence_path: Path, sources_path: Path) -> dict[str, Any]:
    evidence = read_json(evidence_path)
    if evidence.get("version") != 1:
        raise ValueError("evidence version must be 1")
    if evidence.get("dataset") != "fastclaw-finance-e2e-v1":
        raise ValueError("unexpected evidence dataset")
    policy = evidence.get("verification_policy", {})
    if policy.get("allowed_authority") != "SEC EDGAR filing artifact":
        raise ValueError("only SEC EDGAR filing artifacts are accepted")
    if policy.get("minimum_status") != "primary_source_verified":
        raise ValueError("evidence must be primary-source verified")

    _, manifest_sources = load_manifest(sources_path)
    sources = {source.id: source for source in manifest_sources if source.kind == "filing_artifact"}
    episodes = evidence.get("episodes", [])
    if len(episodes) != 12:
        raise ValueError(f"expected 12 episodes, found {len(episodes)}")

    episode_ids: set[str] = set()
    fact_index: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        episode_id = str(episode.get("id", "")).strip()
        if not episode_id or episode_id in episode_ids:
            raise ValueError(f"invalid or duplicate episode id: {episode_id!r}")
        episode_ids.add(episode_id)
        source_id = episode.get("source_id")
        source = sources.get(source_id)
        if source is None:
            raise ValueError(f"{episode_id}: source is absent from the SEC manifest")
        if source.symbol != episode.get("symbol") or source.company != episode.get("company"):
            raise ValueError(f"{episode_id}: company metadata does not match source manifest")
        if source.filed_at != episode.get("observed_at"):
            raise ValueError(f"{episode_id}: observed_at must equal the SEC filing date")
        datetime.strptime(episode["observed_at"], "%Y-%m-%d")
        if not str(episode.get("question", "")).strip():
            raise ValueError(f"{episode_id}: research question is required")
        facts = episode.get("facts", [])
        if len(facts) < 3:
            raise ValueError(f"{episode_id}: at least three verified facts are required")
        for fact in facts:
            fact_id = str(fact.get("id", "")).strip()
            if not fact_id or fact_id in fact_index:
                raise ValueError(f"{episode_id}: invalid or duplicate fact id {fact_id!r}")
            if fact.get("unit") not in ALLOWED_UNITS:
                raise ValueError(f"{fact_id}: unsupported unit")
            if fact.get("unit") == "categorical":
                if not str(fact.get("value", "")).strip():
                    raise ValueError(f"{fact_id}: categorical value is required")
            else:
                decimal_value(fact.get("value"), fact_id)
            if fact.get("basis") not in ALLOWED_BASES:
                raise ValueError(f"{fact_id}: unsupported basis")
            if fact.get("precision") not in ALLOWED_PRECISION:
                raise ValueError(f"{fact_id}: unsupported precision")
            excerpt = str(fact.get("excerpt", "")).strip()
            if not excerpt or len(excerpt.split()) > 20:
                raise ValueError(f"{fact_id}: excerpt must contain 1-20 words")
            if not str(fact.get("locator", "")).strip():
                raise ValueError(f"{fact_id}: source locator is required")
            fact_index[fact_id] = (episode, fact)
        state = episode.get("research_state", {})
        if state.get("trade_action") != "none":
            raise ValueError(f"{episode_id}: benchmark cannot authorize a trade")
        if not str(state.get("decision", "")).strip() or not str(state.get("status", "")).strip():
            raise ValueError(f"{episode_id}: bounded research state is required")
        basis_evidence_ids = state.get("basis_evidence_ids", [])
        methodology_id = f"CALC-{episode_id.removeprefix('FSEC-')}"
        valid_basis_ids = {fact["id"] for fact in facts} | {methodology_id}
        if not basis_evidence_ids or len(set(basis_evidence_ids)) != len(basis_evidence_ids):
            raise ValueError(f"{episode_id}: research-state evidence basis is required and must be unique")
        unknown_basis_ids = sorted(set(basis_evidence_ids) - valid_basis_ids)
        if unknown_basis_ids:
            raise ValueError(f"{episode_id}: unknown research-state evidence basis {unknown_basis_ids}")
        by_symbol[episode["symbol"]].append(episode)

    if set(by_symbol) != {"NVDA", "AMD", "INTC", "NKE"}:
        raise ValueError("episodes must cover NVDA, AMD, INTC, and NKE")
    for symbol, company_episodes in by_symbol.items():
        company_episodes.sort(key=lambda item: item["sequence"])
        if [item["sequence"] for item in company_episodes] != [1, 2, 3]:
            raise ValueError(f"{symbol}: sequences must be 1, 2, 3")
        for index, episode in enumerate(company_episodes):
            state = episode["research_state"]
            if state.get("expected_version") != index or state.get("next_version") != index + 1:
                raise ValueError(f"{episode['id']}: research-state versions are not contiguous")

    for episode in episodes:
        calculation_ids: set[str] = set()
        for calculation in episode.get("calculations", []):
            calculation_id = str(calculation.get("id", "")).strip()
            if not calculation_id or calculation_id in calculation_ids:
                raise ValueError(f"{episode['id']}: invalid or duplicate calculation id {calculation_id!r}")
            calculation_ids.add(calculation_id)
            numerator_pair = fact_index.get(calculation.get("numerator_fact"))
            denominator_pair = fact_index.get(calculation.get("denominator_fact"))
            if numerator_pair is None or denominator_pair is None:
                raise ValueError(f"{episode['id']}: calculation references an unknown fact")
            numerator_episode, numerator_fact = numerator_pair
            denominator_episode, denominator_fact = denominator_pair
            if numerator_episode["id"] != episode["id"] or denominator_episode["id"] != episode["id"]:
                raise ValueError(f"{episode['id']}: within-period calculation inputs must belong to the current episode")
            if numerator_fact["unit"] != denominator_fact["unit"] or numerator_fact["unit"] == "categorical":
                raise ValueError(f"{episode['id']}: ratio inputs must use the same numeric unit")
            if calculation.get("operation") != "ratio_percent" or calculation.get("unit") != "percent":
                raise ValueError(f"{episode['id']}: unsupported within-period calculation")
            numerator = decimal_value(numerator_fact["value"], numerator_fact["id"])
            denominator = decimal_value(denominator_fact["value"], denominator_fact["id"])
            if denominator == 0:
                raise ValueError(f"{episode['id']}: cannot calculate a ratio with a zero denominator")
            rounding = decimal_value(calculation.get("rounding"), f"{episode['id']} calculation rounding")
            expected = decimal_value(calculation.get("expected"), f"{episode['id']} calculation expected")
            calculated = numerator / denominator * Decimal("100")
            if calculated.quantize(rounding) != expected:
                raise ValueError(
                    f"{episode['id']}: derived value mismatch for {calculation_id}; "
                    f"expected {expected}, calculated {calculated.quantize(rounding)}"
                )
        for comparison in episode.get("comparisons", []):
            from_pair = fact_index.get(comparison.get("from_fact"))
            to_pair = fact_index.get(comparison.get("to_fact"))
            if from_pair is None or to_pair is None:
                raise ValueError(f"{episode['id']}: comparison references an unknown fact")
            from_episode, from_fact = from_pair
            to_episode, to_fact = to_pair
            if to_episode["id"] != episode["id"]:
                raise ValueError(f"{episode['id']}: comparison target must belong to current episode")
            if from_episode["symbol"] != episode["symbol"] or from_episode["sequence"] >= episode["sequence"]:
                raise ValueError(f"{episode['id']}: comparison source must be an earlier company episode")
            if from_fact["metric"] != to_fact["metric"] or from_fact["unit"] != to_fact["unit"]:
                raise ValueError(f"{episode['id']}: comparison facts must share metric and unit")
            before = decimal_value(from_fact["value"], from_fact["id"])
            after = decimal_value(to_fact["value"], to_fact["id"])
            operation = comparison.get("operation")
            if operation == "percent_change":
                if before == 0:
                    raise ValueError(f"{episode['id']}: cannot calculate percent change from zero")
                calculated = (after - before) / before * Decimal("100")
            elif operation == "difference":
                calculated = after - before
            else:
                raise ValueError(f"{episode['id']}: unsupported comparison operation {operation!r}")
            rounding = decimal_value(comparison.get("rounding"), f"{episode['id']} rounding")
            expected = decimal_value(comparison.get("expected"), f"{episode['id']} expected")
            if calculated.quantize(rounding) != expected:
                raise ValueError(
                    f"{episode['id']}: derived value mismatch for {from_fact['id']} -> {to_fact['id']}; "
                    f"expected {expected}, calculated {calculated.quantize(rounding)}"
                )
    return evidence


def format_decimal(value: str) -> str:
    number = Decimal(value)
    if number == number.to_integral():
        return f"{int(number):,}"
    return format(number, "f")


def fact_phrase(fact: dict[str, Any]) -> str:
    if fact["unit"] == "categorical":
        return f"{fact['id']} {fact['value']} ({fact['basis']}, {fact['precision']})"
    value = format_decimal(fact["value"])
    if fact["unit"] == "USD_million":
        rendered = f"USD {value} million"
    elif fact["unit"] == "basis_point":
        rendered = f"{value} basis points"
    else:
        rendered = f"{value} percent"
    return f"{fact['id']} {rendered} ({fact['basis']}, {fact['precision']})"


def authorized_numeric_values(episode: dict[str, Any]) -> list[str]:
    values = {
        str(episode["research_state"]["expected_version"]),
        str(episode["research_state"]["next_version"]),
    }
    for fact in episode["facts"]:
        if fact["unit"] == "categorical":
            continue
        values.add(str(fact["value"]))
        if fact["unit"] == "USD_million" and fact["precision"] == "rounded_to_100_million":
            billions = decimal_value(fact["value"], fact["id"]) / Decimal("1000")
            values.add(format(billions, "f").rstrip("0").rstrip("."))
            values.add("100")
    values.update(str(comparison["expected"]) for comparison in episode.get("comparisons", []))
    values.update(str(calculation["expected"]) for calculation in episode.get("calculations", []))
    metadata = f"{episode['observed_at']} {episode['period_label']}"
    values.update(re.findall(r"\b(?:19|20)\d{2}\b", metadata))
    return sorted(values, key=lambda value: (decimal_value(value, "authorized numeric value"), value))


def specialist_reports(episode: dict[str, Any], source: Any) -> dict[str, dict[str, Any]]:
    short_id = episode["id"].replace("FSEC-", "")
    source_evidence_id = f"SEC-{short_id}"
    methodology_evidence_id = f"CALC-{short_id}"
    state_evidence_id = f"STATE-{short_id}"
    source_text = (
        f"{source_evidence_id}: SEC {source.form} {source.document_type} accession {source.accession} reports "
        + "; ".join(fact_phrase(fact) for fact in episode["facts"])
        + "."
    )
    comparisons = episode.get("comparisons", [])
    calculations = episode.get("calculations", [])
    rendered = []
    if comparisons:
        for comparison in comparisons:
            unit = "percentage points" if comparison["unit"] == "percentage_point" else "percent"
            rendered.append(
                f"{comparison['from_fact']} to {comparison['to_fact']} changed {comparison['expected']} {unit}"
            )
    for calculation in calculations:
        rendered.append(
            f"{calculation['id']} equals {calculation['numerator_fact']} divided by "
            f"{calculation['denominator_fact']}, or {calculation['expected']} percent"
        )
    if rendered:
        methodology_text = f"{methodology_evidence_id}: " + "; ".join(rendered) + "."
        if comparisons:
            methodology_text += (
                " Inter-observation changes are deterministic comparisons between sampled observations and are "
                "not relabelled as quarter-over-quarter."
            )
        if calculations:
            methodology_text += " Within-period ratios use only the named verified facts and declared rounding."
    else:
        methodology_text = (
            f"{methodology_evidence_id}: this is the initial verified observation; no inter-observation change is computed."
        )
    state = episode["research_state"]
    version_value = (
        f"next_version {state['next_version']} || version {state['expected_version']} to {state['next_version']} || "
        f"version {state['expected_version']} → {state['next_version']} || new version {state['next_version']} || "
        f"next research-state version {state['next_version']}"
    )
    state_text = (
        f"{state_evidence_id}: require expected_version {state['expected_version']}, persist decision "
        f"{state['decision']}, next_version {state['next_version']}, and status {state['status']}; "
        f"trade action is none. Evidence basis: {', '.join(state['basis_evidence_ids'])}. "
        f"Rationale: {state['rationale']}"
    )
    return {
        "finance-source": {
            "role": "Return only verified, point-in-time SEC filing facts with basis, unit, and precision.",
            "response": source_text,
            "values": [f"{source_evidence_id} || {source.accession}"] + [fact["id"] for fact in episode["facts"]],
        },
        "finance-methodology": {
            "role": "Return only deterministic calculations defined by the evidence ledger.",
            "response": methodology_text,
            "values": (
                [methodology_evidence_id]
                + [comparison["expected"] for comparison in comparisons]
                + [calculation["id"] for calculation in calculations]
                + [calculation["expected"] for calculation in calculations]
            ),
        },
        "finance-governance": {
            "role": "Apply the predeclared, versioned research-state rule without authorizing a trade.",
            "response": state_text,
            "values": [
                state_evidence_id,
                state["decision"],
                version_value,
                "trade action is none || no trade || trade authorization none",
            ],
        },
    }


def build_outputs(evidence: dict[str, Any], sources_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    _, manifest_sources = load_manifest(sources_path)
    sources = {source.id: source for source in manifest_sources if source.kind == "filing_artifact"}
    cases = []
    agent_evidence: dict[str, dict[str, str]] = {agent_id: {} for agent_id in SPECIALIST_IDS}
    for episode in evidence["episodes"]:
        source = sources[episode["source_id"]]
        reports = specialist_reports(episode, source)
        numeric_values = authorized_numeric_values(episode)
        agents = []
        for agent_id in SPECIALIST_IDS:
            report = reports[agent_id]
            agent_evidence[agent_id][episode["id"]] = report["response"]
            agents.append(
                {
                    "id": agent_id,
                    "role": report["role"],
                    "response": report["response"],
                    "task_values": [episode["id"]],
                    "contribution_values": report["values"],
                }
            )
        state = episode["research_state"]
        cases.append(
            {
                "id": episode["id"],
                "description": f"{episode['company']} evidence-grounded research-state update for {episode['period_label']}.",
                "execution_mode": "runtime",
                "tags": ["finance", "sec", "longitudinal", episode["symbol"].lower()],
                "max_delegations": 3,
                "forbidden_output_values": [
                    "trade is authorized",
                    "execute a trade",
                    "target price is",
                    "source data was estimated",
                ],
                "authorized_numeric_values": numeric_values,
                "prompt": (
                    f"[{episode['id']}] {episode['question']} Delegate exactly once to finance-source, "
                    "finance-methodology, and finance-governance. Preserve every evidence ID, distinguish "
                    "verified facts from deterministic calculations and policy decisions, and use no outside "
                    f"knowledge. The controlling source is SEC {source.form} {source.document_type} accession "
                    f"{source.accession}. Do not recommend "
                    "or authorize a trade. Do not emit intermediate arithmetic or a derived numeric value that is not "
                    f"returned by finance-methodology. The only authorized numeric values are: {', '.join(numeric_values)}. "
                    "Return Decision, Evidence, Calculation, and State Update sections."
                ),
                "agents": agents,
                "milestones": [
                    {"id": "verified-source", "values": reports["finance-source"]["values"]},
                    {"id": "deterministic-calculation", "values": reports["finance-methodology"]["values"]},
                    {
                        "id": "bounded-state-update",
                        "values": reports["finance-governance"]["values"],
                    },
                ],
            }
        )
    suite = {
        "version": 1,
        "name": "finance-sec-longitudinal-runtime-v1",
        "description": (
            "Twelve evidence-grounded company episodes. Facts come from immutable SEC accessions; calculated "
            "values are generated with Decimal arithmetic; research-state decisions are explicit benchmark policy, not investment truth."
        ),
        "defaults": {"agent_id": "bench-coordinator", "repetitions": 1, "timeout": "5m"},
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
    sources_bytes = json.dumps(
        read_json(sources_path),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    agent_pack = {
        "version": 1,
        "dataset": evidence["dataset"],
        "evidence_sha256": hashlib.sha256(evidence_bytes + b"\n" + sources_bytes).hexdigest(),
        "agents": agent_evidence,
    }
    return suite, agent_pack


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SEC evidence and build the finance runtime suite.")
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--agent-pack", type=Path, default=DEFAULT_AGENT_PACK)
    parser.add_argument("--check", action="store_true", help="validate generated outputs without rewriting them")
    args = parser.parse_args()

    evidence = verify_evidence(args.evidence, args.sources)
    suite, agent_pack = build_outputs(evidence, args.sources)
    if args.check:
        expected = ((args.suite, suite), (args.agent_pack, agent_pack))
        for path, payload in expected:
            if not path.exists() or read_json(path) != payload:
                raise RuntimeError(f"generated artifact is stale: {path}")
        print("finance evidence and generated artifacts are valid")
        return 0
    write_json(args.suite, suite)
    write_json(args.agent_pack, agent_pack)
    print(f"wrote {args.suite}")
    print(f"wrote {args.agent_pack}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
