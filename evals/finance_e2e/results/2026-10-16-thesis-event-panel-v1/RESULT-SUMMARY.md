# SEC event → research-thesis update: five-case exploratory panel

This is a **one-attempt-per-case exploratory integration result**, not an
accuracy estimate or a Team/Solo comparison. Four cases were frozen in
`thesis_event_panel_v1.json` before that panel ran. A fifth, matching-quarter
Nike deterioration case was separately frozen in
`thesis_event_same_quarter_addendum_v1.json` after review exposed a period
design flaw in the initial Nike case. The earlier observation and both
manifests remain unmodified. The addendum result is in the sibling
`2026-10-16-thesis-event-same-quarter-addendum-v1` directory.

Each case used an isolated Gateway snapshot, an empty `finance-tools` SQLite
ledger, a distinct session, a source-hash-checked SEC artifact, and a
pre-ingested event packet. The common task prompt did not prescribe a
decision, status, or conviction. The model could read the thesis and alert,
record one review, and acknowledge the alert; no trading or portfolio tool was
available. The event was **seeded**, not retrieved autonomously. In the NVDA
case, Q2 gross margin was deliberately omitted from the *packet*; the locked
SEC source itself does disclose 75.1%.

| Case | Agent decision / persisted state | Mechanical workflow | Source, arithmetic, and risk review |
|---|---|---|---|
| AMD Q3, mixed | `maintain`, active, conviction 3 | Pass | Q2→Q3 revenue +16.9%, margin +1 pp, Gaming −28.7%; both improvement and segment risk identified. |
| AMD Q4, positive | `upgrade`, active, conviction 4 | Pass | Q3→Q4 revenue +12.3%, margin +1 pp, Gaming +21.9%; explicitly notes one rebound does not prove sustained recovery. |
| NKE Q2 FY2025, original negative case | `invalidate`, invalidated, conviction 1 | Pass | Numbers are correct for two selected observations, but Q4 FY2024→Q2 FY2025 is **not** year-over-year. The answer called it “year-over-year across non-identical quarters”; exclude this case as clean deterioration evidence. |
| NVDA Q2, omitted packet field | `maintain`, active, conviction 3 | Pass | Revenue +15.3% and Data Center +16.4% are correct; the answer correctly locates the missing margin in the packet, not in the SEC filing. It did **not** choose the predeclared `needs_review` decision for an unverified required thesis condition. |
| NKE Q4 FY2025, matching-quarter addendum | `invalidate`, invalidated, conviction 1 | Pass | Q4-on-Q4 revenue −12.0%, margin −4.4 pp, and digital YoY rate 16 pp more negative; correct period interpretation and risk conclusion. |

All five isolated ledgers independently contain exactly one thesis, one
immutable review, and one alert. SQL inspection confirmed thesis version
`1→2` and alert status `acknowledged` in every case. The trace shows only
`thesis_get`, `alert_list`, `thesis_record_review`, and `alert_update` calls,
with no trade or portfolio call. Source IDs and SHA-256 values were recorded
in the reviews; source-lock hash verification passed, and the cited figures
were checked against the archived SEC exhibits. All five runs returned priced
model-call telemetry. Across 19 model calls, observed wall time summed to
94.238 seconds and frozen-rate estimated cost to USD 0.018378, below the
USD 0.10 stopping cap. This is **not** a provider invoice.

Interpretation must keep three levels separate: mechanical completion was
5/5; the frozen deterministic decision/status oracle passed 4/5 (NVDA
deviated); and a post-run semantic review found a material period-label error
in the original Nike case, leaving 3/5 without these identified analytical
issues. This last fraction is a descriptive audit count, not a predeclared
statistical success rate. The positive, mixed, and matching-quarter negative
cases demonstrate that the runtime can carry different agent-proposed
conclusions into persistent state. The missing-evidence case demonstrates a
calibration gap: the agent preserved the state, but recorded `maintain` where
the frozen oracle required `needs_review`.

Limitations: one attempt per case, three issuers, one Pro model, researcher-
authored thesis conditions, pre-ingested evidence packets, no autonomous SEC
retrieval, no repeat-event/idempotency challenge, no cross-tenant adversarial
turn, no Team comparison, and no investment outcome evaluation. The original
Nike case and its design correction should both remain visible in reporting.
