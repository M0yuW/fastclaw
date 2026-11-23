# Portfolio issuer-aggregation diagnostic: first-pass result

## Why this arm exists

The previous source-grounded portfolio panel left open whether a disclosed 40% COIN line item already represented all COIN exposure or could be augmented by an unidentified 30% sleeve. This **separate, prospectively frozen diagnostic** made the two possibilities explicit without changing old prompts or outputs. It reused the same historical Q3 2024 SEC-source packet, actual screen tool, fictional holdings and Flash configuration. The fixture is not a live account, and the issuers are not an unseen source holdout.

`PA-DISTINCT` states that COIN 40% and HOOD 30% are final issuer-aggregated weights; the distinct residual is 30%. Therefore **no issuer can exceed 50%**: COIN is the largest at 40%, HOOD is 30%, and every residual issuer is at most 30%. Exact HHI remains unknown. `PA-OVERLAP` states instead that 40% and 30% are unaggregated line items and the 30% omnibus sleeve may duplicate them. COIN can be 40–70%, HOOD 30–60%, so the `>50%` verdict is **indeterminate** until the sleeve is decomposed. These are two different answers to two different input semantics, not inconsistent oracles.

## Execution and integrity

The first attempt is retained separately in `2026-10-22-fintech-sec-portfolio-ambiguity-flash-v2/`: one result file, zero model calls and USD 0 cost. Its isolated Gateway could not bind local port 18955 under the filesystem/network sandbox; the timeout occurred during shutdown after the bind error. It is an **environment-startup attempt**, not a model observation and not part of the ten-response denominator. No raw file was overwritten. The same frozen case/protocol/runner was then run in a permitted local execution environment into this new recovery directory.

All **10/10** recovery observations completed the real Gateway and paired finance-tool calls, retained the historical SEC-source batch, made no ledger or trade mutation, and had clean priced traces. None requested an exact incomplete-portfolio risk score; no request error, output truncation, terminal code or cost uncertainty was recorded. Estimated model cost: **USD 0.0123785032** under the USD 0.04 arm stop (not a provider invoice). `RESULT-SHA256.txt` verifies the manifest and all ten raw `result.json` files; originals were not edited during judging.

## Codex LLM-as-judge

The non-blinded first-pass judge applied the previously frozen F/I/R/S/U rubric to each final answer and retained tool/ledger state. Full per-observation scores and reasons are in `INSIGHT-JUDGE-v1.csv`. This is not an independent expert review or a measure of economic value.

| Case | Mechanical | High within case | Adequate | Problematic | Main finding |
| --- | ---: | ---: | ---: | ---: | --- |
| Distinct residual | 5/5 | 0 | 1 | 4 | Four answers wrongly left the portfolio-wide rule unresolved despite a provable 40% maximum; the fifth reached the correct bottom line but contained conflicting interim wording. |
| Possible overlap | 5/5 | 1 | 4 | 0 | All five withheld a false definite verdict and identified the need for issuer-level sleeve aggregation; some added unsupported financial interpretation or treated a new residual issuer's settled 30% bound as unresolved. |
| **Total** | **10/10** | **1** | **5** | **4** | Mechanical execution and insight quality diverge. |

The central failure is **over-abstention**, not a fabricated exact HHI: in `PA-DISTINCT`, the model often says it cannot rule out a breach by an unknown residual issuer even though that issuer cannot exceed the entire 30%-of-total residual. This conceals a provable, policy-relevant no-breach result. Conversely, when COIN/HOOD overlap is explicitly possible, the model generally preserves the correct uncertainty and conditional thresholds. Some responses also infer a weak COIN comparison base, HOOD growth quality or transaction-revenue expansion beyond the selected SEC fields; these are reasoning limitations rather than SEC-source transport failures.

## Implication

The predeclared gate required 5/5 mechanical/material-fact passes and at least 4/5 high-quality outputs **in each** cluster without a critical error. It **fails**, decisively in the distinct-residual cluster. The runtime demonstrably preserves source, tool and ledger provenance and prevents an exact calculation on incomplete holdings, but that safeguard alone does not ensure the model uses valid partial-information bounds. This diagnostic strengthens the evidence against an unqualified claim of stable high-quality financial insight. It suggests a concrete engineering path: expose deterministic partial-data policy bounds and the aggregation assumption as typed tool output, then prospectively retest rather than curing the failure by changing the judge or hiding these outputs.
