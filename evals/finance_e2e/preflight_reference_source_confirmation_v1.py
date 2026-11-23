#!/usr/bin/env python3
"""Read-only gate for the 30-issuer source-distinct confirmation frame.

Presence of a frozen SEC attachment or shared-label catalog is not a numeric
gold packet. This gate fails closed until every selected issuer has a verified
row audit. No model is called and no result file is overwritten.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_reference_source_distinct_frame_v1 import sha256
from run_thesis_event_panel import HERE, ROOT
from verify_reference_source_row_packet_v1 import verify


SELECTION = HERE / "results/2026-10-25-reference-source-pair-selection-v1/SOURCE-PAIRS.json"
FRAME = HERE / "results/2026-10-25-reference-source-distinct-frame-v2/FRAME.json"


def inspect(selection_path: Path = SELECTION, frame_path: Path = FRAME) -> dict:
    selection = json.loads(selection_path.read_text())
    frame = json.loads(frame_path.read_text())
    if selection.get("frame_sha256") != sha256(frame_path):
        raise ValueError("selected source pairs do not match frozen issuer frame")
    if selection.get("source_pair_count") != 30 or len(selection.get("pairs", [])) != 30:
        raise ValueError("confirmation frame must retain 30 source pairs")
    symbols = [pair["symbol"] for pair in selection["pairs"]]
    if len(set(symbols)) != 30:
        raise ValueError("selected issuer symbols are not unique")
    if sum(item["quota"] for item in frame["strata"].values()) != 30:
        raise ValueError("frozen stratum quotas no longer total 30")
    expected = {item["ticker"]: stratum
                for stratum, group in frame["strata"].items()
                for item in group["planned"]}
    replacements = {}
    for pair in selection["pairs"]:
        symbol, stratum, replaced = pair["symbol"], pair["stratum"], pair.get("replaces")
        if replaced:
            if replaced not in expected or expected[replaced] != stratum or replaced in replacements:
                raise ValueError("replacement does not preserve planned stratum")
            reserve = frame["strata"][stratum]["reserves_in_order"][0]["ticker"]
            if symbol != reserve:
                raise ValueError("replacement is not next hash-ranked same-stratum reserve")
            replacements[replaced] = symbol
        elif expected.get(symbol) != stratum:
            raise ValueError("source pair differs from frozen planned stratum")
        if set(pair.get("periods", {})) != {"CY2025_Q2", "CY2025_Q3"}:
            raise ValueError("source pair periods incomplete")
        for source in pair["periods"].values():
            if (not source.get("url", "").startswith("https://www.sec.gov/Archives/")
                    or sha256(ROOT / source["local_path"]) != source["sha256"]):
                raise ValueError(f"SEC source artifact differs: {symbol}")
    if set(symbols) != (set(expected) - set(replacements)) | set(replacements.values()):
        raise ValueError("source selection does not cover frozen planned frame")

    checked = []
    legacy = []
    missing = []
    invalid = []
    for pair in selection["pairs"]:
        symbol = pair["symbol"]
        version = 2 if symbol == "BOKF" else 1
        path = HERE / f"{symbol.lower()}_reference_source_row_audit_v{version}.json"
        if not path.is_file():
            missing.append(symbol)
            continue
        packet = json.loads(path.read_text())
        if packet.get("symbol") != symbol or packet.get("model_observations") != 0 or packet.get("quality_pass") is not None:
            invalid.append({"symbol": symbol, "reason": "packet identity or quality claim invalid"})
            continue
        if "source_pair_selection" not in packet:
            legacy.append({"symbol": symbol, "reason": "legacy audit requires unified row locator verification"})
            continue
        if HERE / packet["source_pair_selection"] != selection_path:
            invalid.append({"symbol": symbol, "reason": "packet points to another source-pair selection"})
            continue
        try:
            result = verify(path)
        except (ValueError, KeyError, IndexError) as exc:
            invalid.append({"symbol": symbol, "reason": str(exc)})
            continue
        if result["checked_rows"] < 6:
            invalid.append({"symbol": symbol, "reason": "fewer than six verified comparable rows"})
            continue
        checked.append({"symbol": symbol, "comparable_rows": result["checked_rows"],
                        "event_only_rows": result["event_only_checked_rows"],
                        "baseline_only_rows": result["baseline_only_checked_rows"],
                        "packet_sha256": sha256(path)})
    ready = len(checked) == 30 and not (legacy or missing or invalid)
    return {
        "status": "ready_for_confirmation_source_freeze" if ready else "source_audits_incomplete_do_not_run_confirmation",
        "frame_sha256": sha256(frame_path),
        "source_pair_selection_sha256": sha256(selection_path),
        "selected_issuers": 30,
        "generic_verified_count": len(checked),
        "generic_verified": checked,
        "legacy_audit_pending_unified_locator": legacy,
        "missing_packet_symbols": missing,
        "invalid_packets": invalid,
        "ready": ready,
        "model_observations": 0,
        "quality_pass": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    result = inspect()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.require_ready and not result["ready"]:
        raise SystemExit("source-distinct confirmation is not source-qualified")


if __name__ == "__main__":
    main()
