#!/usr/bin/env python3
"""Synthetic, offline concentration diagnostic for workflow evaluation."""

import json
import sys

if "--holdings" not in sys.argv or "--concentration" not in sys.argv:
    raise SystemExit("fixture supports holdings concentration only")
raw = sys.argv[sys.argv.index("--holdings") + 1]
weights = dict(item.split(":", 1) for item in raw.split(","))
weights = {key.upper(): float(value) for key, value in weights.items()}
if not set(weights) <= {"FICA", "FICB", "FICC"}:
    raise SystemExit("fixture supports FICA/FICB/FICC only")
total = sum(weights.values())
normalized = {key: value / total for key, value in weights.items()}
top_symbol = max(normalized, key=normalized.get)
print(json.dumps({
    "fixture_id": "synthetic-portfolio-v2", "synthetic": True,
    "holdings": normalized, "largest_holding": top_symbol,
    "largest_weight_pct": round(100 * normalized[top_symbol], 1),
    "concentration_limit_pct": 50,
    "limit_breached": normalized[top_symbol] > 0.5,
    "herfindahl_index": round(sum(value * value for value in normalized.values()), 4),
}))
