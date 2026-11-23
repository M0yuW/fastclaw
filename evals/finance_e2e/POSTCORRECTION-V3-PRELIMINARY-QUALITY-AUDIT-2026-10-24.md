# Complete v3 SEC event panel: preliminary audit

This note reports a focused Codex diagnostic, **not** a completed claim-by-claim
F/I/R/S/U adjudication or an independent finance-professional rating. The v3
arm is kept separate from the stopped v2 arm. The only intended runtime
change was coordinator output `maxTokens` from 2,500 to 5,000; source cases,
prompts, order, model, gateway binary, template, and mechanical rubric were
otherwise fixed in the v3 manifest.

## Frozen execution and integrity

- Results: `results/2026-10-24-postcorrection-event-holdout-v3/`.
- 100/100 new observations: 20 SEC cases, each repeated five times. The
  manifest declares the precomputed 100-item order and USD 1.50 incremental
  estimated-spend stop. The run finished at **USD 0.924521796 estimated**.
- All 201 entries of `RESULT-SHA256.txt` were verified: manifest plus 100
  result JSON files and 100 finance-tool databases. No request errors,
  uncertain usage records, or unpriced sequences were found. The local
  experimental gateway stopped after the final observation.
- 99 observations have `mechanical_pass`. The retained exception is
  `MSCI-2025-Q3-OPERATING-TAX-EPS-BRIDGE-r5`: status `needs_review`, no
  request error, but terminal code `tool_iteration_budget_exhausted`. Its
  tool/state/usage checks are true; clean completion is false. It remains in
  the denominator and has not been retried.
- `CBOE-2025-Q3-SEGMENT-RECONCILIATION-r3`, which hit the 2,500-token output
  limit in the stopped v2 arm, completed and mechanically passed in v3. This
  supports a narrow output-limit diagnosis, not a claim about answer quality.
- 100 outcome/order-masked packets were prepared under
  `results/2026-10-24-postcorrection-event-holdout-v3-masked-judgment/` without
  changing the raw results or contacting another model. The score templates
  are blank; **no 100-answer qualitative pass rate is available**.

## Narrow source-value diagnostic

`audit_postcorrection_fact_echo_v2.py` verified the masked-packet hashes and
checked 492 literal fact-ID/value echoes in final answers plus 222 in
persisted-review rationales. It flagged **zero mismatches**. This check does
not cover unlabelled arithmetic, comparisons, causal claims, omitted risks,
or the full quality rubric; 714 checked echoes are not 714 quality passes.
Its output is
`results/2026-10-24-postcorrection-event-holdout-v3-masked-judgment/fact-echo-audit.json`.

## Focused ALLY exception

The ALLY selected-fact auditor was rerun locally: all 16 selected source
values, eight Q2 cross-filing comparators, and the displayed accounting
bridges matched. The Q2-to-Q3 GAAP pre-tax identity is exact in USD millions:

`revenue +86 - provision expense +31 - noninterest expense change (-22) = +77`.

More explicitly, `86 - 31 - (-22) = 77`; the source row itself labels
pre-tax income `(a+b-c-d)`. This is an accounting decomposition, not an
economic-causality claim.

Two masked v3 answers contradict that available identity:

- `J-7642aae9cfd856aa` says the packet does not supply a full pre-tax bridge
  and leaves the `86`-versus-`77` gap unattributed. Its final answer also
  says the pre-tax increase `77` is **larger** than the revenue increase `86`,
  a reversed numeric comparison. The persisted review repeats that the
  residual is not decomposed.
- `J-942ffa29715e1408` says the pre-tax bridge is not decomposed and refuses
  to attribute the `77` to the supplied lines. Its persisted rationale again
  says the packet does not decompose the bridge.

These are targeted, material arithmetic/interpretation exceptions. They do
not mean the SEC source values are wrong, and they do not amount to a full
review of the other three ALLY answers or the remaining 95 answers. They are
already enough to show that the ALLY case cannot pass the predeclared strict
gate requiring at least four `high` answers out of five with no critical
errors. The retained MSCI mechanical failure independently prevents its
case from passing the all-five-clean gate. Thus the panel cannot satisfy
the predeclared all-20-case claim, even before full qualitative scoring.

## Interpretation boundary

The larger output limit let this 100-observation arm complete and removed the
specific v2 CBOE truncation on a fresh observation. It did **not** demonstrate
stable high-quality financial insight: mechanical completion is distinct from
factually correct interpretation, and the focused ALLY exception remains.
The next quality-improvement test should use a genuinely source-distinct
holdout after wiring the source-defined signed-bridge checker into the live
workflow; the current v4 preparation is not a paid model result.
