# Project-report case-study scope (2026-10-26)

This is a presentation and diagnostic-scope decision, not a revision of the
sealed 30-issuer experiment, its original protocol, raw outputs, or frozen
quality rubric. It does not turn selected examples into an unbiased estimate
of financial-insight quality.

## What remains in scope

- Preserve and report the complete execution denominator: 30 source-distinct
  issuers, five independent sessions each, 150 saved results. A read-only
  check found 150 result files, no recorded request errors, 101 mechanical
  `candidate_for_qualitative_review` outcomes, and 49 mechanical `held`
  outcomes. Mechanical status is not a financial-quality label.
- Present one fully reviewed **positive case cluster**, MQ/Marqeta, as a
  source-bounded event-to-research-state workflow. Its five saved sessions
  all passed the mechanical workflow checks. Local diagnostic F/I/R/S/U
  adjudication found four `high` and one `adequate`; the case meets the
  frozen within-case 4-of-5 threshold on this diagnostic judge, subject to
  the stated lack of independent domain-expert review. Show the disagreement
  between growing TPV/revenue/gross profit and worsening GAAP losses despite
  higher adjusted EBITDA, plus the recorded review, alert acknowledgement,
  and blocked state. Do not describe the case as a profitable or investment-
  worthy company conclusion.
  A read-only check against both locally frozen SEC earnings exhibits
  confirmed the displayed Q2 and Q3 revenue, gross profit, operating expense,
  GAAP loss, TPV, and adjusted-EBITDA figures and the USD-thousand versus
  USD-million units. The report cites the two SEC accession URLs directly.
- Present **one or two individual high-quality but nonpassing/unfinished
  clusters** as illustrations of harder conflicts, not as stable successes:
  AIG (GAAP versus adjusted and reported versus accident-year underwriting)
  and/or SSB (earnings improvement versus worsening credit-loss measures and
  acquisition-date comparison effects). Include each cluster's observed
  failures or unfinished judgments alongside the selected successful answer.
- Present at least **one explicit failure boundary** from a fully or partly
  reviewed cluster, such as ACIW's incorrect tax-rate inference or AIG's
  actionable ledger state despite unresolved basis conflict. State whether
  the defect lies in a model-generated conclusion, saved review rationale,
  tool execution, or runtime containment. A correct hold does not make
  incorrect financial prose correct.

## What the report may and may not infer

The case study demonstrates feasibility: under source-bounded prompts and
finance-tool/ledger integration, this runtime **can** complete a real-SEC
research workflow and sometimes produce a well-supported, appropriately
deferred insight. The 150-session run independently demonstrates execution,
trace and state persistence under the stated cases. A few selected successes
do **not** establish a population insight-quality rate, investment value,
expert-level judgment, absence of failure, or reliable transfer to all
workflows. The first 100 local qualitative reviews were not drawn as a
prospective random subset; their class frequencies must not be presented as
an unbiased rate for all 150.

The same 100 local diagnostic reviews currently include 47 `problematic`
answers: 28 ended with a blocked thesis, while 19 retained an available
thesis. These are **not** automatically 28 successful guard catches and 19
guard failures: a `problematic` judgment may concern an analytical claim
that is not itself a required pre-commit hold, and the baseline model chose
some holds. The count is a reason to perform claim-to-boundary attribution,
not a containment success rate.

No additional paid generation is required for this report scope. The 50
currently unreviewed responses remain sealed evidence, not assumed passes.
If a rate for financial-insight quality is desired, complete the frozen
150-response rubric and case-cluster aggregation or declare and assess a new
prospective source-distinct sample. Do not silently re-label the older
holdout after selecting exemplars.

## Controlled attribution still required

The separate A/B containment replay in
`AGENT-GUARD-CONTROLLED-COMPARISON-PROTOCOL-v1.md` has not yet been run. Its
planned guard was not frozen before the first 100 local judgments were read,
so any guard now designed from those errors is developmental. A defensible
small comparison can hold fixed several **unchanged** saved model outputs and
replay them through baseline versus guarded tool/publication boundaries,
reporting both true and false holds. It must not claim prospective guard
performance on already inspected answers or count a post-final hold as an
undo of a prior ledger write. The report should not attribute observed
financial reasoning defects to the runtime until this separation is made.

One concrete development target is tax reasoning: the existing v2 semantic
screen checks the direction of absolute tax expense against phrases such as
"lower tax burden," but an effective-rate burden requires *tax expense
divided by pretax income* on matching bases. The ACIW and SF local reviews
found this distinction material. Any revised guard should calculate the
rate when both terms are available, keep absolute expense and rate separate,
and demonstrate non-alerts on correctly worded examples; a simple rule that
holds every answer would not establish useful containment.

A developmental v3 post-final screen and six local unit tests now separate
absolute tax expense from an explicitly stated effective tax rate. Its first
fixed-output replay exposed false alerts from generic "tax burden" wording;
those phrases were removed from the deterministic rate rule. On the 93
parseable answers among the first 100 local reviews, v3 removes seven broad
v2 tax-direction flags, adds a narrower effective-rate flag on ACIW, and adds
arithmetic-bridge flags on JKHY and BLK. Six cases consequently move from
held to candidate and one moves from candidate to held; some newly unheld
answers are locally problematic for different reasons. This is a diagnostic
rule comparison on already seen outputs, not a prospective estimate of guard
recall or precision. It neither undoes a prior ledger write nor certifies
unflagged analysis. A separate direct-plugin pre-commit A/B replay on fixed
JKHY and MQ calls is documented in
`REFERENCE-PRECOMMIT-DEVELOPMENTAL-AB-2026-10-27.md`; it verifies a possible
veto mechanism, not deployed Gateway coverage or out-of-sample reliability.

Source examples and exact review records are in
`results/2026-10-26-reference-source-distinct-insight-judgment-v1/`;
raw executions remain in
`results/2026-10-26-reference-source-distinct-insight-flash-v1/`.
