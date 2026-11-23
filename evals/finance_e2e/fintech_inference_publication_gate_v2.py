"""One bounded, source-derived answer check before a workflow publishes prose.

The Gateway has already returned each candidate to this local harness. The
gate controls only downstream acceptance by this workflow; it does not claim
to be a global Gateway output filter or a complete financial fact checker.
"""

import re

from verify_fintech_inference_answer_v1 import check_answer, facts_for, number


CHECK_KEYS = {
    "AFRM-FISCAL-COST": "AFRM_QOQ_REVENUE_DELTA",
    "SOFI-REVENUE-BRIDGE": "SOFI_Q3_GAAP_TO_ADJUSTED_REVENUE",
    "UPST-MIXED-BASIS": "UPST_ADJUSTED_NET_LOSS_YOY",
}


def response_text(turn):
    return turn["response"]["choices"][0]["message"]["content"]


def predeclared_check(case, answer):
    """Check one required result line and all recognized prose contradictions."""
    base = check_answer(case, answer)
    case_id = case["case_id"]
    key = CHECK_KEYS[case_id]
    matches = re.findall(rf"(?m)^\[CHECK\]\s*{key}\s*=\s*([^\n]+)$", answer)
    failures = list(base["failures"])
    if len(matches) != 1:
        failures.append({"code": "REQUIRED_CHECK_MISSING_OR_DUPLICATED", "key": key,
                         "count": len(matches)})
    else:
        raw = matches[0].strip()
        facts = facts_for(case)
        if case_id == "AFRM-FISCAL-COST":
            expected = facts["AFRM-FQ1-REV"] - facts["AFRM-FQ4-REV"]
            try:
                correct = number(raw) == expected
            except Exception:
                correct = False
            if not correct:
                failures.append({"code": "REQUIRED_CHECK_WRONG", "key": key,
                                 "reported": raw, "expected": str(expected)})
        elif case_id == "SOFI-REVENUE-BRIDGE":
            expected = facts["SOFI-Q3-ADJ-REV"]
            expression = re.fullmatch(r"([\d,]+)\s*-\s*([\d,]+)\s*\+\s*([\d,]+)\s*-\s*([\d,]+)\s*=\s*([\d,]+)", raw)
            correct = bool(expression) and tuple(number(part) for part in expression.groups()) == (
                facts["SOFI-Q3-GAAP-REV"], -facts["SOFI-Q3-SERVICING"],
                facts["SOFI-Q3-RESIDUAL"], -facts["SOFI-Q3-DEBTGAIN"], expected)
            if not correct:
                failures.append({"code": "REQUIRED_CHECK_WRONG", "key": key,
                                 "reported": raw, "expected": "697121-4362+9-3323=689445"})
        else:
            expected = ("WIDER" if facts["UPST-Q3-ADJ-NETLOSS"]
                        < facts["UPST-Q3-PRIOR-ADJ-NETLOSS"] else "NARROWER")
            if raw.upper() != expected:
                failures.append({"code": "REQUIRED_CHECK_WRONG", "key": key,
                                 "reported": raw, "expected": expected})
    return {"case_id": case_id, "required_check": key,
            "prose_screen": base, "failures": failures,
            "review_flags": base["review_flags"],
            "accepted_for_claim_review": not failures and not base["review_flags"],
            "quality_pass": None}


def correction_prompt(check):
    """Return bounded, evidence-specific feedback without supplying an answer."""
    failure_codes = sorted({item["code"] for item in check["failures"]})
    return (
        "Your previous research-state review has not been accepted for downstream "
        "publication. Re-read the two stored source packets and recompute the "
        "comparison independently. Correct every arithmetic, sign, comparison-"
        "basis or unsupported attribution issue in the entire answer, including "
        "the required [CHECK] line. Do not create another review, change the "
        "ledger, acknowledge another alert, or trade; this turn is answer-only. "
        "If you cannot verify a claim, omit it and explicitly state the limit. "
        f"Detected issue codes: {', '.join(failure_codes) or 'manual causal-bridge review'}. "
        f"Include exactly one final line [CHECK] {check['required_check']}="
        "<your independently recomputed result> in the format requested in "
        "the original task. Do not copy an unchecked prior value. "
        "Return a complete replacement answer, not just a correction note."
    )


def run_with_one_repair(pilot, case, first_prompt, cap_usd, reserve_repair_usd):
    """Return both immutable candidate turns and the final acceptance decision."""
    candidate = pilot.turn(first_prompt)
    first = predeclared_check(case, response_text(candidate))
    attempts = [{"turn_index": len(pilot.turns) - 1, "check": first}]
    if first["accepted_for_claim_review"]:
        return {"attempts": attempts, "publication_status": "candidate_for_manual_claim_review",
                "final_turn_index": attempts[-1]["turn_index"]}
    if pilot.spent_before + pilot.cost + reserve_repair_usd > cap_usd:
        return {"attempts": attempts, "publication_status": "held_cost_cap",
                "final_turn_index": None}
    replacement = pilot.turn(correction_prompt(first))
    second = predeclared_check(case, response_text(replacement))
    if replacement["tool_calls"]:
        second["failures"].append({"code": "REPAIR_USED_TOOL",
                                   "tools": replacement["tool_calls"]})
        second["accepted_for_claim_review"] = False
    attempts.append({"turn_index": len(pilot.turns) - 1, "check": second})
    return {"attempts": attempts,
            "publication_status": ("candidate_for_manual_claim_review"
                                   if second["accepted_for_claim_review"] else "held_checker"),
            "final_turn_index": attempts[-1]["turn_index"] if second["accepted_for_claim_review"] else None}
