#!/usr/bin/env python3
"""Preflight or run eight seen-case reference-only Flash development probes.

This tests autonomous selection, tool-state and output-contract compatibility,
not source-distinct insight quality. A separate paid authorization is required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import build_postcorrection_v4_event_preflight as source_batch
import build_reference_insight_prompt_v1 as prompt_contract
import reference_insight_catalog_v1 as catalog_builder
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_postcorrection_event_holdout_v4 as prior
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from verify_reference_insight_candidate_v1 import render_reference_card
from workflow_runtime_audit_v2 import audit_turns


SYMBOLS = ("FITB", "RELY", "TFC", "VRSK")
REPETITIONS = 2
ORDER_SEED = "reference-only-seen-case-development-v1"
NEXT_OBSERVATION_RESERVE_USD = 0.05


def preflight() -> dict:
    prepared = source_batch.preflight()
    fixtures = [item for item in prepared["fixtures"]
                if item["runtime_symbol"] in SYMBOLS]
    if len(fixtures) != len(SYMBOLS):
        raise AssertionError("reference-development fixture selection differs")
    order = [(item, repetition) for item in fixtures
             for repetition in range(1, REPETITIONS + 1)]
    order.sort(key=lambda pair: hashlib.sha256(
        f"{ORDER_SEED}:{pair[0]['case_id']}:r{pair[1]}".encode()).hexdigest())
    names = [f"{item['case_id']}-r{repeat}" for item, repeat in order]
    return {"order": order, "run_ids": names,
            "order_hash": hashlib.sha256(json.dumps(names).encode()).hexdigest()}


def catalog_for(symbol: str) -> dict:
    path = source_batch.FIRST_PACKETS.get(symbol) or source_batch.DECLARED_PACKETS[symbol]
    return catalog_builder.build_catalog(symbol, json.loads(path.read_text()))


def run_case(pilot: prior.V4Pilot, fixture: dict, catalog: dict) -> tuple[dict, dict, dict]:
    symbol = fixture["runtime_symbol"]
    seed, event = fixture["seed_thesis"], fixture["event"]
    thesis = must_call(pilot.finance, "thesis_save", seed, pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": symbol, "thesis_id": thesis["id"],
        "event_types": ["earnings"],
        "keywords": [source_batch.watchlist_keyword(symbol)],
        "min_match_score": 1,
    }, pilot.tenant)
    alert = must_call(pilot.finance, "event_alert_ingest", {
        "market": "US", "symbol": symbol, "event": event,
    }, pilot.tenant)["results"][0]["alert"]
    pilot.turn(prompt_contract.reference_prompt(fixture, catalog,
                                                thesis["id"], alert["id"]))
    state = pilot.ledger_state()
    alerts, theses = state["alerts"], state["theses"]
    reviews = theses[0]["reviews"] if len(theses) == 1 else []
    checks = {
        "one_thesis_alert_review": len(theses) == len(alerts) == len(reviews) == 1,
        "source_packet_exact": len(alerts) == 1
            and alerts[0]["event"]["sources"] == event["sources"]
            and alerts[0]["event"]["observed_metrics"] == event["observed_metrics"],
        "source_linked_review": len(reviews) == 1
            and reviews[0]["alert_id"] == alert["id"]
            and reviews[0]["event"]["sources"] == event["sources"],
        "alert_acknowledged": len(alerts) == 1
            and alerts[0]["status"] == "acknowledged",
        "decision_state_consistent": len(reviews) == 1 and (
            theses[0]["thesis"]["actionability"] == "blocked"
            if reviews[0]["decision"] == "needs_review"
            else theses[0]["thesis"]["actionability"] == "available"),
    }
    trace_checks, _ = panel.trace_checks(pilot)
    checks.update(trace_checks)
    final = (pilot.turns[-1]["response"]["choices"][0]["message"].get("content")
             if pilot.turns else None)
    try:
        candidate = json.loads(final) if final else None
    except (json.JSONDecodeError, TypeError):
        candidate = None
    return state, checks, render_reference_card(catalog, candidate, state)


def manifest_paths() -> list[Path]:
    paths = set(prior.manifest_paths())
    paths.update((Path(__file__), Path(prompt_contract.__file__),
                  Path(catalog_builder.__file__),
                  HERE / "REFERENCE-ONLY-INSIGHT-DEVELOPMENT-PROTOCOL-2026-10-25.md",
                  HERE / "verify_reference_insight_candidate_v1.py",
                  HERE / "verify_insight_candidate_v1.py", PLUGIN_PATH))
    return sorted(paths)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--estimated-spend-cap-usd", type=float)
    parser.add_argument("--authorize-paid-development-run", action="store_true")
    args = parser.parse_args()
    frozen = preflight()
    if args.preflight_only:
        print(json.dumps({
            "status": "seen_case_reference_development_preflight_no_model_observations",
            "symbols": SYMBOLS, "planned_observations": len(frozen["order"]),
            "run_order_sha256": frozen["order_hash"],
            "model_requested": prior.MODEL, "model_observations": 0,
            "paid_calls_authorized": False,
        }, indent=2))
        return
    if not args.authorize_paid_development_run:
        parser.error("separate --authorize-paid-development-run required")
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("template DB, Gateway binary and unused output path required")
    if args.estimated_spend_cap_usd is None or not (
            NEXT_OBSERVATION_RESERVE_USD < args.estimated_spend_cap_usd <= 1):
        parser.error("positive bounded incremental estimated-spend cap required")
    if args.output_dir.exists():
        raise ValueError("output path exists; refusing overwrite or implicit resume")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway binary or template DB missing")
    base.MODEL, base.PRICING, base.CAP_USD = (
        prior.MODEL, prior.PRICING, args.estimated_spend_cap_usd)
    panel.MODEL = prior.MODEL
    manifest = {str(path.relative_to(ROOT)): sha256(path)
                for path in manifest_paths()}
    manifest.update(model_requested=prior.MODEL,
                    model_version_expected=prior.EXPECTED_PROVIDER_VERSION,
                    pricing_estimate=prior.PRICING[prior.MODEL],
                    pricing_source=prior.PRICING_SOURCE,
                    pricing_checked_at=prior.PRICING_CHECKED_AT,
                    estimated_spend_stop_usd=args.estimated_spend_cap_usd,
                    next_observation_reserve_usd=NEXT_OBSERVATION_RESERVE_USD,
                    run_order=frozen["run_ids"],
                    run_order_sha256=frozen["order_hash"],
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    source_boundary="seen v4 SEC rows; development only",
                    quality_score_stage="none; claim-level qualitative review required")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    prior.write_hash_list(args.output_dir)
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="reference-insight-development-") as temp_root:
        for fixture, repetition in frozen["order"]:
            if spent + NEXT_OBSERVATION_RESERVE_USD > args.estimated_spend_cap_usd:
                print("STOP: insufficient estimated reserve", flush=True)
                break
            observation_id = f"{fixture['case_id']}-r{repetition}"
            catalog = catalog_for(fixture["runtime_symbol"])
            pilot, process, log = None, None, None
            state, checks, card, error = None, {}, None, None
            try:
                pilot = prior.V4Pilot(observation_id, args.template_db,
                                      args.gateway_binary, temp_root, False, spent)
                process, log = base.start_gateway(pilot.home)
                state, checks, card = run_case(pilot, fixture, catalog)
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
            mechanical = (error is None and bool(checks) and all(checks.values())
                          and runtime["clean_completion"])
            accepted = mechanical and card is not None and (
                card["status"] == "candidate_for_qualitative_review")
            result = {"observation_id": observation_id,
                      "case_id": fixture["case_id"], "repetition": repetition,
                      "workflow": "sec_event_to_reference_only_research_candidate",
                      "status": ("candidate_for_qualitative_review" if accepted else "held"),
                      "mechanical_pass": mechanical, "quality_score": None,
                      "error": error, "checks": checks, "candidate_card": card,
                      "runtime_audit": runtime, "state": state, "turns": turns,
                      "estimated_cost_usd": cost}
            directory = args.output_dir / observation_id
            directory.mkdir()
            (directory / "result.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            if pilot is not None and (pilot.home / "finance-tools.db").is_file():
                shutil.copy2(pilot.home / "finance-tools.db",
                             directory / "finance-tools.db")
            prior.write_hash_list(args.output_dir)
            print(json.dumps({"observation_id": observation_id,
                              "status": result["status"], "error": error,
                              "cumulative_estimated_cost_usd": spent}), flush=True)
            if (error or runtime["request_errors"] or runtime["cost_uncertain_sequences"]
                    or runtime["unpriced_sequences"]
                    or spent > args.estimated_spend_cap_usd):
                print("STOP: error, uncertain price or estimated cap", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(frozen["order"]),
                      "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
