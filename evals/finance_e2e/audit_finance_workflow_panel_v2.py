#!/usr/bin/env python3
"""Read-only, case-specific claim audit of the frozen 80-observation panel.

Target checks are intentionally finite: they do not certify every sentence in
an open-ended answer. The output retains per-observation findings and hashes.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import run_finance_workflow_16_flash_v1 as cases
from test_thesis_event_integration import locked_episode
from workflow_panel_oracle_v2 import adjudicate, tool_result_payload, trace_events


EXPECTED_NUMBERS = {
    "E1": ("6819", "50", "462", "7658", "51", "563"),
    "E2": ("26044", "78.4", "22600", "30040", "75.1", "26300"),
    "E3": ("12606", "44.7", "10", "11097", "40.3", "26"),
    # A missing current gross-margin metric means citing the baseline 78.4 is
    # optional; the output must not invent a current margin.
    "E4": ("26044", "22600", "30040", "26300"),
    "C1": ("8000",), "C2": ("8000", "5000"),
    "C3": ("8000", "5000"), "C4": (),
    "S1": ("16.5", "310", "0.13"),
    "S2": (), "S3": ("420", "260"),
    "S4": ("14.2", "16.5", "0.16", "0.13"),
    "P1": ("45", "30", "25", "50", "0.355"),
    "P2": ("50", "30", "20", "0.38"),
    "P3": ("65", "20", "15", "50", "0.485"),
    "P4": ("45", "30", "25", "50"),
}

EXPECTED_SCREEN = {
    "S1": {"rows": {"FICC": (16.5, 0.12, 0.14, 0.22, 310, 0.13, 0.31)},
           "rejected": {"FICD": "earnings_growth_yoy"}},
    "S2": {"rows": {},
           "rejected": {"FICB": "free_cash_flow", "FICD": "earnings_growth_yoy"}},
    "S3": {"rows": {"FICA": (14.2, 0.18, 0.24, 0.35, 420, 0.16, 0.34)},
           "rejected": {}},
    "S4": {"rows": {"FICA": (14.2, 0.18, 0.24, 0.35, 420, 0.16, 0.34),
                    "FICC": (16.5, 0.12, 0.14, 0.22, 310, 0.13, 0.31)},
           "rejected": {}},
}


def number_present(text, value):
    compact = text.replace(",", "")
    return bool(re.search(r"(?<![\d.])" + re.escape(value) + r"(?![\d.])", compact))


def narrative(result):
    case_id = result["case_id"]
    state = result.get("state") or {}
    if case_id.startswith(("E", "C")):
        try:
            return state["theses"][0]["reviews"][0]["rationale"]
        except (IndexError, KeyError, TypeError):
            return ""
    if case_id == "S1":
        try:
            thesis = state["theses"][0]["thesis"]
            return (thesis.get("title") or "") + "\n" + (thesis.get("thesis") or "")
        except (IndexError, KeyError, TypeError):
            return ""
    turns = result.get("turns") or []
    if not turns:
        return ""
    return str((((turns[-1].get("response") or {}).get("choices") or [{}])[0]
                .get("message") or {}).get("content") or "")


def sec_packet_exact(result):
    case_id = result["case_id"]
    if not case_id.startswith("E"):
        return None
    _, _, episode_id, fact_ids, _ = cases.EVENTS[case_id]
    episode, source = locked_episode(episode_id)
    facts = {fact["id"]: fact for fact in episode["facts"]}
    expected = {facts[fact_id]["metric"]: {
        "value": str(facts[fact_id]["value"]),
        "unit": facts[fact_id]["unit"], "fact_id": fact_id,
    } for fact_id in fact_ids}
    state = result.get("state") or {}
    try:
        actual = state["alerts"][0]["event"]
        return (actual["observed_metrics"] == expected and
                len(actual["sources"]) == 1 and
                actual["sources"][0]["sha256"] == source["sha256"])
    except (IndexError, KeyError, TypeError):
        return False


def conflict_packet_exact(result):
    case_id = result["case_id"]
    if not case_id.startswith("C"):
        return None
    expected, _, _ = cases.conflict_event(case_id)
    state = result.get("state") or {}
    try:
        actual = state["alerts"][0]["event"]
        claims = [{**claim, "value": str(claim["value"])}
                  for claim in expected["source_claims"]]
        return (actual["sources"] == expected["sources"] and
                actual["source_claims"] == claims and
                actual["observed_metrics"] == {
                    key: {**value, "value": str(value["value"])}
                    for key, value in expected["observed_metrics"].items()})
    except (IndexError, KeyError, TypeError):
        return False


def tool_data(result, name):
    payloads = [tool_result_payload(item) for item in trace_events(result, "tool_result", name)]
    return [item for item in payloads if isinstance(item, dict)]


def screen_row_values(row):
    return (row["valuation"]["pe_trailing"],
            row["growth"]["revenue_growth_yoy"],
            row["growth"]["earnings_growth_yoy"],
            row["leverage"]["debt_to_equity"],
            row["cash_flow"]["free_cash_flow"],
            row["profitability"]["roic"],
            row["analyst_consensus"]["upside_pct"])


def financial_tool_data_exact(result):
    case_id = result["case_id"]
    if case_id in ("P1", "P2", "P3"):
        expected = cases.PORTFOLIO[case_id][1]
        output = tool_data(result, "finance-tools__portfolio_risk")
        if len(output) != 1 or output[0].get("ok") is not True:
            return False
        data = output[0].get("data") or {}
        weights = {symbol: round(float(value) * 100, 6)
                   for symbol, value in (data.get("holdings") or {}).items()}
        maximum = max(expected.values())
        hhi = sum((value / 100) ** 2 for value in expected.values())
        return (weights == expected and data.get("largest_weight_pct") == maximum and
                data.get("limit_breached") is (maximum > 50) and
                abs(float(data.get("herfindahl_index", -1)) - hhi) < 1e-9)
    if case_id == "P4":
        output = tool_data(result, "finance-tools__portfolio_risk")
        return not output or all(
            item.get("ok") is False and item.get("data") is None and
            any(error.get("code") == "portfolio_incomplete"
                for error in item.get("errors") or [] if isinstance(error, dict))
            for item in output)
    if case_id.startswith("S"):
        output = tool_data(result, "finance-tools__screen_stocks")
        if len(output) != 1 or output[0].get("ok") is not True:
            return False
        data = output[0].get("data") or {}
        expected = EXPECTED_SCREEN[case_id]
        try:
            rows = {row["symbol"]: screen_row_values(row)
                    for row in data["results"]}
            rejected = {row["symbol"]: row["missing_metrics"][0]
                        for row in data["rejected"]}
        except (KeyError, IndexError, TypeError):
            return False
        return (data.get("synthetic") is True and
                rows == expected["rows"] and rejected == expected["rejected"] and
                data.get("passed") == len(rows) and
                data.get("failed") == len(rejected) and
                (case_id != "S1" or
                 (data["results"][0].get("period") == "FY2025" and
                  data["results"][0]["cash_flow"].get("unit") == "USD_million")))
    return None


def reasoning_flags(case_id, text):
    lower = text.lower()
    flags = []
    if case_id == "E1" and "non-adjacent" in lower and "adjacent" in lower:
        flags.append("contradictory_quarter_adjacency")
    if case_id == "E3" and '"evidence":' in text:
        flags.append("json_fragment_in_stored_rationale")
    if case_id == "E4" and "margin resilience" in lower and "revenue scale grew" in lower:
        flags.append("revenue_used_as_margin_proxy")
    if case_id == "C1" and "duplicate_count 1" in lower and "more than once" in lower:
        flags.append("duplicate_count_one_misread")
    if case_id == "C2" and re.search(r"guidance in the usd.{0,35}range", lower):
        flags.append("conflicting_points_recast_as_range")
    if case_id == "P4":
        # In this case the reported weights are percentages of the whole.
        # Nonnegative omitted weights together cannot exceed the 25% residual.
        if re.search(r"could exceed 50%|might exceed 50%|could itself be the largest|"
                     r"largest position could be|compliance cannot be confirmed or ruled out|"
                     r"cannot be concluded.{0,90}(?:breach|policy)|"
                     r"cannot be confirmed.{0,90}(?:breached|satisfied)|"
                     r"not established.{0,90}third holding", lower, re.S):
            flags.append("unsupported_50_percent_breach_uncertainty")
        if "no position can be confirmed" in lower:
            flags.append("denies_known_position_bound")
    return flags


def audit_one(result, file_path):
    case_id = result["case_id"]
    text = narrative(result)
    missing = [value for value in EXPECTED_NUMBERS[case_id]
               if not number_present(text, value)]
    source_exact = sec_packet_exact(result)
    if source_exact is None:
        source_exact = conflict_packet_exact(result)
    tool_exact = financial_tool_data_exact(result)
    score = adjudicate(result)
    flags = reasoning_flags(case_id, text)
    return {
        "observation_id": result.get("observation_id"), "case_id": case_id,
        "raw_result_sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
        "runtime_pass": score["runtime_pass"],
        "tool_safety_pass": score["tool_safety_pass"],
        "case_process_pass": score["case_process_pass"],
        "raw_false_negative": score["raw_false_negative"],
        "source_packet_exact": source_exact,
        "tool_data_exact": tool_exact,
        "target_number_presence": not missing,
        "missing_target_numbers": missing,
        "reasoning_flags": flags,
        "narrative_present": bool(text.strip()),
        "audit_scope": "targeted assertions, not exhaustive free-text fact certification",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("audit output already exists; refusing to overwrite")
    paths = sorted(args.input_dir.glob("*/result.json"))
    if len(paths) != 80:
        raise ValueError(f"expected exactly 80 frozen observations, got {len(paths)}")
    records = [audit_one(json.loads(path.read_text()), path) for path in paths]
    ids = [item["observation_id"] for item in records]
    if len(set(ids)) != 80:
        raise ValueError("duplicate observation IDs")
    counts = Counter(item["case_id"] for item in records)
    if set(counts.values()) != {5} or len(counts) != 16:
        raise ValueError("expected five observations for each of 16 cases")
    summary = {
        "observations": len(records),
        "runtime_pass": sum(item["runtime_pass"] for item in records),
        "tool_safety_pass": sum(item["tool_safety_pass"] for item in records),
        "case_process_pass": sum(item["case_process_pass"] for item in records),
        "raw_false_negative_ids": [item["observation_id"] for item in records
                                   if item["raw_false_negative"]],
        "source_packet_exact": sum(item["source_packet_exact"] is True for item in records),
        "source_packet_checked": sum(item["source_packet_exact"] is not None for item in records),
        "tool_data_exact": sum(item["tool_data_exact"] is True for item in records),
        "tool_data_checked": sum(item["tool_data_exact"] is not None for item in records),
        "target_number_presence": sum(item["target_number_presence"] for item in records),
        "reasoning_flags": dict(Counter(flag for item in records
                                        for flag in item["reasoning_flags"])),
    }
    manifest_path = args.input_dir / "manifest.json"
    payload = {"auditor": "audit_finance_workflow_panel_v2.py",
               "audit_version": "targeted-claim-v5",
               "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "input_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
               "summary": summary,
               "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
