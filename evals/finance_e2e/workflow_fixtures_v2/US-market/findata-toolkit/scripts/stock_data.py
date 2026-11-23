#!/usr/bin/env python3
"""Synthetic, offline screen fixture for a bounded finance workflow study."""

import json
import sys

if "--screen" not in sys.argv:
    raise SystemExit("fixture supports --screen only")

candidates = {
    "FICA": {"symbol": "FICA", "valuation": {"pe_trailing": 14.2},
             "growth": {"revenue_growth_yoy": 0.18, "earnings_growth_yoy": 0.24},
             "leverage": {"debt_to_equity": 0.35}, "cash_flow": {"free_cash_flow": 420},
             "profitability": {"roic": 0.16},
             "analyst_consensus": {"upside_pct": 0.34}},
    "FICB": {"symbol": "FICB", "valuation": {"pe_trailing": 11.0},
             "growth": {"revenue_growth_yoy": 0.23, "earnings_growth_yoy": 0.28},
             "leverage": {"debt_to_equity": 0.4}, "cash_flow": {"free_cash_flow": None},
             "profitability": {"roic": 0.19},
             "analyst_consensus": {"upside_pct": 0.39}},
    "FICC": {"symbol": "FICC", "valuation": {"pe_trailing": 16.5},
             "growth": {"revenue_growth_yoy": 0.12, "earnings_growth_yoy": 0.14},
             "leverage": {"debt_to_equity": 0.22}, "cash_flow": {"free_cash_flow": 310},
             "profitability": {"roic": 0.13},
             "analyst_consensus": {"upside_pct": 0.31}},
    "FICD": {"symbol": "FICD", "valuation": {"pe_trailing": 9.2},
             "growth": {"revenue_growth_yoy": 0.2, "earnings_growth_yoy": None},
             "leverage": {"debt_to_equity": 0.31}, "cash_flow": {"free_cash_flow": 270},
             "profitability": {"roic": 0.18},
             "analyst_consensus": {"upside_pct": 0.36}},
}
requested = [arg.upper() for arg in sys.argv[1:] if arg.upper() in candidates]
print(json.dumps({"fixture_id": "synthetic-screen-v2", "synthetic": True,
                  "results": [candidates[key] for key in requested],
                  "rejected": [], "passed": len(requested), "failed": 0}))
