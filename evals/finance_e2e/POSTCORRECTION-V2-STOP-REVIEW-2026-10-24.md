# Post-correction v2 event holdout — stopped run review

The predeclared 20-issuer × 5-session panel started after separate user
authorization for an estimated USD 1.50 cap. It stopped at **76/100** in the
frozen run order. All 76 result JSON and 76 finance-ledger DB files are retained
under `results/2026-10-24-postcorrection-event-holdout-v2/` and match its
`RESULT-SHA256.txt`. The manifest hash is
`a1abd5fdb17dac9f9a5477ad733cc2c47eb960621213f9402e168202421d5b05`;
the final hash-list hash is
`1449ec8a00ab8e6b82124257fb874843b86fb0fadebbd2ce18046ea5c6c7af46`.

Of the 76 retained observations, **75** passed the prespecified mechanical
tool/source/state checks and **one** did not. The failed observation is
`CBOE-2025-Q3-SEGMENT-RECONCILIATION-r3`: the third model call reached
`completion_tokens=2500`, the copied Gateway agent's configured `maxTokens`
limit. The provider returned `finish_reason=length`; the Gateway trace records
`model output truncated: finish_reason=length` and flags model-call sequence 3
as `cost_uncertain=true`. Three finance-tool calls were paired with results, but
no thesis review was written and the alert remained `new`. This is a genuine
failed observation, **not** a valid no-change research decision.

The runner's accumulated priced estimate was **USD 0.668692608**, including
USD 0.005428848 reported for the failed observation. Because its last model
call is marked cost-uncertain, this total is not an attested provider bill or a
complete upper bound. The run stopped immediately under the predeclared
uncertain-cost/error rule, well below the nominal USD 1.50 estimate cap. The
other 24 planned observations were **not run**, and this partial panel cannot
pass the 20-case confirmatory gate. No quality rating is inferred from the
75 mechanical passes; factual, inferential, and research-utility review has
not yet been done.

The likely remediation is a **separate new arm** with fresh isolated sessions
and a higher per-call output limit, while keeping source packets, prompt,
run order, tool/state checks, score rubric, and case gate fixed. It must be
authorized separately, must not overwrite or pool with the stopped v2 arm,
and must retain its own failures. No v2 failure should be silently retried.
