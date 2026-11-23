#!/usr/bin/env python3
"""Optional isolated Flash rerun of revised S1; never rewrites the v1 panel."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as previous
import s1_candidate_case_v2 as s1
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns

CAP_USD = 0.02


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    fixture = s1.FIXTURES / "US-market" / "findata-toolkit" / "scripts" / "stock_data.py"
    if not fixture.is_file():
        raise FileNotFoundError(fixture)
    if args.preflight_only:
        print(json.dumps({"case_id": "S1-v2", "fixture": str(fixture),
                          "prompt": s1.prompt(), "status": "preflight_ok"}))
        return
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    base.FIXTURES = previous.FIXTURES = s1.FIXTURES
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), HERE / "s1_candidate_case_v2.py",
             HERE / "workflow_runtime_audit_v2.py", fixture,
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py", PLUGIN_PATH]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(case_id="S1-v2", model=panel.MODEL, pricing=panel.PRICING,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    synthetic_fixture=True, result_scope="sandbox_preliminary_candidate")
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with tempfile.TemporaryDirectory(prefix="finance-s1-v2-") as temp_root:
        pilot = panel.PanelPilot("S1-v2", args.template_db, args.gateway_binary,
                                 temp_root, True, 0.0)
        process, log = base.start_gateway(pilot.home)
        state, checks, error = None, {}, None
        try:
            pilot.turn(s1.prompt())
            state = pilot.ledger_state()
            names = [name for turn in pilot.turns for name in turn["tool_calls"]]
            checks = s1.score(state, names)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            try:
                state = pilot.ledger_state()
            except Exception:
                pass
        finally:
            base.stop_gateway(process, log)
        runtime_audit = audit_turns(pilot.turns)
        result = {"case_id": "S1-v2", "status": "mechanical_pass" if
                  error is None and checks and all(checks.values()) and
                  runtime_audit["clean_completion"] else "needs_review",
                  "error": error, "checks": checks, "runtime_audit": runtime_audit,
                  "state": state, "turns": pilot.turns,
                  "estimated_cost_usd": pilot.cost}
        (args.output_dir / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        shutil.copy2(pilot.home / "finance-tools.db", args.output_dir / "finance-tools.db")
        print(json.dumps({"case_id": "S1-v2", "status": result["status"],
                          "error": error, "checks": checks,
                          "runtime_audit": runtime_audit,
                          "estimated_cost_usd": pilot.cost}, ensure_ascii=False))


if __name__ == "__main__":
    main()
