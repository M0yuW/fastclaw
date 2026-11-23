#!/usr/bin/env python3
"""Deterministic offline concentration calculation for fictional holdings."""

import json
import math
import sys


if "--holdings" not in sys.argv or "--concentration" not in sys.argv:
    raise SystemExit("fixture supports holdings concentration only")
raw = sys.argv[sys.argv.index("--holdings") + 1]
weights = dict(item.split(":", 1) for item in raw.split(","))
weights = {key.upper(): float(value) for key, value in weights.items()}
if set(weights) != {"COIN", "HOOD", "SQ"}:
    raise SystemExit("fixture requires exactly COIN, HOOD, SQ")
if not math.isclose(sum(weights.values()), 100.0, rel_tol=0, abs_tol=0.01):
    raise SystemExit("fixture requires complete percentage weights summing to 100")
normalized = {key: value / 100 for key, value in weights.items()}
top_symbol = max(normalized, key=normalized.get)
print(json.dumps({
    "fixture_id": "fintech-sec-portfolio-v1",
    "synthetic": True,
    "not_live_account": True,
    "holdings": normalized,
    "largest_holding": top_symbol,
    "largest_weight_pct": round(100 * normalized[top_symbol], 3),
    "concentration_limit_pct": 50,
    "limit_breached": normalized[top_symbol] > 0.5,
    "herfindahl_index": round(sum(value * value for value in normalized.values()), 6),
}))
