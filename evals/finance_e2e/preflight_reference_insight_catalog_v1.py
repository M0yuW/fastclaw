#!/usr/bin/env python3
"""Freeze complete selected-row comparison catalogs without model requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_postcorrection_v4_event_preflight as source_batch
import reference_insight_catalog_v1 as catalog_builder
import audit_postcorrection_v4_source_identity as source_audit
import audit_v4_declared_sec_rows as declared_audit
import audit_wex_v4_source_facts as wex_audit
import audit_hban_v4_source_facts as hban_audit
import audit_vrsk_v4_source_facts as vrsk_audit
import audit_ntrs_v4_source_facts as ntrs_audit
from run_thesis_event_panel import ROOT, sha256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    source_batch.preflight()
    packets = {**source_batch.FIRST_PACKETS, **source_batch.DECLARED_PACKETS}
    catalogs = {
        symbol: catalog_builder.build_catalog(symbol, json.loads(path.read_text()))
        for symbol, path in sorted(packets.items())
    }
    if len(catalogs) != 20:
        raise AssertionError("audited case catalog count differs")
    summary = {
        "status": "source_audited_reference_catalog_preflight_only",
        "cases": len(catalogs),
        "comparison_rows": sum(len(item["rows"]) for item in catalogs.values()),
        "rows_by_symbol": {symbol: len(item["rows"])
                           for symbol, item in catalogs.items()},
        "model_observations": 0,
        "external_provider_requests": 0,
        "estimated_external_cost_usd": 0,
        "quality_pass": None,
    }
    sources = {Path(__file__), Path(source_batch.__file__),
               Path(catalog_builder.__file__), Path(source_audit.__file__),
               Path(declared_audit.__file__), Path(wex_audit.__file__),
               Path(hban_audit.__file__), Path(vrsk_audit.__file__),
               Path(ntrs_audit.__file__), *packets.values()}
    for directory in source_batch.MANIFEST_DIRS:
        sources.update(path for path in directory.iterdir() if path.is_file())
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in sorted(sources)}
    args.output_dir.mkdir(parents=True)
    for name, data in (("CATALOGS.json", catalogs), ("SUMMARY.json", summary),
                       ("manifest.json", manifest)):
        (args.output_dir / name).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    outputs = sorted(args.output_dir.glob("*.json"))
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n" for path in outputs))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
