#!/usr/bin/env python3
"""Run the diverse archived-output checker only after explicit egress approval."""

import argparse
import json
import random
import shutil
import tempfile
from pathlib import Path

import preflight_claim_checker_diverse_v2 as preflight
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
from run_finance_workflow_v2 import final_text
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


CORPUS = HERE / "claim_checker_diverse_cases_v2.json"
PROTOCOL = HERE / "CLAIM-CHECKER-DIVERSE-PROTOCOL-v2.md"
CAP_USD = 0.03
RESERVE_NEXT_USD = 0.005
SEED = 2247


def scrub_identifiers(archived_text, archived, item):
    """Mask experiment labels, not company names or substantive evidence."""
    for identifier in (Path(item["result_dir"]).name, archived.get("case_id")):
        if identifier:
            archived_text = archived_text.replace(identifier, "[CASE]")
    return archived_text


def prompt(blind_id, context, archived_text):
    return (
        "You are checking one anonymous financial-research answer against only "
        "the supplied source context. Identify whether it makes a MATERIAL "
        "factual, accounting-basis, causal, policy, or interpretation error "
        "that could change the research reading. A cautious qualification or "
        "missing detail alone is not an error. Do not infer omitted data, "
        "use outside information, call tools, or change any state. If the "
        "context cannot support a fair verdict, abstain. Return only one JSON "
        "object with keys verdict ('material_issue', 'no_material_issue', or "
        "'not_assessable'), issue_type (short string or null), reason (one "
        "sentence), source_pointer (short phrase or null), corrected_sentence "
        "(one sentence or null), and confidence (number 0 to 1).\n\n"
        "ANONYMOUS ITEM: " + blind_id + "\n\nSOURCE CONTEXT:\n" + context
        + "\n\nANSWER UNDER REVIEW:\n" + archived_text
    )


def parse_verdict(text):
    try:
        answer = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(answer, dict) or answer.get("verdict") not in {
        "material_issue", "no_material_issue", "not_assessable"
    }:
        return None
    if not isinstance(answer.get("reason"), str):
        return None
    try:
        confidence = float(answer.get("confidence"))
    except (TypeError, ValueError):
        return None
    if not 0 <= confidence <= 1:
        return None
    return answer


def write_hashes(output_dir):
    paths = [output_dir / "manifest.json", *sorted(output_dir.glob("*/result.json")),
             *sorted(output_dir.glob("*/turn_checkpoint.json")),
             *sorted(output_dir.glob("*/gateway.log"))]
    (output_dir / "RESULT-SHA256.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.resolve().relative_to(ROOT.resolve())}" for path in paths) + "\n")


def save_turn_checkpoint(directory, pilot):
    """Persist the provider response before Gateway shutdown or later scoring."""
    if not pilot.turns:
        return
    directory.mkdir(exist_ok=True)
    (directory / "turn_checkpoint.json").write_text(json.dumps({
        "turns": pilot.turns,
        "estimated_cost_usd": pilot.cost,
    }, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--allow-archived-output-egress", action="store_true",
                        help="Requires direct user authorization in addition to protocol marker")
    args = parser.parse_args()
    source_check = preflight.verify()
    items = json.loads(CORPUS.read_text(encoding="utf-8"))["cases"]
    order = [item["blind_id"] for item in items]
    random.Random(SEED).shuffle(order)
    if args.preflight_only:
        print(json.dumps({"preflight": "ok", "planned": len(items),
                          "source_preflight": source_check["preflight"],
                          "run_order": order, "external_calls": 0}))
        return
    if not args.allow_archived_output_egress:
        parser.error("archived-output egress requires explicit user authorization")
    if "ARCHIVED-OUTPUT-EGRESS-AUTHORIZED: yes" not in PROTOCOL.read_text(encoding="utf-8"):
        raise RuntimeError("protocol lacks user-authorization marker")
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.output_dir.resolve().is_relative_to(ROOT.resolve()):
        parser.error("--output-dir must be within the repository")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    original_paths = [preflight.RESULTS / item["result_dir"] / "result.json"
                      for item in items]
    screen = json.loads(preflight.SCREEN_PACKET.read_text(encoding="utf-8"))
    source_paths = [HERE / candidate["local_path"] for candidate in screen["candidates"]
                    if candidate["symbol"] in {"COIN", "HOOD", "SQ"}]
    paths = [Path(__file__), CORPUS, PROTOCOL, Path(preflight.__file__),
             preflight.SCREEN_PACKET,
             HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md",
             HERE / "run_finance_workflow_pilot.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "workflow_runtime_audit_v2.py", PLUGIN_PATH,
             *original_paths, *source_paths]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=panel.MODEL, pricing=panel.PRICING,
                    run_order=order, random_seed=SEED,
                    source_preflight=source_check,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    reserve_next_observation_usd=RESERVE_NEXT_USD,
                    archived_model_outputs_in_prompt=True)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    by_id = {item["blind_id"]: item for item in items}
    spent = 0.0
    try:
        with tempfile.TemporaryDirectory(prefix="diverse-claim-checker-") as root:
            for blind_id in order:
                if spent + RESERVE_NEXT_USD > CAP_USD:
                    print("STOP: conservative estimated-spend reserve reached", flush=True)
                    break
                item = by_id[blind_id]
                archived_path = preflight.RESULTS / item["result_dir"] / "result.json"
                archived = json.loads(archived_path.read_text(encoding="utf-8"))
                pilot = panel.PanelPilot("checker-" + blind_id, args.template_db,
                                         args.gateway_binary, root, False, spent)
                error, process, log = None, None, None
                try:
                    process, log = base.start_gateway(pilot.home)
                    text_under_review = scrub_identifiers(
                        preflight.final_text(archived), archived, item)
                    pilot.turn(prompt(blind_id, item["context"], text_under_review))
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                finally:
                    directory = args.output_dir / blind_id
                    save_turn_checkpoint(directory, pilot)
                    if process is not None:
                        try:
                            base.stop_gateway(process, log)
                        except Exception as exc:
                            error = (error + "; " if error else "") + f"cleanup {type(exc).__name__}: {exc}"
                    gateway_log = pilot.home / "gateway.log"
                    if gateway_log.is_file():
                        directory.mkdir(exist_ok=True)
                        shutil.copy2(gateway_log, directory / "gateway.log")
                audit = audit_turns(pilot.turns)
                spent += pilot.cost
                text = final_text(pilot) if pilot.turns else ""
                parsed = parse_verdict(text)
                result = {
                    "blind_id": blind_id, "source_result_sha256": sha256(archived_path),
                    "oracle": item["oracle"], "checker_answer": parsed,
                    "checker_text": text,
                    "correct": parsed is not None and parsed["verdict"] == item["oracle"],
                    "no_tool_calls": all(not turn["tool_calls"] for turn in pilot.turns),
                    "error": error, "runtime_audit": audit,
                    "turns": pilot.turns, "estimated_cost_usd": pilot.cost,
                }
                directory = args.output_dir / blind_id
                directory.mkdir(exist_ok=True)
                (directory / "result.json").write_text(
                    json.dumps(result, indent=2, ensure_ascii=False) + "\n")
                ledger = pilot.home / "finance-tools.db"
                if ledger.is_file():
                    shutil.copy2(ledger, directory / "finance-tools.db")
                print(json.dumps({"blind_id": blind_id,
                                  "verdict": (parsed or {}).get("verdict"),
                                  "correct": result["correct"], "error": error,
                                  "cost": pilot.cost, "cumulative_cost": spent}), flush=True)
                if (error or audit["request_errors"] or audit["cost_uncertain_sequences"]
                        or audit["unpriced_sequences"]):
                    print("STOP: request error or uncertain pricing", flush=True)
                    break
    finally:
        write_hashes(args.output_dir)
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(items), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
