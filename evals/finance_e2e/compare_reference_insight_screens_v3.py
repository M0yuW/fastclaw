#!/usr/bin/env python3
"""Read-only, fixed-output developmental comparison of post-final screens.

The saved answers have already been inspected while designing v3. These
counts are a rule diagnostic, not prospective containment accuracy. No ledger
write, Gateway request, or model call occurs here.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from aggregate_postcorrection_judgments_v2 import validate_review
from screen_reference_insight_semantics_v2 import screen as screen_v2
from screen_reference_insight_semantics_v3 import screen as screen_v3
from verify_reference_insight_candidate_v1 import verify_reference_candidate


def comparison_rows(packet: dict) -> dict:
    rows = {}
    for source in packet["source_packet"]["rows"]:
        row = dict(source)
        delta = Decimal(str(row["delta_value"]))
        row["metric"] = row["id"]
        row["direction"] = ("increase" if delta > 0 else
                            "decrease" if delta < 0 else "flat")
        rows["SEQ:" + row["id"]] = row
    return rows


def compare(root: Path) -> dict:
    counts = Counter()
    changes = []
    for score_path in sorted((root / "scores").glob("J-*.json")):
        score = json.loads(score_path.read_text())
        if not score.get("reviewer"):
            continue
        label = validate_review(score, score["masked_id"])
        packet = json.loads((root / "masked_packets" / score_path.name).read_text())
        state = {"theses": packet["persisted_theses_and_reviews"],
                 "alerts": packet["persisted_alerts"]}
        actionability = state["theses"][0]["thesis"].get("actionability")
        counts[("reviewed", label)] += 1
        try:
            candidate = json.loads(packet["final_answer"])
        except json.JSONDecodeError:
            counts[("malformed_final_json", label)] += 1
            continue
        catalog = {"rows": comparison_rows(packet)}
        mechanical = verify_reference_candidate(catalog, candidate, state)
        v2 = screen_v2(catalog, candidate, state)["alerts"]
        v3 = screen_v3(catalog, candidate, state)["alerts"]
        old_status = ("held" if mechanical["issues"] or v2 else
                      "candidate_for_qualitative_review")
        new_status = ("held" if mechanical["issues"] or v3 else
                      "candidate_for_qualitative_review")
        counts[("parsed", label)] += 1
        counts[("v2", label, old_status)] += 1
        counts[("v3", label, new_status)] += 1
        if old_status != new_status or set(v2) != set(v3):
            changes.append({
                "masked_id": packet["masked_id"],
                "symbol": packet["source_packet"]["symbol"],
                "local_review_label": label,
                "observed_actionability": actionability,
                "mechanical_issues": mechanical["issues"],
                "v2_status": old_status, "v3_status": new_status,
                "v2_alerts": v2, "v3_alerts": v3,
            })
    return {
        "study_type": "developmental_post_final_fixed_output_comparison",
        "model_calls": 0, "gateway_calls": 0, "ledger_writes": 0,
        "quality_pass": None,
        "count_rows": [
            {"key": list(key), "count": value}
            for key, value in sorted(counts.items(), key=lambda x: str(x[0]))
        ],
        "changed_items": changes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judgment-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.judgment_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
