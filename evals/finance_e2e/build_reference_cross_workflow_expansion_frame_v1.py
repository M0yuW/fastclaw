#!/usr/bin/env python3
"""Freeze thirty additional issuer candidates for source-disjoint workflow packets.

This ranks a declared hand-curated business/FinTech pool before inspecting its
new SEC exhibits. It does not qualify a source pair or create model cases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import build_reference_source_distinct_frame_v1 as first_frame
from run_thesis_event_panel import HERE, sha256


SNAPSHOT = first_frame.SNAPSHOT
FIRST_SELECTION = HERE / "results/2026-10-25-reference-source-pair-selection-v1/SOURCE-PAIRS.json"
SEED = "cross-workflow-additional-source-disjoint-issuer-frame-v1"
POOL = {
    "regional_banks": "ONB WTFC ZION CFG KEY RF MTB BPOP ASB CUBI FCNCA OZK GBCI UCB HOPE CVBF CATY FULT WAFD COLB SBCF",
    "payments_and_fintech": "EEFT RPAY PAYC PCTY TNET ALIT PAYO APPF INTU PAY",
    "capital_markets_and_wealth": "IVZ BEN PIPR PFSI MS LAZ PJT VIRT CG BX KKR APO BAM ARES",
    "data_and_insurance": "BR PRU CSGP TRV MET MORN SSNC CB AJG AON WTW ACGL RNR ERIE RLI WRB CINF UNM CNA RGA",
}
QUOTAS = {"regional_banks": 8, "payments_and_fintech": 7,
          "capital_markets_and_wealth": 7, "data_and_insurance": 8}


def previous_observed() -> set[str]:
    cross = json.loads(first_frame.PRIOR_CROSS_WORKFLOW.read_text())
    fresh = json.loads(first_frame.PRIOR_FRESH_PANEL.read_text())
    inference = json.loads(first_frame.PRIOR_INFERENCE_PANEL.read_text())
    return (set(first_frame.prior_v2.READY)
            | set(first_frame.prior_v4.FIRST_PACKETS)
            | set(first_frame.prior_v4.DECLARED_PACKETS)
            | set(cross["development_exclusions"])
            | {ticker for group in cross["strata"].values() for ticker in group}
            | {item["symbol"] for item in fresh["cases"]}
            | {item["symbol"] for item in inference["cases"]})


def frame() -> dict:
    snapshot = json.loads(SNAPSHOT.read_text())
    if snapshot.get("fields") != ["cik", "name", "ticker", "exchange"]:
        raise ValueError("SEC ticker snapshot schema differs")
    by_ticker = {row[2]: row for row in snapshot["data"]
                 if isinstance(row, list) and len(row) == 4}
    first = json.loads(FIRST_SELECTION.read_text())
    used = {item["symbol"] for item in first["pairs"]}
    if len(used) != 30:
        raise ValueError("first source frame is not thirty issuers")
    excluded = used | previous_observed()
    all_tickers = [ticker for group in POOL.values() for ticker in group.split()]
    if len(all_tickers) != len(set(all_tickers)) or set(all_tickers) & excluded:
        raise ValueError("pool duplicates or overlaps prior source/model cases")
    if set(POOL) != set(QUOTAS):
        raise ValueError("pool and quotas differ")
    ciks, strata = set(), {}
    for stratum, group in POOL.items():
        if len(group.split()) <= QUOTAS[stratum]:
            raise ValueError("stratum needs qualification reserves")
        entries = []
        for ticker in group.split():
            row = by_ticker.get(ticker)
            if row is None or row[3] not in ("NYSE", "Nasdaq"):
                raise ValueError(f"ticker not in frozen eligible exchange snapshot: {ticker}")
            cik, name, actual_ticker, exchange = row
            if actual_ticker != ticker or cik in ciks:
                raise ValueError(f"ticker or CIK identity conflict: {ticker}")
            ciks.add(cik)
            rank = hashlib.sha256(f"{SEED}:{stratum}:{ticker}:{cik}".encode()).hexdigest()
            entries.append({"ticker": ticker, "cik": cik, "name": name,
                            "exchange": exchange, "rank_sha256": rank})
        entries.sort(key=lambda item: item["rank_sha256"])
        strata[stratum] = {"quota": QUOTAS[stratum],
                           "planned": entries[:QUOTAS[stratum]],
                           "reserves_in_order": entries[QUOTAS[stratum]:]}
    return {
        "status": "provisional_additional_frame_source_pairs_not_yet_qualified",
        "scope": "hand_curated_business_fintech_pool_hash_ranked_within_strata",
        "ticker_snapshot_sha256": sha256(SNAPSHOT),
        "prior_source_selection_sha256": sha256(FIRST_SELECTION),
        "selection_seed": SEED,
        "period_pair_target": {"baseline": "CY2025_Q2", "event": "CY2025_Q3"},
        "source_qualification_rule": (
            "For planned issuers in hash order, require two official SEC 8-K "
            "earnings exhibits for calendar Q2 and Q3 2025 with correct period "
            "labels and auditable same-definition selected rows. Ineligible "
            "issuers retain a documented reason and are replaced only by the "
            "next ranked same-stratum reserve. Never replace based on model "
            "output, direction of profit change, or screen outcome."
        ),
        "strata": strata,
        "planned_issuers": sum(QUOTAS.values()),
        "reserve_issuers": len(all_tickers) - sum(QUOTAS.values()),
        "model_observations": 0,
        "external_provider_requests": 0,
        "quality_pass": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output path exists; refusing overwrite")
    result = frame()
    manifest = {"builder_sha256": sha256(Path(__file__)),
                "ticker_snapshot_sha256": sha256(SNAPSHOT),
                "first_selection_sha256": sha256(FIRST_SELECTION),
                "prior_frame_script_sha256": sha256(Path(first_frame.__file__))}
    args.output_dir.mkdir(parents=True)
    for name, data in (("FRAME.json", result), ("MANIFEST.json", manifest)):
        (args.output_dir / name).write_text(json.dumps(data, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n" for path in sorted(args.output_dir.glob("*.json"))))
    print(json.dumps({key: value for key, value in result.items() if key != "strata"}, indent=2))


if __name__ == "__main__":
    main()
