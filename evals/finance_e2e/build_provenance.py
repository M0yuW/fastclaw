#!/usr/bin/env python3
"""Build deterministic, source-locked provenance for the finance gold oracle."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE = ROOT / "evals" / "finance_e2e" / "evidence.json"
DEFAULT_SOURCES = ROOT / "evals" / "finance_e2e" / "sources.json"
DEFAULT_LOCK = ROOT / "evals" / "finance_e2e" / "source-lock.json"
DEFAULT_ACCEPTANCE_LOCK = ROOT / "evals" / "finance_e2e" / "acceptance-time-lock.json"
DEFAULT_JSON = ROOT / "evals" / "finance_e2e" / "gold-fact-provenance.json"
DEFAULT_CSV = ROOT / "evals" / "finance_e2e" / "gold-fact-provenance.csv"
DEFAULT_DERIVED_JSON = ROOT / "evals" / "finance_e2e" / "gold-derived-provenance.json"
DEFAULT_DERIVED_CSV = ROOT / "evals" / "finance_e2e" / "gold-derived-provenance.csv"

FACT_FIELDS = [
    "fact_id", "company", "symbol", "concept", "value", "unit", "basis", "scope",
    "reporting_period", "filing_date", "accepted_at", "accession", "form",
    "document_type", "url", "locator", "source_sha256", "derivation", "missing_reason",
]
DERIVED_FIELDS = [
    "derived_id", "company", "symbol", "operation", "input_fact_ids", "unit",
    "rounding_rule", "expected_result", "formula", "source_episode_id",
]


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def csv_rows(rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, str]]:
    return [
        {field: json.dumps(row[field]) if isinstance(row[field], list) else str(row[field]) for field in fields}
        for row in rows
    ]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def formula_for(item: dict[str, Any]) -> tuple[list[str], str]:
    if "numerator_fact" in item:
        inputs = [item["numerator_fact"], item["denominator_fact"]]
        return inputs, f"100 * {inputs[0]} / {inputs[1]}"
    inputs = [item["from_fact"], item["to_fact"]]
    if item["operation"] == "percent_change":
        return inputs, f"100 * ({inputs[1]} - {inputs[0]}) / {inputs[0]}"
    return inputs, f"{inputs[1]} - {inputs[0]}"


def build(
    evidence_path: Path, sources_path: Path, lock_path: Path,
    acceptance_lock_path: Path = DEFAULT_ACCEPTANCE_LOCK,
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = read_json(evidence_path)
    sources = {row["id"]: row for row in read_json(sources_path)["sources"]}
    locked = {row["id"]: row for row in read_json(lock_path)["entries"]}
    acceptance = {row["accession"]: row for row in read_json(acceptance_lock_path)["entries"]}
    facts: list[dict[str, Any]] = []
    derived: list[dict[str, Any]] = []
    for episode in evidence["episodes"]:
        source = sources[episode["source_id"]]
        lock = locked[episode["source_id"]]
        accepted = acceptance[source["accession"]]
        if accepted["filing_date"] != source["filed_at"] or accepted["form"] != source["form"]:
            raise ValueError(f"acceptance metadata mismatch: {source['accession']}")
        for fact in episode.get("facts", []):
            missing: list[str] = []
            scope = fact.get("scope", "")
            if not scope:
                missing.append("scope not explicitly stated in the human oracle")
            facts.append(
                {
                    "fact_id": fact["id"],
                    "company": episode["company"],
                    "symbol": episode["symbol"],
                    "concept": fact["metric"],
                    "value": fact["value"],
                    "unit": fact["unit"],
                    "basis": fact["basis"],
                    "scope": scope,
                    "reporting_period": episode["period_label"],
                    "filing_date": source["filed_at"],
                    "accepted_at": accepted["accepted_at"],
                    "accession": source["accession"],
                    "form": source["form"],
                    "document_type": source["document_type"],
                    "url": source["url"],
                    "locator": fact["locator"],
                    "source_sha256": lock["sha256"],
                    "derivation": "source_fact",
                    "missing_reason": "; ".join(missing),
                }
            )
        for category in ("calculations", "comparisons"):
            for index, item in enumerate(episode.get(category, []), 1):
                inputs, formula = formula_for(item)
                derived.append(
                    {
                        "derived_id": item.get("id") or f"{episode['id']}|{category}|{index}",
                        "company": episode["company"],
                        "symbol": episode["symbol"],
                        "operation": item["operation"],
                        "input_fact_ids": inputs,
                        "unit": item["unit"],
                        "rounding_rule": item["rounding"],
                        "expected_result": item["expected"],
                        "formula": formula,
                        "source_episode_id": episode["id"],
                    }
                )
    if len(facts) != 44 or len(derived) != 17:
        raise ValueError(f"unexpected oracle size: {len(facts)} facts and {len(derived)} derived values")
    return (
        {"schema_version": 1, "artifact_status": "human-oracle-provenance", "facts": facts},
        {"schema_version": 1, "artifact_status": "human-oracle-derived-provenance", "derived_values": derived},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--source-lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--acceptance-lock", type=Path, default=DEFAULT_ACCEPTANCE_LOCK)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    facts, derived = build(args.evidence, args.sources, args.source_lock, args.acceptance_lock)
    if args.check:
        if read_json(DEFAULT_JSON) != facts or read_json(DEFAULT_DERIVED_JSON) != derived:
            raise RuntimeError("generated provenance JSON is stale")
        if read_csv(DEFAULT_CSV) != csv_rows(facts["facts"], FACT_FIELDS):
            raise RuntimeError("generated fact provenance CSV is stale")
        if read_csv(DEFAULT_DERIVED_CSV) != csv_rows(derived["derived_values"], DERIVED_FIELDS):
            raise RuntimeError("generated derived provenance CSV is stale")
        print("Gold provenance is valid and current: 44 facts, 17 derived values")
        return 0
    write_json(DEFAULT_JSON, facts)
    write_json(DEFAULT_DERIVED_JSON, derived)
    csv_facts = csv_rows(facts["facts"], FACT_FIELDS)
    csv_derived = csv_rows(derived["derived_values"], DERIVED_FIELDS)
    write_csv(DEFAULT_CSV, csv_facts, FACT_FIELDS)
    write_csv(DEFAULT_DERIVED_CSV, csv_derived, DERIVED_FIELDS)
    print("Wrote provenance for 44 facts and 17 derived values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
