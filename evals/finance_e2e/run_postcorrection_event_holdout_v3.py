#!/usr/bin/env python3
"""Fresh 100-observation SEC event arm with only maxTokens raised to 5000.

The stopped v2 outputs are neither resumed nor pooled. No paid call can occur
without a new-arm authorization flag and an operator-supplied spend cap.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

import build_postcorrection_event_preflight_v2 as source_batch
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_postcorrection_event_holdout_v2 as v2
from run_thesis_event_panel import AGENT_ID, HERE, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


MAX_TOKENS = 5000
EXPECTED_ORDER_SHA256 = "5dd8423a7f8bf6249d1449d31cb057c34bdecff6d5baacf4f3d2b0174a72182b"
V2_MANIFEST = (HERE / "results/2026-10-24-postcorrection-event-holdout-v2/manifest.json")
V2_HASH_LIST = (HERE / "results/2026-10-24-postcorrection-event-holdout-v2/RESULT-SHA256.txt")


def configure_output_limit(home: Path) -> None:
    with sqlite3.connect(home / "fastclaw.db") as database:
        row = database.execute("SELECT config FROM agents WHERE id=?", (AGENT_ID,)).fetchone()
        if row is None:
            raise ValueError("copied Gateway DB lacks finance coordinator")
        config = json.loads(row[0])
        if config.get("maxTokens") != 2500:
            raise ValueError("v2 baseline maxTokens is not 2500")
        config["maxTokens"] = MAX_TOKENS
        database.execute("UPDATE agents SET config=? WHERE id=?",
                         (json.dumps(config), AGENT_ID))
        actual = json.loads(database.execute(
            "SELECT config FROM agents WHERE id=?", (AGENT_ID,)).fetchone()[0])
        if actual.get("maxTokens") != MAX_TOKENS:
            raise AssertionError("copied Gateway output limit was not set")


class OutputLimitPilot(panel.PanelPilot):
    def __init__(self, case_id, template_db, binary, temp_root, synthetic, spent_so_far):
        super().__init__(case_id, template_db, binary, temp_root, synthetic, spent_so_far)
        configure_output_limit(self.home)


def preflight() -> tuple[list[tuple[dict, int]], str]:
    prepared = source_batch.preflight()
    if prepared["ready_cases"] != prepared["target_cases"] or prepared["ready_cases"] != 20:
        raise AssertionError("v3 requires all 20 audited cases")
    order = v2.planned_order(prepared["fixtures"])
    run_ids = [f"{fixture['case_id']}-r{repeat}" for fixture, repeat in order]
    digest = hashlib.sha256(json.dumps(run_ids).encode()).hexdigest()
    if len(order) != 100 or digest != EXPECTED_ORDER_SHA256:
        raise AssertionError("v3 run order differs from frozen v2 order")
    old_manifest = json.loads(V2_MANIFEST.read_text())
    if old_manifest.get("run_order") != run_ids or old_manifest.get("model_requested") != v2.MODEL:
        raise AssertionError("v2 run order or model alias differs")
    for path in v2.manifest_paths():
        relative = str(path.relative_to(ROOT))
        if old_manifest.get(relative) != sha256(path):
            raise AssertionError(f"v2 frozen file changed: {relative}")
    return order, digest


def manifest_paths() -> list[Path]:
    paths = set(v2.manifest_paths())
    paths.update((Path(__file__),
                  HERE / "POSTCORRECTION-HOLDOUT-OUTPUT-LIMIT-ARM-v3.md",
                  HERE / "POSTCORRECTION-V2-STOP-REVIEW-2026-10-24.md",
                  V2_MANIFEST, V2_HASH_LIST))
    return sorted(paths)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--estimated-spend-cap-usd", type=float)
    parser.add_argument("--authorize-paid-run", action="store_true",
                        help="Use only after separate user approval for the v3 arm")
    args = parser.parse_args()
    order, order_hash = preflight()
    if args.preflight_only:
        print(json.dumps({"status": "new_arm_preflight_only_not_authorized",
                          "source_ready_cases": 20, "planned_observations": 100,
                          "model_observations": 0,
                          "max_tokens_v2": 2500, "max_tokens_v3": MAX_TOKENS,
                          "run_order_sha256": order_hash}, indent=2))
        return
    if not args.authorize_paid_run:
        parser.error("--authorize-paid-run is required")
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required")
    if args.estimated_spend_cap_usd is None or not (
            v2.NEXT_OBSERVATION_RESERVE_USD < args.estimated_spend_cap_usd <= 10):
        parser.error("a positive bounded --estimated-spend-cap-usd is required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite or implicit resume")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway template DB or binary missing")
    old_manifest = json.loads(V2_MANIFEST.read_text())
    if (sha256(args.gateway_binary) != old_manifest["gateway_binary_sha256"]
            or sha256(args.template_db) != old_manifest["gateway_template_db_sha256"]):
        raise ValueError("Gateway binary or template differs from frozen v2 arm")
    base.MODEL, base.PRICING, base.CAP_USD = v2.MODEL, v2.PRICING, args.estimated_spend_cap_usd
    panel.MODEL = v2.MODEL
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in manifest_paths()}
    run_ids = [f"{fixture['case_id']}-r{repeat}" for fixture, repeat in order]
    manifest.update(model_requested=v2.MODEL,
                    model_version_expected=v2.EXPECTED_PROVIDER_VERSION,
                    pricing_estimate=v2.PRICING[v2.MODEL],
                    pricing_checked_at=v2.PRICING_CHECKED_AT,
                    pricing_source=v2.PRICING_SOURCE,
                    estimated_spend_stop_usd=args.estimated_spend_cap_usd,
                    next_observation_reserve_usd=v2.NEXT_OBSERVATION_RESERVE_USD,
                    run_order=run_ids, run_order_sha256=order_hash,
                    coordinator_max_tokens=MAX_TOKENS,
                    only_intended_change_from_v2="copied coordinator maxTokens 2500 to 5000",
                    stopped_v2_manifest_sha256=sha256(V2_MANIFEST),
                    stopped_v2_hash_list_sha256=sha256(V2_HASH_LIST),
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    source_boundary="same selected audited SEC facts; no live source fetch",
                    quality_score_stage="post-run claim-level adjudication")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    v2.write_hash_list(args.output_dir)
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="postcorrection-event-v3-") as temp_root:
        for fixture, repetition in order:
            if spent + v2.NEXT_OBSERVATION_RESERVE_USD > args.estimated_spend_cap_usd:
                print("STOP: insufficient estimated reserve for next observation", flush=True)
                break
            observation_id = f"{fixture['case_id']}-r{repetition}"
            pilot, process, log = None, None, None
            state, checks, error = None, {}, None
            try:
                pilot = OutputLimitPilot(observation_id, args.template_db,
                                         args.gateway_binary, temp_root, False, spent)
                process, log = base.start_gateway(pilot.home)
                startup_log = (pilot.home / "gateway.log").read_text(errors="replace")
                if 'msg="gateway started"' not in startup_log or "finance-tools" not in startup_log:
                    raise RuntimeError("finance plugin startup not confirmed")
                state, checks = v2.run_case(pilot, fixture)
                trace_checks, _ = panel.trace_checks(pilot)
                checks.update(trace_checks)
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
            result = {"observation_id": observation_id, "case_id": fixture["case_id"],
                      "repetition": repetition, "workflow": "sec_event_to_thesis_review",
                      "coordinator_max_tokens": MAX_TOKENS,
                      "status": "mechanical_pass" if error is None and checks
                          and all(checks.values()) and runtime["clean_completion"]
                          else "needs_review",
                      "quality_score": None, "error": error, "checks": checks,
                      "runtime_audit": runtime, "state": state, "turns": turns,
                      "estimated_cost_usd": cost}
            directory = args.output_dir / observation_id
            directory.mkdir()
            (directory / "result.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            if pilot is not None and (pilot.home / "finance-tools.db").is_file():
                shutil.copy2(pilot.home / "finance-tools.db", directory / "finance-tools.db")
            v2.write_hash_list(args.output_dir)
            print(json.dumps({"observation_id": observation_id,
                              "status": result["status"], "error": error,
                              "cumulative_estimated_cost_usd": spent}), flush=True)
            if (error or runtime["request_errors"] or runtime["cost_uncertain_sequences"]
                    or runtime["unpriced_sequences"] or spent > args.estimated_spend_cap_usd):
                print("STOP: request error, uncertain pricing, or spend cap", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(order), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
