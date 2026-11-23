#!/usr/bin/env python3
"""Check pre-output reviewer-sheet coverage; no model call or file mutation."""

from __future__ import annotations

import json
import re
from pathlib import Path

from build_reference_source_distinct_frame_v1 import sha256
from preflight_reference_source_confirmation_v1 import SELECTION, inspect as source_inspect
from run_thesis_event_panel import HERE


SHEET = HERE / "REFERENCE-SOURCE-DISTINCT-CASE-CRITICALS-DRAFT-v1.md"
CASE_ROW = re.compile(r"^\| ([A-Z]{2,5}) \| (.+) \| (.+) \| (.+) \|$")
PACKET_LINK = re.compile(r"\]\(([a-z]+_reference_source_row_audit_v[12]\.json)\)")


def inspect(sheet_path: Path = SHEET, selection_path: Path = SELECTION,
            require_source_ready: bool = True) -> dict:
    selection = json.loads(selection_path.read_text())
    expected = {item["symbol"] for item in selection["pairs"]}
    rows = []
    for line in sheet_path.read_text().splitlines():
        if not re.match(r"^\| [A-Z]{2,5} \|", line):
            continue
        match = CASE_ROW.fullmatch(line)
        if match is None:
            raise ValueError("malformed issuer row in reviewer sheet")
        symbol, evidence, must_assess, disqualifier = match.groups()
        packet_links = PACKET_LINK.findall(evidence)
        expected_packet = f"{symbol.lower()}_reference_source_row_audit_v{2 if symbol == 'BOKF' else 1}.json"
        if packet_links != [expected_packet]:
            raise ValueError(f"wrong or missing issuer packet link: {symbol}")
        if len(must_assess.strip()) < 35 or len(disqualifier.strip()) < 35:
            raise ValueError(f"case-specific critical check too thin: {symbol}")
        rows.append(symbol)
    if len(rows) != len(set(rows)):
        raise ValueError("duplicate issuer in reviewer sheet")
    if set(rows) != expected or len(rows) != 30:
        raise ValueError(f"reviewer sheet coverage differs: missing={sorted(expected-set(rows))}, extra={sorted(set(rows)-expected)}")
    source = source_inspect(selection_path=selection_path)
    if require_source_ready and not source["ready"]:
        raise ValueError("source-row preflight is not ready")
    return {
        "status": "case_sheet_coverage_checked_not_expert_validated",
        "issuer_count": len(rows),
        "symbols": sorted(rows),
        "source_ready": source["ready"],
        "sheet_sha256": sha256(sheet_path),
        "source_pair_selection_sha256": sha256(selection_path),
        "model_observations": 0,
        "quality_pass": None,
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), indent=2))
