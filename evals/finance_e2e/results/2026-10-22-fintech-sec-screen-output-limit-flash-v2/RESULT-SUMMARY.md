# Real-source FinTech screening holdout: v2 result

## Integrity and scope

The case, protocol, official SEC exhibit bytes, offline adapter, prompt, rubric, runner, plugin, model, gateway binary and template DB were hashed in `manifest.json` before the first model observation. `RESULT-SHA256.txt` verifies the manifest and all 15 raw `result.json` files. The three source SHA-256 values were checked during preflight and on every screen-tool invocation. The selected disclosures are [Coinbase Q3 2024](https://www.sec.gov/Archives/edgar/data/1679788/000167978824000186/q324shareholderletter.htm), [Robinhood Q3 2024](https://www.sec.gov/Archives/edgar/data/1783879/000178387924000295/q32024robinhoodexhibit991.htm) and [Block Q3 2024](https://www.sec.gov/Archives/edgar/data/1512673/000119312524253135/d835206dex991.htm). This was an **offline historical SEC-source adapter** invoked through the real `finance-tools__screen_stocks` tool and real Gateway/ledger; it was not live market data, a same-day peer ranking or an investment-return test.

The v1 arm stopped at **5/15** planned observations after HOOD-r2 hit the 2,500-token per-call output limit (`finish_reason=length`, `cost_uncertain_sequences=[3]`), with no thesis persisted for that observation. Its five original results are preserved and SHA-locked in the v1 directory; four passed mechanical checks. The separately predeclared v2 arm changed only the per-call output limit to **5,000 tokens**. The old failure was not erased, retried inside v1 or combined into a favorable denominator.

## Execution and cost

All **15/15** v2 observations completed paired model/tool calls without request errors, output truncation, terminal codes, unpriced usage or cost-uncertain sequences. All ten retained COIN/HOOD observations persisted exactly one historical preliminary, source-linked thesis; all five rejected SQ observations persisted none. No alerts or trades were created. The deterministic screen oracle was correct for each case: COIN's matched Q3 total-revenue values imply +78.8% YoY; HOOD reports +36% total net revenue YoY; SQ reports +6% total net revenue YoY and is rejected by the fixed >=20% rule. SQ's +19% gross-profit growth is not substituted for the top-line criterion.

Estimated v2 model cost was **USD 0.0229430992**, below the USD 0.08 arm cap; v1's stopped run added an estimated USD 0.0077139776. The combined estimate is USD 0.0306570768, not a provider invoice. These arms are distinct and are **not pooled** for a reliability claim.

## Codex LLM-as-judge content audit

The separate `INSIGHT-JUDGE-v1.csv` records F/I/R/S/U scores, reasons and critical-error codes for every v2 response and persisted state. The judge read source packet and results after generation and was not independently blinded or a finance expert.

| Issuer | Mechanical pass | High within case | Adequate | Problematic | Main finding |
| --- | ---: | ---: | ---: | ---: | --- |
| COIN | 5/5 | 3 | 2 | 0 | All identify the YoY +78.8% versus QoQ -17% / transaction -27% tension; some assert an unestablished “weak” prior-year base. |
| HOOD | 5/5 | 2 | 2 | 1 | Regulatory-accrual and crypto-mix risks are often useful; r5 wrongly carries an operating-expense accrual effect into a top-line revenue-growth question. |
| SQ | 5/5 | 0 | 4 | 1 | All correctly reject the +6% top-line result despite +19% gross-profit growth; several over-infer a bitcoin-driven mix shift without a packet-level margin bridge, decisively so in r5. |
| **Total** | **15/15** | **5** | **8** | **2** | Workflow completion and research quality diverge. |

The precommitted within-issuer stability gate (5/5 execution/material facts and >=4/5 high in **each** cluster without critical error) **fails in all three clusters on insight quality**. These are correlated repeats of only three frozen issuer cases, so 15/15 mechanical completion is not a general population reliability estimate. Nor do five within-case high labels prove financial value, predictive power or stable high-quality insight.

## Engineering and research interpretation

The v1-to-v2 contrast supports a narrow finding: a 2,500-token output ceiling was implicated in one HOOD workflow abort, and increasing it to 5,000 was followed by clean completion in a fresh full arm. This is not a randomized causal estimate and does not explain or repair the two remaining **reasoning** errors. The source-locked adapter, ledger and tool traces make those errors auditable, but the runtime's mechanical success cannot certify the model's causal or accounting interpretation.

The agent was asked to identify counterpoints, and the adapter supplied selected figures rather than a full research packet. Therefore the responses demonstrate source-grounded workflow behavior under this task design, not unaided discovery of investment insights. Before claiming stable high-quality insight across workflows, a separately frozen real-source portfolio-risk scenario, stronger accounting/inference checks and ideally blinded finance-domain adjudication are still needed. The current evidence does **not** justify the broad claim.
