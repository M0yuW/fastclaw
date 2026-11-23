import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import plugin


STUB_SCRIPT = """\
import json
import sys

payload = {
    "argv": sys.argv[1:],
    "results": [
        {
            "symbol": "COMPLETE",
            "valuation": {"pe_ttm": 10, "pb": 2},
            "profitability": {"roe": 12},
            "leverage": {"debt_to_asset_ratio": 30}
        },
        {
            "symbol": "MISSING",
            "valuation": {"pe_ttm": 10, "pb": None},
            "profitability": {"roe": 12},
            "leverage": {"debt_to_asset_ratio": 30}
        }
    ],
    "rejected": [],
    "passed": 2,
    "failed": 0
}
print(json.dumps(payload))
"""

STUB_PORTFOLIO_SCRIPT = """\
import json
import sys
print(json.dumps({"argv": sys.argv[1:], "synthetic": True}))
"""


class FinanceToolsPluginTest(unittest.TestCase):
    def test_opt_in_guard_sanitizes_bad_deferred_rationale_and_keeps_hold(self):
        catalog_path = self.root / "review-guard-catalog.json"
        catalog_path.write_text(json.dumps({
            "version": "review-arithmetic-guard-catalog-v1",
            "cases": [{
                "symbol": "TAX",
                "baseline_source_sha256": "a" * 64,
                "event_source_sha256": "b" * 64,
                "rows": {"SEQ:gaap_income_tax_provision": {
                    "baseline_value": "-68.7", "event_value": "-53.8",
                    "delta_value": "14.9", "unit": "USD_million",
                    "basis": "GAAP_consolidated_quarter_signed_contribution",
                }},
            }],
        }), encoding="utf-8")
        guarded = plugin.FinanceToolsPlugin()
        guarded.initialize({
            "finskillsPath": str(self.root),
            "stateDbPath": str(self.root / "guarded-state.db"),
            "reviewArithmeticGuardCatalogPath": str(catalog_path),
        })
        thesis = guarded.execute("thesis_save", {
            "market": "US", "symbol": "TAX", "thesis": "Review the tax bridge.",
            "status": "active", "conviction": 3,
            "evidence": [{"id": "before", "sha256": "a" * 64}],
            "required_event_metrics": ["gaap_income_tax_provision"],
        }, self.user_context)["data"]["thesis"]
        guarded.execute("watchlist_save", {
            "market": "US", "symbol": "TAX", "thesis_id": thesis["id"],
            "event_types": ["earnings"], "keywords": ["TAX"],
            "min_match_score": 1,
        }, self.user_context)
        alert = guarded.execute("event_alert_ingest", {
            "market": "US", "symbol": "TAX", "event": {
                "type": "earnings", "summary": "TAX signed tax provision changed.",
                "sources": [{"id": "after", "sha256": "b" * 64}],
                "observed_metrics": {"gaap_income_tax_provision": {
                    "value": "-53.8", "unit": "USD_million",
                    "fact_id": "TAX-Q3-PROVISION",
                }},
            },
        }, self.user_context)["data"]["results"][0]["alert"]
        original = "The tax provision line moved toward a larger provision."
        result = guarded.execute("thesis_record_review", {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "expected_version": thesis["version"],
            "event": {"summary": "untrusted copy"},
            "impact": "mixed", "decision": "needs_review",
            "rationale": original,
            "evidence": [{"id": "before", "sha256": "a" * 64},
                         {"id": "after", "sha256": "b" * 64}],
        }, self.user_context)
        self.assertTrue(result["ok"], result.get("errors"))
        self.assertEqual("blocked", result["data"]["thesis"]["actionability"])
        self.assertTrue(result["data"]["thesis"]["decision_hold"])
        self.assertEqual("needs_review", result["data"]["review"]["decision"])
        rationale = result["data"]["review"]["rationale"]
        self.assertNotEqual(original, rationale)
        self.assertIn("signed_tax_contribution_reversed", rationale)
        self.assertIn("proposed financial interpretation is not accepted", rationale)

        unknown_catalog = self.root / "unknown-review-guard-catalog.json"
        changed = json.loads(catalog_path.read_text(encoding="utf-8"))
        changed["cases"][0]["event_source_sha256"] = "c" * 64
        unknown_catalog.write_text(json.dumps(changed), encoding="utf-8")
        guarded_unknown = plugin.FinanceToolsPlugin()
        guarded_unknown.initialize({
            "finskillsPath": str(self.root),
            "stateDbPath": str(self.root / "guarded-state.db"),
            "reviewArithmeticGuardCatalogPath": str(unknown_catalog),
        })
        unknown = guarded_unknown.execute("thesis_record_review", {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "expected_version": result["data"]["thesis"]["version"],
            "event": {"summary": "untrusted copy"},
            "impact": "mixed", "decision": "needs_review",
            "rationale": original,
        }, self.user_context)
        self.assertTrue(unknown["ok"], unknown.get("errors"))
        self.assertEqual("blocked", unknown["data"]["thesis"]["actionability"])
        self.assertIn("source_comparison_unavailable",
                      unknown["data"]["review"]["rationale"])

    def test_voluntary_needs_review_blocks_until_new_sourced_evidence(self):
        thesis = self.plugin.execute("thesis_save", {
            "market": "US", "symbol": "AMD", "thesis": "Source-bounded baseline.",
            "status": "active", "conviction": 3,
            "required_event_metrics": ["quarterly_revenue"],
        }, self.user_context)["data"]["thesis"]
        self.plugin.execute("watchlist_save", {
            "market": "US", "symbol": "AMD", "thesis_id": thesis["id"],
            "event_types": ["earnings"], "keywords": ["AMD"],
            "min_match_score": 1,
        }, self.user_context)

        def ingest(external_id, hashes):
            response = self.plugin.execute("event_alert_ingest", {
                "market": "US", "symbol": "AMD", "event": {
                    "external_id": external_id, "type": "earnings",
                    "as_of": "2025-10-30", "summary": "AMD Q3 earnings.",
                    "sources": [
                        {"id": f"source-{index}", "sha256": value}
                        for index, value in enumerate(hashes)
                    ],
                    "observed_metrics": {
                        "quarterly_revenue": {
                            "value": "9000", "unit": "USD_million",
                            "fact_id": "AMD-Q3-REV",
                        }
                    },
                },
            }, self.user_context)
            self.assertTrue(response["ok"], response.get("errors"))
            return response["data"]["results"][0]["alert"]

        original = ingest("amd-q3-initial", ["a" * 64])
        review = {
            "thesis_id": thesis["id"], "alert_id": original["id"],
            "expected_version": thesis["version"],
            "event": {"type": "earnings", "summary": "AMD Q3 earnings.",
                      "as_of": "2025-10-30"},
            "impact": "mixed", "decision": "needs_review",
            "rationale": "Revenue is present, but the investment implication needs more evidence.",
        }
        no_alert = self.plugin.execute("thesis_record_review", {
            **review, "alert_id": None,
        }, self.user_context)
        self.assertEqual("alert_required", no_alert["errors"][0]["code"])
        changed_state = self.plugin.execute("thesis_record_review", {
            **review, "new_conviction": 4,
        }, self.user_context)
        self.assertEqual("decision_on_hold", changed_state["errors"][0]["code"])
        deferred = self.plugin.execute("thesis_record_review", review, self.user_context)
        self.assertTrue(deferred["ok"], deferred.get("errors"))
        held = deferred["data"]["thesis"]
        self.assertTrue(held["decision_hold"])
        self.assertEqual("blocked", held["actionability"])
        self.assertEqual(original["id"], held["decision_hold_alert_id"])

        unchanged = self.plugin.execute("thesis_record_review", {
            **review, "expected_version": held["version"],
            "decision": "maintain",
        }, self.user_context)
        self.assertEqual("decision_on_hold", unchanged["errors"][0]["code"])
        no_new_source = ingest("amd-q3-same-source", ["a" * 64])
        premature = self.plugin.execute("thesis_record_review", {
            **review, "alert_id": no_new_source["id"],
            "expected_version": held["version"], "decision": "maintain",
        }, self.user_context)
        self.assertEqual("decision_hold_alert_mismatch", premature["errors"][0]["code"])
        unrelated = ingest("amd-q3-unrelated-source", ["c" * 64])
        no_continuity = self.plugin.execute("thesis_record_review", {
            **review, "alert_id": unrelated["id"],
            "expected_version": held["version"], "decision": "maintain",
        }, self.user_context)
        self.assertEqual("decision_hold_alert_mismatch", no_continuity["errors"][0]["code"])

        supplemented = ingest("amd-q3-supplemented", ["a" * 64, "b" * 64])
        resolved = self.plugin.execute("thesis_record_review", {
            **review, "alert_id": supplemented["id"],
            "expected_version": held["version"], "decision": "maintain",
            "rationale": "The additional source resolves the deferred question.",
        }, self.user_context)
        self.assertTrue(resolved["ok"], resolved.get("errors"))
        self.assertFalse(resolved["data"]["thesis"]["decision_hold"])
        self.assertEqual("available", resolved["data"]["thesis"]["actionability"])
        self.assertIsNone(resolved["data"]["thesis"]["decision_hold_alert_id"])

    def test_preliminary_thesis_is_not_actionable_without_event_hold(self):
        created = self.plugin.execute("thesis_save", {
            "market": "US", "symbol": "AMD",
            "thesis": "Price movement is observed; fundamentals are not verified.",
            "status": "researching", "conviction": 1,
            "evidence": [{"id": "price-bars", "url": "https://example.com/bars"}],
        }, self.user_context)
        self.assertTrue(created["ok"], created.get("errors"))
        thesis = created["data"]["thesis"]
        self.assertFalse(thesis["decision_hold"])
        self.assertEqual("research_only", thesis["actionability"])
        fetched = self.plugin.execute("thesis_get", {
            "thesis_id": thesis["id"],
        }, self.user_context)
        self.assertEqual("research_only", fetched["data"]["thesis"]["actionability"])
        upgraded = self.plugin.execute("thesis_save", {
            "thesis_id": thesis["id"], "expected_version": thesis["version"],
            "status": "active",
        }, self.user_context)
        self.assertTrue(upgraded["ok"], upgraded.get("errors"))
        self.assertEqual("available", upgraded["data"]["thesis"]["actionability"])
        closed = self.plugin.execute("thesis_save", {
            "thesis_id": thesis["id"],
            "expected_version": upgraded["data"]["thesis"]["version"],
            "status": "invalidated",
        }, self.user_context)
        self.assertTrue(closed["ok"], closed.get("errors"))
        self.assertEqual("closed", closed["data"]["thesis"]["actionability"])

    def test_review_causal_claim_schema_exposes_required_shape_and_strength_enum(self):
        review = next(item for item in plugin.tool_definitions()
                      if item["name"] == "thesis_record_review")
        claim = review["parameters"]["properties"]["causal_claims"]["items"]
        self.assertEqual(
            ["target_metric", "strength", "driver_fact_ids"], claim["required"]
        )
        self.assertEqual(
            sorted(plugin._lineage.CLAIM_STRENGTHS),
            claim["properties"]["strength"]["enum"],
        )
        self.assertIn(
            "unquantified source-explicit link",
            claim["properties"]["strength"]["description"],
        )
        self.assertEqual(
            sorted(plugin._lineage.ALLOWED_DRIVER_LINES),
            claim["properties"]["target_metric"]["enum"],
        )

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        script = (
            self.root
            / "China-market"
            / "findata-toolkit-cn"
            / "scripts"
            / "stock_data.py"
        )
        script.parent.mkdir(parents=True)
        script.write_text(STUB_SCRIPT, encoding="utf-8")
        portfolio_script = (
            self.root / "US-market" / "findata-toolkit" / "scripts" / "portfolio_analytics.py"
        )
        portfolio_script.parent.mkdir(parents=True)
        portfolio_script.write_text(STUB_PORTFOLIO_SCRIPT, encoding="utf-8")
        self.plugin = plugin.FinanceToolsPlugin()
        self.plugin.initialize(
            {
                "finskillsPath": str(self.root),
                "stateDbPath": str(self.root / "finance-state.db"),
                "pythonBin": "python3",
                "timeoutSeconds": 5,
            }
        )
        self.user_context = {
            "userId": "user-1",
            "agentId": "coordinator",
            "sessionId": "session-1",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_source_classified_review_rejects_bad_causal_claim_without_ledger_write(self):
        thesis = self.plugin.execute("thesis_save", {
            "market": "US", "symbol": "TEST",
            "thesis": "Assess reported gross margin after the event.",
            "status": "active", "conviction": 3,
            "required_event_metrics": ["gross_margin"],
        }, self.user_context)["data"]["thesis"]
        watch = self.plugin.execute("watchlist_save", {
            "market": "US", "symbol": "TEST", "thesis_id": thesis["id"],
            "event_types": ["earnings"], "keywords": ["TEST"],
            "min_match_score": 1,
        }, self.user_context)
        self.assertTrue(watch["ok"])
        ingested = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "TEST", "event": {
                "external_id": "classified-q3", "type": "earnings",
                "as_of": "2024-10-31", "summary": "TEST Q3 earnings facts.",
                "sources": [{"id": "sec-q3", "sha256": "a" * 64}],
                "observed_metrics": {
                    "gross_margin": {"value": "15.0", "unit": "percent",
                                     "fact_id": "GM", "statement_line": "unknown"},
                    "manufacturing_charge": {"value": "3100", "unit": "USD_million",
                                             "fact_id": "MFG", "statement_line": "cost_of_sales"},
                    "tax_allowance": {"value": "9900", "unit": "USD_million",
                                      "fact_id": "TAX", "statement_line": "income_tax"},
                },
            },
        }, self.user_context)
        self.assertTrue(ingested["ok"])
        alert = ingested["data"]["results"][0]["alert"]
        self.assertEqual("income_tax", alert["event"]["observed_metrics"]["tax_allowance"]["statement_line"])
        before = self.plugin.execute("thesis_get", {
            "thesis_id": thesis["id"]}, self.user_context)["data"]
        args = {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "expected_version": before["thesis"]["version"],
            "event": {"summary": "Model-supplied summary is not the stored alert."},
            "impact": "negative", "decision": "downgrade",
            "new_conviction": 2,
            "rationale": "The tax allowance directly caused the gross-margin collapse.",
            "evidence": [{"claim": "Tax caused gross-margin collapse"}],
            "matched_terms": ["fabricated model term"],
        }
        missing = self.plugin.execute("thesis_record_review", args, self.user_context)
        self.assertEqual("causal_claims_required", missing["errors"][0]["code"])
        bad = self.plugin.execute("thesis_record_review", {
            **args, "causal_claims": [{"target_metric": "gross_margin",
                                        "strength": "consistent_with",
                                        "driver_fact_ids": ["TAX"]}],
        }, self.user_context)
        self.assertEqual("unsupported_causal_claim", bad["errors"][0]["code"])
        unsupported_target = self.plugin.execute("thesis_record_review", {
            **args, "causal_claims": [{"target_metric": "gross_margin_rate",
                                        "strength": "consistent_with",
                                        "driver_fact_ids": ["MFG"]}],
        }, self.user_context)
        target_error = unsupported_target["errors"][0]
        self.assertEqual("unsupported_causal_claim", target_error["code"])
        self.assertIn("gross_margin", target_error["details"]["allowed_target_metrics"])
        self.assertEqual([], target_error["details"]["no_supported_attribution"]["causal_claims"])
        unchanged = self.plugin.execute("thesis_get", {
            "thesis_id": thesis["id"]}, self.user_context)["data"]
        self.assertEqual(before["thesis"]["version"], unchanged["thesis"]["version"])
        self.assertEqual([], unchanged["reviews"])
        good = self.plugin.execute("thesis_record_review", {
            **args, "causal_claims": [{"target_metric": "gross_margin",
                                        "strength": "consistent_with",
                                        "driver_fact_ids": ["MFG"]}],
        }, self.user_context)
        self.assertTrue(good["ok"], good.get("errors"))
        review = good["data"]["review"]
        self.assertIn("MFG", review["rationale"])
        self.assertNotIn("tax allowance directly caused", review["rationale"])
        self.assertEqual(["validated_accounting_lineage"],
                         [item["type"] for item in review["evidence"]])
        self.assertNotIn("fabricated model term", review["matched_terms"])
        self.assertEqual(2, good["data"]["thesis"]["conviction"])
        no_attribution = self.plugin.execute("thesis_record_review", {
            **args,
            "expected_version": good["data"]["thesis"]["version"],
            "decision": "maintain",
            "new_conviction": 2,
            "causal_claims": [],
        }, self.user_context)
        self.assertTrue(no_attribution["ok"], no_attribution.get("errors"))
        self.assertIn(
            "No source-backed causal attribution was recorded.",
            no_attribution["data"]["review"]["rationale"],
        )

    def test_source_explicit_margin_driver_is_accepted_in_guarded_review(self):
        thesis = self.plugin.execute("thesis_save", {
            "market": "US", "symbol": "SHOP",
            "thesis": "Review the issuer's reported gross margin.",
            "status": "active", "conviction": 3,
            "required_event_metrics": ["gross_margin"],
        }, self.user_context)["data"]["thesis"]
        self.plugin.execute("watchlist_save", {
            "market": "US", "symbol": "SHOP", "thesis_id": thesis["id"],
            "event_types": ["earnings"], "keywords": ["SHOP"],
            "min_match_score": 1,
        }, self.user_context)
        result = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "SHOP", "event": {
                "type": "earnings", "summary": "SHOP quarterly margin release.",
                "sources": [{"id": "sec-shop", "sha256": "b" * 64}],
                "observed_metrics": {
                    "gross_margin": {"value": "43.6", "unit": "percent",
                                     "fact_id": "GM", "statement_line": "unknown"},
                    "discounts": {"value": "higher", "unit": "qualitative",
                                  "fact_id": "DISCOUNT", "statement_line": "contra_revenue",
                                  "source_explicit_targets": ["gross_margin"]},
                },
            },
        }, self.user_context)
        self.assertTrue(result["ok"])
        alert = result["data"]["results"][0]["alert"]
        current = self.plugin.execute("thesis_get", {
            "thesis_id": thesis["id"]}, self.user_context)["data"]["thesis"]
        review = self.plugin.execute("thesis_record_review", {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "expected_version": current["version"],
            "event": {"summary": "Untrusted model copy"},
            "impact": "negative", "decision": "maintain",
            "rationale": "Model free text is not authoritative in guarded mode.",
            "causal_claims": [{"target_metric": "gross_margin",
                               "strength": "directly_stated",
                               "driver_fact_ids": ["DISCOUNT"]}],
        }, self.user_context)
        self.assertTrue(review["ok"], review.get("errors"))
        self.assertIn("explicitly links", review["data"]["review"]["rationale"])
        self.assertEqual(["gross_margin"], alert["event"]["observed_metrics"]["discounts"]["source_explicit_targets"])

    def test_next_review_date_is_operational_not_historical_source_date(self):
        seed = {"market": "US", "symbol": "AMD",
                "thesis": "Historical filing analysis remains preliminary."}
        past = "2024-10-31"
        future = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()
        rejected = self.plugin.execute(
            "thesis_save", {**seed, "next_review_at": past}, self.user_context)
        self.assertEqual("invalid_input", rejected["errors"][0]["code"])
        self.assertIn("historical source dates", rejected["errors"][0]["message"])
        created = self.plugin.execute(
            "thesis_save", {**seed, "next_review_at": future}, self.user_context)
        self.assertTrue(created["ok"])
        thesis = created["data"]["thesis"]
        self.assertEqual(future, thesis["next_review_at"])
        update = self.plugin.execute(
            "thesis_save", {"thesis_id": thesis["id"],
                            "expected_version": thesis["version"],
                            "next_review_at": past}, self.user_context)
        self.assertEqual("invalid_input", update["errors"][0]["code"])
        review = self.plugin.execute(
            "thesis_record_review", {
                "thesis_id": thesis["id"], "expected_version": thesis["version"],
                "event": {"type": "earnings", "summary": "Historical AMD filing.",
                          "as_of": past},
                "impact": "neutral", "decision": "maintain",
                "rationale": "The filing date is historical, not a future review schedule.",
                "next_review_at": past,
            }, self.user_context)
        self.assertEqual("invalid_input", review["errors"][0]["code"])
        unchanged = self.plugin.execute(
            "thesis_get", {"thesis_id": thesis["id"]}, self.user_context)
        self.assertEqual(1, unchanged["data"]["thesis"]["version"])
        self.assertEqual([], unchanged["data"]["reviews"])

    def test_tool_list_exposes_typed_finance_tools(self):
        response = plugin.rpc_response(
            self.plugin,
            {"jsonrpc": "2.0", "method": "tool.list", "id": 1},
        )
        names = {item["name"] for item in response["result"]["tools"]}
        self.assertIn("stock_snapshot", names)
        self.assertIn("screen_stocks", names)
        self.assertIn("serenity_scorecard", names)
        self.assertIn("watchlist_save", names)
        self.assertIn("event_alert_ingest", names)
        self.assertIn("alert_update", names)

    def test_stock_snapshot_uses_expected_script_arguments_and_cache(self):
        args = {"market": "CN", "symbols": ["600519"], "view": "metrics"}
        first = self.plugin.stock_snapshot(args)
        second = self.plugin.stock_snapshot(args)
        self.assertTrue(first["ok"])
        self.assertEqual(["600519", "--metrics"], first["data"]["argv"])
        self.assertFalse(first["cache"]["hit"])
        self.assertTrue(second["cache"]["hit"])
        self.assertNotEqual(first["request_id"], second["request_id"])

    def test_screen_rejects_missing_required_metrics(self):
        result = self.plugin.screen_stocks(
            {
                "market": "CN",
                "symbols": ["600519", "000858"],
                "require_complete": True,
            }
        )
        self.assertTrue(result["ok"])
        self.assertEqual(1, result["data"]["passed"])
        self.assertEqual("COMPLETE", result["data"]["results"][0]["symbol"])
        self.assertEqual(
            "insufficient_data",
            result["data"]["rejected"][0]["reason"],
        )
        self.assertIn(
            "incomplete_screen_candidates_rejected",
            result["quality"]["flags"],
        )

    def test_portfolio_risk_rejects_partial_percent_weights_before_running_script(self):
        rejected = self.plugin.execute("portfolio_risk", {
            "holdings": {"FICA": 45, "FICB": 30}, "view": "concentration",
        })
        self.assertFalse(rejected["ok"])
        self.assertEqual("portfolio_incomplete", rejected["errors"][0]["code"])
        self.assertEqual(75, rejected["errors"][0]["details"]["weight_total"])

        explicitly_partial = self.plugin.execute("portfolio_risk", {
            "holdings": {"FICA": 50, "FICB": 50},
            "holdings_complete": False, "view": "concentration",
        })
        self.assertFalse(explicitly_partial["ok"])
        self.assertEqual("portfolio_incomplete", explicitly_partial["errors"][0]["code"])

    def test_portfolio_risk_accepts_complete_percent_and_explicit_relative_weights(self):
        at_limit = self.plugin.execute("portfolio_risk", {
            "holdings": {"FICA": 50, "FICB": 30, "FICC": 20},
            "view": "concentration",
        })
        self.assertTrue(at_limit["ok"])
        self.assertIn("FICA:50,FICB:30,FICC:20", at_limit["data"]["argv"])

        implicit_relative = self.plugin.execute("portfolio_risk", {
            "holdings": {"FICA": 4, "FICB": 3},
            "weight_unit": "relative", "view": "concentration",
        })
        self.assertFalse(implicit_relative["ok"])
        self.assertEqual("portfolio_incomplete", implicit_relative["errors"][0]["code"])

        relative = self.plugin.execute("portfolio_risk", {
            "holdings": {"FICA": 4, "FICB": 3},
            "weight_unit": "relative", "holdings_complete": True,
            "view": "concentration",
        })
        self.assertTrue(relative["ok"])
        self.assertIn("FICA:4,FICB:3", relative["data"]["argv"])

    def test_evaluation_fixture_source_is_not_mislabeled_as_market_data(self):
        self.plugin.initialize({
            "finskillsPath": str(self.root),
            "stateDbPath": str(self.root / "finance-state.db"),
            "evaluationFixture": True,
        })
        result = self.plugin.screen_stocks({
            "market": "CN", "symbols": ["600519", "000858"],
        })
        self.assertTrue(result["ok"])
        self.assertEqual("local_evaluation_fixture", result["sources"][0]["name"])

    def test_online_us_macro_source_is_fred(self):
        self.assertEqual("FRED", self.plugin._market_sources("US", "macro")[0]["name"])
        self.assertEqual("yfinance", self.plugin._market_sources("US", "stock_data")[0]["name"])
        self.assertEqual("AKShare", self.plugin._market_sources("CN", "macro")[0]["name"])

    def test_invalid_symbol_never_reaches_subprocess(self):
        result = self.plugin.execute(
            "stock_snapshot",
            {"market": "CN", "symbols": ["--help"], "view": "metrics"},
        )
        self.assertFalse(result["ok"])
        self.assertEqual("invalid_input", result["errors"][0]["code"])

    def test_rpc_tool_result_is_json_string(self):
        response = plugin.rpc_response(
            self.plugin,
            {
                "jsonrpc": "2.0",
                "method": "tool.execute",
                "params": {
                    "name": "stock_snapshot",
                    "args": {
                        "market": "CN",
                        "symbols": ["600519"],
                        "view": "metrics",
                    },
                },
                "id": 2,
            },
        )
        result = json.loads(response["result"]["result"])
        self.assertEqual(plugin.SCHEMA_VERSION, result["schema_version"])

    def test_stateful_tools_require_trusted_tenant_context(self):
        result = self.plugin.execute("thesis_list", {})
        self.assertFalse(result["ok"])
        self.assertEqual("missing_tenant_context", result["errors"][0]["code"])

    def test_thesis_ledger_is_user_isolated_and_versioned(self):
        created = self.plugin.execute(
            "thesis_save",
            {
                "market": "CN",
                "symbol": "600519",
                "thesis": "渠道韧性和品牌定价权支持长期现金流。",
                "status": "active",
                "conviction": 3,
                "assumptions": ["高端需求保持稳定"],
                "catalysts": ["渠道库存下降"],
                "invalidations": ["应收账款异常上升"],
            },
            self.user_context,
        )
        self.assertTrue(created["ok"])
        thesis = created["data"]["thesis"]
        self.assertEqual(1, thesis["version"])

        other_user = self.plugin.execute(
            "thesis_list",
            {"symbol": "600519"},
            {
                "userId": "user-2",
                "agentId": "coordinator",
                "sessionId": "session-2",
            },
        )
        self.assertEqual(0, other_user["data"]["count"])

        conflict = self.plugin.execute(
            "thesis_save",
            {
                "thesis_id": thesis["id"],
                "expected_version": 99,
                "conviction": 4,
            },
            self.user_context,
        )
        self.assertFalse(conflict["ok"])
        self.assertEqual("version_conflict", conflict["errors"][0]["code"])
        self.assertEqual(1, conflict["errors"][0]["details"]["actual_version"])

    def test_event_match_and_review_are_persisted(self):
        created = self.plugin.execute(
            "thesis_save",
            {
                "market": "CN",
                "symbol": "688981",
                "thesis": "先进制程扩产依赖客户验证与设备交付。",
                "status": "watch",
                "conviction": 2,
                "assumptions": ["设备交付按期"],
                "catalysts": ["客户认证通过"],
                "invalidations": ["扩产失败"],
            },
            self.user_context,
        )
        thesis = created["data"]["thesis"]
        matched = self.plugin.execute(
            "thesis_match_event",
            {
                "market": "CN",
                "symbol": "688981",
                "event_summary": "公司公告关键客户认证通过，设备交付按期推进。",
            },
            self.user_context,
        )
        self.assertTrue(matched["ok"])
        self.assertGreater(matched["data"]["matches"][0]["match_score"], 0)

        reviewed = self.plugin.execute(
            "thesis_record_review",
            {
                "thesis_id": thesis["id"],
                "expected_version": thesis["version"],
                "event": {
                    "type": "announcement",
                    "summary": "关键客户认证通过。",
                    "as_of": "2026-07-30T12:00:00Z",
                    "sources": [{"name": "exchange_announcement"}],
                },
                "impact": "positive",
                "decision": "upgrade",
                "rationale": "核心催化剂得到一手公告确认。",
                "matched_terms": ["客户认证通过"],
                "evidence": [{"strength": "strong", "claim": "认证通过"}],
                "new_status": "active",
                "new_conviction": 4,
            },
            self.user_context,
        )
        self.assertTrue(reviewed["ok"])
        self.assertEqual(2, reviewed["data"]["thesis"]["version"])
        self.assertEqual("active", reviewed["data"]["thesis"]["status"])
        self.assertEqual(4, reviewed["data"]["thesis"]["conviction"])

        fetched = self.plugin.execute(
            "thesis_get",
            {"thesis_id": thesis["id"]},
            {
                "userId": "user-1",
                "agentId": "risk-reviewer",
                "sessionId": "session-3",
            },
        )
        self.assertEqual(1, len(fetched["data"]["reviews"]))
        self.assertEqual("coordinator", fetched["data"]["reviews"][0]["agent_id"])

    def test_watchlist_alerts_are_deduplicated_and_user_isolated(self):
        created = self.plugin.execute(
            "thesis_save",
            {
                "market": "CN",
                "symbol": "688981",
                "thesis": "先进制程扩产依赖客户验证与设备交付。",
                "status": "watch",
                "conviction": 2,
                "assumptions": ["设备交付按期"],
                "catalysts": ["客户认证通过"],
                "invalidations": ["扩产失败"],
            },
            self.user_context,
        )
        thesis = created["data"]["thesis"]
        saved = self.plugin.execute(
            "watchlist_save",
            {
                "market": "CN",
                "symbol": "688981",
                "thesis_id": thesis["id"],
                "event_types": ["announcement"],
                "keywords": ["客户认证"],
                "min_match_score": 2,
                "dedupe_window_seconds": 3600,
            },
            self.user_context,
        )
        self.assertTrue(saved["ok"])
        watchlist = saved["data"]["watchlist"]

        event_args = {
            "market": "CN",
            "symbol": "688981",
            "event": {
                "external_id": "SSE-688981-20260731-01",
                "type": "announcement",
                "summary": "公司公告关键客户认证通过，设备交付按期推进。",
                "as_of": "2026-07-31T08:00:00Z",
                "sources": [{"name": "exchange_announcement"}],
            },
        }
        first = self.plugin.execute(
            "event_alert_ingest", event_args, self.user_context
        )
        second = self.plugin.execute(
            "event_alert_ingest", event_args, self.user_context
        )
        self.assertEqual(1, first["data"]["created"])
        self.assertEqual(0, first["data"]["deduplicated"])
        self.assertEqual(0, second["data"]["created"])
        self.assertEqual(1, second["data"]["deduplicated"])
        alert = second["data"]["results"][0]["alert"]
        self.assertEqual(2, alert["duplicate_count"])
        self.assertEqual(2, alert["version"])

        conflict = self.plugin.execute(
            "alert_update",
            {
                "alert_id": alert["id"],
                "status": "acknowledged",
                "expected_version": 1,
            },
            self.user_context,
        )
        self.assertFalse(conflict["ok"])
        self.assertEqual("version_conflict", conflict["errors"][0]["code"])
        acknowledged = self.plugin.execute(
            "alert_update",
            {
                "alert_id": alert["id"],
                "status": "acknowledged",
                "expected_version": alert["version"],
            },
            self.user_context,
        )
        self.assertEqual(
            "acknowledged", acknowledged["data"]["alert"]["status"]
        )

        owner_alerts = self.plugin.execute(
            "alert_list", {"watchlist_id": watchlist["id"]}, self.user_context
        )
        other_alerts = self.plugin.execute(
            "alert_list",
            {},
            {
                "userId": "user-2",
                "agentId": "coordinator",
                "sessionId": "session-2",
            },
        )
        self.assertEqual(1, owner_alerts["data"]["count"])
        self.assertEqual(0, other_alerts["data"]["count"])

        paused = self.plugin.execute(
            "watchlist_save",
            {"watchlist_id": watchlist["id"], "status": "paused"},
            self.user_context,
        )
        self.assertTrue(paused["ok"])
        self.assertEqual("paused", paused["data"]["watchlist"]["status"])

    def test_watchlist_filters_events_and_rejects_mismatched_thesis(self):
        thesis = self.plugin.execute(
            "thesis_save",
            {
                "market": "CN",
                "symbol": "600519",
                "thesis": "渠道库存下降将改善经销商现金流和价格稳定性。",
            },
            self.user_context,
        )["data"]["thesis"]
        mismatch = self.plugin.execute(
            "watchlist_save",
            {
                "market": "CN",
                "symbol": "000858",
                "thesis_id": thesis["id"],
            },
            self.user_context,
        )
        self.assertFalse(mismatch["ok"])
        self.assertEqual(
            "thesis_watch_mismatch", mismatch["errors"][0]["code"]
        )

        saved = self.plugin.execute(
            "watchlist_save",
            {
                "market": "CN",
                "symbol": "000858",
                "event_types": ["earnings"],
                "keywords": ["库存下降"],
                "min_match_score": 2,
            },
            self.user_context,
        )
        self.assertTrue(saved["ok"])
        filtered = self.plugin.execute(
            "event_alert_ingest",
            {
                "market": "CN",
                "symbol": "000858",
                "event": {
                    "type": "announcement",
                    "summary": "公司公告渠道库存下降。",
                },
            },
            self.user_context,
        )
        below_threshold = self.plugin.execute(
            "event_alert_ingest",
            {
                "market": "CN",
                "symbol": "000858",
                "event": {
                    "type": "earnings",
                    "summary": "财报显示渠道库存下降。",
                },
            },
            self.user_context,
        )
        self.assertEqual(
            "event_type_filtered", filtered["data"]["skipped"][0]["reason"]
        )
        self.assertEqual(
            "below_match_threshold",
            below_threshold["data"]["skipped"][0]["reason"],
        )
        self.assertEqual(0, below_threshold["data"]["created"])

    def test_missing_required_metric_cannot_be_hidden_by_review_arguments(self):
        thesis = self.plugin.execute("thesis_save", {
            "market": "US", "symbol": "NVDA",
            "thesis": "Growth requires a current filing's revenue and GAAP margin evidence.",
            "status": "active", "conviction": 3,
            "required_event_metrics": ["quarterly_revenue", "gross_margin"],
        }, self.user_context)["data"]["thesis"]
        self.plugin.execute("watchlist_save", {
            "market": "US", "symbol": "NVDA", "thesis_id": thesis["id"],
            "event_types": ["earnings"], "keywords": ["NVDA"],
            "min_match_score": 1,
        }, self.user_context)
        ingested = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "NVDA", "event": {
                "external_id": "nvda-q2", "type": "earnings",
                "as_of": "2024-08-28",
                "summary": "NVDA Q2 revenue increased; margin was withheld from this packet.",
                "sources": [{"id": "sec-q2", "sha256": "a" * 64}],
                "observed_metrics": {
                    "quarterly_revenue": {
                        "value": "30040", "unit": "USD_million", "fact_id": "NVDA-Q2-REV"
                    }
                },
            },
        }, self.user_context)
        self.assertTrue(ingested["ok"])
        alert = ingested["data"]["results"][0]["alert"]
        self.assertEqual(["quarterly_revenue"], list(alert["event"]["observed_metrics"]))
        held_after_ingest = self.plugin.execute(
            "thesis_get", {"thesis_id": thesis["id"]}, self.user_context
        )["data"]["thesis"]
        self.assertEqual(2, held_after_ingest["version"])
        self.assertEqual("blocked", held_after_ingest["actionability"])
        review_args = {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "expected_version": held_after_ingest["version"],
            "event": {
                "summary": "Model-supplied claim that margin is present",
                "observed_metrics": {"gross_margin": {"value": "75.1", "unit": "percent"}},
            },
            "impact": "mixed", "decision": "maintain",
            "rationale": "Revenue rose but the required margin is not in the packet.",
        }
        rejected = self.plugin.execute("thesis_record_review", review_args, self.user_context)
        self.assertFalse(rejected["ok"])
        self.assertEqual("decision_on_hold", rejected["errors"][0]["code"])
        self.assertEqual(alert["id"], rejected["errors"][0]["details"]["alert_id"])
        unchanged = self.plugin.execute("thesis_get", {"thesis_id": thesis["id"]}, self.user_context)["data"]
        self.assertEqual(2, unchanged["thesis"]["version"])
        self.assertEqual([], unchanged["reviews"])

        no_alert = self.plugin.execute("thesis_record_review", {
            **review_args, "decision": "needs_review", "alert_id": None,
        }, self.user_context)
        self.assertEqual("alert_required", no_alert["errors"][0]["code"])
        changed_state = self.plugin.execute("thesis_record_review", {
            **review_args, "decision": "needs_review", "new_conviction": 4,
        }, self.user_context)
        self.assertEqual("decision_on_hold", changed_state["errors"][0]["code"])

        reviewed = self.plugin.execute("thesis_record_review", {
            **review_args, "decision": "needs_review", "new_status": "active",
            "new_conviction": 3,
        }, self.user_context)
        self.assertTrue(reviewed["ok"])
        self.assertEqual("needs_review", reviewed["data"]["review"]["decision"])
        self.assertEqual(["gross_margin"], reviewed["data"]["review"]["missing_metrics"])
        self.assertEqual(alert["id"], reviewed["data"]["review"]["alert_id"])
        self.assertEqual(alert["event"]["summary"], reviewed["data"]["review"]["event"]["summary"])
        self.assertEqual(3, reviewed["data"]["thesis"]["version"])
        self.assertEqual(3, reviewed["data"]["thesis"]["conviction"])
        self.assertTrue(reviewed["data"]["thesis"]["decision_hold"])
        self.assertEqual("blocked", reviewed["data"]["thesis"]["actionability"])
        self.assertEqual(alert["id"], reviewed["data"]["thesis"]["decision_hold_alert_id"])
        forbidden = self.plugin.execute("thesis_save", {
            "thesis_id": thesis["id"], "new_conviction": 4, "conviction": 4,
        }, self.user_context)
        self.assertEqual("decision_on_hold", forbidden["errors"][0]["code"])
        remove_requirement = self.plugin.execute("thesis_save", {
            "thesis_id": thesis["id"], "required_event_metrics": ["quarterly_revenue"],
        }, self.user_context)
        self.assertEqual("decision_on_hold", remove_requirement["errors"][0]["code"])

        wrong_period = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "NVDA", "event": {
                "external_id": "nvda-q3-complete", "type": "earnings",
                "as_of": "2024-11-20", "summary": "NVDA later quarter has full metrics.",
                "sources": [{"id": "sec-q3", "sha256": "b" * 64}],
                "observed_metrics": {
                    "quarterly_revenue": {
                        "value": "35000", "unit": "USD_million", "fact_id": "NVDA-Q3-REV"
                    },
                    "gross_margin": {
                        "value": "74.0", "unit": "percent", "fact_id": "NVDA-Q3-GM"
                    },
                },
            },
        }, self.user_context)["data"]["results"][0]["alert"]
        wrong_review = self.plugin.execute("thesis_record_review", {
            **review_args, "alert_id": wrong_period["id"],
            "expected_version": 3, "decision": "maintain",
        }, self.user_context)
        self.assertEqual("decision_hold_alert_mismatch", wrong_review["errors"][0]["code"])

        no_source = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "NVDA", "event": {
                "external_id": "nvda-q2-unsourced", "type": "earnings",
                "as_of": "2024-08-28", "summary": "NVDA same Q2 metrics without a source.",
                "observed_metrics": {
                    "quarterly_revenue": {
                        "value": "30040", "unit": "USD_million", "fact_id": "NVDA-Q2-REV"
                    },
                    "gross_margin": {
                        "value": "75.1", "unit": "percent", "fact_id": "NVDA-Q2-GM"
                    },
                },
            },
        }, self.user_context)
        self.assertFalse(no_source["ok"])

        wrong_source = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "NVDA", "event": {
                "external_id": "nvda-q2-other-source", "type": "earnings",
                "as_of": "2024-08-28", "summary": "NVDA same Q2 from another source.",
                "sources": [{"id": "other", "sha256": "c" * 64}],
                "observed_metrics": {
                    "quarterly_revenue": {
                        "value": "30040", "unit": "USD_million", "fact_id": "NVDA-Q2-REV"
                    },
                    "gross_margin": {
                        "value": "75.1", "unit": "percent", "fact_id": "NVDA-Q2-GM"
                    },
                },
            },
        }, self.user_context)["data"]["results"][0]["alert"]
        unlinked_review = self.plugin.execute("thesis_record_review", {
            **review_args, "alert_id": wrong_source["id"],
            "expected_version": 3, "decision": "maintain",
        }, self.user_context)
        self.assertEqual("decision_hold_alert_mismatch", unlinked_review["errors"][0]["code"])

        complete = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "NVDA", "event": {
                "external_id": "nvda-q2-complete", "type": "earnings",
                "as_of": "2024-08-28", "summary": "NVDA same Q2 report, complete metrics.",
                "sources": [{"id": "sec-q2-complete", "sha256": "a" * 64}],
                "observed_metrics": {
                    "quarterly_revenue": {
                        "value": "30040", "unit": "USD_million", "fact_id": "NVDA-Q2-REV"
                    },
                    "gross_margin": {
                        "value": "75.1", "unit": "percent", "fact_id": "NVDA-Q2-GM"
                    },
                },
            },
        }, self.user_context)["data"]["results"][0]["alert"]
        resolved = self.plugin.execute("thesis_record_review", {
            **review_args, "alert_id": complete["id"],
            "expected_version": 3, "decision": "maintain",
        }, self.user_context)
        self.assertTrue(resolved["ok"], resolved.get("errors"))
        self.assertFalse(resolved["data"]["thesis"]["decision_hold"])
        self.assertEqual("available", resolved["data"]["thesis"]["actionability"])
        self.assertIsNone(resolved["data"]["thesis"]["decision_hold_alert_id"])

    def test_complete_required_metrics_allow_substantive_decision(self):
        thesis = self.plugin.execute("thesis_save", {
            "market": "US", "symbol": "AMD",
            "thesis": "Growth depends on revenue and GAAP margin observations.",
            "status": "active", "conviction": 3,
            "required_event_metrics": ["quarterly_revenue", "gross_margin"],
        }, self.user_context)["data"]["thesis"]
        self.plugin.execute("watchlist_save", {
            "market": "US", "symbol": "AMD", "thesis_id": thesis["id"],
            "event_types": ["earnings"], "keywords": ["AMD"], "min_match_score": 1,
        }, self.user_context)
        alert = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "AMD", "event": {
                "type": "earnings", "summary": "AMD revenue and gross margin improved.",
                "sources": [{"id": "sec-amd", "sha256": "b" * 64}],
                "observed_metrics": {
                    "quarterly_revenue": {"value": 6819, "unit": "USD_million", "fact_id": "AMD-Q3-REV"},
                    "gross_margin": {"value": 50, "unit": "percent", "fact_id": "AMD-Q3-GM"},
                },
            },
        }, self.user_context)["data"]["results"][0]["alert"]
        result = self.plugin.execute("thesis_record_review", {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "expected_version": 1, "event": {"summary": "untrusted model copy"},
            "impact": "positive", "decision": "upgrade",
            "rationale": "Both required metrics were observed and improved.",
            "new_conviction": 4,
        }, self.user_context)
        self.assertTrue(result["ok"])
        self.assertEqual([], result["data"]["review"]["missing_metrics"])
        self.assertEqual(4, result["data"]["thesis"]["conviction"])
        with sqlite3.connect(self.root / "finance-state.db") as database:
            self.assertEqual(4, database.execute("PRAGMA user_version").fetchone()[0])

    def test_review_payload_guard_rejects_embedded_fields_and_accepts_empty_claims(self):
        thesis = self.plugin.execute("thesis_save", {
            "market": "US", "symbol": "TEST", "thesis": "Review the next earnings event.",
            "status": "active", "conviction": 3,
            "required_event_metrics": ["revenue"],
        }, self.user_context)["data"]["thesis"]
        self.plugin.execute("watchlist_save", {
            "market": "US", "symbol": "TEST", "thesis_id": thesis["id"],
            "event_types": ["earnings"], "keywords": ["TEST"],
            "min_match_score": 1,
        }, self.user_context)
        alert = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "TEST", "event": {
                "type": "earnings", "summary": "TEST revenue was 100 in the event period.",
                "sources": [{"id": "source-event", "sha256": "a" * 64}],
                "observed_metrics": {
                    "revenue": {"value": "100", "unit": "USD_million",
                                "fact_id": "TEST-Q3-REVENUE"},
            }},
        }, self.user_context)["data"]["results"][0]["alert"]
        base_args = {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "expected_version": thesis["version"],
            "event": {"summary": "TEST revenue was 100 in the event period."},
            "impact": "mixed", "decision": "needs_review",
            "rationale": "The source is selected evidence and needs follow-up.",
        }
        malformed = self.plugin.execute("thesis_record_review", {
            **base_args,
            "rationale": 'The source needs follow-up.", "evidence": [{"id":"source-event"}]',
        }, self.user_context)
        self.assertEqual("malformed_review_payload", malformed["errors"][0]["code"])
        self.assertTrue(malformed["errors"][0]["retriable"])
        self.assertEqual([], self.plugin.execute(
            "thesis_get", {"thesis_id": thesis["id"]}, self.user_context
        )["data"]["reviews"])

        nonempty = self.plugin.execute("thesis_record_review", {
            **base_args, "causal_claims": [{"target_metric": "gross_margin",
                                           "strength": "consistent_with",
                                           "driver_fact_ids": ["TEST-Q3-REVENUE"]}],
        }, self.user_context)
        self.assertEqual("accounting_lineage_metadata_missing",
                         nonempty["errors"][0]["code"])

        accepted = self.plugin.execute("thesis_record_review", {
            **base_args, "causal_claims": [],
            "evidence": [{"id": "source-event", "sha256": "a" * 64}],
        }, self.user_context)
        self.assertTrue(accepted["ok"], accepted.get("errors"))
        self.assertEqual("blocked", accepted["data"]["thesis"]["actionability"])
        self.assertEqual("source-event", accepted["data"]["review"]["evidence"][0]["id"])

    def test_missing_all_required_evidence_blocks_unsourced_summary(self):
        thesis = self.plugin.execute("thesis_save", {
            "market": "US", "symbol": "FICE", "thesis": "Verify the capex plan.",
            "status": "active", "conviction": 3,
            "required_event_metrics": ["capex_plan"],
        }, self.user_context)["data"]["thesis"]
        self.plugin.execute("watchlist_save", {
            "market": "US", "symbol": "FICE", "thesis_id": thesis["id"],
            "event_types": ["management_update"], "keywords": ["FICE"],
            "min_match_score": 1,
        }, self.user_context)
        alert = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "FICE", "event": {
                "type": "management_update",
                "summary": "FICE capex plan is claimed in an unsourced summary.",
                "sources": [], "observed_metrics": {},
            },
        }, self.user_context)["data"]["results"][0]["alert"]
        held = self.plugin.execute(
            "thesis_get", {"thesis_id": thesis["id"]}, self.user_context
        )["data"]["thesis"]
        self.assertEqual("blocked", held["actionability"])
        self.assertEqual(alert["id"], held["decision_hold_alert_id"])
        review = self.plugin.execute("thesis_record_review", {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "expected_version": held["version"],
            "event": {"type": "management_update", "summary": "untrusted model text"},
            "impact": "neutral", "decision": "needs_review",
            "rationale": "The required capex plan is absent.",
        }, self.user_context)
        self.assertTrue(review["ok"], review.get("errors"))
        self.assertEqual(["capex_plan"], review["data"]["review"]["missing_metrics"])
        self.assertEqual("blocked", review["data"]["thesis"]["actionability"])

    def test_independent_source_conflict_holds_decision_without_changing_conclusion(self):
        thesis = self.plugin.execute("thesis_save", {
            "market": "US", "symbol": "FICE", "thesis": "Capacity plan is under review.",
            "status": "active", "conviction": 3,
        }, self.user_context)["data"]["thesis"]
        self.plugin.execute("watchlist_save", {
            "market": "US", "symbol": "FICE", "thesis_id": thesis["id"],
            "event_types": ["management_update"], "keywords": ["FICE"],
            "min_match_score": 1,
        }, self.user_context)
        claims = [
            {"metric": "capex_plan", "period": "FY2025", "value": value,
             "unit": "USD_million", "fact_id": fact_id, "source_sha256": digest}
            for value, fact_id, digest in [(8000, "A", "a" * 64), (5000, "B", "b" * 64)]
        ]
        event = {
            "type": "management_update", "summary": "FICE FY2025 plan has two claims.",
            "sources": [{"sha256": "a" * 64}, {"sha256": "b" * 64}],
            "source_claims": claims,
        }
        ingested = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "FICE", "event": event,
        }, self.user_context)
        self.assertTrue(ingested["ok"], ingested.get("errors"))
        alert = ingested["data"]["results"][0]["alert"]
        self.assertEqual("capex_plan", alert["event"]["unresolved_conflicts"][0]["metric"])
        held = self.plugin.execute("thesis_get", {"thesis_id": thesis["id"]}, self.user_context)["data"]["thesis"]
        self.assertTrue(held["decision_hold"])
        self.assertEqual("blocked", held["actionability"])
        review = {
            "thesis_id": thesis["id"], "alert_id": alert["id"], "event": {"summary": "ignore conflict"},
            "impact": "mixed", "decision": "invalidate", "rationale": "Two incompatible claims.",
            "new_status": "invalidated", "new_conviction": 1,
        }
        rejected = self.plugin.execute("thesis_record_review", review, self.user_context)
        self.assertEqual("decision_on_hold", rejected["errors"][0]["code"])
        unlinked = self.plugin.execute("thesis_record_review", {
            **review, "alert_id": None, "decision": "needs_review",
            "new_status": "active", "new_conviction": 3,
        }, self.user_context)
        self.assertEqual("alert_required", unlinked["errors"][0]["code"])
        accepted = self.plugin.execute("thesis_record_review", {
            **review, "decision": "needs_review", "new_status": "active", "new_conviction": 3,
        }, self.user_context)
        self.assertTrue(accepted["ok"], accepted.get("errors"))
        self.assertEqual("active", accepted["data"]["thesis"]["status"])
        self.assertEqual(3, accepted["data"]["thesis"]["conviction"])
        self.assertTrue(accepted["data"]["thesis"]["decision_hold"])
        self.assertEqual("blocked", accepted["data"]["thesis"]["actionability"])
        self.assertEqual(alert["id"], accepted["data"]["thesis"]["decision_hold_alert_id"])
        self.assertEqual(1, len(accepted["data"]["review"]["unresolved_conflicts"]))
        save = self.plugin.execute("thesis_save", {
            "thesis_id": thesis["id"], "status": "invalidated",
        }, self.user_context)
        self.assertEqual("decision_on_hold", save["errors"][0]["code"])

    def test_source_claims_must_reference_declared_hashes(self):
        invalid = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "FICE", "event": {
                "summary": "FICE conflicting claim packet.",
                "sources": [{"sha256": "a" * 64}],
                "source_claims": [{"metric": "capex_plan", "period": "FY2025",
                                   "value": 8000, "unit": "USD_million", "fact_id": "A",
                                   "source_sha256": "b" * 64}],
            },
        }, self.user_context)
        self.assertFalse(invalid["ok"])
        self.assertIn("source_sha256", invalid["errors"][0]["message"])

    def test_same_source_incompatible_statement_rows_hold_research_decision(self):
        digest = "d" * 64
        thesis = self.plugin.execute("thesis_save", {
            "market": "US", "symbol": "BILL",
            "thesis": "Quarterly earnings and operating risk require review.",
            "status": "active", "conviction": 3,
        }, self.user_context)["data"]["thesis"]
        watch = self.plugin.execute("watchlist_save", {
            "market": "US", "symbol": "BILL", "thesis_id": thesis["id"],
            "event_types": ["earnings"], "keywords": ["BILL"],
            "min_match_score": 1,
        }, self.user_context)
        self.assertTrue(watch["ok"], watch.get("errors"))
        claims = [
            {"metric": "gaap_net_income", "period": "2025-06-30",
             "value": value, "unit": "USD_thousand", "fact_id": fact_id,
             "source_sha256": digest}
            for value, fact_id in [(-7074, "operations-row"),
                                   (-7072, "cash-flow-row")]
        ]
        ingested = self.plugin.execute("event_alert_ingest", {
            "market": "US", "symbol": "BILL", "event": {
                "type": "earnings", "summary": "BILL quarterly net income differs within one release.",
                "as_of": "2025-06-30", "sources": [{"sha256": digest}],
                "source_claims": claims,
            },
        }, self.user_context)
        self.assertTrue(ingested["ok"], ingested.get("errors"))
        alert = ingested["data"]["results"][0]["alert"]
        conflicts = alert["event"]["unresolved_conflicts"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["metric"], "gaap_net_income")
        self.assertEqual({item["source_sha256"] for item in conflicts[0]["claims"]},
                         {digest})
        state = self.plugin.execute("thesis_get", {
            "thesis_id": thesis["id"],
        }, self.user_context)["data"]["thesis"]
        self.assertTrue(state["decision_hold"])
        self.assertEqual(state["actionability"], "blocked")
        review = {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "event": {"summary": "Untrusted model text"},
            "impact": "mixed", "decision": "upgrade",
            "rationale": "The conflict must not be ignored.",
            "new_conviction": 4,
        }
        rejected = self.plugin.execute("thesis_record_review", review,
                                       self.user_context)
        self.assertFalse(rejected["ok"])
        accepted = self.plugin.execute("thesis_record_review", {
            **review, "decision": "needs_review", "new_conviction": 3,
        }, self.user_context)
        self.assertTrue(accepted["ok"], accepted.get("errors"))
        self.assertEqual(accepted["data"]["thesis"]["actionability"], "blocked")

    def test_equal_same_source_claims_do_not_create_false_conflict(self):
        claims = [{"metric": "gaap_net_income", "period": "2025-06-30",
                   "value": value, "unit": "USD_thousand", "fact_id": fact_id,
                   "source_sha256": "d" * 64}
                  for value, fact_id in [(-7074, "row-a"), (-7074, "row-b")]]
        self.assertEqual(self.plugin._conflicting_claims(claims), [])


if __name__ == "__main__":
    unittest.main()
