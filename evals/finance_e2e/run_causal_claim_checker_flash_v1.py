#!/usr/bin/env python3
"""Anonymous Flash checker on ten archived finance research texts."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
from run_finance_workflow_v2 import final_text
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


CASES = HERE / "causal_claim_checker_cases_v1.json"
PROTOCOL = HERE / "CAUSAL-CLAIM-CHECKER-PROTOCOL-v1.md"
CAP_USD = 0.03
RESULTS = HERE / "results"


def reviewed_text(case, result):
    if case["text_field"] == "review_rationale":
        return result["state"]["theses"][0]["reviews"][0]["rationale"]
    if case["text_field"] == "final_answer":
        return result["turns"][-1]["response"]["choices"][0]["message"]["content"]
    raise ValueError("unknown frozen text field")


def preflight():
    corpus = json.loads(CASES.read_text())
    items = corpus["cases"]
    if (corpus["panel_id"] != "CAUSAL-CLAIM-CHECKER-v1" or len(items) != 10 or
            len({item["blind_id"] for item in items}) != 10 or
            sum(item["oracle"] == "material_issue" for item in items) != 5):
        raise ValueError("invalid frozen checker panel")
    lock = {item["id"]: item for item in json.loads((HERE / "source-lock.json").read_text())["entries"]}
    original_paths = []
    for item in items:
        path = RESULTS / item["result_dir"] / "result.json"
        original_paths.append(path)
        result = json.loads(path.read_text())
        if not reviewed_text(item, result):
            raise ValueError(f"missing archived text for {item['blind_id']}")
        source = lock[item["source_id"]]
        if sha256(HERE / source["local_path"]) != source["sha256"]:
            raise ValueError(f"SEC source hash mismatch for {item['blind_id']}")
    return items, original_paths, lock


def prompt(context, text):
    return (
        "You are a separate financial-claim checker. Review the anonymous research text "
        "against only the supplied source context and thesis terms. Identify a MATERIAL "
        "factual, accounting-line, causal-attribution, or thesis-condition error that "
        "could change the research interpretation. Do not flag merely cautious wording, "
        "missing detail, or a permissible discretionary decision. Distinguish cost of "
        "sales, operating items and income tax; do not infer that a whole charge bundle "
        "affects gross margin. If evidence is insufficient, do not invent a cause. "
        "Do not call tools, change a ledger, or use outside information. Return ONLY "
        "one JSON object with keys verdict ('material_issue' or 'no_material_issue'), "
        "issue_type (short string or null), reason (one sentence), corrected_sentence "
        "(one sentence or null), confidence (number from 0 to 1).\n\n"
        "SOURCE CONTEXT:\n" + context + "\n\nTEXT UNDER REVIEW:\n" + text
    )


def parse_verdict(text):
    try:
        answer = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(answer, dict) or answer.get("verdict") not in {
        "material_issue", "no_material_issue"
    }:
        return None
    return answer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--allow-archived-output-egress", action="store_true",
                        help="Required only after explicit user authorization to send archived outputs")
    args = parser.parse_args()
    items, original_paths, lock = preflight()
    if args.preflight_only:
        print(json.dumps({"preflight": "ok", "planned": len(items),
                          "positive_oracle": 5, "negative_oracle": 5}))
        return
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required")
    if not args.allow_archived_output_egress:
        parser.error("external archived-output egress requires explicit authorization")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or gateway binary")
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    source_paths = [HERE / lock[item["source_id"]]["local_path"] for item in items]
    paths = [Path(__file__), CASES, PROTOCOL, HERE / "source-lock.json",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_thesis_event_panel.py", HERE / "workflow_runtime_audit_v2.py",
             PLUGIN_PATH, *original_paths, *source_paths]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=panel.MODEL, pricing=panel.PRICING,
                    run_order=[item["blind_id"] for item in items],
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="causal-claim-checker-") as root:
        for item in items:
            if spent >= CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            blind_id = item["blind_id"]
            archived = json.loads((RESULTS / item["result_dir"] / "result.json").read_text())
            pilot = panel.PanelPilot("checker-" + blind_id, args.template_db,
                                     args.gateway_binary, root, False, spent)
            error = None
            process, log = None, None
            try:
                process, log = base.start_gateway(pilot.home)
                pilot.turn(prompt(item["context"], reviewed_text(item, archived)))
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            finally:
                if process is not None:
                    base.stop_gateway(process, log)
            audit = audit_turns(pilot.turns)
            spent += pilot.cost
            answer_text = final_text(pilot) if pilot.turns else ""
            parsed = parse_verdict(answer_text)
            result = {"blind_id": blind_id, "source_result_sha256": sha256(
                      RESULTS / item["result_dir"] / "result.json"),
                      "oracle": item["oracle"], "checker_answer": parsed,
                      "checker_text": answer_text,
                      "correct": parsed is not None and parsed["verdict"] == item["oracle"],
                      "no_tool_calls": all(not turn["tool_calls"] for turn in pilot.turns),
                      "error": error, "runtime_audit": audit,
                      "turns": pilot.turns, "estimated_cost_usd": pilot.cost}
            directory = args.output_dir / blind_id
            directory.mkdir()
            (directory / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            ledger_db = pilot.home / "finance-tools.db"
            if ledger_db.is_file():
                shutil.copy2(ledger_db, directory / "finance-tools.db")
            print(json.dumps({"blind_id": blind_id,
                              "verdict": (parsed or {}).get("verdict"),
                              "correct": result["correct"], "error": error,
                              "cost": pilot.cost, "cumulative_cost": spent}), flush=True)
            if error or audit["request_errors"] or audit["cost_uncertain_sequences"] or audit["unpriced_sequences"]:
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(items), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
