#!/usr/bin/env python3
"""Derive a two-mode, all-Flash calibration suite from the Stage 2 SEC suite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "evals" / "finance-retrieval-stage2a-v2.json"
OUTPUT = ROOT / "evals" / "finance-retrieval-matched-flash-calibration.json"
MODEL = "deepseek/deepseek-v4-flash"
MODES = ["solo_staged", "team_shared_retrieval"]


def build(source: Path) -> dict:
    suite = json.loads(source.read_text(encoding="utf-8"))
    suite["name"] = "finance-sec-retrieval-matched-flash-calibration"
    suite["study"] = "finance-sec-retrieval-matched-flash-calibration"
    suite["status"] = "draft"
    suite["description"] = (
        "Capacity-matched Team versus staged Solo calibration over the locked SEC corpus. "
        "All provider calls use DeepSeek V4 Flash; the source/oracle human audit remains open."
    )
    suite["modes"] = MODES
    suite["primary_modes"] = MODES
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
    suite["defaults"]["repetitions"] = 3
    suite["execution_controls"]["provider_concurrency"] = (
        "one case block at a time; three Team specialists parallel within block"
    )
    suite["formal_freeze_blockers"] = [
        "Complete and adjudicate the two independent human source/oracle reviews "
        "before treating any run as confirmatory."
    ]
    return suite


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    suite = build(args.source)
    args.output.write_text(json.dumps(suite, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
