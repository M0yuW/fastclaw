#!/usr/bin/env python3
"""Build a provenance-linked numeric evidence bundle before agent inference.

The caller must run the raw-document/selected-fact preflight first. This
module does not certify that a fact was transcribed from the SEC correctly.
It prevents the model from recomputing or silently changing validated facts
when the workflow assembles the downstream research note.
"""

import datetime as dt
import json
import re

from derive_financial_comparisons_v1 import compare, reconcile


PERIOD = re.compile(r"^(FY|CY)(\d{4}) Q([1-4]) ended (\d{4}-\d{2}-\d{2})$")
REQUIRED_INTERPRETATION_KEYS = {
    "implication", "counterpoint", "next_evidence", "comparison_ids",
    "causal_status", "decision",
}
CAUSAL_STATUS = {"observation_only", "bounded_hypothesis", "source_explicit_bridge"}
DECISIONS = {"maintain", "upgrade", "downgrade", "needs_review", "invalidate"}


def parse_period(value):
    match = PERIOD.fullmatch(value)
    if not match:
        raise ValueError(f"unsupported period label: {value}")
    kind, year, quarter, end = match.groups()
    return {"kind": kind, "year": int(year), "quarter": int(quarter),
            "end": dt.date.fromisoformat(end)}


def check_adjacent_quarters(baseline, event):
    before, after = parse_period(baseline), parse_period(event)
    if before["kind"] != after["kind"]:
        raise ValueError("calendar/fiscal basis changed")
    before_index = before["year"] * 4 + before["quarter"]
    after_index = after["year"] * 4 + after["quarter"]
    if after_index != before_index + 1:
        raise ValueError("periods are not adjacent reported quarters")
    if not (75 <= (after["end"] - before["end"]).days <= 110):
        raise ValueError("quarter end dates are not approximately three months apart")


def fact_map(case):
    facts = {}
    for period in ("baseline", "event"):
        for fact in case[period]["facts"]:
            if fact["id"] in facts:
                raise ValueError(f"duplicate fact ID: {fact['id']}")
            facts[fact["id"]] = (period, fact)
    return facts


def build_bundle(case, reconciliation_specs=()):
    """Generate all same-metric sequential and declared prior-year comparisons."""
    check_adjacent_quarters(case["baseline"]["period"], case["event"]["period"])
    facts = fact_map(case)
    baseline_by_metric = {}
    for fact in case["baseline"]["facts"]:
        if fact["metric"] in baseline_by_metric:
            raise ValueError(f"duplicate baseline metric: {fact['metric']}")
        baseline_by_metric[fact["metric"]] = fact
    event_by_metric = {}
    prior_year = {}
    for fact in case["event"]["facts"]:
        if "_prior_year_same_quarter" in fact["metric"]:
            key = fact["metric"].replace("_prior_year_same_quarter", "")
            if key in prior_year:
                raise ValueError(f"duplicate prior-year comparator: {key}")
            prior_year[key] = fact
        else:
            if fact["metric"] in event_by_metric:
                raise ValueError(f"duplicate event metric: {fact['metric']}")
            event_by_metric[fact["metric"]] = fact

    comparisons = []
    for metric in sorted(set(event_by_metric) & set(baseline_by_metric)):
        result = compare(event_by_metric[metric], baseline_by_metric[metric], "sequential")
        result.update(id=f"SEQ:{metric}",
                      event_source_sha256=case["event"]["source_sha256"],
                      baseline_source_sha256=case["baseline"]["source_sha256"])
        comparisons.append(result)
    for metric in sorted(set(event_by_metric) & set(prior_year)):
        result = compare(event_by_metric[metric], prior_year[metric], "year_over_year")
        result.update(id=f"YOY:{metric}",
                      event_source_sha256=case["event"]["source_sha256"],
                      baseline_source_sha256=case["event"]["source_sha256"])
        comparisons.append(result)
    if not comparisons:
        raise ValueError("no comparable facts in the selected packet")

    reconciliations = []
    for spec in reconciliation_specs:
        ids = [spec["base_fact_id"], *spec["signed_adjustment_fact_ids"],
               spec["reported_fact_id"]]
        if not all(fact_id in facts and facts[fact_id][0] == "event" for fact_id in ids):
            raise ValueError("reconciliation references missing or non-event fact")
        result = reconcile(facts[ids[0]][1], [facts[fact_id][1] for fact_id in ids[1:-1]],
                           facts[ids[-1]][1])
        result.update(id=spec["id"], source_sha256=case["event"]["source_sha256"])
        reconciliations.append(result)
    identifiers = [item["id"] for item in [*comparisons, *reconciliations]]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate calculation ID")
    return {"case_id": case["case_id"], "symbol": case["symbol"],
            "source_basis": "selected_exhibit_facts_not_full_filing",
            "baseline_period": case["baseline"]["period"],
            "event_period": case["event"]["period"],
            "sources": [{"period": period, "url": case[period]["source_url"],
                         "sha256": case[period]["source_sha256"]}
                        for period in ("baseline", "event")],
            "comparisons": comparisons, "reconciliations": reconciliations}


def validate_interpretation(payload, bundle):
    """Validate a model's qualitative envelope; never award insight quality."""
    if not isinstance(payload, dict) or set(payload) != REQUIRED_INTERPRETATION_KEYS:
        raise ValueError("interpretation fields differ from schema")
    for key in ("implication", "counterpoint", "next_evidence"):
        value = payload[key]
        if not isinstance(value, str) or not (30 <= len(value.strip()) <= 1500):
            raise ValueError(f"{key} must be a substantive text field")
        if re.search(r"\d|[%$€£¥]|(?:million|billion|thousand)", value, re.IGNORECASE):
            raise ValueError(f"{key} contains a new numerical claim")
    if payload["causal_status"] not in CAUSAL_STATUS:
        raise ValueError("invalid causal status")
    if payload["decision"] not in DECISIONS:
        raise ValueError("invalid decision")
    references = payload["comparison_ids"]
    known = {item["id"] for item in [*bundle["comparisons"], *bundle["reconciliations"]]}
    if (not isinstance(references, list) or not references
            or any(not isinstance(item, str) for item in references)
            or len(references) != len(set(references))
            or not set(references) <= known):
        raise ValueError("unknown or duplicate comparison reference")
    if payload["causal_status"] == "source_explicit_bridge":
        # Accounting reconciliation is not a causal attribution. This bundle
        # has no source-audited driver-to-outcome evidence, so it cannot grant
        # the stronger causal label.
        raise ValueError("source-explicit causal bridge not supported by this bundle")
    return {"status": "schema_and_numeric_boundary_pass",
            "quality_pass": None, "referenced_comparisons": references}


def render_numeric_table(bundle):
    """Render only host-computed figures; model prose is appended separately."""
    lines = ["| Comparison ID | Direction | Change (USD thousand) | Change % | Precision |",
             "|---|---|---:|---:|---|"]
    for item in bundle["comparisons"]:
        lines.append(f"| {item['id']} | {item['direction']} | {item['delta_usd_thousand']} | "
                     f"{item['percent_change_of_baseline'] or 'n/a'} | {item['precision']} |")
    for item in bundle["reconciliations"]:
        lines.append(f"| {item['id']} | {'reconciled' if item['reconciled'] else 'unreconciled'} | "
                     f"residual {item['residual_usd_thousand']} | n/a | exact_from_selected_facts |")
    return "\n".join(lines)


def render_research_note(bundle, interpretation):
    validate_interpretation(interpretation, bundle)
    source_lines = "\n".join(
        f"- {source['period']}: {source['url']} (SHA-256 {source['sha256']})"
        for source in bundle["sources"])
    return (f"# {bundle['symbol']} source-bounded research note\n\n"
            f"Selected exhibit periods: {bundle['baseline_period']} → {bundle['event_period']}.\n\n"
            + render_numeric_table(bundle) + "\n\n"
            + "Sources:\n" + source_lines + "\n\n"
            + "Referenced calculations: " + ", ".join(interpretation["comparison_ids"]) + ".\n\n"
            + f"Research implication: {interpretation['implication']}\n\n"
            + f"Counterpoint: {interpretation['counterpoint']}\n\n"
            + f"Evidence to seek: {interpretation['next_evidence']}\n\n"
            + f"Decision: {interpretation['decision']}; causal status: {interpretation['causal_status']}.\n"
            + "Source scope: selected, verified exhibit facts; not a full-filing review.\n")


if __name__ == "__main__":
    import preflight_fintech_inference_new_issuer_v1 as preflight
    preflight.verify()
    cases = json.loads(preflight.CORPUS.read_text())["cases"]
    for case in cases:
        specs = ([{"id": "REC:SOFI_Q3_ADJUSTED_REVENUE",
                   "base_fact_id": "SOFI-Q3-GAAP-REV",
                   "signed_adjustment_fact_ids": ["SOFI-Q3-SERVICING", "SOFI-Q3-RESIDUAL",
                                                  "SOFI-Q3-DEBTGAIN"],
                   "reported_fact_id": "SOFI-Q3-ADJ-REV"}]
                 if case["case_id"] == "SOFI-REVENUE-BRIDGE" else [])
        print(json.dumps(build_bundle(case, specs), ensure_ascii=False))
