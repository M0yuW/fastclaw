#!/usr/bin/env python3
"""Run the clean all-Flash restart with the existing frozen cost guard."""

from evals.finance_e2e import run_stage2_project_report as runner


runner.SUITE = runner.ROOT / "evals/finance-retrieval-stage2a-all-flash-v3-frozen-2026-10-11.json"
runner.PROTOCOL = runner.ROOT / "evals/finance_e2e/STAGE2-ALL-FLASH-V3-PROTOCOL-2026-10-11.md"
runner.OUTPUT_DIR = runner.ROOT / "evals/finance_e2e/results/2026-10-11-stage2a-all-flash-v3"
runner.STUDY = "finance-sec-stage2a-all-flash-v3"
runner.STEM_PREFIX = "2026-10-11-stage2a-all-flash-v3"
runner.BASE_URL = "http://127.0.0.1:18956"


if __name__ == "__main__":
    runner.main()
