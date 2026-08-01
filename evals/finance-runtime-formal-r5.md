# Frozen Post-Fix Confirmation of a Coordinator–Specialist Runtime for Financial Research

## Abstract

This report evaluates FastClaw's coordinator–specialist runtime on six fixed-evidence financial research tasks after remediation of grader, telemetry, error-propagation, tool-execution, identity, and SQLite concurrency defects identified during independent review. Four modes were executed once with isolated sessions: Solo Open-Book, Solo Two-Pass, Team, and Oracle Team. The coordinator used `deepseek/deepseek-v4-pro`; three real runtime specialists used `deepseek/deepseek-v4-flash`.

Team, Solo Open-Book, and Solo Two-Pass each passed 5/6 cases (83.3%); Oracle Team passed 4/6 (66.7%). Fair collaboration gain and compute-matched gain were both 0.0 percentage points. All 24 baseline executions completed without infrastructure error, all 54 model calls had pricing coverage, and no configured grounding assertion was violated. Team cost USD 0.008335 with P50/P95 latency of 21.30/22.49 seconds. The result supports the engineering feasibility of auditable routing, bounded evidence synthesis, and role-level cost attribution, but it does not show a decision-quality advantage from multi-agent orchestration.

This run is a frozen post-fix confirmation rather than an independent validation experiment. Earlier outputs informed narrow rubric and matcher repairs; the suite contains six cases and one repetition; no holdout or confidence interval is available.

## 1. Research Questions

1. Does Team execution outperform a one-pass Solo model when evidence visibility is matched?
2. Does Team execution outperform a two-pass Solo model when synthesis opportunity is matched more closely?
3. Does the runtime preserve configured evidence and governance constraints without infrastructure errors?
4. What token, latency, and estimated-cost trade-off is attributable to each execution mode and runtime role?

The experiment does not measure market forecasting, stock-selection alpha, realized return, Sharpe ratio, or an official external benchmark score.

## 2. Experimental Design

### 2.1 Cases

| Case | Application | Deterministic requirement |
|---|---|---|
| `earnings-catalyst-review` | Filing-based catalyst review | Preserve filing facts and bounded thesis update; no trade authorization. |
| `thesis-invalidation-review` | Explicit customer-loss threshold | Invalidate versioned thesis and request fresh review; no target price. |
| `duplicate-event-alert` | Event deduplication | Reuse the alert, increment occurrence state, and review once. |
| `incomplete-screening-data` | Completeness-aware screening | Exclude the candidate, request source refresh, and prohibit imputation. |
| `portfolio-concentration-response` | Portfolio risk governance | Propose a reversible reduction and mandatory revalidation. |
| `contradictory-primary-evidence` | Conflicting disclosure review | Preserve disagreement, retain uncertainty, and request clarification. |

### 2.2 Modes

| Mode | Evidence | Model passes | Delegation |
|---|---|---:|---|
| Solo Open-Book | Same anonymous evidence packet as Team | 1 | Disabled |
| Solo Two-Pass | Same anonymous evidence packet as Team | 2 | Disabled |
| Team | Evidence returned by three real runtime specialists | 2 coordinator calls plus 3 specialist calls | Enabled |
| Oracle Team | Named specialist reports supplied directly | 1 | Perfect delivery assumed |

Outcome success requires the configured milestones and grounding assertions to pass. Infrastructure failures are recorded as `errored` and excluded from the success denominator. Gains are valid only when the compared modes contain the same number of successfully evaluated paired attempts.

### 2.3 Reproducibility Metadata

- Date: 2026-08-01
- Suite: `evals/multiagent-finance-runtime.yaml`
- Suite SHA-256: `4fbf54eca61dc7363342ea1db364cb84426e1541937a99c1e1266dbfb3e5dc44`
- Raw artifact: `finance-runtime-formal-r5.json`
- Artifact SHA-256: `5366a91398ca575d303af56d62da179f2a3f1fb13a1d0f5aae5c1773debfbc00`
- Cases: 6
- Repetitions: 1
- Baseline executions: 24
- Model calls: 54
- Baseline errors: 0
- Pricing coverage: 100%
- Total wall-clock duration: 522.61 seconds

## 3. Results

### 3.1 Quality

| Mode | Passed | Success | Grounding assertions | Violations |
|---|---:|---:|---:|---:|
| Solo Open-Book | 5/6 | 83.3% | 44 | 0 |
| Solo Two-Pass | 5/6 | 83.3% | 44 | 0 |
| Team | 5/6 | 83.3% | 44 | 0 |
| Oracle Team | 4/6 | 66.7% | 44 | 0 |

- Fair collaboration gain, `Team − Solo Open-Book`: **0.0 pp**.
- Compute-matched gain, `Team − Solo Two-Pass`: **0.0 pp**.
- Legacy closed-book gain: **not computed** in this suite.

The configured grounding metric checks whether a set of forbidden assertions is made. It is not an exhaustive entailment judgment over every sentence.

### 3.2 Case-Level Outcome

| Case | Open Book | Two-Pass | Team | Oracle |
|---|---:|---:|---:|---:|
| Earnings catalyst | Pass | Pass | Pass | Pass |
| Thesis invalidation | Fail | Pass | Pass | Pass |
| Duplicate alert | Pass | Pass | Pass | Fail |
| Incomplete screening | Pass | Pass | Fail | Pass |
| Portfolio concentration | Pass | Fail | Pass | Fail |
| Contradictory evidence | Pass | Pass | Pass | Pass |

The only Team failure occurred on incomplete screening. The answer rejected the candidate, labeled the record insufficient, requested source refresh, and prohibited estimation. The local assertion matcher nevertheless required the refresh and anti-estimation terms within one bounded assertion window, while the answer placed them in separate sections. The machine-scored failure is retained rather than manually converted to a pass. This failure illustrates the trade-off between preventing cross-clause false positives and accepting semantically complete but structurally distributed answers.

### 3.3 Efficiency

| Mode | Prompt tokens | Cache read | Uncached prompt | Output tokens | Total tokens | Cost (USD) | Mean latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Solo Open-Book | 3,803 | 3,328 | 475 | 6,082 | 9,885 | 0.005510 | 13.65 s |
| Solo Two-Pass | 13,874 | 6,912 | 6,962 | 16,948 | 30,822 | 0.017798 | 42.65 s |
| Team | 30,222 | 27,264 | 2,958 | 10,997 | 41,219 | 0.008335 | 19.45 s |
| Oracle Team | 4,064 | 3,840 | 224 | 4,838 | 8,902 | 0.004320 | 11.32 s |

The provider reports cache-read tokens as part of prompt tokens; therefore `uncached prompt = prompt − cache read`, while total tokens remain the provider-reported `prompt + completion`. Cache reads are shown separately to prevent the low cached-input price from being confused with a lower token count.

Relative to Solo Open-Book, Team used 4.17 times as many total tokens, cost 51.3% more, and had 42.5% greater mean latency, with no measured quality gain. Relative to Solo Two-Pass, Team used 33.7% more tokens but cost 53.2% less and had 54.4% lower mean latency, again with no measured quality gain. The cost difference is associated with model assignment, output length, and cache pricing; it is not a causal estimate of the value of specialist routing.

### 3.4 Team Role Decomposition

| Component | Tokens | Cost (USD) | Cost share |
|---|---:|---:|---:|
| Coordinator | 22,236 | 0.007060 | 84.7% |
| Specialists | 18,983 | 0.001276 | 15.3% |

- Team P50 latency: 21.30 seconds.
- Team P95 latency: 22.49 seconds.
- Team cost per successful outcome: USD 0.001667.
- Uncorrelated tool results: 0.

## 4. Interpretation

The principal empirical result is a tie, not a collaboration gain. The Team path demonstrates real delegation, concurrent specialist execution, evidence-preserving synthesis, and coordinator/specialist telemetry, but it does not improve the six-case decision score over either evidence-matched Solo baseline. The Team path is economically dominated by one-pass Open-Book Solo for this suite. It is cheaper and faster than Pro-only Two-Pass Solo, but that comparison combines model-price and output-length differences with orchestration.

Oracle Team is not an empirical upper bound here: it passed fewer cases than Team and the Solo baselines. Named evidence, prompt form, and a single synthesis pass can change model behavior even when routing is perfect. Oracle results should therefore be treated as a diagnostic mode rather than a guaranteed ceiling.

## 5. Calibration History and Threats to Validity

The preceding `r1`–`r4` runs are diagnostic artifacts. They exposed defects in negation and quotation handling, direction-sensitive milestones, decimal punctuation, conditional scope, streamed error propagation, baseline denominators, cache accounting, and cost attribution. Those defects were repaired before `r5`. Because the repairs were informed by observed outputs, `r5` is not independent validation.

Additional threats include:

- six cases and one repetition;
- fixed specialist evidence rather than archived-source retrieval;
- no untouched holdout;
- lexical grounding rather than claim-level entailment;
- provider stochasticity in wording, completion length, and latency;
- no financial-return objective or point-in-time market dataset.

## 6. Recommended Validation

1. Freeze the current suite and matcher without further post-output synonym additions.
2. Add at least 24 untouched cases and run three repetitions per mode.
3. Report paired case outcomes and case-bootstrap uncertainty intervals.
4. Validate a claim-to-evidence or entailment grader against blinded human labels.
5. Separate archived-source retrieval experiments from fixed-evidence orchestration tests.
6. Evaluate Serenity and an independent challenger as explicit ablations with identical evidence and budgets.
7. Keep any return-based backtest in a separate protocol with point-in-time data, delisting coverage, corporate actions, turnover, and transaction costs.

