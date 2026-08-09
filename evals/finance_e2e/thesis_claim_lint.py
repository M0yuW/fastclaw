#!/usr/bin/env python3
"""Fail on thesis wording that exceeds the retained evidence."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAPER = ROOT / "project-report" / "fastclaw_project_report.md"
FORBIDDEN = {
    "compute-matched": "use planning-opportunity-matched or coordinator-pass-matched",
    "negative result": "use inconclusive accuracy result or no detected incremental effect",
    "preregistered": "use prespecified unless an externally verifiable registration exists",
    "can improve a deployment Pareto frontier": "the single-case Pilot cannot support a general Pareto claim",
    "multi-agent improves accuracy": "accuracy uplift requires frozen paired evidence",
    "production-grade reliability": "selected tests do not establish production assurance",
}


def check(text: str) -> list[str]:
    lowered = text.lower()
    return [f"{phrase}: {reason}" for phrase, reason in FORBIDDEN.items() if phrase.lower() in lowered]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", type=Path, default=DEFAULT_PAPER)
    args = parser.parse_args()
    failures = check(args.paper.read_text(encoding="utf-8"))
    if failures:
        raise ValueError("\n".join(failures))
    print("Thesis claim-language gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
