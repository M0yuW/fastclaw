# Two-case source-only guarded review pilot

This is a **feasibility pilot**, not a confirmatory quality study. Run one
isolated Flash observation each for Intel Q2→Q3 2024 and Nike Q4 FY2024→Q2
FY2025. The only external model payloads are previously authorized SEC-case
facts, source hashes, the seeded thesis/alert state and this new task prompt.
Do **not** include archived model answers or judge labels from earlier runs.

Trusted harness ingestion attaches audited accounting `statement_line`
metadata to event metrics. Intel's USD 3.1 billion manufacturing-asset item
is cost of sales; goodwill/intangible impairment is not gross margin; the
USD 9.9 billion deferred-tax-asset allowance is income tax. The USD 15.9
billion bundle and USD 2.8 billion restructuring remain distinguishable.
Nike's source explicitly attributes its 100-basis-point gross-margin decline
primarily to higher discounts and channel mix, partly offset by lower input
and logistics costs. Source URL, raw cache bytes and these facts are checked
before the first call.

The review agent is `finance-review-only`: it can read thesis/alerts, record
one review and acknowledge the alert, but cannot save a thesis, ingest a new
alert, use market tools, trade, or call the shell. The model chooses impact,
decision and conviction; the prompt does not supply them. It must submit
structured `causal_claims`. The plugin checks against the stored alert,
rejects incompatible claims without a ledger mutation, and persists a
generated rationale instead of the model's draft. The final chat answer
remains unguarded and is judged separately.

Before the first call freeze this protocol, runner, source locks, plugin,
validator, policy, Gateway binary and template DB hashes. Use fresh ledgers
and sessions. Preserve every observation and tool error; do not selectively
retry. Stop before a new call at USD 0.015 estimated cumulative cost and
immediately on request error or unpriced/uncertain usage.

Pilot feasibility: actual paired tool calls; one review and alert
acknowledgement; exact source and metric retention; guarded evidence entry;
no forbidden tool; no unexpected ledger state; no model/service error.
Separately review numeric fidelity, attribution, risk, final-answer/ledger
alignment and decision utility under `INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md`.
Two cases and one repetition cannot show stability. A blocked bad claim is
a safe rejection, not a high-quality completed answer. Do not proceed to a
larger paid arm without inspecting these two raw traces and fixing any
runtime or rubric defect prospectively.
