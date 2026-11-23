# Financial insight LLM-as-judge: first retrospective pass

## What was reviewed

Codex applied `../../INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md` to all 80 retained observations in this post-fix Flash panel. The review used final answers and targeted checks of relevant tool results, persisted research rationales, alerts, ledger state, and the frozen source/fixture. It is an **observation-level first pass**, not an exhaustive sentence-by-sentence audit or a blinded, pre-registered expert evaluation. The individual rationale and five dimension scores are in `INSIGHT-JUDGE-v1.csv`.

The CSV has exactly one row for each of the 80 result directories. All 80 original `result.json` hashes in `RESULT-SHA256.txt` verified successfully (`shasum -a 256 -c`). The hash-list file itself has SHA-256 `37ea3018fa72cf779f6d9075aeb186e34b2a1cc864c0157f66bebc0b8a601552`. Original observations and the official mechanical result were not changed.

## Descriptive judgment, not a population success rate

| Workflow | High within case | Adequate within case | Problematic | Total |
| --- | ---: | ---: | ---: | ---: |
| SEC event → thesis review (E) | 16 | 4 | 0 | 20 |
| Conflicting/corrected source → review (C) | 13 | 2 | 5 | 20 |
| Screening → candidate thesis (S) | 12 | 5 | 3 | 20 |
| Portfolio risk diagnosis (P) | 13 | 2 | 5 | 20 |
| **All observations** | **54** | **13** | **13** | **80** |

These 80 observations are five correlated repeats of only 16 frozen cases. Most non-SEC cases use synthetic fixtures. “High within case” means that the answer met this rubric against the information available in that case; it does **not** mean verified real-world investment value, predictive validity, or expert agreement. The separate execution check remained 77/80 mechanical pass, 3/80 case-process failure. Neither number should be called a general reliability rate.

## Material findings

- **Conflict represented as a range:** `C2-r1/r2/r3` recast two mutually conflicting 5,000 and 8,000 point claims as a 5,000–8,000 management range. The state was correctly held for review, but the narrative changes what the evidence says.
- **Workflow execution did not finish:** `C3-r3` and `S3-r3` emitted pseudo tool calls in prose rather than completing the required tool/state transition. These were already failures in the official mechanical check.
- **Unsupported causal/metric wording:** `C3-r4` inferred fewer capacity additions from lower capex without supporting scope/timing; its persisted rationale also omitted the corrected 5,000 value. `S3-r1/r2` called `earnings_growth_yoy` “EPS growth” without a defined EPS basis.
- **Portfolio bound reasoning:** All five `P4` answers contained material inconsistency or over-caution about a partially reported portfolio. Given nonnegative weights measured against the same total portfolio, 45% + 30% leaves at most 25% for all other holdings together, so an unreported holding cannot exceed 50%. `P4-r4` expressly suggested that additional undisclosed holdings could invalidate that bound; the others mixed this provable bound with claims that the relevant maximum was unknowable. The risk tool's refusal to calculate a **complete** portfolio metric remains appropriate, but it does not negate a provable bound.
- **Thin insight despite correct bookkeeping:** `S1` was classified adequate rather than high because the outputs mostly restated screening-tool fields. `E3`, `C1`, and `P3` each had occasional mild inference or wording overreach, documented per row.

Positive evidence remains: all ten E4/C4 missing-critical-evidence repeats persisted `needs_review`, `decision_hold=true`, and `actionability=blocked`; the 20 SEC-event answers did not have a problem-level finding in this targeted pass. Those are bounded observations, not a claim that future cases will always work.

## Implication for the project report and next experiment

The existing panel supports a claim that the runtime can orchestrate four financial workflows, retain auditable tool/ledger state, and enforce the missing-evidence decision hold in the tested configurations. It does **not** yet support “stably produces high-quality financial insights” as an unqualified conclusion. The problem clusters are concentrated in source-conflict interpretation, metric naming, and portfolio-bound reasoning, and one case cluster (`P4`) failed this judge criterion in every repeat.

This was a single model's retrospective, unblinded judgment. No external finance reviewer was available. The rubric was written after seeing the outputs, and no independent judge reconciliation or unseen real-source holdout is present. Before making a stronger claim, freeze a forward-looking rubric and case set, use genuinely held-out real-source cases across workflows, repeat runs, and report exact factual/calculation and state outcomes separately from the judge score. A second independent or human review would strengthen validity when available, but is not a prerequisite for conducting the next objective audit.
