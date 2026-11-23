#!/usr/bin/env python3
"""Derive a frozen, owner-reviewed Stage 2A suite without changing the draft."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DRAFT = ROOT / "evals" / "finance-retrieval-stage2a-v2.json"
DEFAULT_OUTPUT = ROOT / "evals" / "finance-retrieval-stage2a-project-report-frozen-2026-10-10.json"
DEFAULT_LOCK = ROOT / "evals" / "finance_e2e" / "source-lock.json"
DEFAULT_OWNER = ROOT / "evals" / "finance_e2e" / "stage2-owner-review-2026-10-10.json"


def freeze(draft_path: Path, lock_path: Path, owner_path: Path) -> dict:
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    owner = json.loads(owner_path.read_text(encoding="utf-8"))
    lock_hash = hashlib.sha256(lock_path.read_bytes()).hexdigest()
    if draft.get("status") != "draft" or draft.get("source_lock_sha256") != lock_hash:
        raise ValueError("draft status or source-lock hash is invalid")
    if len(draft.get("cases", [])) != 24 or draft.get("randomization_seed") != 20260802:
        raise ValueError("Stage 2A case matrix or seed differs from the protocol")
    if owner.get("accepted_for_project_report") is not True or owner.get("tasks") != 103:
        raise ValueError("owner-reviewed audit acceptance is missing")
    result = dict(draft)
    result["study"] = "finance-sec-retrieval-stage2a-project-report-v1"
    result["name"] = "finance-sec-retrieval-stage2a-project-report"
    result["status"] = "frozen"
    result["description"] = "Frozen Stage 2A project-report study with owner-reviewed source/oracle inputs."
    result.pop("formal_freeze_blockers", None)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, default=DEFAULT_DRAFT)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--owner-review", type=Path, default=DEFAULT_OWNER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = freeze(args.draft, args.lock, args.owner_review)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output.exists():
        if args.output.read_text(encoding="utf-8") != encoded:
            raise ValueError(f"frozen suite already exists with different content: {args.output}")
    else:
        args.output.write_text(encoded, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
