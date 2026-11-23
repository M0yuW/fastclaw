#!/usr/bin/env python3
"""Preflight or run six isolated new-issuer SEC research sessions.

Paid execution is impossible without an explicit flag, input paths, a new
output directory and a bounded incremental estimated-spend ceiling.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import preflight_reference_mini_panel_v1 as mini
import run_finance_workflow_pilot as base
import run_postcorrection_event_holdout_v4 as prior
import run_reference_insight_development_flash_v1 as reusable
import run_reference_precommit_gateway_ab_v1 as guard_setup
import run_reference_source_distinct_insight_flash_v1 as previous
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from verify_reference_insight_candidate_v2 import render_reference_card_v2
from workflow_runtime_audit_v2 import audit_turns


NEXT_OBSERVATION_RESERVE_USD = 0.05
MAX_ESTIMATED_SPEND_USD = 0.25


def manifest_paths(prepared: dict) -> list[Path]:
    selection = json.loads(mini.SELECTION.read_text())
    paths = {
        Path(__file__), Path(mini.__file__), Path(previous.__file__),
        Path(reusable.__file__), Path(guard_setup.__file__),
        HERE / "REFERENCE-MINI-ILLUSTRATIVE-PANEL-PROTOCOL-v1.md",
        HERE / "INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md",
        HERE / "verify_reference_source_row_packet_v1.py",
        HERE / "build_reference_source_distinct_event_fixtures_v1.py",
        HERE / "build_reference_insight_prompt_v1.py",
        HERE / "run_reference_insight_citation_development_flash_v2.py",
        HERE / "verify_reference_insight_candidate_v2.py",
        HERE / "workflow_runtime_audit_v2.py",
        mini.SELECTION, PLUGIN_PATH,
        PLUGIN_PATH.with_name("review_arithmetic_guard.py"),
        PLUGIN_PATH.with_name("accounting_lineage.py"),
        PLUGIN_PATH.with_name("plugin.json"),
    }
    for pair in selection["pairs"]:
        paths.add(HERE / f"{pair['symbol'].lower()}_mini_source_row_audit_v1.json")
        for source in pair["periods"].values():
            paths.add(ROOT / source["local_path"])
    if len(prepared["fixtures"]) != 3:
        raise ValueError("mini-panel fixture count differs")
    return sorted(paths)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--estimated-spend-cap-usd", type=float)
    parser.add_argument("--authorize-paid-mini-run", action="store_true")
    args = parser.parse_args()
    prepared = mini.preflight()
    if args.preflight_only:
        print(json.dumps({
            "status": "source_verified_guarded_mini_panel_not_authorized_or_run",
            "issuers": prepared["issuer_cases"],
            "planned_observations": prepared["planned_independent_sessions"],
            "verified_comparable_rows": prepared["verified_comparable_rows"],
            "run_order_sha256": prepared["run_order_sha256"],
            "source_selection_sha256": prepared["source_selection_sha256"],
            "model_requested": prior.MODEL,
            "model_observations": 0,
            "paid_calls_authorized": False,
        }, indent=2))
        return
    if not args.authorize_paid_mini_run:
        parser.error("separate paid mini-panel authorization required")
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("template DB, Gateway binary and unused output path required")
    cap = args.estimated_spend_cap_usd
    if cap is None or not (NEXT_OBSERVATION_RESERVE_USD < cap <= MAX_ESTIMATED_SPEND_USD):
        parser.error("incremental estimated cap must be above reserve and at most USD 0.25")
    if args.output_dir.exists():
        raise ValueError("output path exists; refusing overwrite or implicit resume")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway binary or template DB missing")

    base.MODEL, base.PRICING, base.CAP_USD = prior.MODEL, prior.PRICING, cap
    reusable.prompt_contract.reference_prompt = previous.source_distinct_prompt
    reusable.render_reference_card = render_reference_card_v2
    by_case = {item["case_id"]: item for item in prepared["fixtures"]}
    manifest = {str(path.relative_to(ROOT)): sha256(path)
                for path in manifest_paths(prepared)}
    manifest.update(
        model_requested=prior.MODEL,
        model_version_expected=prior.EXPECTED_PROVIDER_VERSION,
        pricing_estimate=prior.PRICING[prior.MODEL],
        pricing_source=prior.PRICING_SOURCE,
        estimated_spend_stop_usd=cap,
        next_observation_reserve_usd=NEXT_OBSERVATION_RESERVE_USD,
        run_order=prepared["run_order"],
        run_order_sha256=prepared["run_order_sha256"],
        source_selection_sha256=prepared["source_selection_sha256"],
        gateway_binary_sha256=sha256(args.gateway_binary),
        gateway_template_db_sha256=sha256(args.template_db),
        review_arithmetic_guard="enabled_exact_source_pair_per_isolated_session",
        quality_score_stage="post_run_claim_level_F_I_R_S_U_adjudication",
        source_boundary="three previously unrun issuers; selected SEC rows only",
    )
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    prior.write_hash_list(args.output_dir)
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="reference-mini-flash-") as temp:
        for observation_id in prepared["run_order"]:
            if spent + NEXT_OBSERVATION_RESERVE_USD > cap:
                print("STOP: insufficient estimated reserve", flush=True)
                break
            case_id, repeat = observation_id.rsplit("-r", 1)
            fixture = by_case[case_id]
            pilot, process, log = None, None, None
            state, checks, card, error = None, {}, None, None
            try:
                pilot = prior.V4Pilot(observation_id, args.template_db,
                                      args.gateway_binary, temp, False, spent)
                guard_catalog = pilot.home / "review-guard-catalog.json"
                guard_catalog.write_text(json.dumps(
                    guard_setup._guard_catalog(fixture), sort_keys=True) + "\n")
                guard_setup._enable_guard(pilot.home, guard_catalog)
                process, log = base.start_gateway(pilot.home)
                state, checks, card = reusable.run_case(
                    pilot, fixture, fixture["catalog"])
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                if pilot is not None:
                    try:
                        state = pilot.ledger_state()
                    except Exception:
                        pass
            finally:
                if process is not None and log is not None:
                    base.stop_gateway(process, log)
            turns = pilot.turns if pilot is not None else []
            runtime = audit_turns(turns)
            cost = pilot.cost if pilot is not None else 0.0
            spent += cost
            mechanical = (error is None and bool(checks)
                          and all(checks.values()) and runtime["clean_completion"])
            candidate = (mechanical and card is not None
                         and card["status"] == "candidate_for_qualitative_review")
            result = {
                "observation_id": observation_id,
                "case_id": case_id, "repetition": int(repeat),
                "workflow": "source_distinct_sec_event_to_research_view",
                "status": "candidate_for_qualitative_review" if candidate else "held",
                "mechanical_pass": mechanical, "quality_pass": None,
                "review_arithmetic_guard_enabled": True,
                "error": error, "checks": checks, "candidate_card": card,
                "runtime_audit": runtime, "state": state, "turns": turns,
                "estimated_cost_usd": cost,
            }
            directory = args.output_dir / observation_id
            directory.mkdir()
            (directory / "result.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            if pilot is not None and (pilot.home / "finance-tools.db").is_file():
                shutil.copy2(pilot.home / "finance-tools.db", directory / "finance-tools.db")
            prior.write_hash_list(args.output_dir)
            print(json.dumps({"observation_id": observation_id,
                              "status": result["status"], "error": error,
                              "cumulative_estimated_cost_usd": spent}), flush=True)
            if (error or runtime["request_errors"]
                    or runtime["cost_uncertain_sequences"]
                    or runtime["unpriced_sequences"] or spent > cap):
                print("STOP: error, uncertain price or estimated cap", flush=True)
                break
    print(json.dumps({
        "completed": len(list(args.output_dir.glob("*/result.json"))),
        "planned": len(prepared["run_order"]),
        "estimated_cost_usd": spent,
    }), flush=True)


if __name__ == "__main__":
    main()
