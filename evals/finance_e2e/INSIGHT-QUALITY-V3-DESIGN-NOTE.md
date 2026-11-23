# V3 design note — move arithmetic out of free-form answer generation

Status: **design, not frozen protocol and not a completed experiment**.

## Why v2 cannot simply be rerun

The source-hashed v1 panel completed 15/15 workflows but failed its content
gate. The v2 one-turn publication check detected some known mistakes, yet
10 checker-accepted answers still contained two critical first-pass content
errors. The repair turn also sometimes introduced a new error. The signed
adjustment prompt for SOFI admitted a double-negative interpretation.
Changing a few phrases or repeating these same three issuers would test
adaptation to known cases, not stability on new financial situations.

## Proposed workflow boundary

1. **Source adapter:** ingest issuer, period, URL, exact raw SHA-256, fact ID,
   value, unit and accounting basis. Fail closed if original documents, period
   columns or selected facts cannot be independently reconciled. The adapter
   may not treat “not in packet” as “not in filing.”
2. **Deterministic comparison service:** use exact decimal arithmetic on
   declared fact pairs. Return signed changes, direction, precision and a
   percentage only when its denominator and units are meaningful. Reconcile
   GAAP/non-GAAP lines by **adding the source's signed adjustments once**;
   never ask a model to choose between `−(−x)` and `+(-x)`. The first tested
   implementation is `derive_financial_comparisons_v1.py`; its output is a
   calculation record, not an investment judgment. For future cases, the
   comparison-basis metadata must itself be checked against period dates.
3. **Agent interpretation:** the agent receives the validated calculation
   record and may select an implication, strongest counterevidence, missing
   inputs and what evidence would change the view. It cites comparison IDs
   and source fact IDs. It does not independently type new material numbers
   into the final prose. Unsupported causal attribution must be marked as a
   hypothesis or omitted; the structured ledger guard remains in force.
4. **Publication assembly:** the host renders the numerical table from the
   validated record and appends the agent's qualitative analysis only after
   checking source references, ledger state, no trade, and no new numerical
   claims outside the record. If the narrative fails, withhold it. Any repair
   is bounded, answer-only, retained, and rescored; a repair is never assumed
   to improve quality. This is a workflow-level gate, not a claim that every
   Gateway chat response is globally filtered.
5. **Independent adjudication:** manually examine the assembled output and
   persisted state with the frozen F/I/R/S/U rubric. A clear calculation
   record cannot compensate for generic, incorrect or misleading inference.
   Codex first-pass judgments are explicitly not domain-expert ground truth.

## Prospective experiment required for the user objective

- Freeze **new, previously unused** issuer/event clusters for SEC event→thesis
  and screening→candidate, plus distinct source-linked portfolio-risk cases
  with explicit holding completeness and policy bounds. Sample positive,
  mixed, adverse, missing and conflicting evidence. Prior AFRM/SOFI/UPST,
  COIN/HOOD/SQ and earlier named fixtures are development data, not a new
  holdout. A case cluster, not a repeated answer, is the independent unit.
- Predeclare runtime/model/prompt/tool hashes, source audit, case-selection
  frame, comparison specification, budget, failure-denominator rules and
  quality rubric before the first model call. Retain first candidate, any
  held output, every tool response, final ledger and raw hashes. Do not
  replace failures or relabel them after output inspection.
- Run a small **engineering pilot** first to verify that numeric tables,
  state transitions and publication gating work; report it as diagnostic.
  Then use a distinct sealed holdout for the substantive reliability claim.
  The existing evidence plan calls for at least 14 independent all-success
  clusters per workflow for a separate one-sided 95% lower bound above 80%,
  or 19 per workflow under a three-workflow familywise correction. Those are
  mathematical minimums, not a claim that the data currently meet them and
  not permission to launch paid calls without a frozen design and spend cap.
- Report arithmetic correctness, inference discipline, useful bounded
  conclusions, state/action alignment, completion, repair/hold rate and cost
  separately. Even a successful operational panel would support only
  repeatable **source-bounded research explanations** in the tested workflows,
  not profitable investment advice or universally valuable insights.
