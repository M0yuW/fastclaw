# Three-issuer illustrative SEC research panel (pre-model protocol)

Status: source-preflight complete; **no model sessions run or authorized by this protocol**. This is a small, source-distinct application demonstration, not a reliability estimate or a replacement for the existing 30-issuer archive. Freeze this file and the source packets before any new answer is observed. A later change requires a new version, not an edit to the scored protocol.

## Fixed frame and workload

Use the three period-eligible issuers in `results/2026-10-27-reference-mini-prospective-source-selection-v1/SOURCE-PAIRS.json`, in its fixed membership order: MTB, RPAY, CSGP. Each has two hash-pinned, SEC-hosted earnings exhibits, for calendar Q2 and Q3 2025. The source-row packets `mtb_mini_source_row_audit_v1.json`, `rpay_mini_source_row_audit_v1.json`, and `csgp_mini_source_row_audit_v1.json` must pass `verify_reference_source_row_packet_v1.py` before a run. This establishes source transcription, not answer quality. Use `preflight_reference_mini_panel_v1.py` to construct the existing event-to-review fixture type and the six-session fixed order; the preflight makes no Gateway or provider request.

Run two fresh, isolated sessions per issuer, six total, with the **same** model, frozen prompt contract, initial thesis status and conviction, source-bound tool configuration, review guard setting, generation limits, and evaluator. Preserve every result, request error, timeout, rejected tool call, trace and ledger copy. No selective retries or replacement runs enter the six-observation denominator. Report provider/model version, per-observation token usage, estimated cost and any usage uncertainty. A separate authorization and bounded incremental cost cap are required before sending material to a model service.

The model receives only the selected source rows, source URLs and hashes, host-computed sequential differences, and workflow instructions. It does **not** receive the following case-critical adjudication notes or a target decision. The Q2/Q3 comparison is sequential, not year-over-year. A `needs_review` decision with a genuinely blocked ledger can be a strong outcome; a confident upgrade is not inherently better.

## Private case-critical checks

| Issuer | Evidence tension to verify, not an answer to supply | Critical misinterpretation to watch for |
| --- | --- | --- |
| MTB | GAAP net income and interest/fee lines improved while the annualized net charge-off ratio rose and allowance-to-loans edged down. Other credit indicators differ; no one ratio alone settles asset quality. | Equating quarterly earnings growth with uniformly improving credit quality, or mixing taxable-equivalent interest income with GAAP interest income without labeling the basis. |
| RPAY | Q2 included a reported USD 103.781 million impairment; GAAP loss contracted in Q3 while company-defined adjusted EBITDA declined slightly. | Treating the GAAP loss improvement as recurring operating recovery without accounting for the nonrecurrence of the Q2 impairment, or conflating adjusted EBITDA with GAAP earnings. |
| CSGP | GAAP revenue and gross profit increased, but expenses increased more and the operating/net loss worsened; company-defined adjusted EBITDA improved. | Claiming growth alone proves profitability improved, confusing tax benefit with a tax charge, or treating adjusted EBITDA as a GAAP replacement. |

These checks describe the adjudicator's source-grounded failure modes; they do not require a predetermined investment view. Financial significance, management explanations and future outlook beyond selected rows must be framed as hypotheses or missing evidence.

## Predeclared evaluation

Score **every** observation's final prose **and persisted rationale** using `INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md`: factual/numeric fidelity (F), inference discipline (I), risk/uncertainty (R), state/action alignment (S), and research utility (U). List material claims with exact source-row or trace pointers; verify derived calculations, units and bases. `high_within_case` requires all applicable dimensions at 2, no critical error, completed execution and an assessable implication. A missing trace or ledger is `not_assessable`, not a pass. Completion, successful tool calls, or a blocked thesis alone are not evidence of high financial quality. The reviewer is the project assistant, not an independent finance-domain human; keep that limitation prominent.

Report six individual outcomes and the issuer-level pair outcomes; do **not** apply the existing five-repetition cluster pass threshold to two runs, call 6/6 a population reliability rate, or infer future investment returns. A single high answer may be shown as an *illustrative capability case* only with its source-value table, calculation bridge, quoted conclusion, tool/ledger trace and a concise limitations note. Show at least one non-high or failed answer if present, and never suppress such results to make the example look better. If no new answer is high, report that fact and do not replace these issuers post hoc.

For errors, distinguish (a) source fixture/transcription failure, (b) model-proposed wrong claim or tool input, (c) runtime or plugin policy that allowed or blocked a wrong write, and (d) evaluator error. The optional arithmetic review guard checks only explicit, machine-decidable contradictions. If enabled for new runs, bind its trusted catalog to these exact source hashes and record that setting. For a wrong first write, replay the saved proposal on isolated ledger copies with guard off/on using a local scripted provider, without fresh model calls, to test the pre-commit effect. Do not attribute a model reasoning error to runtime merely because the runtime executed it; conversely, a rejected or blocked write is not proof the prose is correct.

Pre-run negative-control probes show that this guard can catch a false hold assurance in each case and explicit reversed operating/tax claims where the necessary typed rows exist. It does not detect RPAY's more interpretive but misleading claim that GAAP loss improvement *proves* recurring operating recovery. Treat that as a claim-level inference error if it occurs, not as a guarded pass. Guard coverage is a narrow, versioned engineering property, not a full semantic verifier.

## Report claim boundary

The project report may state that the runtime *can* complete a source-linked, tool-backed research workflow and preserve a high-quality selected answer **if** a new answer passes the declared rubric. The report must separately disclose failures, variability and the absence of independent expert validation. This six-session panel cannot substantiate stable or general financial-insight quality. Existing 30-issuer observations and the selected MQ/AIG examples remain historical, separately labeled evidence; they are not pooled with this prospective mini-panel.
