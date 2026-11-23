#!/usr/bin/env python3
"""Re-use the byte-locked SEC disclosure adapter from the screen holdout."""

import runpy
from pathlib import Path


HERE = Path(__file__).resolve().parents[4]
SOURCE_ADAPTER = (HERE / "workflow_fixtures_fintech_sec_screen_holdout_v1"
                  / "US-market/findata-toolkit/scripts/stock_data.py")
runpy.run_path(str(SOURCE_ADAPTER), run_name="__main__")
