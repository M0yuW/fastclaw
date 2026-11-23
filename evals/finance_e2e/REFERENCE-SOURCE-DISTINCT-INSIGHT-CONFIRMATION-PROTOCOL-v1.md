# Source-distinct SEC insight confirmation: event → thesis review (v1)

Status: **pre-observation plan; no model-backed observation from this 30-issuer frame has run**. This document does not authorize external requests or spending.

## Boundary and fixed material

The [qualified source freeze](results/2026-10-26-reference-source-qualified-freeze-v1/MANIFEST.json) contains 30 issuer pairs, two official SEC exhibits per issuer, 523 same-definition sequential comparisons and eight single-period rows. The [fixture builder](build_reference_source_distinct_event_fixtures_v1.py) fixes 30 event→thesis-review inputs and a SHA-ranked order of five fresh sessions per issuer, 150 sessions total. Case-critical notes in [the investigator sheet](REFERENCE-SOURCE-DISTINCT-CASE-CRITICALS-DRAFT-v1.md) are **not** model input. The [30-case offline tool replay](results/2026-10-26-reference-source-distinct-tool-chain-preflight-v1/RESULT.json) checks input and ledger compatibility, not model quality.

This is one **single-issuer SEC event → research-view update** workflow. Screening, portfolio risk, live market data, returns, and trading are outside this arm. The claims cannot be generalized to those workflows or to the complete filings: model context contains selected audited exhibit rows only. The 30 issuers are source-distinct from the four FITB/RELY/TFC/VRSK citation-development cases, but were selected by the declared issuer frame and are not a random sample of all listed companies.

## Run and preservation rules

Before any paid session, freeze one Gateway binary, configuration template, finance-plugin version, model/version, prompt, complete comparison catalog, source packet hashes, session order, maximum output/tool iterations, pricing assumption and estimated-spend stop. Obtain a **new, explicit** authorization for this 150-session batch; earlier authorizations are not portable. Check each next session against a conservative cost reserve; stop on uncertainty, unpriced usage or cap. Never erase or retry a failed/time-out observation in the primary series. Store every raw response, tool trace, persisted review/alert state, request error, finish reason and priced usage in an append-only result directory with hashes. Five sessions for one issuer use isolated fresh ledgers and session keys; no previous answer is fed into a later repetition. The numeric catalog is rendered by the host in full, so model-selected references cannot conceal opposing rows from review.

The formal prompt clarifies a tool-level date rule learned from the sealed
seen-case development trace: historical SEC event dates cannot be used as a
future `next_review_at`. That optional field must be future relative to the
Gateway clock or omitted. Tool rejection is recorded, and the model must
correct it before claiming a saved review. This prospective prompt difference
is pinned in the new run manifest; the previous development answers are not
rewritten or pooled with the source-distinct observations.

Budget planning uses the earlier seven seen-case Flash sessions only as a rough
calibration: mean USD 0.00741 per session implies about USD 1.11 for 150 at
unchanged request size, but these new prompts range roughly 6.3k–19.3k
characters versus 8.4k–12.8k in that development sample. Tool-round counts
and output lengths may differ. A proposed **USD 4.00 incremental estimated
ceiling** is therefore a stop limit, not a spending forecast or provider bill;
the run will halt before the next observation if the reserve is unavailable.

## Predeclared review

Use the F/I/R/S/U definitions and critical-error rules in [the existing frozen rubric](INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md), but score **this** 30-issuer arm separately rather than silently treating the older 20-case protocol as its result. Audit every material claim in the final answer **and** saved review rationale against the frozen SEC rows, scope, units, period, arithmetic and ledger trace. Distinguish a source-supported observation, a bounded hypothesis, an unsupported assertion and a contradiction; a comparison ID alone is not proof of an inference. Check the case-critical sheet only during adjudication. `needs_review` with an actually blocked thesis can be a high-quality result when justified. A malformed final, missing trace/source, unpriced request or incomplete ledger is retained as failure or not-assessable, never a pass.

An observation is `high_within_case` only when every applicable F/I/R/S/U dimension scores 2, execution is complete and there is no critical error. The issuer cluster passes only when all five sessions complete the workflow and fact gate, none has a critical error, and at least four are high (the fifth may be adequate). Publish all individual judgments and exceptions, not only cluster totals. Codex and another LLM judge may supply **diagnostic** labels; without a blinded finance-domain human reviewer the result must not be called independent expert validation.

After a result directory is sealed, use
[`prepare_reference_source_distinct_judgment_v1.py`](prepare_reference_source_distinct_judgment_v1.py)
to verify its hashes and generate outcome-masked source/answer/state packets and
blank scores. The private observation mapping must not be shown to the judge
before scoring. Review both final text and persisted rationale, then use
[`aggregate_reference_source_distinct_judgments_v1.py`](aggregate_reference_source_distinct_judgments_v1.py)
to join scores to mechanical results and calculate issuer-cluster bounds. The
aggregator refuses incomplete result/masked-packet hash lists and treats blank
scores or missing observations as non-passing; its tests exercise the 30-case
threshold and incomplete-panel behavior. A machine candidate passes only the
output/reference/state contract, not the qualitative F/I/R/S/U review.

## Stability analysis and claim limit

The independent-candidate unit is the **issuer cluster**, not each of 150 correlated repetitions. Report 30 cluster outcomes, the exact number of passing clusters, and a one-sided exact binomial lower confidence bound for the declared frame, plus stratum-specific descriptive counts. For this event arm alone, at least **28/30** passing clusters yields a one-sided 95% lower bound above 0.80 (28/30: approximately 0.8047). If reserving familywise 5% across three planned workflows by a Bonferroni one-sided level of 0.05/3, at least **29/30** are needed (29/30: approximately 0.8146; 28/30: approximately 0.7652). These are *conditional* calculations: exchangeability with the declared frame, source adequacy, and consistent non-independent judgment are substantive limitations; the binomial formula cannot repair selection or judging bias.

Even a passing event arm would support only repeatable, source-bounded research decision support in the tested workflow. It would not establish profitable investments, analyst superiority, subjective market value, or stability across screening and portfolio workflows. A broader runtime claim needs additional source-distinct multi-issuer workflow packets with dependence handled explicitly and a finance-domain review if independent high-quality validation is to be asserted.
