# FastClaw Financial Research Runtime

## Product Position

The target application is a portfolio and watchlist research copilot, not an
autonomous stock recommender. The runtime helps users collect evidence,
prioritize research, monitor thesis changes, and challenge conclusions. It
does not execute trades or promise returns.

The first implementation separates three concerns:

1. deterministic market data and calculations;
2. reusable investment research methods;
3. selective model reasoning and multi-agent review.

This avoids using language-model agents as expensive data fetchers.

## Serenity Skill Decision

The project vendors
`muxuuu/serenity-skill@c2fe93deedfd0d1bd9fe7ef0601ea1b9c20ea24a`
under `skills/serenity-skill`.

It is suitable for:

- translating a market narrative into a value-chain map;
- identifying difficult-to-expand supply-chain layers;
- grading evidence and separating facts from leads;
- ranking research priority;
- defining failure conditions and next verification steps.

It is not suitable as:

- a price or return prediction model;
- a source of current market facts;
- a replacement for valuation or portfolio-risk calculations;
- a ground-truth label for evaluation;
- an automatic buy or sell engine.

Its scorecard inputs are analyst judgments from zero to five. The deterministic
script makes repeated scoring reproducible, but does not make the inputs
objective. Reports must label Serenity scores as research-priority scores.

The installed upstream commit contains only Markdown, JSON, YAML, and two
local-only Python scripts. The scripts do not access the network, credentials,
broker accounts, or shell commands. The upstream `SHA256.txt` has stale hashes
for two README files at the pinned commit; executable scripts and `SKILL.md`
match the published hash list.

## Runtime Architecture

```text
user or scheduled event
        |
        v
research coordinator
        |
        +--> finance-tools plugin
        |      stock / macro / announcements / portfolio calculations
        |
        +--> selected research method
        |      Serenity / financial statements / event-driven / factor analysis
        |
        +--> optional challenger
               evidence gaps / contradiction / downside / compliance
        |
        v
research report + thesis state + follow-up checks
```

Market data and calculations are tools, not sub-agents. A sub-agent is useful
only when an independent opinion, parallel deep dive, or risk challenge can
improve the final decision.

## Finance Tool Contract

`plugins/finance-tools` exposes:

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

Every tool returns the `finance.tool.v1` envelope:

```json
{
  "schema_version": "finance.tool.v1",
  "ok": true,
  "request_id": "uuid",
  "as_of": "2026-07-30T12:00:00Z",
  "stale_after": "2026-07-30T12:05:00Z",
  "data": {},
  "sources": [
    {"name": "AKShare", "kind": "market_data"},
    {"name": "finskills", "kind": "stock_data"}
  ],
  "quality": {
    "completeness": 0.95,
    "flags": []
  },
  "errors": [],
  "cache": {
    "hit": false,
    "ttl_seconds": 300
  }
}
```

External scripts run through `subprocess.run` without a shell, with validated
symbols, bounded arguments, captured output, and a configurable timeout.
Failures become structured tool results so the coordinator can degrade
gracefully instead of inventing missing facts.

Stock screens apply an additional runtime quality gate. By default, a candidate
that appears to pass but is missing a metric used by the filter is moved to the
rejected list with `reason=insufficient_data`.

## Plugin Registration Fix

FastClaw previously discovered and started native tool plugins, but did not
register their arbitrary tools into user Agent registries. Provider and channel
plugins worked through separate adapters, while a normal tool plugin remained
invisible to the model.

The user-space loader now registers every running tool plugin on:

- initial user-space creation;
- foreign-agent injection for super-admin chat;
- gateway startup for any already-loaded user spaces.

Plugin tools use qualified names such as
`finance-tools.stock_snapshot`, unless intentionally overriding a built-in.

## Trusted Tool Context

Stateful plugins cannot rely on model-supplied tenant arguments. FastClaw now
adds an `ExecutionScope` to every Agent turn and forwards it in the native
plugin protocol:

```json
{
  "context": {
    "userId": "runtime-user",
    "agentId": "research-coordinator",
    "sessionId": "web-session"
  }
}
```

The scope is generated after message routing from the loaded user space. It is
not part of the tool's model-visible arguments. Stateless plugins remain
backward compatible, and direct calls without scope continue to work. Stateful
finance tools reject calls that lack trusted `userId` and `agentId`.

## Thesis Ledger

`finance-tools` persists research state in SQLite, defaulting to
`$FASTCLAW_HOME/data/finance-tools.db`. The database contains:

- thesis text, status, conviction, and review schedule;
- assumptions, catalysts, and invalidation conditions;
- evidence snapshots;
- immutable event review records;
- creating and reviewing agent/session identifiers;
- an integer version for optimistic concurrency.

Isolation is user-level so a coordinator and its specialists can collaborate on
the same ledger. Every read and write filters by trusted `userId`; records are
never queried by a model-supplied tenant key.

The event workflow is:

1. fetch events through a deterministic data tool;
2. match symbol and thesis terms through `thesis_match_event`;
3. ask the model to assess evidence and impact;
4. persist the conclusion through `thesis_record_review`;
5. reject stale writes when `expected_version` no longer matches.

Event matching is deliberately not sentiment analysis. Invalidation phrases
receive a larger deterministic match weight than catalysts and assumptions,
but the final impact still requires evidence-backed model or human review.

## Default Workflow

### Theme Scan

1. Define market, theme, and time horizon.
2. Use Serenity to map the value chain and candidate universe.
3. Fetch deterministic data only for the candidate universe.
4. Reject data-incomplete candidates.
5. Rank scarce layers before companies.
6. Ask a challenger to inspect evidence gaps and failure conditions.
7. Save the result as a research priority list, not a trade recommendation.

### Single-Company Research

1. Capture an immutable stock and financial snapshot.
2. Identify the exact value-chain position.
3. Grade each material claim by source strength.
4. Run deterministic financial, valuation, and risk checks.
5. Build bull, base, bear, and invalidation conditions.
6. Persist evidence timestamps and the next review trigger.

### Portfolio Monitoring

1. Calculate concentration, correlation, risk, and stress metrics.
2. Fetch new announcements and material events for holdings.
3. Match events to stored thesis assumptions.
4. Trigger model analysis only for meaningful changes.
5. Require human approval for any portfolio action.

## Evaluation Plan

Do not use short-term stock returns as the first quality target. Early runtime
evaluation should measure system behavior:

| Dimension | Metric |
|---|---|
| Data access | tool success rate, timeout rate, cache hit rate |
| Data quality | required-field coverage, freshness, partial-failure rate |
| Grounding | supported-claim rate, primary-source coverage |
| Research | bottleneck identification, evidence grading, invalidation quality |
| Monitoring | event recall, alert precision, duplicate-alert rate |
| Orchestration | Solo versus Team pass rate and unsupported-claim rate |
| Cost | model calls, tokens, estimated fee, P50/P95 latency |

Serenity-specific evaluation must compare:

- no skill;
- Serenity Skill with the same data tools;
- Serenity plus an independent challenger.

The candidate universe, source snapshots, model, prompt budget, and tool access
must remain identical. This isolates methodology lift from data-access lift.

## Next Phases

### Phase 2: Persistent Research State

Completed:

- tenant-isolated thesis, assumptions, catalysts, and invalidation conditions;
- evidence snapshots and immutable review history;
- deterministic event-to-thesis matching;
- optimistic version checks and agent/session audit fields.

Remaining:

- portfolio and watchlist records;
- alert deduplication and delivery state;
- exchange-calendar-aware scheduling.

### Phase 3: Progressive Skill Loading

FastClaw currently injects every installed `SKILL.md` in full. Financial agents
should receive only skill names and descriptions initially, then load one to
three selected methods on demand. This is required before installing the full
Finskills collection on one agent.

### Phase 4: Point-in-Time Evaluation

- freeze source data by `as_of`;
- use historical constituent universes;
- prevent look-ahead and survivorship bias;
- evaluate alerts and research conclusions against facts available at the time;
- add return-based analysis only after the data pipeline is point-in-time safe.
