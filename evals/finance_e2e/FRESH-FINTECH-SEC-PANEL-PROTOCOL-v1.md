# Prospective FinTech SEC event-to-thesis holdout panel (v1)

## Freeze and scope

This protocol and `fresh_fintech_sec_panel_v1.json` are frozen before any model observation. Six SEC-furnished Exhibit 99.1 HTML documents for previously untested payment issuers V, PYPL and MA are cached and SHA-256 locked. The corpus selects facts from the releases; the agent is **not** represented as having read the complete filing. Source URLs, raw-document hashes, facts, units, periods, locators and precommitted interpretation checks are in the corpus. A factual discrepancy requires a numbered revision **before** the paid run. Do not rewrite this protocol, corpus, prompt or runner after results exist.

The three clusters test different inference traps: Visa service revenue uses prior-quarter payments volume, not current-quarter volume; PayPal's payment-volume level, YoY growth rate, net revenue and transaction-margin dollars move differently; Mastercard's GAAP and adjusted operating-margin bases diverge in the presence of separately disclosed litigation and restructuring charges. These are **new issuers but the same event-to-thesis workflow**. Passing would support this workflow's cross-issuer generalization only, not all financial workflows.

## Run and stopping rules

- Five fresh, independent Gateway/session/finance-ledger observations for each issuer, 15 planned. Fixed Flash model and price estimator, source packet, task wording, tool policy, iteration limit and template DB; randomize case order with recorded seed 2243. Do not adapt prompts, replace failures, or cherry-pick repetitions.
- Execute real finance-tool event ingestion, guarded thesis review and alert acknowledgement. Record the initial thesis, source-linked event packet, every call/result, final answer, ledger state, runtime/usage audit and hashes. The review-only agent must not save a new thesis or trade.
- Estimated spend stop is USD 0.10 with USD 0.02 reserved before starting the next observation. Stop on a request error, unpriced usage or uncertain cost sequence; preserve the failure. Cost estimates are not provider invoices. No archived internal model output is included in external prompts.
- After the run, freeze raw `result.json` hashes before judging. Do not silently repair or rerun a failed observation. A later changed system is a separate diagnostic or new panel.

## Judgment and success gate

Deterministic checks: actual required tool calls, source-packet equality, one linked guarded review, alert acknowledgement, versioning, no prohibited mutation, clean trace and priced usage. Report separately from answer quality. A model's prudent refusal may be substantively appropriate but is not an executed workflow.

Codex scores each answer **with** the persisted review and ledger against the already-existing F/I/R/S/U rubric, recording material factual/period/basis/causal errors and an overall high/adequate/problematic/not-assessable label. This judge is not a blinded finance expert and does not prove market value. The precommitted within-panel gate requires 15/15 mechanically complete; F=2 and no critical error in all 15; and at least 4/5 high-within-case in **each** issuer cluster. Preserve all denominators and cluster-level variation. Passing this gate would justify only consistency in this selected event-to-thesis panel, not stable production-wide high-quality insight or predictive returns.

For the broad runtime objective, this panel must later be combined with prospective real-source tests of other workflow families (e.g. screening and portfolio risk) rather than pooled indiscriminately with synthetic or post-hoc diagnostics. Report any negative result explicitly.
