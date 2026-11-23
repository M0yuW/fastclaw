#!/usr/bin/env python3
"""Freeze a provisional, source-distinct SEC issuer frame before source review.

The hand-curated pool is a bounded business/FinTech universe, not a random
sample of every US public company. Within each declared stratum the order is
hash-ranked before examining the new issuers' earnings answers or outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import build_postcorrection_event_preflight_v2 as prior_v2
import build_postcorrection_v4_event_preflight as prior_v4
from run_thesis_event_panel import HERE, ROOT, sha256


SNAPSHOT = HERE / "source_snapshots/sec-company-tickers-exchange-2026-10-23.json"
PRIOR_CROSS_WORKFLOW = HERE / "prospective_cross_workflow_frame_v1.json"
PRIOR_FRESH_PANEL = HERE / "fresh_fintech_sec_panel_v1.json"
PRIOR_INFERENCE_PANEL = HERE / "fintech_inference_new_issuer_v1.json"
SEED = "source-distinct-reference-insight-confirmation-frame-v1"
PERIODS = ("CY2025 Q2", "CY2025 Q3")
POOL = {
    "regional_banks": ("CFG", "ZION", "WAL", "FHN", "FNB", "ONB", "PB", "BOKF",
                       "UMBF", "EWBC", "WTFC", "SSB"),
    "payments_and_fintech": ("ADP", "PAYX", "EEFT", "GDOT", "ACIW", "TOST",
                             "BILL", "MQ", "RPAY", "JKHY"),
    "capital_markets_and_wealth": ("RJF", "SF", "AMP", "BLK", "TROW", "IVZ",
                                   "BEN", "EVR", "PIPR", "PFSI", "LNC"),
    "data_and_insurance": ("DFIN", "CLVT", "MORN", "EFX", "FICO", "SSNC",
                           "CSGP", "BR", "AIG", "PGR", "TRV", "CB", "ALL",
                           "HIG", "PRU", "MET"),
}
QUOTAS = {"regional_banks": 8, "payments_and_fintech": 7,
          "capital_markets_and_wealth": 7, "data_and_insurance": 8}


def frame() -> dict:
    snapshot = json.loads(SNAPSHOT.read_text())
    if snapshot.get("fields") != ["cik", "name", "ticker", "exchange"]:
        raise ValueError("SEC ticker snapshot schema differs")
    by_ticker = {row[2]: row for row in snapshot["data"]
                 if isinstance(row, list) and len(row) == 4}
    cross_workflow = json.loads(PRIOR_CROSS_WORKFLOW.read_text())
    fresh = json.loads(PRIOR_FRESH_PANEL.read_text())
    inference = json.loads(PRIOR_INFERENCE_PANEL.read_text())
    observed = (set(prior_v2.READY) | set(prior_v4.FIRST_PACKETS)
                | set(prior_v4.DECLARED_PACKETS)
                | set(cross_workflow["development_exclusions"])
                | {ticker for group in cross_workflow["strata"].values()
                   for ticker in group}
                | {item["symbol"] for item in fresh["cases"]}
                | {item["symbol"] for item in inference["cases"]})
    tickers = [ticker for group in POOL.values() for ticker in group]
    if len(tickers) != len(set(tickers)) or set(tickers) & observed:
        raise ValueError("candidate pool overlaps itself or prior observed issuers")
    if set(POOL) != set(QUOTAS):
        raise ValueError("strata and quotas differ")
    strata = {}
    ciks = set()
    for stratum, group in POOL.items():
        if len(group) <= QUOTAS[stratum]:
            raise ValueError("each stratum requires unused fallback candidates")
        entries = []
        for ticker in group:
            row = by_ticker.get(ticker)
            if row is None:
                raise ValueError(f"candidate missing from SEC ticker snapshot: {ticker}")
            cik, name, actual_ticker, exchange = row
            if actual_ticker != ticker or exchange not in ("NYSE", "Nasdaq"):
                raise ValueError(f"candidate exchange/ticker differs: {ticker}")
            if cik in ciks:
                raise ValueError(f"duplicate CIK in candidate pool: {ticker}")
            ciks.add(cik)
            rank_digest = hashlib.sha256(
                f"{SEED}:{stratum}:{ticker}:{cik}".encode()).hexdigest()
            entries.append({"ticker": ticker, "cik": cik, "name": name,
                            "exchange": exchange, "rank_sha256": rank_digest})
        entries.sort(key=lambda item: item["rank_sha256"])
        strata[stratum] = {
            "quota": QUOTAS[stratum],
            "planned": entries[:QUOTAS[stratum]],
            "reserves_in_order": entries[QUOTAS[stratum]:],
        }
    return {
        "status": "provisional_frame_before_new_source_qualification_no_model_observations",
        "scope": "hand_curated_business_fintech_pool_hash_ranked_within_strata",
        "ticker_snapshot_sha256": sha256(SNAPSHOT),
        "selection_seed": SEED,
        "period_pair": {"baseline": PERIODS[0], "event": PERIODS[1]},
        "source_qualification_rule": (
            "For each hash-ranked planned issuer, require official SEC baseline and "
            "event exhibits with auditable, comparable selected rows and source "
            "dates. If unavailable, retain a reason and take the next reserve "
            "from the same stratum; never replace based on the direction of results "
            "or a model answer. Freeze all source rows and audits before model calls."
        ),
        "strata": strata,
        "planned_issuers": sum(item["quota"] for item in strata.values()),
        "model_observations": 0,
        "external_provider_requests": 0,
        "quality_pass": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    result = frame()
    args.output_dir.mkdir(parents=True)
    frame_path = args.output_dir / "FRAME.json"
    frame_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps({
        str(Path(__file__).relative_to(ROOT)): sha256(Path(__file__)),
        str(SNAPSHOT.relative_to(ROOT)): sha256(SNAPSHOT),
        str(Path(prior_v2.__file__).relative_to(ROOT)): sha256(Path(prior_v2.__file__)),
        str(Path(prior_v4.__file__).relative_to(ROOT)): sha256(Path(prior_v4.__file__)),
        str(PRIOR_CROSS_WORKFLOW.relative_to(ROOT)): sha256(PRIOR_CROSS_WORKFLOW),
        str(PRIOR_FRESH_PANEL.relative_to(ROOT)): sha256(PRIOR_FRESH_PANEL),
        str(PRIOR_INFERENCE_PANEL.relative_to(ROOT)): sha256(PRIOR_INFERENCE_PANEL),
    }, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n" for path in (frame_path, manifest_path)))
    print(json.dumps({key: value for key, value in result.items()
                      if key != "strata"}, indent=2))


if __name__ == "__main__":
    main()
