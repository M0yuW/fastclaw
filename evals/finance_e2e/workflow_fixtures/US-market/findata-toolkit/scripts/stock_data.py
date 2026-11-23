#!/usr/bin/env python3
"""Synthetic screen response for the isolated workflow pilot; no network use."""

import json
import sys

if "--screen" not in sys.argv:
    raise SystemExit("fixture supports --screen only")

requested = {arg.upper() for arg in sys.argv[1:] if arg.upper() in {"FICA", "FICB"}}
candidates = {
    "FICA": {
        "symbol": "FICA", "valuation": {"pe_trailing": 14.2},
        "growth": {"revenue_growth_yoy": 0.18, "earnings_growth_yoy": 0.24},
        "leverage": {"debt_to_equity": 0.35},
        "cash_flow": {"free_cash_flow": 420},
        "profitability": {"roic": 0.16},
        "analyst_consensus": {"upside_pct": 0.34},
    },
    "FICB": {
        "symbol": "FICB", "valuation": {"pe_trailing": 11.0},
        "growth": {"revenue_growth_yoy": 0.23, "earnings_growth_yoy": 0.28},
        "leverage": {"debt_to_equity": 0.4},
        "cash_flow": {"free_cash_flow": None},
        "profitability": {"roic": 0.19},
        "analyst_consensus": {"upside_pct": 0.39},
    },
}
print(json.dumps({
    "fixture_id": "synthetic-screen-v1", "synthetic": True,
    "results": [candidates[key] for key in ("FICA", "FICB") if key in requested],
    "rejected": [], "passed": len(requested), "failed": 0,
}))
