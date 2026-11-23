#!/usr/bin/env python3
"""Print source-text period hints; a human still verifies actual fiscal adjacency."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fetch_sources import ROOT, verify_local_lock
from sec_exhibit_text import extract_lines


MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
PERIOD_HINT = re.compile(r"(?:first|second|third|fourth)\s+quarter|\bQ[1-4]\s*(?:20\d{2}|FY\s*20\d{2})|quarter\s+ended", re.I)


def hints(path: Path) -> list[str]:
    lines = extract_lines(path)
    matches = []
    for line in lines[:140]:
        if PERIOD_HINT.search(line):
            snippet = re.sub(r"\s+", " ", line).strip()[:210]
            if snippet not in matches:
                matches.append(snippet)
        if len(matches) == 3:
            break
    return matches


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    for item in lock["entries"]:
        print(item["id"], " | ".join(hints(ROOT / item["local_path"])) or "NO_PERIOD_HINT")
