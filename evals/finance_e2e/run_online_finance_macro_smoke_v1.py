#!/usr/bin/env python3
"""Read-only online FRED macro smoke through the deployed finance plugin."""

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
    spec = importlib.util.spec_from_file_location("deployed_finance_tools", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load finance plugin: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FinanceToolsPlugin()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", required=True, type=Path)
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    plugin = load_plugin(args.plugin.resolve())
    plugin.finskills_path = args.adapter.resolve()
    plugin.python_bin = sys.executable
    plugin.timeout_seconds = 60
    plugin.evaluation_fixture = False
    status = plugin.toolkit_status({})
    started_at = datetime.now(timezone.utc).isoformat()
    snapshot = plugin.macro_snapshot({"market": "US", "view": "rates"})
    finished_at = datetime.now(timezone.utc).isoformat()

    data = snapshot.get("data") if isinstance(snapshot.get("data"), dict) else {}
    fed_funds = data.get("fed_funds_rate") if isinstance(data.get("fed_funds_rate"), dict) else {}
    series = fed_funds.get("series") if isinstance(fed_funds.get("series"), list) else []
    last_record = series[-1] if series else {}
    sources = [item.get("name") for item in snapshot.get("sources", [])]
    checks = {
        "us_macro_script_available": status.get("data", {}).get("scripts", {}).get("us_macro", {}).get("available") is True,
        "requests_importable": status.get("data", {}).get("dependencies", {}).get("requests") is True,
        "tool_succeeded": snapshot.get("ok") is True,
        "source_correctly_labeled_fred": "FRED" in sources and "local_evaluation_fixture" not in sources,
        "cache_miss": snapshot.get("cache", {}).get("hit") is False,
        "dated_numeric_value": bool(last_record.get("date")) and isinstance(last_record.get("value"), (int, float)),
        "timestamp_and_staleness_present": bool(snapshot.get("as_of")) and bool(snapshot.get("stale_after")),
    }
    result = {
        "case_id": "FINANCE-ONLINE-FRED-RATES-SMOKE-v1",
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "source_endpoint": "https://fred.stlouisfed.org/graph/fredgraph.csv",
        "source_series": "FEDFUNDS",
        "plugin_sha256": sha256(args.plugin),
        "adapter_sha256": sha256(args.adapter / "US-market/findata-toolkit/scripts/macro_data.py"),
        "installed_skill_script_sha256": sha256(Path.home() / ".fastclaw/skills/findata-toolkit/scripts/macro_data.py"),
        "python_executable": sys.executable,
        "checks": checks,
        "status": "pass" if all(checks.values()) else "needs_review",
        "latest_record": last_record,
        "toolkit_status": status,
        "macro_snapshot": snapshot,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "checks": checks,
                      "latest_record": last_record, "sources": sources,
                      "errors": snapshot.get("errors")}, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
