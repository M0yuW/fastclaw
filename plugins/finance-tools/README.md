# Finance Tools Plugin

`finance-tools` is the deterministic data and calculation layer for FastClaw
financial research agents. It wraps Finskills scripts behind typed tools and a
stable response envelope instead of asking the model to construct shell
commands.

Serenity Skill is used only as a research methodology and scorecard. It does
not fetch evidence, predict returns, execute trades, or replace portfolio risk
checks.

## Tools

- `finance-tools__toolkit_status`
- `finance-tools__stock_snapshot`
- `finance-tools__screen_stocks`
- `finance-tools__market_events`
- `finance-tools__macro_snapshot`
- `finance-tools__portfolio_risk`
- `finance-tools__serenity_scorecard`
- `finance-tools__thesis_save`
- `finance-tools__thesis_get`
- `finance-tools__thesis_list`
- `finance-tools__thesis_match_event`
- `finance-tools__thesis_record_review`
- `finance-tools__watchlist_save`
- `finance-tools__watchlist_list`
- `finance-tools__event_alert_ingest`
- `finance-tools__alert_list`
- `finance-tools__alert_update`

The runtime uses `plugin-id__tool-name` because the configured model provider
rejects periods in function names. The plugin's internal JSON-RPC tool names
remain unqualified (for example, `thesis_get`).

All tools return `finance.tool.v1` JSON with source, freshness, completeness,
structured errors, and cache metadata. Screening defaults to rejecting
candidates that are missing any metric used by the underlying filter.

`portfolio_risk` requires a complete holdings set. By default, weights must
sum to 100 (percent) or 1 (fraction), within a small rounding tolerance;
otherwise it returns `portfolio_incomplete` before running the analytics
script. Set `holdings_complete=false` when a position is unknown. Intentional
relative weights require `weight_unit="relative"` and
`holdings_complete=true`. This prevents a partial 45% + 30% portfolio from
being silently normalized to 60% + 40% and falsely flagged as a breach.

Thesis tools use trusted `userId`, `agentId`, and `sessionId` values injected
by FastClaw at tool execution time. The model cannot supply or override this
scope. Records are shared by agents owned by the same user, isolated from other
users, and retain creating/reviewing agent and session identifiers for audit.
Updates support `expected_version` to prevent silent lost writes.

Watchlist items may link to an owned thesis with the same market and symbol.
They define allowed event types, deterministic keywords, a minimum match score,
and a deduplication window. Event alerts keep an occurrence count and
`first_seen_at`/`last_seen_at` timestamps. Repeated events inside the window
update the existing alert instead of creating another model-review task.

Evidence-completeness protection is opt-in per thesis. Set
`required_event_metrics` to canonical names such as `quarterly_revenue` and
`gross_margin` when saving the thesis. The trusted event-ingestion step stores
`observed_metrics` for the alert; each entry has a nonempty `value`, `unit`,
and `fact_id`, and the packet must include a SHA-256 source reference. When
recording a review for such a thesis, provide the linked `alert_id`. The
plugin checks the **stored alert**, not metric claims in the model's review
arguments. If a required metric is absent, only decision `needs_review` is
accepted, with thesis status and conviction unchanged. A rejected attempt
does not create a review or increment the thesis version; the error contains
`missing_metrics`. A successful deferred review stores `alert_id` and the
missing-metric list for audit. Existing theses with no declared requirements
retain their metric-completeness behavior, but an explicit `needs_review`
still creates a decision hold. The ingress caller remains responsible for
checking that metric values and fact IDs truly correspond to the cited source;
the plugin cannot prove SEC content from a hash alone. Review agents should
not have permission to call `event_alert_ingest` or `thesis_save` when this
guard is intended to be independent of the model.

Any recorded `needs_review` now requires a linked alert and sets
`decision_hold=true`/`actionability=blocked`, even when the required metric
list is complete and no source conflict is stored. The deferred review cannot
change status or conviction. A later substantive review may release the hold
only against a complete, conflict-free alert for the same issuer, event type,
and event date with source-hash continuity. A voluntary or conflict hold also
requires at least one new source hash; simply re-reviewing the same packet
cannot turn the thesis actionable. This is a state-consistency guard, not an
automatic certification that the new source resolves the research question.

### Experimental accounting-lineage guard

Trusted event ingestion may attach audited `statement_line` metadata to
`observed_metrics` entries, plus optional `source_explicit_targets` and
`reconciled_targets`. An alert with this metadata requires the reviewer to
provide `causal_claims` when calling `thesis_record_review`. Each claim names
a target metric, source fact IDs and a strength (`directly_stated`,
`consistent_with`, or `unresolved`). The plugin checks these claims against
the **stored alert**, rejects incompatible accounting lines before a ledger
write, and replaces the model's free-form rationale with a generated summary
of validated facts and claims. A rejected call leaves thesis version and
reviews unchanged. Legacy alerts without classification metadata keep the
existing review behavior.

This is an opt-in research safeguard, not proof that every conclusion is
correct. The ingestion caller must independently verify the classifications
against the cited filing; the plugin cannot infer them from a SHA-256 hash.
It does not validate the model's final chat answer, whether the decision to
upgrade/downgrade is economically sound, or whether omitted claims should
have been made. Keep review agents from editing the trusted ingestion path.

### Experimental source-bound review veto

When `reviewArithmeticGuardCatalogPath` is configured, a trusted catalog
binds selected SEC comparison rows to the thesis and event source hashes.
Before a substantive `thesis_record_review` write, the plugin rejects a few
explicit contradictions in the proposed rationale: reversed operating-versus-
revenue or expense-versus-revenue increments, a reversed **signed** tax
contribution where the catalog declares that basis, and a claim that a
research/decision hold is preserved when the stored thesis has no hold.
The model cannot supply or modify this catalog through review arguments.
The option is off by default. For a proposed `needs_review` write, a flagged
contradiction does **not** reject the write and risk leaving the previous
thesis available: the plugin saves a deterministic warning in place of the
erroneous rationale and still establishes the decision hold. An unrecognised
source pair similarly yields a neutral warning and a hold for `needs_review`,
while substantive writes fail closed. The original tool arguments remain in
the Gateway trace for audit. This guard does not validate the final chat
response.
An empty flag list is not evidence that the financial analysis is correct.
These narrow rules were developed after inspecting saved errors and have not
been prospectively validated on unseen issuer cases.

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

1. Save a thesis with assumptions, catalysts, invalidation conditions,
   evidence, and—when applicable—`required_event_metrics`.
2. Save a watchlist item linked to that thesis.
3. Fetch and normalize a symbol-tagged announcement or event.
4. Call `event_alert_ingest` with source-linked `observed_metrics`; duplicate
   events inside the configured window are counted but do not create a second
   alert.
5. Let the research agent assess each new alert using source evidence.
6. Call `thesis_record_review` with the previously read `expected_version` and
   linked `alert_id`; if required metrics are missing, use `needs_review` and
   leave status and conviction unchanged.
7. Acknowledge or dismiss the alert with `alert_update`.
8. Keep portfolio and trading actions outside the plugin.

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
