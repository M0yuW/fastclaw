# Partial v2 SEC event panel: preliminary quality audit

This is a **diagnostic, incomplete** Codex review of the frozen 76-observation
v2 arm. It does not change its raw results, masked packets, or predeclared
rubric, and it is not an independent finance-professional assessment.

## Evidence inventory

- Frozen raw results: `results/2026-10-24-postcorrection-event-holdout-v2/`.
  Its 76 observation hashes were verified by
  `prepare_postcorrection_judgment_v2.py` before masking.
- Read-only masked review inputs:
  `results/2026-10-24-postcorrection-v2-masked-judgment/`.
  Preparation reported 76 packets, 20 source cases, no raw-result changes and
  zero model calls. The blank score files are **not** completed ratings.
- The PNC selected-fact auditor was rerun locally. It confirmed 20 source
  cells, 10 cross-filing comparator checks and the displayed Q2→Q3 deltas
  against the locked SEC exhibits. This checks selected source facts, not every
  claim in the agent's prose.
- The 76 observations cover all 20 issuer cases, but only ALLY, CBOE, COF and
  MSCI have all five planned repetitions. PNC has three of five. The CBOE
  cluster includes the retained output-limit failure, so even its five raw
  result files do not constitute five successful executions.

## One confirmed comparative error

Masked packet `J-624ae297e6704f5e` (PNC) contains the final-answer claim:
“Expense grew faster in relative terms than NII (+2.62% vs +2.31% is close,
but expense growth is a real offset).” The direction is reversed. The frozen
source facts are PNC-Q2-NII=3555 and PNC-Q3-NII=3648 USD million, giving
`(3648−3555)/3555 = +2.616%`; PNC-Q2-OPEX=3383 and PNC-Q3-OPEX=3461 USD
million, giving `(3461−3383)/3383 = +2.306%`. Thus NII, not expense, grew
faster in relative terms. The fact IDs point to the current-quarter columns
of the locked [Q2 SEC exhibit](https://www.sec.gov/Archives/edgar/data/713676/000071367625000048/q22025financialhighlightsa.htm)
and [Q3 SEC exhibit](https://www.sec.gov/Archives/edgar/data/713676/000071367625000126/q32025financialhighlightsa.htm).

The separate statement that rising expense absorbed **part** of the revenue
gain remains arithmetically true (+78 versus +254 USD million). The cautious
`needs_review`/blocked ledger state is not invalidated by this one error.
Nevertheless, the false “grew faster” comparison is a material answer-level
numeric/inferential defect under the frozen F/I rubric; a mechanical pass
cannot count it as a high-quality answer. This is a **focused exception**, not
a completed all-claims F/I/R/S/U score. The other 75 masked packets have not
been fully adjudicated, and no case-quality pass rate is claimed here.

The other two available PNC final answers were screened for the same specific
reversal; neither repeats it. That is not a full quality clearance for those
answers, and the two missing PNC repetitions cannot be inferred from them.

## Narrow fact-ID echo check

`audit_postcorrection_fact_echo_v2.py` verified the 76 masked-packet hashes and
compared literal `fact-ID=value` / `fact-ID:value` echoes against the frozen
baseline and event fact values. It checked **380** such echoes in final answers
and **232** in persisted-review rationales. No final-answer echo was flagged.
Two persisted-review echoes in `J-12a89de52b708223` were flagged:
`PNC-Q3-NII=93` and `PNC-Q3-NONINT=161`, whereas the SEC-selected Q3 values
under those IDs are **3648** and **2267** USD million. The surrounding sentence
discusses the arithmetic *changes* of +93 and +161, which are correct, but
using the Q3 source-fact IDs as if they equalled those changes conflates level
and delta and weakens traceability. This is an adjudication flag, not evidence
that the source packet itself is wrong. The reproducible output is
`results/2026-10-24-postcorrection-v2-masked-judgment/FACT-ECHO-DIAGNOSTIC.json`;
three targeted checker tests pass. The check does **not** cover unlabelled
numbers, relative-rate comparisons, risk claims, causal inferences, or the
complete claim-level score rubric; its 610 matching echoes are not 610 quality
passes.

## ALLY five-repeat case: targeted pre-tax bridge review

All five frozen ALLY repetitions are available. The selected SEC rows include
an explicit `Pre-Tax Income (loss) (a+b-c-d)` formula. The local ALLY source
auditor again verified all 16 selected cells and eight Q2 comparator checks.
The displayed values reconcile **exactly** in both quarters:

| USD million | Q2 | Q3 | Q3−Q2 contribution to pre-tax income |
| --- | ---: | ---: | ---: |
| Net financing revenue | 1,516 | 1,584 | +68 |
| Other revenue | 566 | 584 | +18 |
| Provision for credit losses | 384 | 415 | −31 |
| Noninterest expense | 1,262 | 1,240 | +22 |
| Pre-tax income | 436 | 513 | **+77** |

Thus `+68 +18 −31 +22 = +77`, with **zero residual**. This is an
accounting identity, not a claim about the economic cause of any component.
The source links and byte hashes are in every ALLY masked packet and the
audited fact packet; the [Q2 exhibit](https://www.sec.gov/Archives/edgar/data/40729/000119312525160823/d931552dex991.htm)
and [Q3 exhibit](https://www.sec.gov/Archives/edgar/data/40729/000119312525241967/d50905dex991.htm)
identify the current-quarter columns.

Three final answers make an explicit, contrary bridge claim:

- `J-01268a1b972bf578`: “the listed items do not by themselves reconcile to
  the +77 pre-tax change without additional lines”. This answer also says a
  pre-tax margin is “not computable” because no denominator is supplied,
  although reported revenue and pre-tax income permit a derived margin:
  Q2 `436/2082 = 20.94%`; Q3 `513/2168 = 23.66%`.
- `J-ae029f6b70b06601`: “no source reconciliation in the packet bridges
  revenue, provision and expense to the +77 pre-tax delta, and a residual
  there is unquantified”. The stated SEC row formula and selected values do
  bridge it with a zero residual.
- `J-af70aada11bf035a`: “revenue +86, less provision +31, plus a 22
  noninterest-expense decline does not reconcile to +77 without further line
  items”. Its persisted review repeats that same assertion. The expression
  is `86−31+22=77`.

`J-814e125fcbd5ea40` describes the bridge as “unexplained” without an
explicit nonzero-residual claim; `J-ecbdb73608f97527` does not compute it.
Those two are **not** cleared by this targeted check. The three explicit
non-reconciliation statements are material factual/arithmetic errors under
the frozen F rubric, sufficient to prevent these three answers from being
`high` and hence sufficient to fail ALLY's strict five-answer case gate.
This is a targeted, disqualifying finding, **not** a complete claim-by-claim
F/I/R/S/U adjudication of all five answers.

The pattern suggests a design/evaluation issue, not a SEC source error: the
agent correctly distinguishes arithmetic from causality for revenue, but in
the pre-tax bridge it treats the absence of causal driver evidence as if the
published arithmetic formula were unavailable. A fresh arm with only a larger
output limit cannot be presumed to repair this reasoning error.

A free remediation prototype, `selected_fact_signed_bridge_v4.py`, now checks
a source-defined signed identity at **both** period levels and at the delta
level. For ALLY, its source-formula configuration returns zero residual in
both quarters and for the +77 delta; removing the expense component exposes
the expected +22 delta residual. The independent
`accounting_bridge_catalog_v4.py` records only formulas already checked by
issuer source auditors. `build_postcorrection_signed_bridge_fixture_v4.py`
re-audits the same 20 **seen development cases** and renders **22** exact
bridges across **11** issuers (million- or thousand-dollar units), with zero
external model observations. Nine targeted tests pass. These fixtures are
**not wired into the v2 or v3 paid workflows**, are not an observed agent
improvement, and cannot justify relabelling either arm. A genuinely fresh,
source-distinct holdout is required to test whether this intervention improves
answer quality rather than just teaching the already-inspected cases.

## Implication for the experiment

The v2 arm is already incomplete at 76/100, including one genuine output-limit
failure, so it cannot satisfy its 20-case confirmatory gate. The newly found
PNC exception and ALLY's three false non-reconciliation claims separately
illustrate why the 75 mechanical passes must not be relabelled as 75
high-quality insights. A later fresh arm must retain an
independent, claim-level quality review before a reliability conclusion;
changing the output limit alone cannot be assumed to fix reasoning errors.
