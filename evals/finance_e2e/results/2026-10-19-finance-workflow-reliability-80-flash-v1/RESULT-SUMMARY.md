# Three-layer reliability evidence — exploratory Flash panel

The frozen run order was 16 cases × 5 new repetitions, each with a fresh
Gateway home, session, and finance ledger. The previous 16-case v2 run was
not counted. All 80 observations completed under an estimated USD 0.12 stop
cap; their estimated total was **USD 0.0902079472**. See `manifest.json` for
the scripts, fixtures, plugin, Gateway binary, model, and pricing hashes.

## 1. Runtime and fault handling

Across 80 observations there were 285 priced model calls and 246 tool calls.
All 80 runtime audits had paired tool-call/result IDs and clean completion;
there were zero request errors, trace errors, unpriced calls, cost-uncertain
calls, or typed budget terminals. These are bounded observations on the
tested workflows, not a production uptime or security guarantee.

The current Gateway binary was also exercised with a **free local scripted
provider**, separately from the 80 paid observations:

- `../2026-10-19-finance-reliability-json-fault-replay-v1/`: malformed tool
  arguments were rejected and paired; one corrected request then persisted a
  linked review and acknowledged its alert, while a second malformed request
  ended with `malformed_tool_arguments_exhausted` and no ledger write.
- `../2026-10-19-finance-reliability-tool-fault-replay-v1/`: a deterministic
  invalid-input call was recovered, whereas repeated invalid calls reached
  the iteration limit without persisting a review or acknowledging the alert.

Go tests for `internal/agent` and `internal/api`, 17 finance-plugin tests, and
10 Python preflight/oracle/audit tests passed. The existing scheduler-only
load test was rerun five times and passed for root capacities one and four;
it uses 48 synthetic tasks over 12 chat keys and makes no model request, so
its throughput must not be presented as end-to-end service capacity.

## 2. Repeated workflow execution

| Workflow | Observations | Raw mechanical passes | Clean runtime audits |
|---|---:|---:|---:|
| SEC event → view update (E) | 20 | 20 | 20 |
| Source conflict / correction (C) | 20 | 20 | 20 |
| Candidate screening (S) | 20 | 20 | 20 |
| Portfolio-risk diagnostic (P) | 20 | 19 | 20 |
| **Total** | **80** | **79** | **80** |

The sole raw failure, `P4-r4`, is a **case-oracle false negative**, not a
failed runtime observation. That case calls for safe handling of an incomplete
portfolio. The agent made **zero** tool calls, explained why it would not
compute a full risk view, and made no ledger write. Its runtime audit records
`tool_calls_paired=true` and `clean_completion=true`. The generic
`tool_trace_complete` check nonetheless requires at least one call. The
original result remains unchanged (SHA-256
`c8bca07e67f34d6f12845388066be7e586fc12e292c4c969afb548961cb26838`).
On the task-specific safety criterion, all 80 observations passed; the raw
79/80 score is retained to make the adjudication visible.

The repeated prompts and fixtures are identical within each case. Five
repetitions therefore test execution stability under model variability, not
generalization to new companies, filings, holdings, or unseen workflows.
There is no defensible population reliability percentage from this panel.

## 3. Evidence and analysis quality — separate from runtime success

The structured oracles checked source packets, stored values, linked reviews,
screen selection, portfolio tool inputs, ledger state, and policy handling
where applicable. A targeted qualitative read covered one output from each
of the 16 cases and the other four P4 outputs; it was **not** a full
independent review of all 80 narratives. Several content limitations remain:

- `E1-r1` simultaneously calls the two quarters non-adjacent and acknowledges
  that Q3/Q4 of the same fiscal year are adjacent. This is inconsistent
  wording, although its copied values and one-point margin change are correct.
- `E4-r1` briefly connects higher revenue scale to “margin resilience” while
  acknowledging that the current gross-margin metric is absent. Revenue alone
  cannot establish margin resilience.
- All five P4 outputs correctly avoided a full incomplete-portfolio risk
  calculation, but their prose overstates uncertainty about the >50%
  single-holding limit. With reported nonnegative weights of 45% and 30% of
  the whole, the unreported remainder is at most 25%, so an omitted position
  cannot exceed 50% under that interpretation. Some outputs even say the
  omitted holding might be the largest or above 50%. The case prompt's
  “do not infer a missing weight” wording also blurs the distinction between
  inventing a position and deriving a mathematical upper bound; this should
  be clarified before using P4 as a financial-reasoning quality benchmark.

Thus the panel supports a **bounded engineering claim**: on these four
workflow families, the runtime repeatedly executed with auditable traces,
isolated state, and safe fault behavior. It does **not** establish that every
generated financial insight is analytically sound. A larger unseen-case set
and a separately frozen content-quality rubric would be needed for that claim.

## Post-run audit addendum

The subsequent read-only [claim and oracle audit](CLAIM-AUDIT-V5.md) checked
targeted source, tool-data, and numeric assertions in **all 80** observations,
and added counterexample tests for the P4 scoring rule. It confirmed the
`P4-r4` raw false negative without rewriting the frozen result and identified
ten observations with claim-level or presentation flags. The earlier
qualitative sample above remains a description of the initial review, not the
scope of the later audit. No overall financial-insight quality rate is claimed.

The later [conclusion-level audit](CONCLUSION-LEVEL-AUDIT.md) also read the
final answer and, where applicable, the persisted research artifact for
**each of the 80** observations. It separates correct copied values and
arithmetic from unsupported interpretations and actual ledger state. Most
importantly, E4/C4 each recorded five `needs_review` decisions on missing
required evidence while leaving `actionability=available`, and P4's five
safe tool abstentions nevertheless made unsound or contradictory claims about
the derivable 50% limit. These findings supersede any inference that the
corrected process score constitutes an 80/80 financial-conclusion or safety
closure score.
