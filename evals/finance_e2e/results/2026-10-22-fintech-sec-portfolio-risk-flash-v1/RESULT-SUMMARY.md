# Source-grounded portfolio-risk panel: v1 audit

## Scope and integrity

The frozen v1 protocol paired the actual `finance-tools__screen_stocks` and `finance-tools__portfolio_risk` workflow with three historical Q3 2024 SEC-hosted issuer exhibits: COIN, HOOD and SQ. The portfolio holdings and analytics fixture were fictional and deterministic; the SEC disclosures were historical frozen source data, not live market data. There were three case clusters with five fresh sessions each: exactly at a strict 50% single-name limit, 55% above it, and an incomplete holdings map. This is a new workflow pairing using previously seen issuers, not an independent new-issuer holdout or a real-account investment test.

The manifest and all 15 original `result.json` files are covered by `RESULT-SHA256.txt`; `shasum -a 256 -c` verified every entry. Raw result, ledger and manifest files were not changed during adjudication. All 15 observations completed paired calls without request/terminal, tool-trace, pricing or cost-uncertainty errors. Estimated model cost was USD 0.0192291288 (not a provider invoice), below the USD 0.08 arm cap.

## Mechanical adjudication

The runner recorded 14 `mechanical_pass` and one `needs_review` (`PR-INCOMPLETE-r2`). The latter used `holdings_complete=false`; the portfolio tool returned `portfolio_incomplete` with `ok=false`, `data=null` and “risk calculation refused.” This is **allowed by the pre-frozen protocol**. The runner's boolean `no_incomplete_risk_calculation` instead treated any risk-tool call as a failure. Thus the raw script count remains 14/15, while an explicit protocol adjudication is **15/15 compliant**. No exact HHI or full-map result was produced for the incomplete case, and no thesis, alert, trade or account mutation was recorded. This is a scoring-code/protocol mismatch, not a runtime failure or a post-hoc change of the observation.

For complete holdings, all five limit-case outputs correctly state COIN 50% is **at**, not above, the strict `>50%` limit and HHI is 0.38. All five breach-case outputs correctly state COIN 55% exceeds the limit by five percentage points and HHI is 0.405. The screen's separate 20% issuer-revenue criterion was not substituted for the portfolio policy. The main source figures were cross-checked against the three original SEC-hosted exhibits: COIN total revenue USD 1,205,193 thousand versus 674,148 thousand (derived +78.8% YoY), HOOD crypto revenue USD 61 million (+165% YoY) within USD 637 million total net revenue, and SQ total net revenue USD 5.98 billion (+6% YoY) with USD 2.25 billion gross profit (+19% YoY).

## Codex LLM-as-judge content audit

`INSIGHT-JUDGE-v1.csv` applies the frozen F/I/R/S/U rubric to every answer and retained tool/ledger state. This is a non-blinded, non-independent Codex judgment, **not** an expert finance rating or an economic-value test. Labels for the incomplete case are provisional under the intended interpretation that named ticker weights are aggregate and the unknown sleeve contains other ticker holdings.

| Cluster | Protocol-adjudicated mechanical | High within case | Adequate | Problematic |
| --- | ---: | ---: | ---: | ---: |
| At 50% limit | 5/5 | 2 | 3 | 0 |
| 55% breach | 5/5 | 2 | 3 | 0 |
| Incomplete holdings | 5/5 | 0 | 5 | 0 |
| **Total** | **15/15** | **4** | **11** | **0** |

The outputs usually preserve the SEC periods, units and arithmetic and distinguish position weight from a measured crypto factor exposure. Their content weakness is **inference**, not a wrong threshold calculation: several infer a “weak” COIN prior-year base, “accelerating” cross-issuer activity, or a low-margin bitcoin/merchant-mix explanation for SQ's revenue/gross-profit gap without the selected packet's historical benchmark or segment margin bridge. The incomplete-case responses correctly avoid fabricating an exact HHI, but two say SQ is not a holding even though the undisclosed sleeve could contain it; another first entertains an unknown >50% position before correctly deriving the intended bound.

## Case-design limitation discovered by the judge

The v1 prompt says COIN is 40%, HOOD is 30%, and 30% is unspecified, but does not explicitly say whether those named weights are **final ticker-aggregated positions** or whether the residual could contain additional COIN/HOOD exposure. Under the intended distinct-holdings interpretation, each unknown position is at most 30%, so COIN at 40% is the largest and a `>50%` single-name breach is impossible, while exact HHI remains unknown. If the residual could duplicate COIN, aggregate COIN exposure could instead reach 70%, reversing the policy conclusion. `PR-INCOMPLETE-r5` notices this ambiguity. The v1 oracle assumed the first interpretation without stating it in the user-facing case. Consequently **do not use the incomplete cluster as clean evidence of a universally correct policy bound**. A separately frozen clarification is needed; the existing prompt and raw outputs must not be silently edited.

## Interpretation

The precommitted stability gate required five mechanically and materially correct outputs and at least four high-quality outputs in **each** cluster. It is **not met**: the two complete clusters have only two high labels each, while the incomplete cluster is also case-design ambiguous. The result supports a narrower engineering claim: this workflow executed, enforced the exact-input/refusal boundary, preserved source and state provenance, and made reasoning imperfections auditable. It does **not** establish that the system stably produces high-quality financial insight across cases, nor that any output predicts returns or is appropriate investment advice. The repeated outputs are correlated within three frozen scenarios and cannot be read as a population reliability rate.
