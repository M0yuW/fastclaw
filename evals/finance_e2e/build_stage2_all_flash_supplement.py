#!/usr/bin/env python3
"""Derive the owner-reviewed, eight-configuration all-Flash supplement."""

from __future__ import annotations

import json
from pathlib import Path

from evals.finance_e2e.stage2_artifacts import write_json


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "evals/finance-retrieval-stage2a-project-report-v2-frozen-2026-10-10.json"
OUTPUT = ROOT / "evals/finance-retrieval-stage2a-all-flash-supplement-v2-frozen-2026-10-11.json"
MODEL = "deepseek/deepseek-v4-flash"


def build() -> dict:
    suite = json.loads(SOURCE.read_text(encoding="utf-8"))
    chosen = set(suite["ablation_case_ids"])
    suite["cases"] = [case for case in suite["cases"] if case["id"] in chosen]
    if len(suite["cases"]) != 8:
        raise ValueError("expected eight prespecified case configurations")
    suite["name"] = "finance-sec-stage2a-all-flash-supplement-v2"
    suite["study"] = "finance-sec-stage2a-all-flash-supplement-v2"
    suite["description"] = (
        "Separate capacity-matched all-Flash Team versus staged Solo supplement "
        "over eight prespecified, owner-reviewed Stage 2A configurations; "
        "not pooled with the frozen v2 primary analysis."
    )
    suite["status"] = "frozen"
    suite["modes"] = ["solo_staged", "team_shared_retrieval"]
    suite["primary_modes"] = list(suite["modes"])
    suite["diagnostic_modes"] = []
    suite["ablation_modes"] = []
    suite["ablation_case_ids"] = []
    suite["model_allocation"] = {
        "coordinator": MODEL,
        "solo_staged": MODEL,
        "retriever": MODEL,
        "specialists": MODEL,
    }
    suite["defaults"]["capacity_matched_model"] = MODEL
    suite["formal_freeze_blockers"] = []
    return suite


if __name__ == "__main__":
    write_json(OUTPUT, build())
    print(OUTPUT)
