#!/usr/bin/env python3
"""Generate reviewable shared HTML-table row candidates, not gold facts.

Requires lxml. A repeated label or first numeric cell is never assumed to
represent the same metric, unit, basis, or period. Table context and all
duplicate rows are retained for manual qualification.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import lxml
from lxml import html

from build_reference_source_distinct_frame_v1 import sha256
from run_thesis_event_panel import ROOT


NUMBER = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")
SPACE = re.compile(r"\s+")


def clean(value: str) -> str:
    return SPACE.sub(" ", value).strip()


def extract_rows(path: Path) -> dict[str, list[dict]]:
    tree = html.parse(str(path))
    output = defaultdict(list)
    for table_index, table in enumerate(tree.xpath("//table")):
        header_rows = []
        for row_index, row in enumerate(table.xpath(".//tr")):
            cells = [clean(" ".join(cell.itertext()))
                     for cell in row.xpath("./th|./td")]
            populated = [item for item in cells if item]
            if row_index < 4 and populated:
                header_rows.append(" | ".join(populated)[:240])
            if len(populated) < 2:
                continue
            label = populated[0]
            if (not re.search(r"[A-Za-z]", label)
                    or not 4 <= len(label) <= 115
                    or not any(NUMBER.search(item) for item in populated[1:])):
                continue
            key = clean(label).casefold()
            output[key].append({"label": label,
                                "table_index": table_index,
                                "row_index": row_index,
                                "table_opening_rows": header_rows[:4],
                                "cells": cells[:30]})
    return dict(output)


def build(selection_path: Path) -> dict:
    selection = json.loads(selection_path.read_text())
    if selection.get("status") != "provisional_thirty_source_pairs_no_model_observations":
        raise ValueError("source-pair selection status differs")
    issuers = []
    for pair in selection["pairs"]:
        period_rows = {}
        for period, source in pair["periods"].items():
            path = ROOT / source["local_path"]
            if sha256(path) != source["sha256"]:
                raise ValueError(f"source artifact hash differs: {path}")
            period_rows[period] = extract_rows(path)
        common = sorted(set(period_rows["CY2025_Q2"]) &
                        set(period_rows["CY2025_Q3"]))
        issuers.append({"symbol": pair["symbol"],
                        "source_sha256": {period: item["sha256"]
                                          for period, item in pair["periods"].items()},
                        "baseline_row_labels": len(period_rows["CY2025_Q2"]),
                        "event_row_labels": len(period_rows["CY2025_Q3"]),
                        "shared_label_count": len(common),
                        "shared_label_candidates": [
                            {"normalized_label": label,
                             "baseline_rows": period_rows["CY2025_Q2"][label],
                             "event_rows": period_rows["CY2025_Q3"][label]}
                            for label in common],
                        "status": "table_row_candidates_not_gold_facts"})
        print(f"{pair['symbol']}: {len(common)} shared row labels", flush=True)
    return {"version": 1,
            "status": "shared_html_table_row_candidates_not_gold_facts",
            "source_pair_selection_sha256": sha256(selection_path),
            "extractor_sha256": sha256(Path(__file__)),
            "lxml_version": lxml.__version__,
            "issuer_count": len(issuers),
            "model_observations": 0,
            "quality_pass": None,
            "issuers": issuers}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pairs", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    result = build(args.source_pairs)
    args.output_dir.mkdir(parents=True)
    target = args.output_dir / "ROW-CANDIDATES.json"
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text(
        f"{sha256(target)}  ROW-CANDIDATES.json\n")
    print(json.dumps({"issuer_count": result["issuer_count"],
                      "shared_label_counts": {item["symbol"]: item["shared_label_count"]
                                              for item in result["issuers"]},
                      "model_observations": 0}, indent=2))


if __name__ == "__main__":
    main()
