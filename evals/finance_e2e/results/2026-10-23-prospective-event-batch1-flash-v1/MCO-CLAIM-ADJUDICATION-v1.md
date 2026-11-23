# MCO first-batch claim adjudication v1 — unblinded diagnostic

This is an **unblinded Codex self-review** of all five frozen MCO observations under `INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md`. It is not a finance-professional rating or an independent LLM judge. The reviewer saw run IDs and mechanical outcomes; do not present these scores as blinded validation. The raw `result.json` files, `quality_score: null`, and `RESULT-SHA256.txt` remain unchanged. All five observations stay in the denominator.

## Evidence and claim inventory

The source auditor `audit_mco_holdout_facts_v1.py` was rerun and matched all eight selected SEC cells and four displayed-value deltas to the locked exhibits. Q2 source SHA-256 is `a38b443f026feb4beb955af3b6a5ad4350b3972b474fe1ba98a664b5ca30c46a`; Q3 is `b6e13cec25a77929c16fb40f81fd525c2ecfcdfb4a3d0484dd0dfe731fd2329b`. Each observation's material numeric table appears in `turns[-1].response.choices[0].message.content`; its persisted research judgment is `state.theses[0].reviews[0].rationale`. The following separately enumerated claim types were checked in **both locations** for r1–r5:

| Claim type | Evidence and arithmetic | Finding across five runs |
| --- | --- | --- |
| Source, basis, period | Q2/Q3 releases; same issuer, GAAP, USD million, quarters ended 2025-06-30 and 2025-09-30. | Supported. All five label their main comparison sequential, not year-over-year. |
| Revenue | `MCO-Q2-REV=1898`, `MCO-Q3-REV=2007`; +109, +5.74% relative. | Supported, including displayed rounding to ≈5.7%. |
| Total expenses | `MCO-Q2-EXP=1080`, `MCO-Q3-EXP=1090`; +10, +0.93% relative. | Supported, including ≈0.9%. |
| Operating income | `MCO-Q2-OPINC=818`, `MCO-Q3-OPINC=917`; +99, +12.10% relative. In each period revenue less expense equals operating income. | Supported. |
| Net income attributable to Moody's | `MCO-Q2-NETATTR=578`, `MCO-Q3-NETATTR=646`; +68, +11.76% relative. | Supported as a *movement*. The four selected facts do **not** reconcile operating income to attributable net income or establish the cause of +68. |
| Derived margins | Operating income/revenue 43.10%→45.69%, +2.59 percentage points; r5 also calculates attributable net income/revenue 30.45%→32.19%, +1.74 points. | Supported at the stated rounding; all five distinguish percentage points from relative percent and label the margins as derived. |
| Segment counterevidence | Q3 source anchor: Moody's Analytics **transaction** revenue declined 19% versus the **prior-year** period. This is a segment/sub-line YoY relative change, not the company's Q2→Q3 total change. | Supported and correctly scoped in all five. No answer nets the 19% against consolidated sequential revenue. |
| Research state | For r1–r5, the actual ledger has one linked review, `maintain`, active status, conviction 3, thesis version 2, no decision hold, and an acknowledged alert at version 2. `r4` records impact `positive`; the others `mixed`. | Final prose and persisted state match in each run. No trade, order, or valuation action appears in the retained trace. `positive` impact in r4 is not itself a false ledger claim because the adverse segment detail is disclosed and the thesis is not upgraded. |

The numeric rows above are a shared oracle, **not** a claim that the five prose outputs are identical. The observation-specific implication/risk/state claims were read individually:

| Observation | Exact material inference span and location | Adjudication |
| --- | --- | --- |
| r1 | Final §2: “revenue growth accompanied by much slower expense growth, so operating income and attributable net income grew faster than revenue”; persisted rationale makes the same relative-growth comparison. §3–5 explicitly says the segment decline can be masked, the mix is unquantified, and no cause is established. | `supported`: comparison of relative growth rates, not a claimed net-income bridge. Counterpoint and next evidence are decision-relevant. |
| r2 | Final *Supported implication*: revenue growing faster than expense “lifts both operating income and attributable net income”; persisted rationale likewise says the selected facts are “consistent with revenue growth outpacing expense growth, lifting operating and attributable net income.” The answer later says no causal attribution is recorded. | `bounded_hypothesis`, not fully supported: revenue−expense **arithmetically** explains the +99 operating-income move but not the +68 attributable-net-income move without below-operating lines. The later caveat limits harm, so I=1 rather than a critical causal error; do not describe the attributable-income lift as established. |
| r3 | Final §§3–6: faster revenue than expense growth and +12.1% operating/+11.8% attributable income are described as arithmetic observations; the Analytics −19% YoY is explicitly marked as a different basis and no driver is assigned. Persisted rationale has the same scope. | `supported` within the declared selected-fact scope. The line “consolidated growth is therefore not uniform across the business” is read as a warning against a universal breadth claim, **not** as a claim that Analytics transactions fell sequentially. |
| r4 | Final §3: revenue growth outpacing expenses “lifts operating income and attributable net income sequentially”; persisted rationale also says “lifting operating income and attributable net income.” Final §5 then says causation is unresolved. | `bounded_hypothesis`, not fully supported for attributable net income. The +99 operating-income identity is proven; the +68 attributable-income bridge is not. The explicit later limit and unchanged conviction prevent a critical-error classification, but I=1. |
| r5 | Final *Supported implication* states levels rose and expenses were nearly flat; *Material counterpoint* notes Analytics transaction weakness; *Evidence still needed* explicitly refuses a causal explanation. Persisted rationale calls margin expansion “consistent with,” not caused by, the expense/revenue relationship. | `supported`: implication, counterpoint, and evidence request are bounded by the source packet. |

All other material state assertions in final prose (review/alert IDs, source hashes, version changes, decision, conviction, and no trade) were compared with the corresponding `result.json` state and trace. Future review dates r1/r4 `2027-01-29`, r2 `2026-11-20`, and r3/r5 `2026-11-20T00:00:00Z` match the stored thesis. No missing source, response, review, or trace prevented assessment.

## Diagnostic scores and frozen case gate

| Observation | F | I | R | S | U | Critical error | Class |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| MCO-r1 | 2 | 2 | 2 | 2 | 2 | none found | high |
| MCO-r2 | 2 | 1 | 2 | 2 | 2 | none found | adequate |
| MCO-r3 | 2 | 2 | 2 | 2 | 2 | none found | high |
| MCO-r4 | 2 | 1 | 2 | 2 | 2 | none found | adequate |
| MCO-r5 | 2 | 2 | 2 | 2 | 2 | none found | high |

Result: **3 high + 2 adequate**. The source/fact and execution requirements pass in this diagnostic review, but the *predeclared* MCO cluster gate requires **at least four high and at most one adequate**. Therefore **MCO does not pass that strict quality gate** under this adjudication. This is not an SEC fact error and not an infrastructure error; it is sensitivity to inference wording in two outputs. The decision is not repaired by a retrospective prompt change, a dropped repeat, or relabelling `mechanical_pass` as quality success.

An independent blinded reviewer could disagree about whether “lifts attributable net income” is shorthand for co-movement or a causal accounting bridge. That uncertainty must be shown rather than concealed: if both spans were judged fully bounded, MCO would become 5 high; if either were judged materially causal, it would score lower. The present self-review supplies a reproducible diagnostic, not final external construct validation. The other 20 first-batch observations still require the same full review before reporting a first-batch quality distribution.
