#!/usr/bin/env python3
"""Run the separately frozen Stage 2A v2 study; never resume the v1 results."""

from evals.finance_e2e import run_stage2_project_report as runner


runner.SUITE = runner.ROOT / "evals" / "finance-retrieval-stage2a-project-report-v2-frozen-2026-10-10.json"
runner.PROTOCOL = runner.ROOT / "evals" / "finance_e2e" / "STAGE2-PROJECT-REPORT-V2-PROTOCOL-2026-10-10.md"
runner.OUTPUT_DIR = runner.ROOT / "evals" / "finance_e2e" / "results" / "2026-10-10-stage2a-project-report-v2-confirmatory"
runner.STUDY = "finance-sec-retrieval-stage2a-project-report-v2"
runner.STEM_PREFIX = "2026-10-10-stage2a-v2"


if __name__ == "__main__":
    runner.main()
