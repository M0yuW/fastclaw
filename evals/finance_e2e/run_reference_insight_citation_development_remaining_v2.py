#!/usr/bin/env python3
"""Continue only seven unattempted citation-development observations.

The first TFC-r1 infrastructure-start failure stays sealed in its own result
directory. This script neither retries it nor pools it away.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import run_reference_insight_citation_development_flash_v2 as citation
import run_reference_insight_development_flash_v1 as runner
import verify_reference_insight_candidate_v2 as gate_v2


SKIPPED = "TFC-2025-Q3-FTE-NII-FEE-CREDIT-MIX-r1"
ORIGINAL_PREFLIGHT = runner.preflight


def remaining_preflight() -> dict:
    frozen = ORIGINAL_PREFLIGHT()
    selected = [(item, repeat) for item, repeat in frozen["order"]
                if f"{item['case_id']}-r{repeat}" != SKIPPED]
    names = [f"{item['case_id']}-r{repeat}" for item, repeat in selected]
    if len(selected) != 7 or SKIPPED in names:
        raise AssertionError("remaining seven run set differs")
    return {"order": selected, "run_ids": names,
            "order_hash": hashlib.sha256(json.dumps(names).encode()).hexdigest()}


def manifest_paths() -> list[Path]:
    return sorted(set(citation.manifest_paths()) | {Path(__file__)})


if __name__ == "__main__":
    runner.ORDER_SEED = "reference-only-seen-case-citation-development-v2"
    runner.prompt_contract.reference_prompt = citation.citation_prompt
    runner.render_reference_card = gate_v2.render_reference_card_v2
    runner.manifest_paths = manifest_paths
    runner.preflight = remaining_preflight
    runner.main()
