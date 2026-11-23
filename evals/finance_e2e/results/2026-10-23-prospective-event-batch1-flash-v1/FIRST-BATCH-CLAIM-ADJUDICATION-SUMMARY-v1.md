# First prospective event batch — completed diagnostic adjudication v1

## Design and integrity

Five pre-frozen SEC issuer packets (BNY/BK, FISV/FI, GS, MCO, OMF) were each run in five independent fresh sessions with the requested `deepseek/deepseek-v4-flash` alias: **25/25 observations**. The Gateway request and ledger chain completed mechanically in **24/25**; one FISV observation ended `needs_review`. There were no request errors in the retained records. The runner's preflight-peak-rate estimated spend is **USD 0.187249212**, below the authorized **USD 0.25 estimated stop**; actual provider billing and the provider's underlying model-version identity were not independently attested.

All 25 frozen `result.json` hashes were rechecked with `shasum -a 256 -c RESULT-SHA256.txt`: **25/25 OK**. The five source auditors were rerun and matched all **52 selected SEC cells** (MCO 8, GS 12, BNY 10, FISV 8, OMF 14) and their declared deltas to locked local exhibit bytes. The raw `quality_score` fields remain null; none of the below judgments was written into or substituted for the original model results.

## Conclusion-level self-review

This is an **unblinded Codex diagnostic judgment**, made with issuer IDs, run IDs and mechanical outcomes visible. It reads both the final answer and the persisted review rationale, checks material source claims/calculations, risk treatment and actual ledger state, then applies the predeclared F/I/R/S/U rubric. It is **not** an independent finance-domain human rating, blinded LLM-as-judge validation, an investment-performance result, or a population-level reliability estimate. The per-claim evidence and discretionary calls are in the linked case notes.

| Frozen case | High | Adequate | Problematic | Strict five-session gate | Key exception |
| --- | ---: | ---: | ---: | --- | --- |
| [MCO](MCO-CLAIM-ADJUDICATION-v1.md) | 3 | 2 | 0 | fail: only 3 high | Two answers weakly bridge operating to attributable-income growth. |
| [GS](GS-CLAIM-ADJUDICATION-v1.md) | 3 | 1 | 1 | fail: critical | r5 persisted a false absolute comparison: earnings +375 < revenue +601 USDm. |
| [BNY](BNY-CLAIM-ADJUDICATION-v1.md) | 0 | 3 | 2 | fail: critical | r2 calls NII +33 the **entire** revenue gain +53; r4 understates the +24 unlisted revenue residual. |
| [FISV](FISV-CLAIM-ADJUDICATION-v1.md) | 2 | 2 | 1 | fail: critical/state | r3 over-attributes operating-profit decline and leaves `needs_review` actionable. |
| [OMF](OMF-CLAIM-ADJUDICATION-v1.md) | 2 | 2 | 1 | fail: critical inference | r5 infers lower absolute realized losses from only a lower net-charge-off **ratio**. |
| **Total observations** | **10** | **10** | **5** | **0/5 cases pass** | Clusters are correlated repetitions, not 25 independent issuer cases. |

The predeclared case gate requires all five tool/ledger observations to complete and pass factual/execution checks, no critical errors, and at least four `high` with at most one `adequate`. No case reaches that composite threshold in this diagnostic adjudication. The **24/25 mechanical-pass fraction is not an insight-quality success rate**. The five selected-fact packets were accurately extracted from the locked SEC exhibits; the confirmed defects lie in the generated conclusion or, for FISV-r3, the frozen runtime/plugin actionability state. The post-batch plugin hold-rule correction is prospective only and cannot retroactively erase that observation.

## What can responsibly be claimed

The batch supports a bounded **engineering** statement: across five distinct SEC event packets, an isolated Gateway/finance-tool workflow completed 25 source-linked event→alert→review→acknowledgement sessions under the recorded estimated cost, preserved auditable outputs, and surfaced rather than discarded a review/state exception. It does **not** support “the system stably generates high-quality financial insights.” Even the 10 high labels are unblinded self-review judgments, not verified economic value or independent expert agreement.

To test improvement without reusing the same evaluated issuers, use the **source-distinct, post-correction v2 holdout** after all candidate source packets are independently checked. The current v2 frame has 20 unobserved issuer candidates, but only six have source-audited preflight packets; 14 still need source-row/period/unit/basis completion. No v2 paid model call is authorized by this completed v1 batch. A separate blinded judge could strengthen construct validity, while the absence of a finance-domain human reviewer must stay explicit. Any future result should retain failures and score final prose **plus persisted state**, not only numeric tables.
