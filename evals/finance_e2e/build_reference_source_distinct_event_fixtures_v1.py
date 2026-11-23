#!/usr/bin/env python3
"""Render frozen 30-issuer selected SEC rows into model-facing event fixtures.

Only source values, locators and host-computed signed differences are exposed.
Investigator limitations and case-critical adjudication notes stay private.
This is an offline preflight; it makes no Gateway or provider call.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from preflight_reference_source_confirmation_v1 import SELECTION
from run_thesis_event_panel import HERE
from verify_reference_source_freeze_v1 import verify as verify_freeze


FREEZE = HERE / "results/2026-10-26-reference-source-qualified-freeze-v1/MANIFEST.json"
ORDER_SEED = "reference-source-distinct-event-30-v1"


def _number(value: str) -> str:
    return format(Decimal(value).normalize(), "f")


def _row_field(row: dict, field: str, period: str):
    by_period = row.get(field + "_by_period")
    return by_period[period] if by_period is not None else row[field]


def _source_ref(symbol: str, period: str, source: dict) -> dict:
    return {"id": f"RS-{symbol}-{period[-2:]}",
            "url": source["url"], "sha256": source["sha256"]}


def _fact_text(row: dict, period: str, value: str) -> str:
    label = _row_field(row, "source_label", period)
    table = _row_field(row, "table_index", period)
    source_row = _row_field(row, "row_index", period)
    return (f"{row['id']}={_number(value)} {row['unit']} [{row['basis']}] "
            f"(SEC table {table}, row {source_row}, label {label!r})")


def fixture(pair: dict, packet: dict) -> dict:
    symbol = pair["symbol"]
    if packet["symbol"] != symbol or packet["model_observations"] != 0:
        raise ValueError("issuer packet identity/observation differs")
    q2, q3 = "CY2025_Q2", "CY2025_Q3"
    baseline_ref = _source_ref(symbol, q2, pair["periods"][q2])
    event_ref = _source_ref(symbol, q3, pair["periods"][q3])
    rows = {}
    baseline_lines, event_lines, comparison_lines = [], [], []
    observed_metrics = {}
    for row in packet["rows"]:
        baseline, event, delta = (Decimal(row[name]) for name in
                                  ("baseline_value", "event_value", "delta_value"))
        if event - baseline != delta:
            raise ValueError(f"signed comparison differs: {symbol} {row['id']}")
        baseline_lines.append(_fact_text(row, q2, row["baseline_value"]))
        event_lines.append(_fact_text(row, q3, row["event_value"]))
        identifier = f"SEQ:{row['id']}"
        rows[identifier] = {
            "metric": row["id"], "baseline_value": _number(row["baseline_value"]),
            "event_value": _number(row["event_value"]),
            "delta_value": _number(row["delta_value"]),
            "direction": ("increase" if delta > 0 else "decrease" if delta < 0
                          else "flat"), "unit": row["unit"], "basis": row["basis"],
            "precision": "difference_of_verified_displayed_values",
        }
        comparison_lines.append(
            f"{identifier}: {_number(row['delta_value'])} {row['unit']} "
            f"[{row['basis']}] Q3 minus Q2; not a causal attribution")
        observed_metrics[row["id"]] = {
            "value": _number(row["event_value"]), "unit": row["unit"],
            "fact_id": f"RS-{symbol}-Q3-{row['id']}",
        }
    if len(rows) != len(packet["rows"]):
        raise ValueError("duplicate comparison ID")
    for row in packet.get("baseline_only_rows", []):
        baseline_lines.append("Q2 only, no Q3 comparator: "
                              + _fact_text(row, q2, row["baseline_value"]))
    for row in packet.get("event_only_rows", []):
        event_lines.append("Q3 only, no Q2 comparator: "
                           + _fact_text(row, q3, row["event_value"]))
        observed_metrics[row["id"]] = {
            "value": _number(row["event_value"]), "unit": row["unit"],
            "fact_id": f"RS-{symbol}-Q3-{row['id']}",
        }
    if len(observed_metrics) != len(packet["rows"]) + len(packet.get("event_only_rows", [])):
        raise ValueError("duplicate event metric ID")
    context = (
        f"{symbol}: selected SEC exhibit rows for calendar quarters ended "
        "2025-06-30 and 2025-09-30. These are selected disclosures, not complete "
        "filings; do not infer that an omitted item is absent from the filing. "
        "All comparisons are sequential displayed-value arithmetic, not YoY "
        "comparisons or established economic causes. Stocks, flows, ratios, "
        "GAAP and company-defined measures retain their stated bases.\n"
        f"Q2 source {baseline_ref['id']} SHA-256 {baseline_ref['sha256']} "
        f"{baseline_ref['url']}\n"
        f"Q3 source {event_ref['id']} SHA-256 {event_ref['sha256']} "
        f"{event_ref['url']}\n"
        "Q2 selected source facts:\n" + "\n".join(baseline_lines)
        + "\nQ3 selected source facts:\n" + "\n".join(event_lines)
        + "\nHost-computed comparable signed differences:\n"
        + "\n".join(comparison_lines)
    )
    case_id = f"RS-{symbol}-CY2025Q2Q3"
    seed = {
        "market": "US", "symbol": symbol,
        "title": f"{symbol} source-bounded earnings research thesis",
        "thesis": (f"Baseline Q2 selected SEC facts for {symbol}: "
                   + "; ".join(baseline_lines)
                   + ". Reassess on the next earnings release; no valuation, "
                     "trade or change in conviction is preordained."),
        "status": "active", "conviction": 3,
        "required_event_metrics": sorted(observed_metrics),
        "evidence": [baseline_ref],
    }
    event = {
        "external_id": f"{case_id}-EVENT", "type": "earnings",
        "as_of": pair["periods"][q3]["filing_date"],
        "summary": (f"{symbol} Q3 selected SEC facts: " + "; ".join(event_lines)),
        "sources": [event_ref], "observed_metrics": observed_metrics,
    }
    catalog = {
        "case_id": case_id, "symbol": symbol,
        "scope": "selected_source_rows_not_full_filing",
        "comparison": "sequential_event_minus_baseline_not_year_over_year",
        "baseline": {"period": q2, "source_id": baseline_ref["id"],
                     "source_url": baseline_ref["url"],
                     "source_sha256": baseline_ref["sha256"],
                     "filing_date": pair["periods"][q2]["filing_date"]},
        "event": {"period": q3, "source_id": event_ref["id"],
                  "source_url": event_ref["url"],
                  "source_sha256": event_ref["sha256"],
                  "filing_date": pair["periods"][q3]["filing_date"]},
        "rows": rows,
    }
    return {"case_id": case_id, "runtime_symbol": symbol,
            "seed_thesis": seed, "event": event,
            "numeric_context": context, "catalog": catalog}


def preflight() -> dict:
    frozen = verify_freeze(FREEZE)
    if frozen["counts"]["issuers"] != 30:
        raise ValueError("source freeze is not the 30-issuer frame")
    selection = json.loads(SELECTION.read_text())
    manifest = json.loads(FREEZE.read_text())
    fixtures = [fixture(pair, json.loads((HERE / manifest["packets"][pair["symbol"]]["path"]).read_text()))
                for pair in selection["pairs"]]
    if len(fixtures) != 30 or len({x["case_id"] for x in fixtures}) != 30:
        raise ValueError("fixture case membership differs")
    run_order = [f"{x['case_id']}-r{repetition}"
                 for x in fixtures for repetition in range(1, 6)]
    run_order.sort(key=lambda name: hashlib.sha256(
        f"{ORDER_SEED}:{name}".encode()).hexdigest())
    return {
        "status": "offline_source_distinct_event_fixtures_no_model_observations",
        "issuer_cases": len(fixtures),
        "comparable_rows": sum(len(x["catalog"]["rows"]) for x in fixtures),
        "planned_fresh_sessions": len(run_order),
        "run_order_sha256": hashlib.sha256(json.dumps(run_order).encode()).hexdigest(),
        "run_order": run_order,
        "source_freeze_sha256": frozen["manifest_sha256"],
        "model_observations": 0,
        "paid_calls_authorized": False,
        "fixtures": fixtures,
    }


if __name__ == "__main__":
    result = preflight()
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ("fixtures", "run_order")}, indent=2))
