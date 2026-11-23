#!/usr/bin/env python3
"""Eight separately authorized, seen-case citation-contract development probes.

This deliberately reuses the v1 isolated Gateway harness and frozen SEC inputs,
but changes the prompt and prospective publication gate. It is not a holdout.
"""

from __future__ import annotations

from pathlib import Path

import build_reference_insight_prompt_v1 as prompt_v1
import run_reference_insight_development_flash_v1 as runner
import verify_reference_insight_candidate_v2 as gate_v2


HERE = Path(__file__).resolve().parent
ORIGINAL_PROMPT = prompt_v1.reference_prompt
ORIGINAL_MANIFEST_PATHS = runner.manifest_paths


def citation_prompt(fixture: dict, catalog: dict, thesis_id: str,
                    alert_id: str) -> str:
    return ORIGINAL_PROMPT(fixture, catalog, thesis_id, alert_id) + (
        "\n\nAdditional citation-development instructions: first read the actual "
        "thesis and alert, then select comparison IDs from the supplied table "
        "for both supporting and opposing evidence. Treat these IDs as links to "
        "selected SEC rows, not as proof of a causal explanation. In the saved "
        "review rationale, state the qualitative case and uncertainty without "
        "free-form numbers, currency symbols, dates, or unsupported consensus "
        "beat/miss language. A tax-expense increase must not be described as a "
        "smaller tax drag; same-direction GAAP profit comparisons cannot be "
        "opposing evidence solely because one is a different subtotal. If the "
        "selected evidence cannot support a defensible view, choose needs_review "
        "and preserve the research hold. Copy the final asserted_state from "
        "observed tool results, not from the requested action. Do not present "
        "the final JSON until the linked review and alert acknowledgement are "
        "actually recorded."
    )


def manifest_paths() -> list[Path]:
    return sorted(set(ORIGINAL_MANIFEST_PATHS()) | {
        Path(__file__), Path(gate_v2.__file__),
        HERE / "screen_reference_insight_semantics_v2.py",
        HERE / "REFERENCE-INSIGHT-CITATION-DEVELOPMENT-PROTOCOL-v2.md",
    })


if __name__ == "__main__":
    runner.ORDER_SEED = "reference-only-seen-case-citation-development-v2"
    runner.prompt_contract.reference_prompt = citation_prompt
    runner.render_reference_card = gate_v2.render_reference_card_v2
    runner.manifest_paths = manifest_paths
    runner.main()
