#!/usr/bin/env python3
"""Allocate frozen SEC issuers to non-overlapping three-issuer packets.

This is only a source-identity plan for screening and portfolio workflows.
It does not define prompts, holdings, labels, or model observations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from preflight_reference_source_confirmation_v1 import SELECTION
from run_thesis_event_panel import HERE, sha256
from verify_reference_source_freeze_v1 import verify as verify_freeze


FREEZE = HERE / "results/2026-10-26-reference-source-qualified-freeze-v1/MANIFEST.json"
SEED = "cross-workflow-three-issuer-source-allocation-v1"
TARGET_PACKETS_PER_WORKFLOW = 20
ISSUERS_PER_PACKET = 3


def ranked(items: list[str], tag: str) -> list[str]:
    return sorted(items, key=lambda value: hashlib.sha256(
        f"{SEED}:{tag}:{value}".encode()).hexdigest())


def build() -> dict:
    verified = verify_freeze(FREEZE)
    selection = json.loads(SELECTION.read_text())
    pairs = selection["pairs"]
    if len(pairs) != 30 or len({item["symbol"] for item in pairs}) != 30:
        raise ValueError("qualified selection is not 30 unique issuers")
    by_stratum: dict[str, list[str]] = defaultdict(list)
    for item in pairs:
        by_stratum[item["stratum"]].append(item["symbol"])
    expected = {"regional_banks": 8, "payments_and_fintech": 7,
                "capital_markets_and_wealth": 7, "data_and_insurance": 8}
    if {key: len(value) for key, value in by_stratum.items()} != expected:
        raise ValueError("issuer stratum counts differ from frozen frame")
    # Each of ten ready triplets omits exactly one of four strata. Omission
    # counts 10-count(stratum) guarantee every issuer appears once, with three
    # different business strata in each packet.
    # Stable occurrence indices avoid a duplicate-key ambiguity in sorting.
    tagged = [(name, index) for name in sorted(expected)
              for index in range(10 - expected[name])]
    omissions = [name for name, _ in sorted(tagged, key=lambda pair: hashlib.sha256(
        f"{SEED}:omit:{pair[0]}:{pair[1]}".encode()).hexdigest())]
    slots = [{"packet_id": f"XW-{index:02d}", "omitted_stratum": omitted,
              "issuers": []}
             for index, omitted in enumerate(omissions, start=1)]
    for stratum, symbols in sorted(by_stratum.items()):
        eligible = [slot for slot in slots if slot["omitted_stratum"] != stratum]
        if len(eligible) != len(symbols):
            raise AssertionError("stratum allocation capacity differs")
        for slot, symbol in zip(eligible, ranked(symbols, stratum)):
            slot["issuers"].append({"symbol": symbol, "stratum": stratum})
    for slot in slots:
        slot["issuers"].sort(key=lambda item: item["stratum"])
    assigned = [item["symbol"] for slot in slots for item in slot["issuers"]]
    if (len(slots) != 10 or len(assigned) != 30 or len(set(assigned)) != 30
            or any(len(slot["issuers"]) != 3 for slot in slots)
            or any(len({item["stratum"] for item in slot["issuers"]}) != 3
                   for slot in slots)):
        raise AssertionError("ready packet allocation is not source-disjoint")
    return {
        "status": "allocation_only_no_screen_or_portfolio_model_observations",
        "source_freeze_sha256": verified["manifest_sha256"],
        "source_selection_sha256": sha256(SELECTION),
        "selection_seed": SEED,
        "ready_source_disjoint_packets": slots,
        "ready_packet_count_per_workflow": len(slots),
        "target_packet_count_per_workflow": TARGET_PACKETS_PER_WORKFLOW,
        "unfilled_packet_slots_per_workflow": TARGET_PACKETS_PER_WORKFLOW - len(slots),
        "additional_source_qualified_issuers_needed":
            TARGET_PACKETS_PER_WORKFLOW * ISSUERS_PER_PACKET - len(assigned),
        "cross_workflow_reuse": "same packet identities may be tested in separate arms; disclose dependence",
        "prompts_or_holdings_frozen": False,
        "model_observations": 0,
        "paid_calls_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    result = build()
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "ALLOCATION.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text(
        f"{sha256(path)}  ALLOCATION.json\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key != "ready_source_disjoint_packets"}, indent=2))


if __name__ == "__main__":
    main()
