# Four-Company Financial Agent Runtime Pilot (R7, Final Calibrated Run)

## 1. Research Objective

This experiment evaluates whether the FastClaw multi-agent runtime can produce evidence-grounded financial research-state updates from frozen SEC disclosures while preserving provenance, restricting arithmetic to predeclared methods, and preventing unverified trading actions. It also compares the coordinated team with evidence-matched solo and oracle baselines.

The experiment measures research-process integrity and orchestration behavior. It is not an investment-performance backtest, an earnings forecast, or evidence that the system generates excess returns.

## 2. Benchmark Defects Diagnosed and Corrected

| Observed defect | Root cause | Correction | Validity implication |
|---|---|---|---|
| The AMD task requested a Data-Center-led growth assessment, but the evidence ledger omitted the corresponding segment facts. | Dataset validation required only a minimum fact count and did not check whether the evidence set was sufficient for the task's substantive objective. | Added independently identified Data Center revenue, Data Center year-over-year growth, Gaming year-over-year change, and the predeclared Data Center revenue-share calculation. | Safe abstention is no longer incorrectly treated as full completion of the AMD task. |
| Intel's external-revenue conclusion relied on a ratio that had not been declared by the methodology contract. | The original calculation schema supported inter-observation changes but not same-period ratios. | Added a validated `ratio_percent` calculation, `INTC-2023-EXT-SHARE = 953 / 18,910 = 5.0%`, with named evidence inputs and deterministic rounding. | The coordinator no longer needs to invent an intermediate ratio or operating margin. |
| NIKE governance reasoning cited true filing disclosures without independent evidence identifiers. | Governance rationale was free text and was not structurally linked to source facts or methodology outputs. | Added source facts for the 110-basis-point gross-margin increase, the 8% NIKE Direct decline, and the 10% NIKE Brand Digital decline; every state rule now declares `basis_evidence_ids`. | Every policy-relevant claim can be traced to a specific evidence item. |
| Prompt instructions alone did not prevent undeclared arithmetic. | The runtime had no machine-enforced numeric authorization contract. | Added per-case authorized numeric values and runtime grounding checks for team and all baselines. | Intermediate values and undeclared derived values now fail the attempt rather than relying on model self-policing. |
| Correct outputs were initially rejected when numbers appeared in descriptive parentheses or Unicode-hyphenated SEC identifiers. | The numeric grader treated every opening parenthesis as an accounting negative and did not normalize Unicode hyphens before removing accession numbers, document labels, and evidence IDs. | Accounting-negative inference now depends on the authorized value set, and structural identifiers are normalized before numeric extraction. Regression tests cover both cases. | The final R7 metrics exclude the false failures observed during grader calibration. |

Runs R2 through R6 are retained as benchmark-development and grader-calibration artifacts. They must not be used for comparative inference. R7 is the first run in which the corrected evidence ledger, calculation contract, numeric authorization policy, and structural-identifier normalization were active together.

## 3. Data Provenance and Integrity Controls

- Primary authority: SEC EDGAR filing artifacts only.
- Filing type for the four evaluated episodes: Form 8-K, Exhibit 99.1.
- Frozen corpus: 16 files, 19,535,026 bytes.
- Retrieval timestamp: 2026-08-01T17:13:57+00:00.
- Source manifest SHA-256: `7162fc1560e043789697eed793d501c44a6a6e8ec981ac58a256a73c484b1699`.
- Source lock SHA-256: `a4d4b4dc3be440238e3d428d60d04fb4a4a9d21d8c0b4eec4cb313e2e181fe22`.
- Evidence ledger SHA-256: `a5fb9e238b20681f30270b2079c68eb41aecd8b2fc9644b7850682cda9a76621`.
- Offline lock verification: all cached files matched their recorded byte lengths and SHA-256 hashes.
- Mechanical fact audit: 44 of 44 encoded facts were present in their linked locked SEC artifacts; no encoded fact was absent.

The mechanical audit verifies that each encoded value or categorical disclosure occurs in the locked source artifact. It does not independently prove complete accounting-semantic equivalence, XBRL concept selection, period alignment, or management-definition comparability.

Official evaluated filing artifacts:

- NVIDIA Q1 FY2025: `https://www.sec.gov/Archives/edgar/data/1045810/000104581024000113/q1fy25pr.htm`
- AMD Q2 2024: `https://www.sec.gov/Archives/edgar/data/2488/000000248824000121/q22024991.htm`
- Intel restated Foundry reporting: `https://www.sec.gov/Archives/edgar/data/50863/000005086324000068/a04022024form8-kexhibit991.htm`
- NIKE Q4 FY2024: `https://www.sec.gov/Archives/edgar/data/320187/000032018724000028/q4fy24exhibit991er.htm`

## 4. Experimental Design

- Cases: `FSEC-NVDA-01`, `FSEC-AMD-01`, `FSEC-INTC-01`, and `FSEC-NKE-01`.
- Repetitions: one per case.
- Coordinator model: `deepseek/deepseek-v4-pro`.
- Specialist models: `deepseek/deepseek-v4-flash`.
- Team topology: one coordinator and three parallel specialists for source extraction, deterministic methodology, and versioned governance.
- Baselines: `solo_open_book`, `solo_two_pass`, `team`, and `oracle_team`.
- Evidence fairness: every condition receives the same substantive evidence; only the team condition invokes runtime specialists.
- Safety contract: no condition may authorize or recommend a trade.
- Numeric contract: outputs may reproduce source values, version values, period years, and declared calculation results only.
- Raw report SHA-256: `d252bec97a1a8c20d9afb8077eba5d1feebacd7025504656dc680df37c042643`.
- Generated suite SHA-256: `cb3fb6f30fcbe90bf6a705cb777f7a1b8fddf87870e37d1859a87c6e3b3269e8`.

## 5. Final Quantitative Results

| Metric | R7 result |
|---|---:|
| Team success rate | 100% (4/4) |
| Solo open-book success rate | 100% (4/4) |
| Solo two-pass success rate | 100% (4/4) |
| Oracle-team success rate | 100% (4/4) |
| Fair collaboration gain | 0 percentage points |
| Delegation F1 | 100% |
| Contribution utilization | 100% |
| Contribution-item coverage | 100% |
| Team grounding accuracy | 100% |
| Evidence-ID retention | 100% |
| Unauthorized numeric values | 0 |
| Team latency P50 / P95 | 37.766 s / 40.195 s |
| Team tokens | 49,847 |
| Team estimated cost | USD 0.009994 |
| Total experiment tokens | 110,324 |
| Total estimated cost | USD 0.045400 |

The team completed all tasks with perfect routing, contribution use, provenance retention, and numeric grounding. However, all evidence-matched baselines also achieved 100% success. The fair collaboration gain is therefore zero. The experiment validates runtime integrity on these four tasks but does not demonstrate that multi-agent orchestration improves answer correctness.

Relative to `solo_open_book`, the team used 330.8% more tokens, cost 55.2% more, and had 35.5% higher average latency. Relative to `solo_two_pass`, the team used 42.1% more tokens but cost 51.8% less and reduced average latency by 59.3%, because the specialists ran concurrently on the lower-cost Flash model. These comparisons are descriptive and must not be generalized from four single-repetition cases.

## 6. Company-Level Financial Results

### NVIDIA

The evidence ledger contains Q1 FY2025 revenue of USD 26,044 million, GAAP gross margin of 78.4%, and Data Center revenue of USD 22,600 million. The predeclared calculation yields an 86.8% Data Center revenue share. The runtime initialized an active margin-watch state without adding an undeclared value or authorizing a trade.

### AMD

The corrected evidence ledger contains revenue of USD 5,835 million, GAAP gross margin of 49%, Data Center revenue of USD 2,834 million, Data Center year-over-year growth of 115%, Gaming revenue of USD 648 million, and a 59% Gaming decline. The predeclared Data Center share is 48.6%. The runtime can now complete the requested Data-Center-led baseline rather than safely abstaining because of missing benchmark evidence.

### Intel

The evidence ledger contains Foundry segment revenue of USD 18,910 million, Foundry operating income of negative USD 6,955 million, and external Foundry revenue of USD 953 million. The methodology contract explicitly computes external revenue as 5.0% of segment revenue. No operating-margin percentage or implied internal-revenue value is permitted unless separately declared.

### NIKE

The evidence ledger contains revenue of USD 12,606 million, GAAP gross margin of 44.7%, a 110-basis-point gross-margin increase, an 8% decline in NIKE Direct, and a 10% decline in NIKE Brand Digital. The governance state cites the three policy-relevant evidence IDs directly, closing the earlier provenance-granularity gap.

## 7. Interpretation for a Financial-Technology Thesis

The corrected pilot supports a narrow conclusion: FastClaw can enforce a controlled financial research workflow in which source extraction, deterministic calculation, and governance state updates remain traceable and numerically bounded across a real multi-agent runtime. It does not support a claim that the team is more accurate than a strong evidence-matched single agent on simple initial-observation cases.

The zero collaboration gain is itself informative. The four tasks are saturated by the coordinator model once all evidence is visible. A stronger thesis experiment must create a genuine coordination requirement rather than merely distributing an easy synthesis task across agents.

## 8. Required Main-Study Extension

1. Run episodes 2 and 3 sequentially for each company so the system must compare disclosures and update persistent, versioned state.
2. Add stale-state rejection, conflicting disclosures, missing metrics, malformed specialist responses, timeout injection, and partial specialist failure.
3. Separate evidence retrieval, metric reconciliation, deterministic calculation, and governance decisions so no single prompt contains the full solution path.
4. Add XBRL concept, fiscal-period, accounting-basis, and segment-definition checks beyond string-level value presence.
5. Increase the number of companies, cases, and repetitions; report confidence intervals and paired case-level differences.
6. Evaluate decision consistency and safe abstention, not only answer-format milestones.
7. Keep investment outcomes outside the current claims unless a separately designed point-in-time backtest prevents look-ahead and survivorship bias.

## 9. Reproduction Artifacts

- Raw runtime report: `2026-08-02-pilot-r7-4cases.json`
- Post-run audit: `2026-08-02-pilot-r7-4cases-analysis.json`
- Source fact audit: `2026-08-02-source-fact-audit-r4.json`
- Source lock: `../source-lock.json`
- Evidence ledger: `../evidence.json`
- Generated suite: `../../multiagent-finance-sec-e2e.json`

## 10. Completed Longitudinal Extension

The required three-observation extension was subsequently implemented as `../../multiagent-finance-sec-hard.json`. It adds cross-observation chronology, declared calculation control, a contiguous `0→1→2→3` governance chain, and stale-candidate rejection for all four companies. In the frozen R3 primary run, Team and Solo Open-Book each passed 3/4 cases, producing zero fair collaboration gain. The harder suite removed the R7 ceiling effect but still did not establish incremental Team accuracy. The complete design, calibration exclusions, cost comparison, and failure analysis are recorded in `2026-08-02-hard-r3-final-summary.md`.
