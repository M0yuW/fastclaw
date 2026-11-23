#!/usr/bin/env python3
"""Select provisional SEC pairs and expose shared table rows for human audit.

Earliest filing-date/accession selection is independent of numbers and model
answers. Period identity and metric comparability remain unqualified.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import lxml

from build_reference_row_candidates_v1 import extract_rows
from inspect_reference_source_exhibits_v1 import PlainText
from run_thesis_event_panel import HERE, ROOT, sha256


ARCHIVE = HERE / "results/2026-10-26-reference-cross-workflow-expansion-exhibits-v1"
FRAME = HERE / "results/2026-10-26-reference-cross-workflow-expansion-frame-v1/FRAME.json"


def verified_archive() -> dict:
    checked = set()
    for line in (ARCHIVE / "RESULT-SHA256.txt").read_text().splitlines():
        digest, relative = line.split(maxsplit=1)
        path = ARCHIVE / relative.strip()
        if not path.is_file() or sha256(path) != digest:
            raise ValueError(f"source archive hash mismatch: {path}")
        checked.add(relative.strip())
    manifest = json.loads((ARCHIVE / "manifest.json").read_text())
    if (manifest["status"] != "cross_workflow_expansion_exhibits_frozen_unqualified"
            or manifest["frame_sha256"] != sha256(FRAME)
            or "manifest.json" not in checked
            or len(checked) != manifest["artifact_count"] + 1):
        raise ValueError("source archive manifest coverage differs")
    return manifest


def pair_and_rows() -> tuple[dict, dict]:
    manifest = verified_archive()
    grouped = {}
    for item in manifest["artifacts"]:
        grouped.setdefault(item["symbol"], {}).setdefault(item["period_window"], []).append(item)
    if len(grouped) != 30:
        raise ValueError("not thirty distinct source candidates")
    pairs, candidates = [], []
    for symbol in sorted(grouped):
        selection, period_rows = {}, {}
        alternatives = {}
        for period in ("CY2025_Q2", "CY2025_Q3"):
            options = sorted(grouped[symbol][period],
                             key=lambda item: (item["filing_date"], item["accession"]))
            chosen = options[0]
            path = ARCHIVE / chosen["path"]
            if sha256(path) != chosen["sha256"]:
                raise ValueError("selected SEC exhibit hash differs")
            parser = PlainText()
            parser.feed(path.read_text(errors="replace"))
            preview = " ".join(parser.text().split())[:1000]
            selection[period] = {
                "filing_date": chosen["filing_date"],
                "accession": chosen["accession"],
                "url": chosen["url"],
                "local_path": str(path.relative_to(ROOT)),
                "sha256": chosen["sha256"],
                "period_preview": preview,
                "period_identity_review": "pending_manual_confirmation",
            }
            alternatives[period] = [
                {"filing_date": item["filing_date"],
                 "accession": item["accession"], "sha256": item["sha256"],
                 "url": item["url"]} for item in options[1:]
            ]
            period_rows[period] = extract_rows(path)
        common = sorted(set(period_rows["CY2025_Q2"]) &
                        set(period_rows["CY2025_Q3"]))
        pairs.append({"symbol": symbol, "periods": selection,
                      "unselected_alternatives": alternatives,
                      "source_pair_status": "candidate_period_and_rows_not_qualified"})
        candidates.append({"symbol": symbol,
                           "source_sha256": {period: value["sha256"]
                                             for period, value in selection.items()},
                           "shared_label_count": len(common),
                           "shared_label_candidates": [
                               {"normalized_label": label,
                                "baseline_rows": period_rows["CY2025_Q2"][label],
                                "event_rows": period_rows["CY2025_Q3"][label]}
                               for label in common],
                           "status": "table_row_candidates_not_gold_facts"})
    pair_doc = {"status": "provisional_expansion_pairs_not_qualified",
                "selection_rule": "earliest filing date then lexicographically earliest accession per issuer and calendar filing window; source number and model output ignored",
                "frame_sha256": sha256(FRAME),
                "archive_manifest_sha256": sha256(ARCHIVE / "manifest.json"),
                "issuer_count": len(pairs), "model_observations": 0,
                "quality_pass": None, "pairs": pairs}
    rows_doc = {"status": "shared_html_rows_not_gold_facts",
                "source_pair_selection_sha256": None,
                "extractor_sha256": sha256(Path(__file__)),
                "lxml_version": lxml.__version__,
                "issuer_count": len(candidates),
                "model_observations": 0, "quality_pass": None,
                "issuers": candidates}
    return pair_doc, rows_doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    pairs, rows = pair_and_rows()
    args.output_dir.mkdir(parents=True)
    pair_path = args.output_dir / "SOURCE-PAIR-CANDIDATES.json"
    pair_path.write_text(json.dumps(pairs, indent=2, ensure_ascii=False) + "\n")
    rows["source_pair_selection_sha256"] = sha256(pair_path)
    row_path = args.output_dir / "ROW-CANDIDATES.json"
    row_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    manifest = {"builder_sha256": sha256(Path(__file__)),
                "source_archive_manifest_sha256": sha256(ARCHIVE / "manifest.json"),
                "source_frame_sha256": sha256(FRAME),
                "pair_candidates_sha256": sha256(pair_path),
                "row_candidates_sha256": sha256(row_path)}
    (args.output_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n" for path in sorted(args.output_dir.glob("*.json"))))
    print(json.dumps({"issuer_candidates": pairs["issuer_count"],
                      "shared_row_labels": sum(item["shared_label_count"] for item in rows["issuers"]),
                      "model_observations": 0, "qualified_issuers": 0}, indent=2))


if __name__ == "__main__":
    main()
