#!/usr/bin/env python3
"""Freeze provisional SEC document pairs for the source-distinct 30-issuer frame.

Document selection is based on period/title/source type before any model
answer. It does not certify fact rows or insight quality.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_reference_source_distinct_frame_v1 import sha256
from run_thesis_event_panel import HERE, ROOT


RESULTS = HERE / "results"
FRAME = RESULTS / "2026-10-25-reference-source-distinct-frame-v2/FRAME.json"
FREEZES = (
    RESULTS / "2026-10-25-reference-source-distinct-sec-exhibits-pilot-v1/manifest.json",
    RESULTS / "2026-10-25-reference-source-distinct-sec-exhibits-remaining-v1/manifest.json",
    RESULTS / "2026-10-25-reference-source-distinct-sec-exhibits-payx-reserve-v1/manifest.json",
)
OVERRIDE_ACCESSIONS = {
    ("JKHY", "CY2025_Q2"): "0000779152-25-000053",  # quarterly release, not deconversion note
    ("JKHY", "CY2025_Q3"): "0000779152-25-000090",
    ("DFIN", "CY2025_Q3"): "0001193125-25-254603",  # earnings, not pension note
}
REPLACEMENT = {"PAYX": "BILL"}


def select_pairs() -> dict:
    frame = json.loads(FRAME.read_text())
    planned = {item["ticker"]: stratum
               for stratum, group in frame["strata"].items()
               for item in group["planned"]}
    if len(planned) != frame["planned_issuers"] or frame["planned_issuers"] != 30:
        raise ValueError("frozen planned count differs")
    if planned["PAYX"] != "payments_and_fintech":
        raise ValueError("replacement stratum differs")
    if frame["strata"]["payments_and_fintech"]["reserves_in_order"][0]["ticker"] != "BILL":
        raise ValueError("BILL is not first frozen same-stratum reserve")
    selected_symbols = (set(planned) - set(REPLACEMENT)) | set(REPLACEMENT.values())
    if len(selected_symbols) != 30:
        raise ValueError("selected issuer count differs")
    by_key = {}
    for manifest_path in FREEZES:
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("status") != "sec_exhibits_frozen_period_and_rows_unverified":
            raise ValueError("source freeze status differs")
        for artifact in manifest["artifacts"]:
            path = manifest_path.parent / artifact["path"]
            if sha256(path) != artifact["sha256"]:
                raise ValueError(f"source bytes changed: {path}")
            key = (artifact["symbol"], artifact["period_window"])
            by_key.setdefault(key, []).append((artifact, path))
    pairs = []
    for symbol in sorted(selected_symbols):
        periods = {}
        for period in ("CY2025_Q2", "CY2025_Q3"):
            candidates = by_key.get((symbol, period), [])
            accession = OVERRIDE_ACCESSIONS.get((symbol, period))
            if accession:
                matching = [(item, path) for item, path in candidates
                            if item["accession"] == accession]
                method = "predeclared_title_period_disambiguation"
            else:
                matching = candidates
                method = "unique_ex99_family_candidate_in_period_window"
            if len(matching) != 1:
                raise ValueError(f"source pair unresolved: {symbol} {period}")
            item, path = matching[0]
            periods[period] = {"accession": item["accession"],
                               "filing_date": item["filing_date"],
                               "url": item["url"],
                               "sha256": item["sha256"],
                               "bytes": item["bytes"],
                               "local_path": str(path.relative_to(ROOT)),
                               "selection_method": method,
                               "fact_rows_status": "not_audited"}
        pairs.append({"symbol": symbol,
                      "stratum": planned.get(symbol, planned["PAYX"]),
                      "replaces": "PAYX" if symbol == "BILL" else None,
                      "periods": periods,
                      "status": "provisional_source_pair_numeric_rows_pending"})
    return {"version": 1,
            "status": "provisional_thirty_source_pairs_no_model_observations",
            "frame_sha256": sha256(FRAME),
            "source_freeze_manifest_sha256": {
                str(path.relative_to(ROOT)): sha256(path) for path in FREEZES},
            "replacement": REPLACEMENT,
            "source_pair_count": len(pairs),
            "model_observations": 0,
            "quality_pass": None,
            "pairs": pairs}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    payload = select_pairs()
    args.output_dir.mkdir(parents=True)
    target = args.output_dir / "SOURCE-PAIRS.json"
    target.write_text(json.dumps(payload, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text(
        f"{sha256(target)}  SOURCE-PAIRS.json\n")
    print(json.dumps({"source_pair_count": payload["source_pair_count"],
                      "model_observations": 0}, indent=2))


if __name__ == "__main__":
    main()
