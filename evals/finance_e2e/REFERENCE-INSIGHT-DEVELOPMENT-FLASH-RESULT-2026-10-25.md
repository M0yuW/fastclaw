# Reference-only insight development run — 2026-10-25

This is a **seen-case development test**, not an independent or source-distinct confirmation of financial-insight quality. The user authorized eight DeepSeek Flash sessions (FITB, RELY, TFC, VRSK twice each), with a new cumulative *estimated* cost ceiling of USD 0.25. The frozen order, source hashes, prompts, runtime files, and pricing assumptions are in the [run manifest](results/2026-10-25-reference-insight-development-flash-v1/manifest.json). Original observations are retained in the [result directory](results/2026-10-25-reference-insight-development-flash-v1/).

## Recorded outcome

| Check | Result |
| --- | ---: |
| Planned / completed independent sessions | 8 / 8 |
| Runtime and ledger mechanical completion | 8 / 8 |
| Reference-format candidate for qualitative review | 4 / 8 |
| Held by deterministic candidate gate | 4 / 8 |
| Request errors / uncertain-cost sequences / unpriced sequences | 0 / 0 / 0 |
| Cumulative estimated cost | USD 0.061476384 |

All files listed in `RESULT-SHA256.txt` passed SHA-256 verification. Each session used one Gateway turn; none was retried. The cost was below the authorized estimated ceiling. The `candidate_for_qualitative_review` status means only that a response passed the *mechanical* reference, schema, and ledger-state gate; `quality_pass` remains `null` for every response.

The four held responses were:

- FITB repetition 2: incomplete interpretation and unstructured numeric values in the saved rationale.
- RELY repetition 1: unstructured numeric values in the saved rationale.
- TFC repetition 1: candidate and state-claim schema mismatches plus incomplete interpretation.
- TFC repetition 2: malformed final JSON despite a normal `stop` finish reason; it was not an output-token truncation.

## Preliminary qualitative screen of the four machine-accepted candidates

This screen is a diagnostic reading, not an independent expert grade or a substitute for blinded scoring.

- **FITB repetition 1:** The answer correctly identifies improving selected GAAP earnings and the countervailing credit-loss provision. However, it calls the result a “beat” without any consensus or guidance comparator, while its own uncertainty paragraph says no beat/miss can be inferred. It also speculates that near-flat margin implies a volume/scale driver, which the selected rows do not establish. **Not a clean quality pass.**
- **RELY repetition 2:** The operating-profit versus headline-net-income divergence is useful, but the answer says a “smaller tax drag” helped net income. The audited comparison table shows GAAP income-tax expense rose from USD 1.578 million to USD 3.594 million. The saved rationale repeats the smaller-tax-drag claim. **Factual interpretation error; not a quality pass.**
- **VRSK repetition 1:** The answer recognizes weaker selected earnings, stronger free cash flow, and mixed guidance. But it assigns the *decline* in GAAP pretax income to the `counterevidence` ID set for the weakening thesis. The prose gives a more nuanced tax explanation; the reference-role mismatch shows the current gate does not check whether a valid ID actually supports the assigned argumentative role. **Requires further review; not a clean pass.**
- **VRSK repetition 2:** The selected comparison IDs, negative earnings signal, opposing free-cash-flow signal, unchanged adjusted-EPS guidance, and bounded uncertainty appear internally coherent against the frozen selected rows. This is the **only provisional qualitative candidate** in this small screen; it is not an independent expert-verified pass.

The VRSK packet does contain the compared full-year guidance ranges. Both VRSK answers properly limit the analysis to selected sequential rows and distinguish guidance from realized results. Nevertheless, the test covered only four previously used companies, with two attempts each. It cannot establish a stable success rate across unseen sources or workflows.

### Offline post-hoc regression screen

After the paid run, `screen_reference_insight_semantics_v2.py` was added as a **diagnostic only**. It flags affirmative unsupported benchmark language in FITB repetition 1, a tax-direction contradiction in RELY repetition 2, and a same-direction GAAP profit reference assigned the opposite evidence role in VRSK repetition 1. VRSK repetition 2 has no alert, but its `quality_pass` is still `null`. The malformed TFC repetition 2 final remains a separate alert. Five recorded-response regression tests pass. These rules were written after seeing this development batch, so their success on these responses is not out-of-sample validation; they must not be folded into the frozen v1 score.

## Implication for the next iteration

The reference-only design prevented free-form numeric claim generation in some outputs and preserved the end-to-end tool/ledger path, but it **did not** make interpretation automatically reliable. The next non-paid change should validate the semantic role and polarity of selected comparison IDs against the claimed thesis, reject unsupported benchmark language such as “beat,” and cross-check qualitative tax/credit statements against audited direction and sign. These checks should be tested offline against the preserved eight responses before considering a new, separately authorized source-distinct run. No additional paid model sessions are implied by this result.

### Prospective publication gate added after this run

`verify_reference_insight_candidate_v2.py` now composes the original mechanical gate with the conservative semantic red-flag screen. In an **offline counterfactual replay** of the sealed responses, it holds the three previously machine-accepted but flagged answers (FITB repetition 1, RELY repetition 2, VRSK repetition 1); VRSK repetition 2 remains only a candidate for qualitative review. The other four were already held by the original gate. Sixteen focused gate and regression tests pass. This is neither a rescoring of the frozen v1 run nor a prospective success estimate: the rules were derived from these same examples, and the checker runs at publication/evaluation time, **not before the model's ledger write**. A ledger-side pre-write control would require a separate structured claim contract and runtime integration test. Even a non-alerted answer is not a financial-quality pass.
