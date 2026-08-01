# FastClaw Financial Workflow Evaluation

## Experimental Objective

This experiment measures whether FastClaw's coordinator-and-specialist workflow improves evidence-grounded financial research decisions relative to a solo model that receives the same evidence. It does not measure investment returns, stock-selection alpha, or the official score of an external benchmark.

The primary estimand is the fair collaboration gain:

`team outcome success rate - solo_open_book success rate`

`solo_closed_book` is retained only as an optimistic diagnostic because it does not receive the specialist evidence. `oracle_team` provides a synthesis upper-bound diagnostic under perfect routing.

## Experimental Setup

- Date: 2026-07-31
- Suite: `evals/multiagent-finance-workflow.yaml`
- Coordinator: `bench-coordinator`
- Coordinator model: `deepseek/deepseek-v4-pro`
- Cases: 6 fixed-evidence financial research workflows
- Repetitions: 3 per case
- Baselines: `solo_closed_book`, `solo_open_book`, `team`, `oracle_team`
- Evaluated attempts: 18
- Model calls: 90
- Team tool calls: 54
- Baseline execution errors: 0
- Pricing coverage: 100%
- Specialist execution: simulated deterministic reports; no sub-agent model tokens were consumed
- Formal output: `finance-workflow-formal-r3.json`
- Output SHA-256: `29f5a67b94477e1d5e50612bb09dd44f5d46fb1bcf46092d09791c2925b7dbe6`

The scoring vocabulary, evidence-preservation prompts, semantic alternatives, text normalization, and model pricing were calibrated with single-repetition pilot runs and frozen before this formal run.

## Aggregate Results

| Metric | Result |
|---|---:|
| Team full harness success | 13/18 (72.2%) |
| Team outcome success | 14/18 (77.8%) |
| Solo open-book success | 14/18 (77.8%) |
| Oracle-team success | 14/18 (77.8%) |
| Solo closed-book success | 0/18 (0.0%) |
| Fair collaboration gain | 0.0 percentage points |
| Optimistic closed-book gain | +72.2 percentage points |
| Delegation precision / recall / F1 | 1.000 / 1.000 / 1.000 |
| Contribution utilization | 90.7% |
| Coordination score | 95.4% |
| Milestone KPI | 92.6% |
| Consistent cases across three repetitions | 2/6 (33.3%) |
| Pass@3 | 6/6 (100%) |

The paired Team/Solo open-book table contains 10 joint passes, 4 team-only passes, 4 solo-only passes, and no joint failures. The observed gain is therefore exactly zero; the symmetric disagreement count also gives an exploratory exact McNemar p-value of 1.0. With only 18 paired attempts, this is not evidence of equivalence.

## Efficiency Results

| Mode | Success | Tokens | Tokens/Attempt | Cost (USD) | Cost/Attempt (USD) | P50 Latency | P95 Latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Solo closed-book | 0/18 | 22,492 | 1,249.6 | 0.01333 | 0.000740 | 14.80 s | 29.46 s |
| Solo open-book | 14/18 | 27,657 | 1,536.5 | 0.01511 | 0.000840 | 16.43 s | 25.79 s |
| Team | 14/18 | 67,505 | 3,750.3 | 0.02732 | 0.001518 | 19.78 s | 32.70 s |
| Oracle team | 14/18 | 27,514 | 1,528.6 | 0.01390 | 0.000772 | 14.37 s | 20.14 s |

Relative to `solo_open_book`, Team used 2.44 times as many tokens (+144.1%), cost 1.81 times as much (+80.8%), and had 42.0% higher mean latency. The complete four-baseline run cost an estimated USD 0.06965.

## Case-Level Results

| Case | Team Full | Team Outcome | Solo Open | Oracle |
|---|---:|---:|---:|---:|
| Earnings catalyst review | 3/3 | 3/3 | 3/3 | 3/3 |
| Thesis invalidation review | 3/3 | 3/3 | 1/3 | 1/3 |
| Duplicate event alert | 2/3 | 2/3 | 2/3 | 3/3 |
| Incomplete screening data | 1/3 | 1/3 | 2/3 | 1/3 |
| Portfolio concentration response | 2/3 | 2/3 | 3/3 | 3/3 |
| Contradictory primary evidence | 2/3 | 3/3 | 3/3 | 3/3 |

## Failure Audit

Routing itself was reliable: every Team attempt delegated exactly once to every expected specialist, with no unknown or duplicate target. Most automated failures occurred during synthesis scoring:

- Duplicate-alert output said `increment duplicate_count from 1 to 2` and `review exactly once`, while the grader expected a narrower phrase.
- Incomplete-screening outputs correctly prohibited estimation but used variants such as `no estimation` instead of the configured `not estimate`.
- Portfolio output used `re-running` instead of one of the registered `rerun` variants.
- A contradictory-evidence output preserved both claims but inserted unsupported source hierarchy, regulatory-weight assumptions, and a fallback preference for the lower filed figure. This is a substantive financial-governance failure that the current positive-milestone grader does not detect.

The first three findings indicate residual false negatives in lexical grading. The final finding indicates a more serious false positive: milestone completion can coexist with unsupported financial claims.

## Interpretation

For short, fixed evidence packets, multi-agent orchestration did not improve decision success over a solo model with the same evidence. The runtime demonstrated strong routing reliability and auditable tool traces, but the second coordinator pass increased compute without increasing measured outcome quality.

The 72.2-point improvement over `solo_closed_book` must not be presented as orchestration gain. It primarily measures evidence access. The defensible result is the zero-point fair gain versus `solo_open_book`, together with the measured cost and latency overhead.

## Next Experiment

The next financial benchmark should target conditions where orchestration can plausibly add value:

1. Add a compute-matched `solo_two_pass` baseline to separate orchestration benefit from an extra inference pass.
2. Execute real `deepseek-v4-flash` specialists through the finance plugin instead of simulated reports.
3. Use point-in-time immutable tool snapshots and verify data lineage, event time, and state transitions.
4. Add an evidence-grounding grader for unsupported source hierarchy, invented execution rules, and unprovided numeric claims.
5. Expand to at least 30 cases with a calibration split and an untouched holdout split.
6. Report bootstrap confidence intervals over cases and paired significance tests, not only aggregate success rates.
7. Evaluate adaptive routing against fixed three-specialist routing to determine whether the coordinator can avoid unnecessary calls.

