# Evaluation of a Coordinator–Specialist Agent Runtime for Evidence-Grounded Financial Analysis

> **Historical calibration artifact.** This report describes the first formal run before independent review found matcher, error-propagation, denominator, cache-accounting, and report-attribution defects. Its scores must not be presented as frozen validation results. The post-fix primary report is `evals/finance-runtime-formal-r5.md`, backed by `finance-runtime-formal-r5.json`.

## Abstract

This experiment evaluates whether FastClaw's coordinator–specialist runtime improves evidence-grounded financial analysis relative to solo inference under controlled evidence visibility and compute conditions. Six fixed, point-in-time cases were executed with a DeepSeek-V4-Pro coordinator and three DeepSeek-V4-Flash specialists representing source extraction, analytical methodology, and decision governance. Four baselines were measured: `solo_open_book`, `solo_two_pass`, `team`, and `oracle_team`.

The raw automated success rate was 83.3% for Team, 83.3% for Solo Open-Book, 100% for Solo Two-Pass, and 83.3% for Oracle Team. Manual adjudication found that all three automated baseline failures were lexical false negatives rather than incorrect financial decisions. Under semantic adjudication, all four modes solved all six cases, so neither the fair collaboration gain nor the compute-matched collaboration gain was positive. Team inference was 54.4% cheaper and 47.9% faster than Solo Two-Pass, but was 41.0% more expensive and 58.9% slower than Solo Open-Book. The experiment therefore supports a systems claim—auditable multi-agent routing with bounded evidence and measurable costs—but does not yet support a claim that orchestration improves financial decision quality.

## 1. Research Questions

The evaluation addresses four questions:

1. Does coordinator–specialist orchestration improve decision correctness when the solo baseline receives the same evidence?
2. Does orchestration outperform a compute-matched solo model that receives two sequential reasoning passes?
3. Does the runtime preserve evidence identifiers, numeric facts, versioned state transitions, and conservative financial controls?
4. What token, cost, and latency overhead is introduced by coordinator and specialist execution?

The experiment does not measure portfolio returns, stock-selection alpha, forecasting accuracy, or an official external benchmark score.

## 2. Experimental Design

### 2.1 Financial Tasks

The suite contains six deterministic workflows:

| Case | Financial Application | Required Decision |
|---|---|---|
| `earnings-catalyst-review` | Filing-based catalyst review | Update thesis conviction without authorizing a trade |
| `thesis-invalidation-review` | Customer-loss risk review | Apply an explicit invalidation threshold and versioned state transition |
| `duplicate-event-alert` | Multi-source event processing | Deduplicate an alert and preserve auditable occurrence state |
| `incomplete-screening-data` | Equity screening quality control | Reject a candidate when required factors are missing |
| `portfolio-concentration-response` | Portfolio risk governance | Propose a reversible concentration control with revalidation |
| `contradictory-primary-evidence` | Conflicting disclosure review | Preserve the contradiction and defer directional judgment |

Each case uses immutable evidence identifiers and fixed decision rules. This design removes dependence on live market movements and makes the expected behavior reproducible.

### 2.2 Agent Roles

- **Coordinator:** `bench-coordinator`, using `deepseek/deepseek-v4-pro`.
- **Source specialist:** retrieves the case-specific filing, event, screening, portfolio, or capital-expenditure evidence.
- **Methodology specialist:** applies the stored thesis condition, screening contract, risk model, or conflicting-source analysis.
- **Governance specialist:** produces a bounded, auditable state transition and prohibits unsupported execution advice.
- **Specialist model:** all three specialists use `deepseek/deepseek-v4-flash`.

The specialists are real runtime agents. Their controlled identity files contain only the fixed evidence corpus, and they are instructed to return the evidence associated with the delegated case marker. This measures routing, context isolation, sub-agent execution, synthesis, and telemetry without introducing live-data drift.

### 2.3 Baselines

| Baseline | Evidence | Passes | Delegation |
|---|---|---:|---|
| `solo_open_book` | Same anonymous evidence packet as Team | 1 | Disabled |
| `solo_two_pass` | Same anonymous evidence packet as Team | 2 | Disabled |
| `team` | Evidence obtained through three runtime specialists | 2 coordinator calls + 3 specialist calls | Enabled |
| `oracle_team` | All labeled specialist reports supplied directly | 1 | Perfect routing assumed |

`solo_open_book` is the primary fairness baseline because evidence visibility is equalized. `solo_two_pass` controls for the additional synthesis pass. `oracle_team` estimates the upper bound when routing is perfect but sub-agent execution is removed.

### 2.4 Metrics

The primary quality metrics are:

- **Team outcome success:** all decision milestones pass and no forbidden assertion is made.
- **Fair collaboration gain:** Team outcome success minus Solo Open-Book success.
- **Compute-matched collaboration gain:** Team outcome success minus Solo Two-Pass success.
- **Delegation F1:** accuracy of specialist selection and task targeting.
- **Contribution utilization:** proportion of healthy specialist evidence represented in the final answer.
- **Grounding accuracy:** configured forbidden assertions not made by the model.

Efficiency is measured separately for each baseline using tokens, configured model pricing, and wall-clock latency. Coordinator and specialist usage is also decomposed.

## 3. Formal Runtime Experiment

### 3.1 Execution Metadata

- Date: 2026-07-31
- Suite: `evals/multiagent-finance-runtime.yaml`
- Cases: 6
- Repetitions: 1
- Baseline executions: 24
- Model calls: 54
- Baseline execution errors: 0
- Pricing coverage: 100%
- Raw artifact: `finance-runtime-formal-r1.json`
- SHA-256: `fa18d56e39067240a949347e5b0a38e08c89728d186591937e053c90b8d25d53`

One repetition is sufficient for engineering validation but insufficient for statistical claims about model quality.

### 3.2 Raw Quality Results

| Mode | Passed | Success Rate |
|---|---:|---:|
| Team full harness | 5/6 | 83.3% |
| Team outcome | 5/6 | 83.3% |
| Solo Open-Book | 5/6 | 83.3% |
| Solo Two-Pass | 6/6 | 100.0% |
| Oracle Team | 5/6 | 83.3% |

The raw fair collaboration gain was `0.0` percentage points. The raw compute-matched collaboration gain was `-16.7` percentage points.

Routing and evidence control were stronger than the aggregate success rate suggests:

| Runtime Metric | Result |
|---|---:|
| Delegation precision / recall / F1 | 1.000 / 1.000 / 1.000 |
| Contribution utilization | 100.0% |
| Coordination score | 100.0% |
| Milestone KPI | 94.4% |
| Grounding assertions checked | 28 |
| Grounding violations | 0 |
| Grounding accuracy | 100.0% |

The grounding metric is a configured forbidden-assertion check. It is not exhaustive natural-language-inference verification of every generated claim.

### 3.3 Case-Level Results

| Case | Team | Solo Open | Solo Two-Pass | Oracle |
|---|---:|---:|---:|---:|
| Earnings catalyst review | Pass | Fail | Pass | Pass |
| Thesis invalidation review | Pass | Pass | Pass | Fail |
| Duplicate event alert | Pass | Pass | Pass | Pass |
| Incomplete screening data | Pass | Pass | Pass | Pass |
| Portfolio concentration response | Fail | Pass | Pass | Pass |
| Contradictory primary evidence | Pass | Pass | Pass | Pass |

### 3.4 Lexical Failure Audit

Manual inspection identified three false negatives:

1. Solo Open-Book wrote `conviction moves from 3 to 4`, while the rubric expected `conviction from 3 to 4`.
2. Oracle Team wrote that the observed value `exceeds` the threshold, while the rubric expected `crosses`.
3. Team wrote `re-running` or `re-run`, while the rubric expected `rerun`, `re-check`, or `recheck`.

All three outputs preserved the controlling evidence and made the expected financial decision. Under manual semantic adjudication, each mode passed all six cases. The adjusted fair and compute-matched gains are therefore both `0.0` percentage points. The raw scores remain the reproducible machine-scored result; the adjusted scores are reported only as an error analysis.

The rubric was subsequently expanded with narrowly scoped semantic alternatives. This calibration must be frozen before a larger repeated or holdout evaluation.

## 4. Cost and Latency

### 4.1 Baseline Efficiency

| Mode | Tokens | Cost (USD) | Mean Latency |
|---|---:|---:|---:|
| Solo Open-Book | 10,301 | 0.006148 | 18.05 s |
| Solo Two-Pass | 31,604 | 0.019023 | 54.99 s |
| Team | 40,905 | 0.008668 | 28.67 s |
| Oracle Team | 9,383 | 0.005181 | 15.42 s |

The complete four-baseline experiment consumed 92,193 tokens and had an estimated cost of USD 0.039019.

Relative to Solo Open-Book, Team:

- used `3.97×` as many tokens;
- cost `1.41×` as much, an increase of 41.0%;
- took `1.59×` as long, an increase of 58.9%;
- produced no measured decision-quality gain.

Relative to Solo Two-Pass, Team:

- used `1.29×` as many tokens because three Flash specialist calls were added;
- cost `0.46×` as much, a reduction of 54.4%;
- took `0.52×` as long, a reduction of 47.9%;
- produced equivalent decisions after semantic adjudication.

The lower Team cost relative to Solo Two-Pass results from assigning evidence retrieval to the cheaper Flash specialists while reducing Pro-only reasoning time.

### 4.2 Team Cost Decomposition

| Component | Tokens | Share of Team Tokens | Cost (USD) | Share of Team Cost |
|---|---:|---:|---:|---:|
| Coordinator | 21,977 | 53.7% | 0.007305 | 84.3% |
| Specialists | 18,928 | 46.3% | 0.001363 | 15.7% |

The coordinator dominates monetary cost even though specialist tokens account for nearly half of Team usage. This supports adaptive routing and coordinator-prompt compression as higher-value optimization targets than removing individual Flash specialist calls.

## 5. Runtime Parallelization Validation

The initial runtime path classified only read-only tools as concurrency-safe. Consequently, three independent `spawn_subagent` calls were executed serially. The runtime was changed to execute distinct specialist targets concurrently while preserving serialization for repeated calls to the same target.

During the first parallel run, concurrent session writes exposed SQLite `SQLITE_BUSY` failures. The store configuration was corrected to enable WAL, foreign keys, and a 5-second busy timeout. Identity validation was also changed to preserve transient database errors rather than misreporting them as missing identity files.

### 5.1 Revalidation Metadata

- Scope: Team-only engineering revalidation
- Cases: 6
- Repetitions: 1
- Model calls: 30
- Baseline execution errors: 0
- Concurrent specialist tasks observed: 3
- Raw artifact: `finance-runtime-parallel-team-r2.json`
- SHA-256: `c7f9b99478b4483f1110f279bf70ad08bbf4171bdbcb39ee29775a73a735182f`

### 5.2 Within-Run Parallelism Estimate

For each case, the serial counterfactual is computed as:

`sum(coordinator model latency) + sum(specialist model latency)`

The parallel execution floor is:

`sum(coordinator model latency) + max(specialist model latency)`

| Metric | Mean |
|---|---:|
| Observed Team wall-clock latency | 34.47 s |
| Serial counterfactual | 37.99 s |
| Parallel model-call floor | 34.33 s |
| Observed latency saved versus serial counterfactual | 3.52 s |
| Avoided specialist waiting time | 3.66 s |

Parallel execution reduced the within-run serial counterfactual by approximately 9.3% and eliminated approximately 57.1% of cumulative specialist waiting time. The observed wall-clock result was within 0.14 seconds of the model-call floor on average.

The parallel revalidation was slower than the earlier serialized run in absolute terms because average coordinator model latency increased from 21.10 seconds to 31.58 seconds. This is provider/model latency variation, not a regression caused by specialist parallelization. Cross-run wall-clock differences therefore cannot isolate the optimization; the within-run call decomposition is the defensible engineering measurement.

### 5.3 Revalidation Quality

The parallel revalidation produced:

- raw Team outcome success: 5/6;
- delegation F1: 1.000;
- contribution utilization: 94.4%;
- grounding accuracy: 100.0%;
- execution errors: 0.

The only raw failure used the phrases `24-hour concurrence window` and `review exactly once`, while the rubric expected `24-hour window` and `review only once`. The evidence, deduplication decision, occurrence-count update, and one-time review behavior were correct. This is another lexical false negative and was added to the frozen semantic alternatives.

## 6. Interpretation

The current evidence supports the following claims:

1. FastClaw can execute auditable financial workflows through a real coordinator and real specialist agents with request-scoped routing, evidence identifiers, versioned decisions, and token/cost/latency decomposition.
2. Distinct specialists can execute concurrently without allowing duplicate calls to the same specialist to race.
3. Store-level concurrency controls are necessary for reliable multi-agent execution even when model calls themselves are independent.
4. For this small fixed-evidence suite, orchestration does not improve decision quality over a solo model given the same evidence.
5. Team execution is economically favorable relative to a Pro-only two-pass baseline, but not relative to a one-pass open-book baseline.

The experiment should not be presented as evidence that the system predicts markets or generates excess returns. Its strongest result is runtime reliability, auditability, and measured cost–latency trade-offs under controlled financial decision tasks.

## 7. Threats to Validity

- **Sample size:** six cases and one formal repetition do not support confidence intervals or statistical significance.
- **Calibration leakage:** semantic alternatives were refined after pilot and formal error inspection. A holdout set is required.
- **Static evidence:** specialist evidence is fixed in identity files rather than retrieved from live financial sources.
- **Model stochasticity:** coordinator latency and phrasing vary materially across runs.
- **Grounding scope:** forbidden-assertion matching cannot detect every unsupported inference.
- **Domain scope:** the cases measure research-state governance, not security selection or realized performance.
- **Oracle limitation:** Oracle Team tests synthesis under perfect evidence delivery but is still subject to lexical grader errors.

## 8. Recommended Next Experiment

1. Freeze the calibrated rubric and add at least 24 unseen cases, yielding a 30-case suite.
2. Run three repetitions per case and report case-bootstrap confidence intervals.
3. Separate calibration, validation, and untouched holdout partitions.
4. Compare fixed three-agent routing with adaptive routing based on evidence need.
5. Add source-retrieval perturbations: missing filing, stale event, contradictory transcript, malformed record, and specialist timeout.
6. Replace static evidence in a separate integration track with point-in-time archived documents and deterministic extraction scripts.
7. Add claim-level evidence attribution that links each material generated claim to an evidence ID.
8. Keep financial-outcome evaluation separate: if return-based experiments are added, use walk-forward historical data with transaction costs and no look-ahead leakage.

## 9. Reproduction

Start the provisioned FastClaw gateway, then execute:

```bash
FASTCLAW_API_KEY="$(jq -r .api_key runtime-benchmark-tenant.json)" \
go run ./cmd/fastclaw eval multiagent run \
  evals/multiagent-finance-runtime.yaml \
  --base-url http://127.0.0.1:18953 \
  --agent-id bench-coordinator \
  --repetitions 1 \
  --timeout 10m \
  --format json \
  --output finance-runtime-formal-r1.json
```

The API key must not be committed or included in reports.
