#!/usr/bin/env python3
"""Offline-only preflight for three new-issuer SEC event-to-review examples."""

from __future__ import annotations

import hashlib
import json

from build_reference_source_distinct_event_fixtures_v1 import fixture
from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


SELECTION = HERE / "results/2026-10-27-reference-mini-prospective-source-selection-v1/SOURCE-PAIRS.json"
SYMBOLS = ("MTB", "RPAY", "CSGP")
ORDER_SEED = "reference-mini-new-issuer-event-v1"


def preflight() -> dict:
    selection = json.loads(SELECTION.read_text())
    pairs = selection["pairs"]
    if tuple(item["symbol"] for item in pairs) != SYMBOLS:
        raise ValueError("mini-panel issuer order or membership differs")
    fixtures = []
    verified_rows = {}
    for pair in pairs:
        symbol = pair["symbol"]
        packet_path = HERE / f"{symbol.lower()}_mini_source_row_audit_v1.json"
        packet = json.loads(packet_path.read_text())
        result = verify(packet_path)
        if result["source_pair_selection_sha256"] != hashlib.sha256(SELECTION.read_bytes()).hexdigest():
            raise ValueError("packet and source selection hashes differ")
        if result["checked_rows"] < 10 or packet["symbol"] != symbol:
            raise ValueError("source row coverage or symbol differs")
        fixtures.append(fixture(pair, packet))
        verified_rows[symbol] = result["checked_rows"]
    run_order = [f"{case['case_id']}-r{repeat}"
                 for case in fixtures for repeat in (1, 2)]
    run_order.sort(key=lambda name: hashlib.sha256(
        f"{ORDER_SEED}:{name}".encode()).hexdigest())
    if len(run_order) != 6 or len(set(run_order)) != 6:
        raise ValueError("mini-panel run order differs")
    return {
        "status": "offline_source_verified_no_model_observations",
        "issuer_cases": len(fixtures),
        "verified_comparable_rows": verified_rows,
        "planned_independent_sessions": len(run_order),
        "run_order": run_order,
        "run_order_sha256": hashlib.sha256(json.dumps(run_order).encode()).hexdigest(),
        "source_selection_sha256": hashlib.sha256(SELECTION.read_bytes()).hexdigest(),
        "model_observations": 0,
        "paid_calls_authorized": False,
        "fixtures": fixtures,
    }


if __name__ == "__main__":
    result = preflight()
    print(json.dumps({key: value for key, value in result.items()
                      if key != "fixtures"}, indent=2))
