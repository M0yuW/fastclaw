#!/usr/bin/env python3
"""Model-free isolated Gateway and classified-review write-path smoke."""

import argparse
import json
import sqlite3
import tempfile
import urllib.request
from pathlib import Path

from run_thesis_event_gateway import create_ephemeral_key, load_plugin, must_call
from run_thesis_event_panel import AGENT_ID, PORT, prepare_home, start_gateway, stop_gateway


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="accounting-guard-gateway-smoke-") as root:
        home = prepare_home(args.template_db, args.gateway_binary, root)
        with sqlite3.connect(home / "fastclaw.db") as db:
            agent = json.loads(db.execute(
                "SELECT config FROM agents WHERE id=?", (AGENT_ID,)
            ).fetchone()[0])
        if agent["policy"] != "finance-review-only":
            raise RuntimeError("review-only policy was not applied")
        token, user_id = create_ephemeral_key(home / "fastclaw.db", AGENT_ID)
        tenant = {"userId": user_id, "agentId": AGENT_ID, "sessionId": "guard-smoke-seed"}
        finance = load_plugin().FinanceToolsPlugin()
        finance.initialize({"stateDbPath": str(home / "finance-tools.db")})
        thesis = must_call(finance, "thesis_save", {
            "market": "US", "symbol": "TEST", "status": "active", "conviction": 3,
            "thesis": "Check gross-margin drivers against the stored source facts.",
            "required_event_metrics": ["gross_margin"],
        }, tenant)["thesis"]
        must_call(finance, "watchlist_save", {
            "market": "US", "symbol": "TEST", "thesis_id": thesis["id"],
            "event_types": ["earnings"], "keywords": ["TEST"], "min_match_score": 1,
        }, tenant)
        alert = must_call(finance, "event_alert_ingest", {
            "market": "US", "symbol": "TEST", "event": {
                "external_id": "guard-smoke-q3", "type": "earnings",
                "summary": "TEST Q3 source-classified earnings facts.",
                "sources": [{"id": "local-verified-source", "sha256": "a" * 64}],
                "observed_metrics": {
                    "gross_margin": {"value": "15.0", "unit": "percent",
                                     "fact_id": "GM", "statement_line": "unknown"},
                    "asset_charge": {"value": "3100", "unit": "USD_million",
                                     "fact_id": "COST", "statement_line": "cost_of_sales"},
                    "tax_allowance": {"value": "9900", "unit": "USD_million",
                                      "fact_id": "TAX", "statement_line": "income_tax"},
                },
            },
        }, tenant)["results"][0]["alert"]
        current = must_call(finance, "thesis_get", {"thesis_id": thesis["id"]}, tenant)["thesis"]
        review = {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "expected_version": current["version"],
            "event": {"summary": "untrusted model copy"},
            "impact": "negative", "decision": "downgrade", "new_conviction": 2,
            "rationale": "The tax allowance caused the gross-margin collapse.",
        }
        invalid = finance.execute("thesis_record_review", {
            **review, "causal_claims": [{"target_metric": "gross_margin",
                                         "strength": "consistent_with",
                                         "driver_fact_ids": ["TAX"]}],
        }, tenant)
        if invalid["ok"] or invalid["errors"][0]["code"] != "unsupported_causal_claim":
            raise RuntimeError("tax-to-margin claim was not rejected")
        after_reject = must_call(finance, "thesis_get", {"thesis_id": thesis["id"]}, tenant)
        if after_reject["thesis"]["version"] != current["version"] or after_reject["reviews"]:
            raise RuntimeError("rejected claim mutated ledger")
        valid = must_call(finance, "thesis_record_review", {
            **review, "causal_claims": [{"target_metric": "gross_margin",
                                         "strength": "consistent_with",
                                         "driver_fact_ids": ["COST"]}],
        }, tenant)
        if "tax allowance caused" in valid["review"]["rationale"].lower():
            raise RuntimeError("untrusted rationale was persisted")
        process, log = start_gateway(home)
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{PORT}/v1/agents",
                headers={"Authorization": "Bearer " + token},
            )
            with urllib.request.urlopen(request, timeout=5) as handle:
                agents = json.load(handle)
            gateway_log = (home / "gateway.log").read_text(errors="replace")
            if 'msg="gateway started"' not in gateway_log or "finance-tools" not in gateway_log:
                raise RuntimeError("gateway or finance plugin did not finish initialization")
            print(json.dumps({"result": "pass", "model_calls": 0,
                              "policy": agent["policy"],
                              "rejected_claim_no_mutation": True,
                              "validated_review_version": valid["thesis"]["version"],
                              "gateway_agents_response_type": type(agents).__name__}))
        finally:
            stop_gateway(process, log)


if __name__ == "__main__":
    main()
