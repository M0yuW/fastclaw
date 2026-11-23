#!/usr/bin/env python3
"""Freeze a clean all-Flash restart after the provider-balance interruption."""

from __future__ import annotations

from evals.finance_e2e.build_stage2_all_flash_supplement import ROOT, build
from evals.finance_e2e.stage2_artifacts import write_json


OUTPUT = ROOT / "evals/finance-retrieval-stage2a-all-flash-v3-frozen-2026-10-11.json"


if __name__ == "__main__":
    suite = build()
    suite["name"] = "finance-sec-stage2a-all-flash-v3"
    suite["study"] = "finance-sec-stage2a-all-flash-v3"
    suite["description"] = (
        "Clean, separate all-Flash Team versus staged Solo experiment after "
        "the v2 provider-balance interruption. Earlier observations are retained "
        "as historical artifacts and never pooled into this study."
    )
    write_json(OUTPUT, suite)
    print(OUTPUT)
