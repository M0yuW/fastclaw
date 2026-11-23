#!/usr/bin/env python3
"""Conservative, packet-derived checks of explicit claims in retained answers.

This is an offline diagnostic. A clean result is never a content-quality pass:
unparsed prose and causal explanations still require claim-level review.
"""

import argparse
from decimal import Decimal
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
CORPUS = HERE / "fintech_inference_new_issuer_v1.json"
NUMBER = r"([+-]?[\d,]+(?:\.\d+)?)"


def facts_for(case):
    return {fact["id"]: Decimal(str(fact["value"]))
            for period in ("baseline", "event") for fact in case[period]["facts"]}


def number(value):
    return Decimal(value.replace(",", ""))


def check_answer(case, answer):
    """Return only directly observable contradictions, with coverage separate."""
    case_id = case["case_id"]
    facts = facts_for(case)
    failures = []
    review_flags = []
    checked = []

    # Recompute explicit simple equations, independent of issuer or metric.
    # The left operand must not be a tail of a longer multi-term expression.
    equation = re.compile(rf"(?<![\w.+\-−]){NUMBER}\s*([−+\-])\s*{NUMBER}\s*=\s*\*{{0,2}}{NUMBER}")
    for match in equation.finditer(answer):
        line_prefix = answer[answer.rfind("\n", 0, match.start()) + 1:match.start()]
        if re.search(r"[+−-]\s*$", line_prefix):
            # This is a tail of a longer, multi-term expression, not a
            # self-contained two-operand equation.
            continue
        left, operator, right, reported = match.groups()
        expected = number(left) + number(right) if operator == "+" else number(left) - number(right)
        checked.append("explicit_equation")
        if expected != number(reported):
            failures.append({"code": "EQUATION", "text": match.group(),
                             "expected": str(expected)})

    if case_id == "AFRM-FISCAL-COST":
        expected = facts["AFRM-FQ1-REV"] - facts["AFRM-FQ4-REV"]
        # Only an explicitly signed revenue *change* is read here; a source
        # figure or a percentage is not mistaken for the sequential delta.
        delta = re.compile(rf"(?i)(?:GAAP\s+)?revenue\s+(?:\*\*)?\+{NUMBER}")
        for match in delta.finditer(answer):
            checked.append("afrm_sequential_revenue_delta")
            if number(match.group(1)) != expected:
                failures.append({"code": "AFRM_REVENUE_DELTA", "text": match.group(),
                                 "expected": str(expected)})

    elif case_id == "SOFI-REVENUE-BRIDGE":
        q2_gap = facts["SOFI-Q2-GAAP-REV"] - facts["SOFI-Q2-ADJ-REV"]
        q3_gap = facts["SOFI-Q3-GAAP-REV"] - facts["SOFI-Q3-ADJ-REV"]
        relative_widens = q3_gap / facts["SOFI-Q3-GAAP-REV"] > q2_gap / facts["SOFI-Q2-GAAP-REV"]
        relative = re.search(r"(?i)(?:GAAP/non-GAAP\s+)?gap\s+(narrowed|widened)\s+in\s+relative\s+terms", answer)
        if relative:
            checked.append("sofi_relative_gap_direction")
            if (relative.group(1).lower() == "widened") != relative_widens:
                failures.append({"code": "SOFI_RELATIVE_GAP", "text": relative.group(),
                                 "expected": "widened" if relative_widens else "narrowed"})
        gaap_growth = ((facts["SOFI-Q3-GAAP-REV"] / facts["SOFI-Q2-GAAP-REV"]) - 1)
        adjusted_growth = ((facts["SOFI-Q3-ADJ-REV"] / facts["SOFI-Q2-ADJ-REV"]) - 1)
        growth = re.search(r"(?i)adjusted.revenue\s+growth\s+(overstates|understates)\s+GAAP.basis\s+growth", answer)
        if growth:
            checked.append("sofi_growth_basis_direction")
            if (growth.group(1).lower() == "overstates") != (adjusted_growth > gaap_growth):
                failures.append({"code": "SOFI_GROWTH_BASIS", "text": growth.group(),
                                 "expected": "overstates" if adjusted_growth > gaap_growth else "understates"})

    elif case_id == "UPST-MIXED-BASIS":
        # A more negative loss is wider, not narrower. This check is scoped
        # to explicit YoY adjusted-net-loss assertions, not all uses of YoY.
        wider = facts["UPST-Q3-ADJ-NETLOSS"] < facts["UPST-Q3-PRIOR-ADJ-NETLOSS"]
        directions = [
            re.search(r"(?i)(?:year.over.year|YoY)\s+(?:non.GAAP\s+)?adjusted\s+net\s+loss\s+(?:\*\*)?(narrowed|narrower|widened|wider|improved|worsened)", answer),
            re.search(r"(?i)adjusted\s+net\s+loss[^\n]{0,180}?(narrowed|narrower|widened|wider|improved|worsened)[^\n]{0,80}?(?:YoY|year.over.year)", answer),
        ]
        for match in filter(None, directions):
            checked.append("upst_yoy_adjusted_loss_direction")
            claimed_wider = match.group(1).lower() in ("widened", "wider", "worsened")
            if claimed_wider != wider:
                failures.append({"code": "UPST_ADJUSTED_LOSS_YOY", "text": match.group(),
                                 "expected": "widened" if wider else "narrowed"})
        if re.search(r"(?i)(?:net.loss\s+narrowing|net.loss\s+improvement)[^\n.]{0,90}heavily\s+shaped\s+by", answer):
            review_flags.append({"code": "UPST_CAUSAL_BRIDGE_REVIEW",
                                 "reason": "Q3 debt gain does not quantify its share of the Q2-to-Q3 change"})

    if failures:
        screen = "contradiction"
    elif review_flags:
        screen = "needs_review"
    elif not checked:
        screen = "unassessed"
    else:
        screen = "no_detected_contradiction"
    return {"case_id": case_id, "checked_claims": checked,
            "failures": failures, "review_flags": review_flags,
            "screen": screen, "quality_pass": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    args = parser.parse_args()
    cases = {case["case_id"]: case for case in json.loads(CORPUS.read_text())["cases"]}
    for path in sorted(args.results_dir.glob("*/result.json")):
        result = json.loads(path.read_text())
        answer = result["turns"][0]["response"]["choices"][0]["message"]["content"]
        print(json.dumps({"observation_id": result["observation_id"],
                          **check_answer(cases[result["case_id"]], answer)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
