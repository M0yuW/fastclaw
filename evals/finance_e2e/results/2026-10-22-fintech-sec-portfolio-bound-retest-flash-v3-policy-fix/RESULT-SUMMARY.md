# Partial-portfolio policy-bound tool: same-case retest

## What changed and what did not

The v2 diagnostic found that an incomplete holdings map can still support a **provable single-issuer policy bound**, yet the agent repeatedly withheld it. This engineering retest reused the same two fictional 40/30/30 cases, historical Q3 2024 COIN/HOOD/SQ SEC-source packet, Flash model, ten fresh sessions and the same content rubric. It is **not** a new-issuer holdout, randomized causal comparison, live portfolio or investment-performance test.

Finance-tools v0.3.1 added `portfolio_policy_bound`, which takes known issuer line-item percentages, a same-denominator long-only remainder, an explicit overlap boolean and a strict `>50%` limit. It returns one of `breach_proven`, `no_breach_proven` or `indeterminate` plus issuer bounds, while explicitly refusing to compute HHI or full portfolio risk. The original `portfolio_risk` incomplete-holdings refusal remains intact. The Go `finance-workflow-pilot` tool allowlist was updated to expose the new tool; Python guard tests and Go policy/Gateway tests passed before the successful run.

The first v3 result directory, `2026-10-22-fintech-sec-portfolio-bound-retest-flash-v3/`, remains an **integration failure arm**: 10/10 outputs are retained as `needs_review`, because the then-used Gateway binary did not permit the new tool. The model attempted the call, the Gateway returned `Unknown tool`, and the agent often fell back to the old tool, which correctly refused incomplete inputs. Its estimated cost was USD 0.0135882712. Those failures were not overwritten or recoded as successes. This separate directory used a rebuilt, policy-corrected binary under the otherwise same frozen v3 protocol.

## Execution and content audit

All **10/10** policy-corrected observations completed paired `finance-tools__screen_stocks` and `finance-tools__portfolio_policy_bound` calls with the exact frozen inputs, clean priced traces and no ledger or trade mutation. The tool returned `no_breach_proven` in all five distinct-residual cases and `indeterminate` in all five possible-overlap cases. No exact `portfolio_risk` call was made, and no exact HHI was returned. Estimated model cost was **USD 0.0129590160**, below the USD 0.04 arm cap; this is not a provider invoice. The manifest and ten raw results pass `RESULT-SHA256.txt` verification.

Codex then applied the pre-existing F/I/R/S/U rubric to final answers and retained tool/ledger traces. Detailed non-blinded, non-independent LLM-as-judge reasons are in `INSIGHT-JUDGE-v1.csv`:

| Case | Mechanical | Correct policy conclusion | High within case | Adequate | Problematic |
| --- | ---: | ---: | ---: | ---: | ---: |
| Distinct residual: no breach possible | 5/5 | 5/5 | 2 | 2 | 1 |
| Possible overlap: verdict indeterminate | 5/5 | 5/5 | 1 | 4 | 0 |
| **Total** | **10/10** | **10/10** | **3** | **6** | **1** |

This is a **narrow improvement** over v2's distinct-residual responses, only one of which reached the unambiguous no-breach bottom line; the new tool-supported arm did so in all five. It is consistent with the deterministic bound making a previously missed implication available to the agent, but prompt/tool exposure and binary policy changed together. The observed contrast is not an isolated causal estimate, and the same cases were reused.

The content gate still **fails** (required >=4/5 high in each cluster and no critical error). `PA-DISTINCT-r5` asserts that *both* issuers' crypto-sensitive revenue lines outgrew overall top-line revenue; the selected COIN packet contains total-revenue YoY and transaction-revenue QoQ, not a matched COIN crypto-specific YoY line, so that is an unsupported core inference. Other noncritical overreach includes describing COIN's prior-year base as weak without history, treating a pretax crypto-investment loss as a directly comparable fraction of after-tax net income, and reading a lower HOOD regulatory accrual as established earnings-quality improvement. The tool fixed policy arithmetic support, not narrative inference discipline.

## Project-report implication

The credible engineering claim is that the runtime now composes historical SEC-source retrieval with a typed partial-information policy-bound tool, preserves exact-risk refusal and auditable state, and reaches the intended strict-threshold answer in both tested semantics. The credible limitation is that this **does not establish stable high-quality financial insight**: only 3/10 answers were high under the prospective content rubric, one had a critical unsupported inference, the issuers/cases were reused, and no independent expert or return-validity test exists. The complete observations and the prior integration failure both belong in the engineering evidence; neither may be silently omitted from a broad reliability claim.
