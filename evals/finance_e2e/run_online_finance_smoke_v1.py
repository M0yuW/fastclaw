#!/usr/bin/env python3
"""Read-only live FinData Toolkit smoke through the installed finance plugin.

This calls one US price-history tool. It does not invoke an LLM, write a thesis,
or claim that a recent price is an exchange-grade tick quote.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_plugin(path: Path):
    spec = importlib.util.spec_from_file_location("installed_finance_tools", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load plugin: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FinanceToolsPlugin()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbol", default="AMD")
    args = parser.parse_args()

    plugin = load_plugin(args.plugin.resolve())
    plugin.finskills_path = args.adapter.resolve()
    plugin.python_bin = sys.executable
    plugin.evaluation_fixture = False
    status = plugin.toolkit_status({})
    started_at = datetime.now(timezone.utc).isoformat()
    snapshot = plugin.stock_snapshot({
        "market": "US", "symbols": [args.symbol],
        "view": "history", "period": "5d",
    })
    finished_at = datetime.now(timezone.utc).isoformat()

    data = snapshot.get("data") if isinstance(snapshot, dict) else None
    if not isinstance(data, dict):
        data = {}
    prices = data.get("prices") if isinstance(data.get("prices"), list) else []
    source_names = [item.get("name") for item in snapshot.get("sources", [])]
    checks = {
        "us_stock_script_available": status.get("data", {}).get("scripts", {}).get("us_stock", {}).get("available") is True,
        "yfinance_importable": status.get("data", {}).get("dependencies", {}).get("yfinance") is True,
        "tool_succeeded": snapshot.get("ok") is True,
        "live_source_declared": "yfinance" in source_names and "local_evaluation_fixture" not in source_names,
        "cache_miss": snapshot.get("cache", {}).get("hit") is False,
        "dated_prices_returned": bool(prices) and all(item.get("date") and isinstance(item.get("close"), (int, float)) for item in prices),
        "timestamp_and_staleness_present": bool(snapshot.get("as_of")) and bool(snapshot.get("stale_after")),
    }
    record = {
        "case_id": "FINANCE-ONLINE-US-HISTORY-SMOKE-v1",
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "symbol": args.symbol,
        "plugin_sha256": sha256(args.plugin),
        "adapter_sha256": sha256(args.adapter / "US-market/findata-toolkit/scripts/stock_data.py"),
        "installed_skill_script_sha256": sha256(Path.home() / ".fastclaw/skills/findata-toolkit/scripts/stock_data.py"),
        "python_executable": sys.executable,
        "checks": checks,
        "status": "pass" if all(checks.values()) else "needs_review",
        "toolkit_status": status,
        "stock_snapshot": snapshot,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "status": record["status"], "checks": checks,
        "latest_date": data.get("end_date"),
        "data_points": data.get("data_points"),
        "estimated_source": source_names,
        "error": snapshot.get("errors"),
    }, ensure_ascii=False, indent=2))
    return 0 if record["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
