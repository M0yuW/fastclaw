#!/usr/bin/env python3
"""Freeze only the interrupted and unrun all-Flash case configurations."""

from __future__ import annotations

import json

from evals.finance_e2e.build_stage2_all_flash_supplement import ROOT
from evals.finance_e2e.stage2_artifacts import write_json


SOURCE = ROOT / "evals/finance-retrieval-stage2a-all-flash-supplement-v2-frozen-2026-10-11.json"
OUTPUT = ROOT / "evals/finance-retrieval-stage2a-all-flash-recovery-v1-frozen-2026-10-11.json"
CASE_IDS = (
    "FRET-INTC-POINT-LARGE",
    "FRET-INTC-LONG-MEDIUM",
    "FRET-NKE-POINT-LARGE",
    "FRET-NKE-LONG-MEDIUM",
)


if __name__ == "__main__":
    suite = json.loads(SOURCE.read_text(encoding="utf-8"))
    chosen = set(CASE_IDS)
    suite["cases"] = [case for case in suite["cases"] if case["id"] in chosen]
    if {case["id"] for case in suite["cases"]} != chosen:
        raise ValueError("targeted recovery cases do not match the frozen suite")
    suite["name"] = "finance-sec-stage2a-all-flash-targeted-recovery"
    suite["study"] = "finance-sec-stage2a-all-flash-targeted-recovery-v1"
    suite["description"] = (
        "Separate recovery of the balance-interrupted INTC point-in-time case "
        "and three previously unrun all-Flash configurations. The four clean "
        "earlier case reports remain unchanged."
    )
    write_json(OUTPUT, suite)
    print(OUTPUT)
