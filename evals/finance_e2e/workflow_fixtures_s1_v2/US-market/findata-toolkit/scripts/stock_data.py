#!/usr/bin/env python3
"""Offline, explicitly synthetic S1 candidate-screening fixture v2."""

import json
import sys

if "--screen" not in sys.argv:
    raise SystemExit("fixture supports --screen only")

candidates = {
    "FICC": {
        "symbol": "FICC", "period": "FY2025", "as_of": "2026-10-18",
        "source_id": "synthetic-screen-s1-v2-FICC-FY2025",
        "valuation": {"pe_trailing": 16.5},
        "growth": {"revenue_growth_yoy": 0.12, "earnings_growth_yoy": 0.14},
        "leverage": {"debt_to_equity": 0.22},
        "cash_flow": {"free_cash_flow": 310, "unit": "USD_million"},
        "profitability": {"roic": 0.13},
        "analyst_consensus": {"upside_pct": 0.31},
    },
    "FICD": {
        "symbol": "FICD", "period": "FY2025", "as_of": "2026-10-18",
        "source_id": "synthetic-screen-s1-v2-FICD-FY2025",
        "valuation": {"pe_trailing": 9.2},
        "growth": {"revenue_growth_yoy": 0.20, "earnings_growth_yoy": None},
        "leverage": {"debt_to_equity": 0.31},
        "cash_flow": {"free_cash_flow": 270, "unit": "USD_million"},
        "profitability": {"roic": 0.18},
        "analyst_consensus": {"upside_pct": 0.36},
    },
}
requested = [arg.upper() for arg in sys.argv[1:] if arg.upper() in candidates]
print(json.dumps({
    "fixture_id": "synthetic-screen-s1-v2", "synthetic": True,
    "scope": "isolated_candidate_research_only",
    "results": [candidates[key] for key in requested],
    "rejected": [], "passed": len(requested), "failed": 0,
}))
