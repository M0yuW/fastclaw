# FinTech SEC holdout: Codex LLM-as-judge second pass

## Scope and independence

This is a read-only second-pass assessment of the **15 frozen v1 observations** in `results/2026-10-22-fresh-fintech-sec-panel-flash-v1/`, using `INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md`. The result-file SHA-256 manifest and all six cached SEC exhibit hashes were verified before judgment. I read each final answer, its recorded workflow status, persisted review count, alert status and thesis actionability, compared material claims with `fresh_fintech_sec_panel_v1.json`, and spot-checked disputed facts against the official exhibits. The first-pass labels were visible to this judge, so this is **not blinded or independent adjudication**. No paid model call or new runtime observation was made. Original result, ledger, manifest and first-pass score files remain unchanged.

This judge assesses **decision-useful, source-bounded research explanation**, not forecast accuracy, profitable advice or a human expert's view of investment merit. A completed tool sequence is not itself a high-quality insight.

## Observation-level verdict

Scores are F (fact/number), I (inference), R (risk), S (state/action), U (research utility), each 0–2 or NA. `P` means problematic, `A` adequate within case, `H` high within case. The pointers identify the frozen `case_id-rN/result.json` file; the final response is `turns[0].response.choices[0].message.content` and the persisted state is under `state`.

| Observation | F/I/R/S/U | Verdict | Reason or decisive pointer |
| --- | --- | --- | --- |
| V-r1 | 2/1/1/2/1 | A | Correct opposing rate directions; falsely says the packet contains no recognition-timing clue despite the `prior_quarter` metric label. Mostly recaps inputs. |
| V-r2 | 2/1/1/2/1 | A | Correct values and state; treats the recognition basis as wholly unavailable and does not derive a clear service-lag implication. |
| V-r3 | 2/1/1/2/1 | A | Correct values; overstates uncertainty about the explicitly named prior-quarter basis. |
| V-r4 | 2/2/2/2/1 | A | Clean separation of current-quarter and prior-quarter YoY rates; implication remains a restatement of the divergence. |
| V-r5 | 1/1/1/2/1 | A | Assigns Q4 fact IDs to both baseline and event table columns, and calls timing absent despite the prior-quarter label; numerical values remain correct. |
| PYPL-r1 | 2/1/2/2/2 | A | Correct differences and mixed decision; “higher margin capture” is a qualified hypothesis, not established attribution. |
| PYPL-r2 | 2/2/2/2/2 | H | Separates rising TPV/TMD and GAAP margin from lower sequential revenue and weaker disclosed TPV YoY rate; states what further evidence would matter. |
| PYPL-r3 | 2/1/2/2/2 | A | Correct numeric comparison, but wrongly says the successive disclosed YoY rates are not evidence of deceleration in that YoY growth-rate series. |
| PYPL-r4 | 2/2/2/2/2 | H | Separates growth from margin signals, identifies revenue divergence and appropriate follow-up evidence. |
| PYPL-r5 | 1/2/2/2/2 | A | Says the entire selected packet is GAAP-basis, sweeping company operating KPIs into a GAAP label; direction and decision are otherwise sound. |
| MA-r1 | NA/NA/NA/0/0 | P | Iteration-budget terminal response; zero persisted reviews, alert still new, no completed analysis. |
| MA-r2 | 2/2/2/2/2 | H | Separates GAAP and adjusted margins and the two Q3 charges; avoids unsupported quantitative attribution; completed after rejected tool attempts. |
| MA-r3 | 1/1/2/1/2 | A | Calls the required metric set incomplete although it is complete; `needs_review` was recorded but thesis actionability stayed `available`, a distinction not made clear. |
| MA-r4 | NA/NA/NA/0/0 | P | Same terminal failure as r1: zero reviews and unacknowledged alert. |
| MA-r5 | 2/2/2/2/2 | H | Correct GAAP/adjusted divergence, bounded qualitative charge linkage and unresolved residual question; state matches ledger. |

**Second-pass tally:** 4 H, 9 A, 2 P; 13/15 completed tool/ledger workflows. The label totals agree with the first pass, though V-r5 is downgraded from F=2 to F=1 for its fact-ID imprecision. Per cluster: Visa 0 H / 5 A / 0 P; PayPal 2 H / 3 A / 0 P; Mastercard 2 H / 1 A / 2 P. These are **correlated repeats of three prompts**, not 15 independent financial situations. The precommitted gate in `FRESH-FINTECH-SEC-PANEL-PROTOCOL-v1.md` is not met.

## Case-design and source boundaries

- Visa: the selected fact ID names the *prior-quarter* payments-volume basis but the prompt packet omits the release's explicit sentence that Q4 service revenue is recognized on Q3 payment volume. Thus the answers' timing uncertainty is partly induced by the packet. The full [Q4 SEC exhibit](https://www.sec.gov/Archives/edgar/data/1403161/000140316124000053/q42024earningsrelease.htm) states the recognition rule and separately reports Q3-basis 7% and current-quarter 8%. Do not report that Visa failed to disclose timing, or attribute all five non-high ratings to model ability.
- PayPal: the [Q2](https://www.sec.gov/Archives/edgar/data/1633917/000163391724000096/pypl2q-24earningsrelease.htm) and [Q3](https://www.sec.gov/Archives/edgar/data/1633917/000163391724000108/pypl3q-24earningsrelease.htm) exhibits verify the selected revenue, TPV, transaction-margin-dollar and GAAP-margin facts. The selected packet contains no explanatory driver bridge, so qualified follow-up questions are useful, but a causal mechanism is not established by co-movement.
- Mastercard: the packet provides the two charges and margin levels but omits the [Q3 exhibit's GAAP-to-adjusted reconciliation](https://www.sec.gov/Archives/edgar/data/1141391/000114139124000200/ma09302024-exx991xearnings.htm), which actually quantifies the Q3 litigation and restructuring effects on operating margin as 2.4 and 2.6 percentage points. Therefore “the packet cannot quantify attribution” is accurate, but “the issuer disclosure cannot” would be false. The two workflow failures were malformed nested causal-claim submissions and exhausted iteration budget, not source-number errors.

## What this supports, and does not

The result supports a narrow claim that the runtime can persist source-linked financial research reviews and retain auditable state in many runs, while the guard rejects malformed causal claims. It does **not** support “stable high-quality financial insight”: the observed content is uneven even within each repeated case, two complex runs did not finish, and the selected packets and prompt supply much of the analytical structure. This assessment is by Codex, with known first-pass labels, and cannot replace blind expert scoring. The post-run Mastercard schema diagnostic is a separate same-case repair check, not part of this holdout denominator.
