#!/usr/bin/env python3
"""Offline, source-locked historical SEC screen adapter for 30 issuers.

The deterministic rule is only a research-priority filter. It never fetches
live prices, scores economic quality, or ranks heterogeneous company metrics.
"""

from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path


HERE = Path(__file__).resolve().parents[4]
ROOT = HERE.parents[1]
SELECTION = HERE / "results/2026-10-25-reference-source-pair-selection-v1/SOURCE-PAIRS.json"
FREEZE = HERE / "results/2026-10-26-reference-source-qualified-freeze-v1/MANIFEST.json"
ALLOCATION = HERE / "results/2026-10-26-cross-workflow-packet-allocation-v1/ALLOCATION.json"
METRIC_MAP = HERE / "reference_source_profit_metric_map_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_inputs() -> tuple[dict, dict, dict, dict]:
    selection = json.loads(SELECTION.read_text())
    freeze = json.loads(FREEZE.read_text())
    allocation = json.loads(ALLOCATION.read_text())
    mapping = json.loads(METRIC_MAP.read_text())["metric_by_symbol"]
    if (digest(FREEZE) != allocation["source_freeze_sha256"]
            or digest(SELECTION) != allocation["source_selection_sha256"]):
        raise ValueError("allocation source hashes differ")
    symbols = {item["symbol"] for item in selection["pairs"]}
    if len(symbols) != 30 or set(mapping) != symbols:
        raise ValueError("metric map is not exactly the frozen issuer frame")
    return selection, freeze, allocation, mapping


def candidate(pair: dict, freeze: dict, metric: str | None) -> dict:
    symbol = pair["symbol"]
    entry = freeze["packets"][symbol]
    packet_path = HERE / entry["path"]
    if digest(packet_path) != entry["sha256"]:
        raise ValueError(f"source-row packet hash mismatch: {symbol}")
    packet = json.loads(packet_path.read_text())
    periods = {}
    for name in ("CY2025_Q2", "CY2025_Q3"):
        source = pair["periods"][name]
        if digest(ROOT / source["local_path"]) != source["sha256"]:
            raise ValueError(f"official SEC exhibit hash mismatch: {symbol} {name}")
        periods[name] = {
            "filing_date": source["filing_date"], "source_url": source["url"],
            "source_sha256": source["sha256"],
        }
    rows = {}
    for row in packet["rows"]:
        delta = Decimal(row["delta_value"])
        def period_field(field: str) -> dict:
            if field + "_by_period" in row:
                return row[field + "_by_period"]
            return {period: row.get(field) for period in ("CY2025_Q2", "CY2025_Q3")}
        rows[f"SEQ:{row['id']}"] = {
            "metric": row["id"], "baseline_value": row["baseline_value"],
            "event_value": row["event_value"], "delta_value": row["delta_value"],
            "unit": row["unit"], "basis": row["basis"],
            "direction": "increase" if delta > 0 else "decrease" if delta < 0 else "flat",
            "source_label_by_period": period_field("source_label"),
            "table_index_by_period": period_field("table_index"),
            "row_index_by_period": period_field("row_index"),
        }
    selected = rows.get(f"SEQ:{metric}") if metric else None
    if metric and selected is None:
        raise ValueError(f"mapped profit row missing: {symbol} {metric}")
    if selected and not (
            selected["basis"].startswith("GAAP") or
            selected["basis"] in ("consolidated_reported", "company_reported_unaudited")):
        raise ValueError(f"profit screen row has unsuitable basis: {symbol}")
    return {
        "symbol": symbol, "business_stratum": pair["stratum"],
        "comparison_scope": "selected SEC exhibit rows, Q3 minus Q2, within issuer only",
        "source_periods": periods, "source_row_packet_sha256": entry["sha256"],
        "selected_rows": rows, "mapped_profit_comparison_id": f"SEQ:{metric}" if metric else None,
        "mapped_profit_comparison": selected,
        "source_data_synthetic": False, "live_market_data": False,
    }


def screen(symbols: list[str]) -> dict:
    selection, freeze, allocation, mapping = checked_inputs()
    by_symbol = {item["symbol"]: item for item in selection["pairs"]}
    if len(symbols) != len(set(symbols)) or not symbols or not set(symbols) <= set(by_symbol):
        raise ValueError("request only distinct frozen symbols")
    retained, rejected = [], []
    for symbol in symbols:
        item = candidate(by_symbol[symbol], freeze, mapping[symbol])
        comparison = item["mapped_profit_comparison"]
        if comparison is None:
            rejected.append({**item, "reason": "insufficient_data",
                             "missing_metrics": ["comparable_reported_profit_row"]})
        elif Decimal(comparison["delta_value"]) > 0:
            retained.append(item)
        else:
            rejected.append({**item, "reason": "criterion_not_met",
                             "failed_criteria": ["positive_sequential_reported_profit_change"]})
    return {
        "fixture_id": "REFERENCE-SOURCE-HISTORICAL-PROFIT-SCREEN-v1",
        "offline_frozen_adapter": True, "synthetic": False,
        "not_live_market_data": True,
        "scope": "within-issuer selected-profit sequential research-priority filter, not valuation or peer ranking",
        "criteria": {"positive_sequential_reported_profit_change": True},
        "basis_warning": "Profit labels vary by issuer; directions are within-issuer only and do not rank economic quality across issuers.",
        "allocation_source_freeze_sha256": allocation["source_freeze_sha256"],
        "results": retained, "rejected": rejected,
        "passed": len(retained), "failed": len(rejected),
    }


def main() -> None:
    if "--screen" not in sys.argv:
        raise SystemExit("offline adapter supports --screen only")
    available = set(json.loads(METRIC_MAP.read_text())["metric_by_symbol"])
    symbols = [arg.upper() for arg in sys.argv[1:]
               if arg.upper() in available]
    if not symbols:
        raise SystemExit("request frozen symbols")
    print(json.dumps(screen(symbols), separators=(",", ":")))


if __name__ == "__main__":
    main()
