#!/usr/bin/env python3
"""Read-only archival audit of the opt-in pre-commit arithmetic guard.

This replays saved review rationales against the frozen source-pair catalog. It
does not resend a review through the Gateway, observe model recovery, or measure
prospective guard sensitivity. The 100 earlier judgments were visible during
rule development; the other 50 have blank masked scores and are not labelled
as high/low quality by this script.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

from aggregate_postcorrection_judgments_v2 import (
    blank_template, validate_review, verify_frozen_results,
)
from aggregate_reference_source_distinct_judgments_v1 import verify_masked_packet_hashes
from build_reference_source_distinct_event_fixtures_v1 import preflight
from run_thesis_event_panel import HERE, sha256


REPO = HERE.parents[1]
RESULTS = HERE / "results/2026-10-26-reference-source-distinct-insight-flash-v1"
JUDGMENTS = HERE / "results/2026-10-26-reference-source-distinct-insight-judgment-v1"
GUARD_PATH = REPO / "plugins/finance-tools/review_arithmetic_guard.py"


def load_guard_class():
    spec = importlib.util.spec_from_file_location("offline_review_arithmetic_guard", GUARD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("finance guard module unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.ReviewArithmeticGuard, module.GuardCatalogError


def guard_catalog(fixtures: list[dict]) -> dict:
    cases = []
    for fixture in fixtures:
        cases.append({
            "symbol": fixture["runtime_symbol"],
            "baseline_source_sha256": fixture["seed_thesis"]["evidence"][0]["sha256"],
            "event_source_sha256": fixture["event"]["sources"][0]["sha256"],
            "rows": fixture["catalog"]["rows"],
        })
    return {"version": "review-arithmetic-guard-catalog-v1", "cases": cases}


def audit(results: Path = RESULTS, judgments: Path = JUDGMENTS) -> dict:
    verify_frozen_results(results)
    prepared = preflight()
    if prepared["issuer_cases"] != 30 or prepared["planned_fresh_sessions"] != 150:
        raise ValueError("source-distinct frame differs from frozen plan")
    mapping = json.loads((judgments / "PRIVATE-MAPPING.json").read_text())
    if len(mapping) != 150 or len({m["masked_id"] for m in mapping}) != 150:
        raise ValueError("masked mapping must contain 150 unique observations")
    verify_masked_packet_hashes(judgments, {m["masked_id"] for m in mapping})

    ReviewArithmeticGuard, GuardCatalogError = load_guard_class()
    with tempfile.TemporaryDirectory(prefix="finance-guard-archival-") as temp:
        catalog_path = Path(temp) / "catalog.json"
        catalog_path.write_text(json.dumps(guard_catalog(prepared["fixtures"])))
        guard = ReviewArithmeticGuard(catalog_path)
        counts = Counter()
        flagged = []
        unevaluable = []
        for entry in mapping:
            mask = entry["masked_id"]
            raw_path = Path(entry["raw_result_path"])
            if (raw_path.resolve() != (results / entry["observation_id"] / "result.json").resolve()
                    or sha256(raw_path) != entry["raw_result_sha256"]):
                raise ValueError(f"raw result mapping changed: {mask}")
            score = json.loads((judgments / "scores" / f"{mask}.json").read_text())
            if blank_template(score, mask):
                label = "unreviewed"
            else:
                label = validate_review(score, mask)
            counts[("score", label)] += 1
            packet = json.loads((judgments / "masked_packets" / f"{mask}.json").read_text())
            if packet.get("masked_id") != mask:
                raise ValueError(f"masked packet identity changed: {mask}")
            theses = packet.get("persisted_theses_and_reviews") or []
            alerts = packet.get("persisted_alerts") or []
            if (len(theses) != 1 or len(theses[0].get("reviews") or []) != 1
                    or len(alerts) != 1):
                unevaluable.append({"masked_id": mask, "reason": "review_or_alert_not_unique"})
                counts[("coverage", "not_unique")] += 1
                continue
            thesis = theses[0]["thesis"]
            review = theses[0]["reviews"][0]
            event = alerts[0].get("event") or {}
            decision = review.get("decision")
            counts[("decision", decision)] += 1
            if label == "problematic":
                counts[("problematic_actionability", thesis.get("actionability"))] += 1
            try:
                flags = guard.check(thesis, event, str(review.get("rationale") or ""))
            except GuardCatalogError as exc:
                unevaluable.append({"masked_id": mask, "reason": str(exc)})
                counts[("coverage", "source_mismatch")] += 1
                continue
            counts[("coverage", "checked")] += 1
            if flags:
                item = {
                    "masked_id": mask,
                    "observation_id": entry["observation_id"],
                    "local_review_label": label,
                    "original_decision": decision,
                    "original_actionability": thesis.get("actionability"),
                    "rationale_flags": flags,
                    "would_veto_original_write": decision != "needs_review",
                }
                flagged.append(item)
                counts[("flagged", label)] += 1
                if item["would_veto_original_write"]:
                    counts[("would_veto", label)] += 1
    return {
        "study_type": "archival_read_only_precommit_guard_scope_audit",
        "source_issuer_cases": prepared["issuer_cases"],
        "saved_model_observations": len(mapping),
        "new_model_observations": 0,
        "gateway_requests": 0,
        "external_provider_requests": 0,
        "estimated_external_cost_usd": 0,
        "quality_pass": None,
        "counts": [{"key": list(key), "count": value}
                   for key, value in sorted(counts.items(), key=lambda pair: str(pair[0]))],
        "flagged": sorted(flagged, key=lambda item: item["observation_id"]),
        "unevaluable": sorted(unevaluable, key=lambda item: item["masked_id"]),
        "interpretation_boundary": (
            "Rules were developed after inspecting some saved answers. A would-veto flag "
            "is a counterfactual on a saved rationale, not an observed Gateway recovery "
            "or an estimate of false-hold or missed-error rates. Unreviewed scores "
            "are not quality labels."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory already exists; refusing overwrite")
    result = audit()
    args.output_dir.mkdir(parents=True)
    summary = args.output_dir / "SUMMARY.json"
    summary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    manifest = {
        "source_result_hash_list_sha256": sha256(RESULTS / "RESULT-SHA256.txt"),
        "masked_packet_hash_list_sha256": sha256(JUDGMENTS / "MASKED-PACKET-SHA256.txt"),
        "private_mapping_sha256": sha256(JUDGMENTS / "PRIVATE-MAPPING.json"),
        "guard_code_sha256": sha256(GUARD_PATH),
        "audit_code_sha256": sha256(Path(__file__)),
    }
    manifest_path = args.output_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text(
        "".join(f"{sha256(args.output_dir / name)}  {name}\n"
                for name in ("MANIFEST.json", "SUMMARY.json")))
    print(json.dumps({
        "saved_model_observations": result["saved_model_observations"],
        "flagged": len(result["flagged"]),
        "unevaluable": len(result["unevaluable"]),
        "counts": result["counts"],
    }, indent=2))


if __name__ == "__main__":
    main()
