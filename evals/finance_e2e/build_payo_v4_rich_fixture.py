#!/usr/bin/env python3
"""Build a model-facing PAYO development fixture from source-audited SEC facts.

No model is called. Private interpretation checks never enter the fixture.
This seen-source development case is not a confirmatory quality observation.
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP

import audit_payo_v4_rich_facts as source_audit


MODEL_UNIT = {
    "USD_thousand_reported": "USD_thousand",
    "USD_million_displayed": "USD_million_displayed",
    "USD_billion_displayed": "USD_billion_displayed",
    "thousand_customers_displayed": "thousand_customers_displayed",
    "basis_points": "basis_points",
    "percent": "percent",
}


def number(value: Decimal) -> str:
    return format(value.normalize(), "f")


def fact_text(section: dict) -> str:
    return "; ".join(f"{fact['id']}={fact['value']} {MODEL_UNIT[fact['unit']]}"
                     for fact in section["facts"])


def source_ref(section: dict) -> dict:
    return {"id": section["source_id"], "url": section["source_url"],
            "sha256": section["source_sha256"]}


def numeric_context(packet: dict) -> str:
    before = {fact["metric"]: fact for fact in packet["baseline"]["facts"]}
    after = {fact["metric"]: fact for fact in packet["event"]["facts"]}
    if before.keys() != after.keys():
        raise ValueError("PAYO baseline/event metric set differs")
    lines = [
        f"Case {packet['case_id']}: source-audited selected evidence only, not an assertion that the full exhibits contain no other facts.",
        f"Baseline {packet['baseline']['period']} SEC SHA-256 {packet['baseline']['source_sha256']}.",
        f"Event {packet['event']['period']} SEC SHA-256 {packet['event']['source_sha256']}.",
        "Historical reported and operating comparisons are sequential Q2→Q3; units and evidence classes follow each row:",
        "metric | baseline fact/value | event fact/value | displayed-value change | relative % of Q2 baseline | evidence class",
    ]
    for metric in sorted(before):
        old, new = before[metric], after[metric]
        if old["unit"] != new["unit"] or old["kind"] != new["kind"]:
            raise ValueError(f"PAYO metric unit/class changed: {metric}")
        left, right = Decimal(str(old["value"])), Decimal(str(new["value"]))
        delta = right - left
        relative = (number((delta / left * 100).quantize(Decimal("0.01"),
                    rounding=ROUND_HALF_UP)) + "% of baseline") if left > 0 else "n/a"
        lines.append(
            f"{metric} | {old['id']}={number(left)} {MODEL_UNIT[old['unit']]} | "
            f"{new['id']}={number(right)} {MODEL_UNIT[new['unit']]} | "
            f"{number(delta)} {MODEL_UNIT[old['unit']]} | {relative} | {old['kind']}"
        )
    delta = lambda metric: Decimal(str(after[metric]["value"])) - Decimal(str(before[metric]["value"]))
    revenue, expense, operating = (delta(name) for name in
                                    ("gaap_revenues", "gaap_total_operating_expenses",
                                     "gaap_operating_income"))
    finance, pretax, tax, net = (delta(name) for name in
                                 ("gaap_financial_income_expense_signed",
                                  "gaap_income_before_taxes", "gaap_tax_expense_magnitude",
                                  "gaap_net_income"))
    if not (revenue - expense == operating and operating + finance == pretax
            and pretax - tax == net):
        raise ValueError("PAYO host GAAP delta bridge does not reconcile")
    lines.append(
        f"Source-defined GAAP change bridge, USD_thousand: revenue {number(revenue)} "
        f"− operating-expense change {number(expense)} = operating-income change {number(operating)}; "
        f"operating-income change {number(operating)} + signed-financial-change {number(finance)} "
        f"= pre-tax change {number(pretax)}; pre-tax change {number(pretax)} "
        f"− tax-expense change {number(tax)} = net-income change {number(net)}. "
        "All three residuals are zero. This is arithmetic, not a cause of the underlying line changes."
    )
    lines.append("Company guidance (forward-looking, not realized):")
    for role in ("baseline", "event"):
        guide = packet[role]["guidance"]
        lines.append(f"{role}: total-revenue range {guide['revenue_usd_million_range']} USD_million; "
                     f"adjusted-EBITDA range {guide['adjusted_ebitda_usd_million_range']} USD_million; "
                     f"approximate transaction-cost ratio {guide['transaction_cost_percent_approx']}%.")
    lines.append("Attributed management statements (source claims, not independently established causes):")
    lines.extend(f"{item['period']}: {item['claim']}" for item in
                 packet["attributed_management_statements"])
    lines.append("Boundary: adjusted EBITDA is non-GAAP and not interchangeable with GAAP net income; guidance is not an actual result. Distinguish missing selected-packet evidence from absence in the full SEC exhibit.")
    return "\n".join(lines)


def fixture() -> dict:
    source_audit.audit()
    packet = json.loads(source_audit.PACKET.read_text())
    before, after = packet["baseline"], packet["event"]
    observed = {fact["metric"]: {
        "value": str(fact["value"]),
        "unit": MODEL_UNIT[fact["unit"]],
        "fact_id": fact["id"],
    } for fact in after["facts"]}
    result = {
        "case_id": packet["case_id"], "runtime_symbol": "PAYO",
        "seed_thesis": {
            "market": "US", "symbol": "PAYO",
            "title": "PAYO source-bounded research thesis",
            "thesis": (f"Baseline {before['period']}: {fact_text(before)}. Review the next "
                       "SEC earnings exhibit for supported implications, counterevidence "
                       "and missing context. No valuation or trading conclusion has been established."),
            "status": "active", "conviction": 3,
            "required_event_metrics": sorted(observed),
            "evidence": [source_ref(before)],
        },
        "event": {
            "external_id": "HOLDOUT-V4-PAYO-EVENT",
            "type": "earnings", "as_of": after["filed_at"],
            "summary": (f"PAYO {after['period']} selected SEC evidence: "
                        f"{fact_text(after)}."),
            "sources": [source_ref(after)],
            "observed_metrics": observed,
        },
        "numeric_context": numeric_context(packet),
    }
    serialized = json.dumps(result, ensure_ascii=False)
    if ("precommitted_interpretation_checks" in serialized or
            any(check in serialized for check in packet["precommitted_interpretation_checks"])):
        raise ValueError("private interpretation check leaked into model input")
    return result


def review_prompt(prepared: dict, thesis_id: str, alert_id: str) -> str:
    return (
        "Historical SEC source-bounded research-state replay, not a trade request. "
        "Use finance tools to read the stored thesis and event alert. Independently "
        "form a supported implication, material counterpoint, missing-evidence list, "
        "and research-state decision; do not assume any specified outcome. Distinguish "
        "GAAP, non-GAAP, operating metrics, company guidance and attributed management "
        "explanations. Check arithmetic without treating an accounting identity as "
        "economic causation. Persist one source-linked version-protected review, "
        "acknowledge the alert, and verify the actual thesis/alert state. If key "
        "evidence remains unresolved, a needs_review outcome must remain blocked for "
        "downstream decisions. Do not trade.\n\n"
        + prepared["numeric_context"] + "\n\n"
        + f"Case {prepared['case_id']}; thesis ID {thesis_id}; alert ID {alert_id}."
    )


if __name__ == "__main__":
    item = fixture()
    print(json.dumps({"status": "payo_rich_fixture_ready_no_model_observation",
                      "case_id": item["case_id"],
                      "observed_metrics": len(item["event"]["observed_metrics"]),
                      "model_observations": 0}, indent=2))
