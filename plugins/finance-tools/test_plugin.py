import json
import tempfile
import unittest
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


class FinanceToolsPluginTest(unittest.TestCase):
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

    def test_tool_list_exposes_typed_finance_tools(self):
        response = plugin.rpc_response(
            self.plugin,
            {"jsonrpc": "2.0", "method": "tool.list", "id": 1},
        )
        names = {item["name"] for item in response["result"]["tools"]}
        self.assertIn("stock_snapshot", names)
        self.assertIn("screen_stocks", names)
        self.assertIn("serenity_scorecard", names)

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


if __name__ == "__main__":
    unittest.main()
