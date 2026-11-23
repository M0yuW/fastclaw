# Post-correction SEC event holdout — output-limit arm v3

Status: **predeclared after the v2 arm stopped, before v2 qualitative answer
review or any v3 model observation**. This is a separate prospective arm, not
completion, replacement, or pooling of the 76 v2 observations.

## Technical reason for the new arm

`POSTCORRECTION-V2-STOP-REVIEW-2026-10-24.md` records the original arm's
76/100 stop. One CBOE session reached the coordinator's per-call
`maxTokens=2500` and returned `finish_reason=length`; it had no persisted
review. The last model-call estimate is flagged cost-uncertain. The old failure
and 24 unrun positions remain as recorded.

## Frozen intervention and denominator

Run all **20 source-distinct SEC event cases × 5 fresh isolated sessions =
100 observations** in the identical v2 SHA-256-derived run order. Use the same
source packet bytes and auditors, host-computed numeric context, exact review
prompt, finance tool/plugin semantics, Gateway binary, Flash model alias,
peak-rate estimate, mechanical checks, F/I/R/S/U rubric and case gate. The
**only intended intervention difference** is the copied coordinator agent's
per-call `maxTokens`, raised from **2500 to 5000**. Do not change `maxToolIterations`,
context compression, model, prompt, or any source/score material. Verify the
copied DB setting before each observation, and record this difference and all
relevant hashes in the new manifest.

All errors, output truncations, uncertain costs, and failed writes count in the
new 100-observation denominator. No outcome-based retry. Stop before a new
observation if the authorized cumulative estimated spend lacks the fixed
USD 0.05 reserve. Stop immediately on request error, unpriced usage, cost
uncertainty, or cap breach. Retain any partial new-arm result; do not continue
or amend a stopped arm in place. User authorization for this **new arm** and
its cap is required before paid execution.

The strict event-case claim remains all 20 case gates passing: each case
requires five completed tool/ledger/fact observations, no critical error, and
at least four `high` plus at most one `adequate` qualitative rating. The
one-sided Bonferroni-adjusted lower-bound calculation is unchanged. A passing
event arm still does not prove economic value or screening/portfolio-workflow
reliability; Codex/LLM ratings remain diagnostic without a blinded finance
professional.
