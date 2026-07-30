# Finance Tools Plugin

`finance-tools` is the deterministic data and calculation layer for FastClaw
financial research agents. It wraps Finskills scripts behind typed tools and a
stable response envelope instead of asking the model to construct shell
commands.

Serenity Skill is used only as a research methodology and scorecard. It does
not fetch evidence, predict returns, execute trades, or replace portfolio risk
checks.

## Tools

- `finance-tools.toolkit_status`
- `finance-tools.stock_snapshot`
- `finance-tools.screen_stocks`
- `finance-tools.market_events`
- `finance-tools.macro_snapshot`
- `finance-tools.portfolio_risk`
- `finance-tools.serenity_scorecard`
- `finance-tools.thesis_save`
- `finance-tools.thesis_get`
- `finance-tools.thesis_list`
- `finance-tools.thesis_match_event`
- `finance-tools.thesis_record_review`

All tools return `finance.tool.v1` JSON with source, freshness, completeness,
structured errors, and cache metadata. Screening defaults to rejecting
candidates that are missing any metric used by the underlying filter.

Thesis tools use trusted `userId`, `agentId`, and `sessionId` values injected
by FastClaw at tool execution time. The model cannot supply or override this
scope. Records are shared by agents owned by the same user, isolated from other
users, and retain creating/reviewing agent and session identifiers for audit.
Updates support `expected_version` to prevent silent lost writes.

## Configuration

```json
{
  "plugins": {
    "enabled": true,
    "paths": ["/path/to/fastclaw/plugins"],
    "entries": {
      "finance-tools": {
        "enabled": true,
        "config": {
          "finskillsPath": "/Users/example/finskills",
          "serenitySkillPath": "/Users/example/.fastclaw/skills/serenity-skill",
          "stateDbPath": "/Users/example/.fastclaw/data/finance-tools.db",
          "pythonBin": "python3",
          "timeoutSeconds": 45
        }
      }
    }
  }
}
```

The default Finskills path is `~/finskills`. The default Serenity path is
`$FASTCLAW_HOME/skills/serenity-skill`, or the project `skills/serenity-skill`
directory when running from source. The default ledger is
`$FASTCLAW_HOME/data/finance-tools.db` and is created with user-only file
permissions.

## Thesis Event Workflow

1. Save a thesis with assumptions, catalysts, invalidation conditions, and
   evidence.
2. Fetch a symbol-tagged announcement or event.
3. Call `thesis_match_event` for deterministic keyword and symbol matching.
4. Let the research agent assess impact using source evidence.
5. Call `thesis_record_review` with the previously read `expected_version`.
6. Keep portfolio and trading actions outside the plugin.

## Serenity Version

The project copy is pinned to
`muxuuu/serenity-skill@c2fe93deedfd0d1bd9fe7ef0601ea1b9c20ea24a`.
The upstream `SHA256.txt` at that commit has stale hashes for `README.md` and
`README.zh-CN.md`; executable scripts and the core `SKILL.md` match the
published hash list.

## Test

```bash
cd plugins/finance-tools
python3 -m unittest -v
```
