# Financial insight quality: retrospective LLM-as-judge calibration rubric (v1)

## Scope and status

Apply this rubric to the retained, post-fix 80-observation Flash panel in
`results/2026-10-19-finance-workflow-reliability-80-flash-v3/`. It was written
**after** those model outputs existed. It is a transparent exploratory audit,
not a pre-registered holdout test, an independent expert assessment, an
investment recommendation, or proof of predictive value. The judge is Codex,
not the DeepSeek model that generated the observations. The judge can still
share model-family biases and should not be treated as ground truth.

The audit unit is one observation, not one sentence. For E/C observations,
review both the final answer and persisted review rationale, source-linked
alert, and final thesis state. For S observations, review final answer, screen
tool result, and any persisted candidate thesis. For P observations, review
final answer, risk-tool result, and absence/presence of ledger mutations.
Source facts are checked against the frozen SEC packet or declared synthetic
fixture available to the agent, not against hindsight or a live market view.

## Dimensions (0, 1, 2, or NA)

1. **Factual and numerical fidelity (F).** 2 = material values, units, periods,
   directions, arithmetic and metric definitions correct; 1 = non-decision-
   changing imprecision or omission; 0 = a material wrong value, metric label,
   period, calculation, or contradiction. NA only if the task has no factual
   or numerical claim to assess.
2. **Inference discipline (I).** 2 = main conclusion follows from available
   evidence, with alternatives or assumptions correctly bounded; 1 = useful
   conclusion but a noncritical inference is weakly supported; 0 = unsupported
   causal/temporal claim, false source independence, wrong policy bound, or
   another overreach that could change the research interpretation.
3. **Risk and uncertainty handling (R).** 2 = salient counterevidence and
   missing inputs are explicitly and correctly handled; 1 = partial but not
   misleading treatment; 0 = missing critical risk, fabricated certainty, or
   refusal/abstention that conceals a provable decision-relevant conclusion.
4. **State and action alignment (S).** 2 = final and persisted statements match
   actual tool and ledger state; 1 = imprecise description without a false
   decision consequence; 0 = claims a hold, write, alert, or usable decision
   state that the ledger does not show, or silently treats a blocked state as
   actionable. NA for a no-ledger task only if no state/action claim is made.
5. **Research utility (U).** 2 = states a source-grounded implication useful
   for the declared research decision, including a justified decision to
   defer; 1 = accurate but largely restates inputs or tool output; 0 = the
   proposed implication would mislead the decision. NA when task design cannot
   support an insight judgment. This is not a return or economic-value score.

## Critical errors and overall label

- A **critical error** is a material unsupported fact/calculation, reversal of
  a risk or policy conclusion, false assurance that a decision is blocked, or
  an actionable recommendation without required evidence. Record each by a
  short code and a source/result pointer.
- `high_within_case` requires F=2, I=2, R=2, S in {2,NA}, U=2, no critical
  error, a completed workflow, and an assessable research implication.
- `adequate_within_case` requires no critical error and every applicable
  dimension >=1, but does not meet all high conditions.
- `problematic` applies if any critical error or any applicable dimension 0.
- `not_assessable` applies if the retained material does not permit a fair
  determination. Do not force a pass.

Report counts by **case cluster** and workflow as well as by observation.
Repeated outputs for one frozen case are correlated. The aggregate is a
descriptive calibration count, never a population success rate. The audit must
retain raw result hashes and never rewrite original result or ledger files.

## Known evaluation boundaries

- E cases use source-locked historical SEC excerpt packets; C/S/P cases use
  synthetic fixtures. Do not call synthetic cases evidence of real-world
  investment value.
- A complete SEC filing may contain facts omitted from an experiment packet.
  Judge what the agent was given; flag claims that pretend broader access.
- A tool-level refusal of incomplete portfolio data is not the same as a
  correct statement about every logically derivable bound.
- A `needs_review` narrative is not a decision hold unless the retained thesis
  actually has `decision_hold=true` and `actionability=blocked`.
- External expert validation and an unseen real-source holdout panel remain
  necessary for a strong claim of stable, high-quality financial insight.
