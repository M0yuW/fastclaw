# Accounting-lineage quality gate: proposed runtime experiment

Status: a structured-claim validator exists in
`../../plugins/finance-tools/accounting_lineage.py`. It is now connected to
`thesis_record_review` **only for alerts with trusted statement-line metadata**.
The plugin rejects incompatible claims before a ledger write and replaces
the model's draft rationale with a source-bound generated summary. Eight
deterministic controls and the full 30-test finance-tools unit suite pass,
including rejection with unchanged ledger version. It still **does not
constrain the final chat answer or assess decision merit**, and no model-backed
guarded end-to-end run has yet been completed. These unit results must not be
reported as an end-to-end financial-insight improvement.

A separate **model-free** isolated Gateway smoke in
`smoke_accounting_guard_gateway_local_v1.py` now passes under the
`finance-review-only` policy: the direct tool write rejects an income-tax
to gross-margin claim without changing the ledger, accepts a cost-of-sales
claim, and the Gateway starts with the finance plugin registered. It made
zero model calls. An initial sandbox-restricted localhost attempt timed out;
the retry with localhost permission passed and left no paid request. This
confirms startup and write-path wiring, not agent behavior.

## Why this is needed

The existing `finance-tools__thesis_record_review` write path verifies a stored alert's source/required-metric completeness, conflicts and optimistic version, but stores the model's `rationale` as free text. In the five-repeat Intel charge-composition retest, **5/5** reviews executed correctly while **2/5** persisted or displayed an unsupported gross-margin attribution. Adding more source facts was insufficient. A quality mechanism must check *which financial-statement line* supports a causal claim, not only whether a source hash and numbers are present.

## General rule, not an Intel exception

For the model-backed guarded test, use the existing `finance-review-only`
Gateway policy, not `finance-workflow-pilot`: the latter permits
`thesis_save`, whereas the review-only preset denies both `thesis_save` and
`event_alert_ingest`. Only the trusted harness may seed the thesis and
source-classified alert. Go policy tests pass, but an end-to-end policy
trace is still required before counting any guarded trial as valid.

Trusted event ingestion, not the reviewing model, supplies for each source fact: `fact_id`, value/unit/period, source hash, `statement_line` (`revenue`, `cost_of_sales`, `operating_expense`, `nonoperating`, `income_tax`, `balance_sheet`, or `unknown`), and whether the source explicitly links that item to a target metric. The classification is independently audited against the primary document. A model-generated claim names the target metric (`gross_margin`, `operating_margin`, `net_income`, etc.), the driver fact IDs, and strength (`directly_stated`, `consistent_with`, `unresolved`).

Before any substantive thesis state write, validate the structured claim against a fixed accounting dependency graph. An `income_tax` or `nonoperating` fact cannot directly explain `gross_margin`; `cost_of_sales` may affect it, but the claim may not quantify its contribution in percentage points without a sourced reconciliation. `unknown` or missing line classification cannot support `directly_stated`; the safe outcome is unresolved attribution. For a mixed charge bundle, each component must be validated separately. The guard must not equate a large EPS effect with a gross-margin effect.

Free-text rationale is a bypass if it can contradict the validated fields. A guarded review must therefore publish a rationale assembled from validated, structured claims and source-bound observations, while keeping the draft prose in a separate non-authoritative trace; or it must use a separate checker that flags and blocks unsupported free-text causal assertions before commit. A word-list-only regex over `rationale` is not sufficient. This is an opt-in experimental path so existing unguarded ledgers are not retroactively reinterpreted.

## Negative and positive controls

Use SEC-locked cases with distinct accounting relationships, not only repeats of Intel:

1. **Intel Q3 2024:** USD 3.1 billion manufacturing-asset charges substantially in cost of sales may be cited as a gross-margin influence; USD 2.9 billion goodwill/intangible impairment and USD 9.9 billion deferred-tax-asset valuation allowance may not be assigned to gross margin. The USD 2.8 billion restructuring charge is separate from the USD 15.9 billion bundle. Do not assert that the USD 3.1 billion explains the entire 20.4-point observed margin decline without a bridge.
2. **Nike Q2 FY2025:** The SEC exhibit states gross margin fell 100 basis points to 43.6%, primarily due to higher discounts and channel mix, partly offset by lower product input, warehousing and logistics costs. A source-explicit margin-driver claim should be *accepted*. Revenue fell 8% on a reported basis and Nike Brand Digital fell 21%; do not conflate these with margin points.
3. **NVIDIA Q2 FY2025:** GAAP gross margin fell 3.3 percentage points sequentially while revenue rose 122% year over year. The supplied selected table alone gives co-occurrence, not a line-item causal bridge. A specific margin-driver claim from that table should be deferred, while the numerical contrast is allowed.
4. **AMD Q3 2024:** GAAP gross margin was 50% (up 3 points year over year) while Gaming revenue fell 69% year over year. Segment decline is a countervailing risk, not by itself proof of what caused consolidated gross-margin change.

These are not unseen issuer filings: they test the guard's *logic* and false-accept/false-reject behavior across different statement lines. Before a model-backed run, freeze one separately sourced new-issuer control to test transfer rather than merely memorizing these four companies.

## Evaluation design and gates

1. Unit tests: accepted cost-of-sales and source-explicit pricing/mix claims; rejected tax/goodwill→gross-margin and whole-bundle attribution; unresolved missing line or missing reconciliation; no ledger mutation on rejection. Check version and alert state after rejection.
2. Free deterministic replay: send previously retained bad Intel claims and good Nike/NVIDIA/AMD controls through the gate, before any paid calls. Report confusion matrix by distinct claim, not by paraphrased duplicate.
3. Prospective model-backed arm: freeze prompts, plugin/runtime hashes, source packets and independent numeric oracle. Run five fresh repeats per case with a bounded cost cap, retaining every attempt. Compare guarded versus unguarded in separate arms; score actual final/persisted text, tool traces, source/calc accuracy, risk, state and research utility. Do not score a blocked bad review as a high-quality insight; it is a *safe rejection* and must be followed by a corrected review or a `needs_review` hold.
4. Independent assessment: Codex can provide a first-pass LLM-as-judge score, ideally on masked outputs; disclose that no independent finance expert is available. A guard's pass rate alone cannot prove valuable insights or future returns.

The primary success criterion is not “more reviews accepted.” It is **zero persisted unsupported causal attributions among test controls, with legitimate source-supported claims still accepted and useful reviews completed**. Also report abstentions, recovery turns, latency, tool counts and cost. This would support a bounded runtime-quality claim only after cross-case, prospective evidence; it would not establish universal stable high-quality insight.
