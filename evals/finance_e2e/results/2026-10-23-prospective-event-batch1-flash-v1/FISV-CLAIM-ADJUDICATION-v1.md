# FISV first-batch claim adjudication v1 — unblinded diagnostic

All five frozen FISV final answers and persisted review rationales were checked under `INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md`. This is an **unblinded Codex diagnostic**, not independent finance-professional judging. Raw observations, null `quality_score`, and the original hash manifest remain unchanged. `audit_fisv_holdout_facts_v1.py` rechecked all eight selected cells and four Q3−Q2 changes against the locked SEC releases.

## Material claim oracle

| Claim | SEC-selected values and deterministic arithmetic | Judgment |
| --- | --- | --- |
| Period/basis | Same issuer, Q2 ended 2025-06-30 vs Q3 ended 2025-09-30; USD million. Revenue, operating income and net income attributable are GAAP; adjusted net income is **non-GAAP**. | All five answers distinguish sequential comparison and separate the bases. |
| Revenue | `FISV-Q2-REV=5516`, `FISV-Q3-REV=5263`: −253, −4.59% relative. | Correct in all five. |
| Operating income | `FISV-Q2-OPINC=1696`, `FISV-Q3-OPINC=1436`: −260, −15.33% relative. | Correct levels/delta in all five. Derived operating margin 30.75%→27.28%, −3.46 percentage points. |
| Net income attributable | `FISV-Q2-NETATTR=1026`, `FISV-Q3-NETATTR=792`: −234, −22.81% relative. | Correct in all five. |
| Adjusted net income | `FISV-Q2-ADJNET=1364`, `FISV-Q3-ADJNET=1105`: −259, −18.99% relative. | Correct in all five. The adjusted-minus-GAAP net-income gap narrows 338→313, but the adjustment components are not in the packet. |
| Operating bridge | Revenue less operating income, calculated on the **same GAAP basis**, is 3820 in Q2 and 3827 in Q3, +7. Thus the −260 operating-income delta decomposes as **−253 revenue −7 implied operating costs**. | This derived identity is crucial: a larger *relative percentage* decline in operating income does not prove that margin/cost change contributed more **dollars** than revenue decline. The selected facts do not break the +7 cost change into drivers. |
| Management statement | The release uses qualitative “guidance reset” / “current performance is not where we want it” language; the packet has no old/new numeric guidance range. | Answers correctly attribute this as management framing rather than quantified causal evidence. |
| Ledger | r1 `maintain`/3; r2 `downgrade`/2; r3 `needs_review`/3; r4–r5 `downgrade`/2. Each has one linked review and acknowledged alert, no trade. | r1/r2/r4/r5 final descriptions match their persisted states. **r3 is not actually blocked** despite its `needs_review`: `decision_hold=false`, `actionability=available`. |

## Observation-specific inferences and risks

| Observation | Material span and location | Adjudication |
| --- | --- | --- |
| r1 | Final and persisted call the sequential deterioration “profitability-led, not revenue-led,” noting −15.3% operating income versus −4.6% revenue; they also explicitly say no specific driver is established. | `bounded_hypothesis`: defensible only as a **relative-rate** description. As a dollar explanation, −253 of −260 comes from revenue, so the phrase is misleading without that distinction. I=1, noncritical because the answer refuses a causal driver and keeps conviction unchanged. |
| r2 | Final/persisted list all four declines, show derived margins and say the pattern is *directionally consistent* with, but does not quantify, the management guidance reset. The downgrade cites broad deterioration while seeking full guidance/reconciliation. | `supported` within the selected-fact scope. Changing conviction is a research judgment, not an asserted accounting cause; it is explicit and source-linked. |
| r3 | Final *Supported implication*: “margin compression rather than revenue decline as the larger contributor to the profit drop.” Its final and persisted review also assert `needs_review` but the actual thesis is still actionable. | `contradicted` as a dollar driver: the same-basis operating bridge is −253 revenue and −7 implied costs, not primarily margin/cost. I=0. Separately, `needs_review` without a blocked ledger is a critical state/actionability inconsistency, S=0. This observation fails even if the margin wording is read generously. |
| r4 | Final says “margin compression is larger in percentage-point terms than the revenue decline”; persisted rationale states the correctly rounded margin and revenue moves and calls the reset only directionally consistent. | `bounded_hypothesis`: the final compares **percentage points of a ratio** with **relative percentage decline in dollars**, which are unlike measures; no valid magnitude ranking follows. I=1, while the reported numeric facts themselves are correct. The downgrade is not dependent on that ranking. |
| r5 | Final and persisted compare relative declines, explicitly keep GAAP and non-GAAP separate, state the adjustment gap cannot be explained, and request prior-year, segment, cash-flow and guidance evidence. | `supported`: the inference is a bounded deterioration finding and a documented downgrade, not a causal cost bridge. |

All answers identify missing prior-year comparisons, adjustment reconciliations and actual guidance figures; those counterpoints matter. The r3 final's correct statement that it recorded `needs_review` is insufficient because the persistent ledger would still permit downstream decision use. The finance plugin's subsequent hold-rule correction was made **after** this batch and cannot repair or re-score r3.

## Diagnostic scores and strict case gate

| Observation | F | I | R | S | U | Critical error | Class |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| FISV-r1 | 2 | 1 | 2 | 2 | 2 | none found | adequate |
| FISV-r2 | 2 | 2 | 2 | 2 | 2 | none found | high |
| FISV-r3 | 2 | 0 | 2 | 0 | 0 | false operating-profit attribution; unblocked `needs_review` | problematic |
| FISV-r4 | 2 | 1 | 2 | 2 | 2 | none found | adequate |
| FISV-r5 | 2 | 2 | 2 | 2 | 2 | none found | high |

Result: **2 high, 2 adequate, 1 problematic**. The case fails the predeclared all-five/no-critical/4-high gate. The FISV-r3 state error is an end-to-end runtime/plugin failure in the frozen batch; the margin attribution error is generated-analysis reasoning. Neither is a discrepancy in the locked SEC selected rows. Different defensible ratings of r1/r4 do not cure the r3 failure.
