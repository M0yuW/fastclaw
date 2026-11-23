#!/usr/bin/env python3
"""Read-only diagnostic scan of final-answer claims against saved review state.

Flags are review leads, not automatic F/I/R/S/U scores or a substitute for
claim-level reading. This deliberately never edits the frozen observations.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from aggregate_postcorrection_judgments_v2 import verify_frozen_results
from prepare_postcorrection_judgment_v2 import final_text


REVIEW_ID = re.compile(r"\btr_[0-9a-f]{20}\b")
NEXT_REVIEW = re.compile(r"next_review_at[`\s:]*([0-9]{4}-[0-9]{2}-[0-9]{2})", re.I)


def inspect(result: dict) -> list[dict]:
    final = final_text(result) or ""
    state = result.get("state") or {}
    theses = state.get("theses") or []
    alerts = state.get("alerts") or []
    reviews = theses[0].get("reviews") or [] if len(theses) == 1 else []
    review = reviews[0] if len(reviews) == 1 else None
    thesis = theses[0].get("thesis") or {} if len(theses) == 1 else {}
    flags = []

    def flag(code: str, span: str, actual) -> None:
        flags.append({"code": code, "answer_span": span, "actual_state": actual})

    if review:
        rationale = review.get("rationale") or ""
        if re.search(r'"\s*,\s*"(?:evidence|matched_terms|next_review_at)"\s*:', rationale):
            flag("serialized_sibling_fields_inside_rationale",
                 "persisted review rationale contains escaped sibling JSON fields",
                 {"evidence_count": len(review.get("evidence") or []),
                  "next_review_at": thesis.get("next_review_at")})
        both_sources = re.search(
            r"(?:with )?both source (?:records|references|documents)[^\n.]{0,180}",
            final, re.I)
        if (both_sources
                and not review.get("evidence")
                and len(review.get("event", {}).get("sources") or []) < 2):
            flag("claimed_both_sources_attached_but_absent",
                 both_sources.group(0),
                 {"review_evidence_count": 0,
                  "review_event_source_count": len(review.get("event", {}).get("sources") or [])})
        asserted_ids = set(REVIEW_ID.findall(final))
        wrong_ids = asserted_ids - {review.get("id")}
        if wrong_ids:
            flag("incorrect_review_id_in_final", ", ".join(sorted(wrong_ids)),
                 review.get("id"))
    elif re.search(r"review (?:persisted|recorded|saved)", final, re.I):
        flag("claimed_review_write_but_none_saved", "review persisted/recorded/saved", 0)

    for match in NEXT_REVIEW.finditer(final):
        claimed = match.group(1)
        actual = thesis.get("next_review_at")
        if actual != claimed:
            flag("claimed_next_review_date_differs", match.group(0), actual)
    if re.search(r"alert (?:was |is )?acknowledged", final, re.I):
        if len(alerts) != 1 or alerts[0].get("status") != "acknowledged":
            flag("claimed_alert_acknowledged_but_not_saved", "alert acknowledged",
                 [a.get("status") for a in alerts])
    return flags


def audit(results_dir: Path) -> dict:
    verify_frozen_results(results_dir)
    paths = sorted(results_dir.glob("*/result.json"))
    items = []
    for path in paths:
        result = json.loads(path.read_text())
        flags = inspect(result)
        if flags:
            items.append({"observation_id": result["observation_id"],
                          "raw_result": str(path.resolve()), "flags": flags})
    counts = Counter(flag["code"] for item in items for flag in item["flags"])
    return {"status": "diagnostic_flags_not_quality_scores",
            "observations_scanned": len(paths), "flagged_observations": len(items),
            "flag_counts": dict(sorted(counts.items())), "items": items}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output exists; refusing overwrite")
    result = audit(args.results_dir)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "items"}, indent=2))


if __name__ == "__main__":
    main()
