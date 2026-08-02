# Four-Company Financial Agent Runtime Pilot (R2)

## 1. Study Scope

This pilot evaluates whether the FastClaw coordinator improves evidence-grounded financial research synthesis under controlled evidence visibility. It covers the first disclosure episode for NVIDIA, AMD, Intel, and NIKE. Each case is an initial state-establishment task; longitudinal state persistence is not tested in this run.

The experiment is a runtime and research-process evaluation, not an investment-performance backtest. Every case explicitly prohibits trade authorization.

## 2. Data Provenance and Integrity Controls

- Primary authority: SEC EDGAR filing artifacts only.
- Filing type: Form 8-K, Exhibit 99.1.
- Frozen corpus: 12 filing artifacts and 4 SEC Company Facts files, 19,535,026 bytes in total.
- Retrieval time: 2026-08-01T17:13:57+00:00.
- Source manifest SHA-256: `7162fc1560e043789697eed793d501c44a6a6e8ec981ac58a256a73c484b1699`.
- Source lock SHA-256: `a4d4b4dc3be440238e3d428d60d04fb4a4a9d21d8c0b4eec4cb313e2e181fe22`.
- Offline lock verification: all 16 cached files matched their recorded byte lengths and SHA-256 hashes.
- Mechanical fact audit: 38 of 38 encoded numeric values were found in their corresponding locked SEC filing artifacts; no encoded value was absent.

The mechanical fact audit establishes numeric presence, not complete accounting-semantic equivalence. Manual source review and metric-specific XBRL reconciliation remain necessary for publication-quality validation.

## 3. Experimental Design

- Cases: `FSEC-NVDA-01`, `FSEC-AMD-01`, `FSEC-INTC-01`, and `FSEC-NKE-01`.
- Repetitions: one per case.
- Coordinator: `deepseek/deepseek-v4-pro`.
- Specialists: `deepseek/deepseek-v4-flash`.
- Baselines: `solo_open_book`, `solo_two_pass`, `team`, and `oracle_team`.
- Evidence visibility: `solo_open_book`, `solo_two_pass`, `team`, and `oracle_team` receive the same substantive evidence; the team condition alone may invoke specialists.
- Raw report SHA-256: `9ed8634c4c9d873e16f69c82fccb635efb35816a4b6de1299465c4d1a3d4b074`.
- Suite SHA-256: `d95aab3f1980687b5797c81b01880b7017ef460da37c4ba6099e3f600a64acbe`.

## 4. Quantitative Results

| Metric | Result |
|---|---:|
| Team success rate | 100% (4/4) |
| Solo open-book success rate | 100% (4/4) |
| Solo two-pass success rate | 100% (4/4) |
| Oracle-team success rate | 100% (4/4) |
| Fair collaboration gain | 0 percentage points |
| Compute-matched collaboration gain | 0 percentage points |
| Delegation F1 | 100% |
| Contribution-item coverage | 100% |
| Evidence-ID retention | 100% |
| Unauthorized numeric values | 0 |
| Team latency P50 / P95 | 32.822 s / 37.345 s |
| Team tokens | 43,092 |
| Team estimated cost | USD 0.009992 |
| Total experiment tokens | 99,244 |
| Total estimated cost | USD 0.046601 |

All four conditions achieved the same task success rate. Therefore, this pilot does not provide evidence that multi-agent orchestration improves answer correctness for simple initial-observation tasks. It does show that the runtime can route three specialists correctly, preserve all specialist evidence identifiers, and synthesize the evidence without introducing a new numeric value.

Compared with `solo_open_book`, the team condition used 275.1% more tokens and cost 26.2% more, while average latency was 13.4% lower because specialist calls were parallelized and used the lower-cost Flash model. Compared with `solo_two_pass`, the team condition reduced average latency by 69.5% and cost by 53.6%, although it used 27.6% more tokens. These comparisons are descriptive because the sample contains only four single-repetition cases.

## 5. Company-Level Findings

### NVIDIA

The coordinator preserved revenue of USD 26,044 million, GAAP gross margin of 78.4%, and Data Center revenue of USD 22.6 billion. It initialized the non-trading margin-watch state and introduced no unauthorized numeric value. The case is suitable as an initial-state integrity test, but it does not yet test change detection.

### AMD

The coordinator correctly preserved total revenue of USD 5,835 million, GAAP gross margin of 49%, and Gaming revenue of USD 648 million. However, the task asks for a data-center-led growth baseline while the encoded source ledger omits the filing's Data Center revenue and year-over-year growth disclosure. The model safely reported insufficient evidence, but the grader still marked the case as successful. This is a benchmark-design gap: safe abstention and substantive task completion are not distinguished.

### Intel

The coordinator preserved Foundry segment revenue of USD 18,910 million, operating loss of USD 6,955 million, and external revenue of USD 953 million. It described external revenue as limited relative to segment revenue, but the benchmark did not predeclare the corresponding ratio calculation. The conclusion is directionally supported by the filing, yet the methodology contract should explicitly define the ratio before using it as a governed financial signal.

### NIKE

The coordinator preserved revenue of USD 12,606 million, GAAP gross margin of 44.7%, and a 10% year-over-year decline in NIKE Brand Digital. Its governance rationale also referred to gross-margin improvement and a NIKE Direct decline. Those claims are present in the SEC filing, but they were not represented as independently identified source facts in the specialist evidence ledger. This is a provenance granularity gap rather than a factual fabrication.

## 6. Interpretation

The runtime passed the narrow orchestration-integrity objective, but the pilot is too easy to establish a positive collaboration effect. The zero fair collaboration gain is the central empirical result and must not be reframed as an orchestration improvement. The current cases mainly test evidence transport, tool routing, bounded policy output, and citation retention.

For a financial-technology thesis, the next experiment should shift from initial observations to longitudinal disclosure updates, where deterministic changes, versioned state transitions, conflicting signals, stale-state rejection, missing disclosures, and specialist failures can affect the research decision.

## 7. Required Corrections Before the Main Study

1. Add AMD Data Center revenue and disclosed growth facts, then distinguish safe abstention from full task completion.
2. Add a predeclared within-period calculation schema for segment shares and loss margins; do not permit the coordinator to invent ratios ad hoc.
3. Promote every policy-relevant NIKE claim to a source fact with its own evidence ID.
4. Add semantic source anchors or XBRL concepts so validation checks the metric-value pairing, not only numeric presence.
5. Run episodes 2 and 3 sequentially with persistent version checks and stale-version fault injection.
6. Increase repetitions and report confidence intervals before making any comparative claim.

## 8. Reproduction Artifacts

- Raw runtime report: `2026-08-02-pilot-r2-4cases.json`
- Post-run audit: `2026-08-02-pilot-r2-4cases-analysis.json`
- Source fact audit: `2026-08-02-source-fact-audit.json`
- Source lock: `../source-lock.json`
- Evidence ledger: `../evidence.json`
- Generated suite: `../../multiagent-finance-sec-e2e.json`
