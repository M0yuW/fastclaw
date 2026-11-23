#!/usr/bin/env python3
"""Run the four-case all-Flash recovery with the frozen cost guard."""

from evals.finance_e2e import run_stage2_project_report as runner


runner.SUITE = runner.ROOT / "evals/finance-retrieval-stage2a-all-flash-recovery-v1-frozen-2026-10-11.json"
runner.PROTOCOL = runner.ROOT / "evals/finance_e2e/STAGE2-ALL-FLASH-RECOVERY-PROTOCOL-2026-10-11.md"
runner.OUTPUT_DIR = runner.ROOT / "evals/finance_e2e/results/2026-10-11-stage2a-all-flash-recovery-v1"
runner.STUDY = "finance-sec-stage2a-all-flash-targeted-recovery-v1"
runner.STEM_PREFIX = "2026-10-11-stage2a-all-flash-recovery-v1"
runner.BASE_URL = "http://127.0.0.1:18956"


if __name__ == "__main__":
    runner.main()
