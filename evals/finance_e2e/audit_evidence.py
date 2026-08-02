#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.finance_e2e.fetch_sources import ROOT as EVAL_ROOT, verify_local_lock


DEFAULT_EVIDENCE = EVAL_ROOT / "evidence.json"
DEFAULT_SOURCES = EVAL_ROOT / "sources.json"
DEFAULT_LOCK = EVAL_ROOT / "source-lock.json"
NEGATIVE_MARKERS = ("-", "−", "–", "(", "declin", "decreas", "down", "fell", "loss", "negative")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def visible_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    without_markup = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(without_markup)).strip()


def value_candidates(fact: dict[str, Any]) -> set[str]:
    if fact["unit"] == "categorical":
        return {str(fact["value"]).strip()}
    value = abs(Decimal(str(fact["value"])))
    plain = format(value, "f")
    candidates = {plain}
    if value == value.to_integral():
        candidates.add(f"{int(value):,}")
    else:
        candidates.add(f"{value:,f}".rstrip("0").rstrip("."))
    if fact["unit"] == "USD_million" and fact["precision"] == "rounded_to_100_million":
        candidates.add(format(value / Decimal("1000"), "f").rstrip("0").rstrip("."))
    return {candidate for candidate in candidates if candidate}


def matching_windows(text: str, candidates: set[str], radius: int = 96) -> list[str]:
    lowered = text.lower()
    windows = []
    for candidate in sorted(candidates, key=len, reverse=True):
        start = 0
        while True:
            index = lowered.find(candidate.lower(), start)
            if index < 0:
                break
            windows.append(text[max(0, index - radius):index + len(candidate) + radius])
            start = index + len(candidate)
    return windows


def fact_is_present(text: str, fact: dict[str, Any]) -> tuple[bool, list[str]]:
    candidates = value_candidates(fact)
    windows = matching_windows(text, candidates)
    if fact["unit"] == "categorical":
        return bool(windows), sorted(candidates)
    if Decimal(str(fact["value"])) >= 0:
        return bool(windows), sorted(candidates)
    return any(any(marker in window.lower() for marker in NEGATIVE_MARKERS) for window in windows), sorted(candidates)


def audit(evidence_path: Path, sources_path: Path, lock_path: Path) -> dict[str, Any]:
    verify_local_lock(sources_path, lock_path)
    evidence = read_json(evidence_path)
    lock = read_json(lock_path)
    locked_entries = {entry["id"]: entry for entry in lock["entries"]}
    facts = []
    for episode in evidence["episodes"]:
        entry = locked_entries[episode["source_id"]]
        source_path = EVAL_ROOT / entry["local_path"]
        source_text = visible_text(source_path)
        for fact in episode["facts"]:
            present, candidates = fact_is_present(source_text, fact)
            facts.append(
                {
                    "episode_id": episode["id"],
                    "fact_id": fact["id"],
                    "source_id": episode["source_id"],
                    "present": present,
                    "numeric_candidates": candidates,
                }
            )
    missing = [fact["fact_id"] for fact in facts if not fact["present"]]
    return {
        "version": 1,
        "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        "source_lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
        "facts_audited": len(facts),
        "facts_present": len(facts) - len(missing),
        "missing_fact_ids": missing,
        "facts": facts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit finance fact values against SHA-256-locked SEC artifacts.")
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.evidence, args.sources, args.lock)
    if result["missing_fact_ids"]:
        raise RuntimeError(f"facts absent from locked SEC artifacts: {result['missing_fact_ids']}")
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
