# BNY first-batch claim adjudication v1 — unblinded diagnostic

This reviews all five frozen BNY observations against `INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md`. It is an **unblinded Codex self-review**, not independent finance-professional or blinded LLM judging. Raw `result.json`, null `quality_score`, and `RESULT-SHA256.txt` remain unchanged. Final prose and persisted review rationale are both in scope.

## Source and claim inventory

`audit_bny_holdout_facts_v1.py` was rerun: ten selected cells in the locked Q2/Q3 SEC earnings exhibits and all five deterministic deltas match. The Q2 source hash is `c9f76d07c310f0b49775a477bbd51f73b0f8a19279a11ae20f5b425b0f25dbc6`; Q3 is `87982c2dd1374794ddeea6a58b0e432866495b963abb3964213bb22fb8a34e0d`. The case ID uses BNY; the actual thesis and alert symbol is BK. The answers identify this rather than silently altering the records.

| Material claim | Frozen evidence/arithmetic | Adjudication across runs |
| --- | --- | --- |
| Scope and basis | Same issuer; sequential Q2 ended 2025-06-30 and Q3 ended 2025-09-30; selected GAAP USD million rows, not a complete income statement. | Correctly described in all five; no YoY-to-sequential confusion. |
| Total revenue | `BNY-Q2-REV=5028`, `BNY-Q3-REV=5081`: **+53**, +1.05% relative. | Correct numeric levels and changes in all five. |
| Fee revenue | `BNY-Q2-FEE=3641`, `BNY-Q3-FEE=3637`: **−4**, −0.11% relative. | Correct in all five. |
| Net interest income | `BNY-Q2-NII=1203`, `BNY-Q3-NII=1236`: **+33**, +2.74% relative. | Correct in all five. But +33 is **62.3%**, not 100%, of the +53 total-revenue change. The two listed components sum to +29, leaving **+24** unlisted revenue change, 45.3% of total. |
| Noninterest expense | `BNY-Q2-OPEX=3206`, `BNY-Q3-OPEX=3236`: **+30**, +0.94% relative. | Correct in all five. Revenue less this expense increases by +23, but the packet cannot reconcile to common net income. |
| Common net income | `BNY-Q2-NETCOMMON=1391`, `BNY-Q3-NETCOMMON=1339`: **−52**, −3.74% relative. | Correct direction and amount in all five. The gap from revenue less noninterest expense is not explained; tax, provision, preferred dividends and other items are absent. |
| Research state | One review linked to the alert; `maintain`, active status, conviction 3, no hold, actionability available, alert acknowledged; no trade. | Actual persisted state and final claims agree in all five. This verifies execution, not the truth of every inference. |

The decisive distinction is **majority contribution versus exhaustive attribution**. NII +33 can be described as the largest *listed* contributor or 62.3% of the total gain. The packet does not support saying NII produced the *entire* +53 or that the missing +24 is immaterial. The five selected rows also do not establish a causal earnings bridge.

## Observation-level claim adjudication

| Observation | Exact material span in final answer or `state.theses[0].reviews[0].rationale` | Claim label and judgment |
| --- | --- | --- |
| BNY-r1 | Persisted: “the quarter's revenue growth came from net interest income rather than fees”; final says “the revenue increase is consistent with the net interest income increase” and carefully refuses to attribute the −52 common-income decline to a specific driver. Persisted text also says the earnings decline is “consistent with expense growth plus a fee mix that did not offset it.” | `bounded_hypothesis`: NII is the main listed positive line and fees fell, but the +24 unlisted change prevents an exhaustive revenue explanation; expense co-movement is not an earnings cause. The final caveat and unchanged decision contain the overstatement. I=1, not critical. |
| BNY-r2 | Final and persisted: “The revenue gain came entirely from net interest income (+33 of +53).” | `contradicted`: +33 cannot be the entire +53. The explicit arithmetic contradiction is material even though the answer later notes missing income-statement lines. F=0 and I=0; critical mix-attribution error. |
| BNY-r3 | Final: total revenue higher, “driven by net interest income”; persisted: revenue rose 53 “on higher net interest income (+33)” while fee −4; both refuse to attribute the −52 net-income decline. | `bounded_hypothesis`: “driven by” is defensible as the largest listed positive contributor, but it leaves 45.3% unlisted and never quantifies that material residual. I=1 for incomplete coverage, not a claim that NII is all of revenue growth. |
| BNY-r4 | Final: “entirely accounted for by net interest income (+33) plus a small residual”; persisted: “driven by NII +33.” | `contradicted` as worded: +33 is not the entirety of +53, and the unlisted +24 after fee −4 is not a small residual relative to +53. The answer does identify the unknown common-income bridge, but that does not cure the revenue-mix error. F=0, I=0; critical comparison/coverage error. |
| BNY-r5 | Final: growth “concentrated in net interest income (+33 of the +53 total)”; persisted: the increase is “attributable to net interest income, not fees”; both say the selected lines do not explain the common-income decline. | `bounded_hypothesis`: +33/53 is a genuine majority, and the final supplies both numbers. The persisted attribution should have said “main listed contributor” because +24 remains unlisted. I=1, noncritical. |

All five answers identify material uncertainty in the common-income bridge and seek provision, tax, preferred-dividend, segment/fee and comparable-period details. They do not claim to have placed a trade. Those are useful counterpoints, but they do not convert false revenue-mix arithmetic into a supported claim.

## Diagnostic scores and gate

| Observation | F | I | R | S | U | Critical error | Class |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| BNY-r1 | 2 | 1 | 2 | 2 | 2 | none found | adequate |
| BNY-r2 | 0 | 0 | 2 | 2 | 1 | entire-revenue attribution contradicts +33/+53 | problematic |
| BNY-r3 | 2 | 1 | 2 | 2 | 2 | none found | adequate |
| BNY-r4 | 0 | 0 | 2 | 2 | 1 | “entirely” and “small residual” contradict material +24 | problematic |
| BNY-r5 | 2 | 1 | 2 | 2 | 2 | none found | adequate |

Result: **0 high, 3 adequate, 2 problematic** under this intentionally strict, unblinded interpretation. The case fails the predeclared no-critical/4-high gate. A reviewer might score the “driven by” wording differently, but r2's explicit +33-of-+53 “entirely” claim independently fails the gate. The defect is in the generated explanation, not the locked SEC cells or the runtime's recorded tool/ledger execution.
