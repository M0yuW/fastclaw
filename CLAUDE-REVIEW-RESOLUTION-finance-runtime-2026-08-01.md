# Claude Review Resolution: Finance Runtime and Project Report

## 1. Scope and Decision

This document maps the findings in `CLAUDE-REVIEW-FINDINGS-finance-runtime-2026-08-01.md` to implemented changes, tests, residual risks, and reporting decisions. The review was treated as a blocking audit of three coupled surfaces:

1. the production agent runtime;
2. the evaluation harness and financial suite;
3. `project-report/`, including its Markdown source, generator, DOCX, and PDF.

The original `r1`–`r4` finance runs are retained as calibration or fault-discovery artifacts. The post-fix primary artifact is `finance-runtime-formal-r5.json`. No earlier score is promoted to validation evidence.

## 2. Critical Findings

| Finding | Resolution | Verification |
|---|---|---|
| C1: forbidden assertion failed under quotation and negation | Replaced raw substring logic with clause-local assertion matching; normalized quotation/table punctuation; distinguished expected negative assertions from negated positive assertions; added conditional-scope suppression for `if`, `unless`, and `whether`. | Unit tests cover quoted assertions, denial, hedging, `instead of`, `rather than`, decimal punctuation, and conditional negative phrases. `r5` records 0/44 Team grounding violations without infrastructure errors. |
| C2: milestone grader lacked direction and negation | Milestones and contributions now share the same bounded, order-sensitive assertion matcher with a maximum token gap. Required positive assertions are rejected under local negation; required negative assertions must be asserted rather than merely hypothesized. | Tests cover reversed state transitions, negative decisions, conditional statements, and cross-clause separation. |
| C3: published scores were not reproducible from the current rubric | Added suite SHA-256 to reports, archived raw artifact SHA-256, labeled `r1`–`r4` as calibration/diagnostic, and ran a new frozen `r5` confirmation after the final matcher repair. | Suite SHA `4fbf54…dc44`; artifact SHA `5366a9…bc00`. The `r5` report preserves the machine-scored 5/6 Team result and does not post hoc override the remaining failure. |
| C4: tool panic could terminate the Gateway | Added panic recovery inside each SDK tool goroutine, stack logging, and an explicit error `tool_result`. | `internal/agent/sdkbridge_test.go` verifies that a panicking tool returns a failure and later tool handling remains well formed. |

## 3. High Findings

| Finding | Resolution | Verification |
|---|---|---|
| H1: duplicate/empty tool-call identifiers copied results | Results are correlated through a consume-once ID map. Empty IDs, duplicate executor IDs, and missing responses become explicit failures; no response is reused for a second call. | Tests cover duplicate request IDs, empty IDs, missing results, and concurrent completion order. |
| H2: SQLite pragma detection used whole-DSN substring matching | Added case-insensitive DSN normalization using parsed query parameters. Path text no longer suppresses pragmas; encoded pragmas are detected; legacy ignored `_journal`/`_fk` keys do not suppress real defaults. | Table-driven DSN tests cover path collisions, mixed case, encoded values, legacy keys, and custom options. |
| H3: WAL and foreign keys applied only to the default factory path | Every SQLite DSN now receives missing WAL, foreign-key, busy-timeout, and immediate-transaction settings. | Integration tests query effective pragmas through both default and custom DSNs. |
| H4: busy timeout did not address read-to-write upgrades | Added `_txlock=immediate` so writers acquire the write lock before reads in a transaction. Retained WAL and busy timeout. | Control/treatment tests reproduce `BUSY_SNAPSHOT` with deferred transactions and verify immediate transactions; a 12-worker public Store API write test completes without lost writes. |
| H5: production sub-agent dedup contradicted its tool description | Production turns now install exact `(agentID, task)` dedup. Eval requests may opt into target-only dedup for the fixed one-call-per-specialist contract. | Tests prove identical production calls reuse one result, distinct tasks for one specialist both execute, and eval target-only mode remains isolated. |
| H6: grounding aggregate covered Team only while baselines used grounding | Added per-baseline grounding assertions, violations, and accuracy; retained Team aggregate under the existing `multi_agent_grounding_*` names. | JSON and text reports expose all four baseline buckets. `r5` reports 44 assertions and 0 violations for each mode. |
| H7: collaboration gain mixed strict and outcome criteria | Fair, compute-matched, and legacy gains use the same Team outcome definition and matching baseline outcome. Validity requires equal evaluated paired counts and zero errors. | Integration tests cover strict-vs-outcome divergence and invalid/error denominators. |
| H8: report failure attributions were incorrect | Deprecated the `r1` narrative as historical calibration and produced `evals/finance-runtime-formal-r5.md` from a new artifact. | The new report names the single Team failure and quotes its actual grader cause. |
| H9: cache-read accounting made token/cost interpretation misleading | Reports now separate provider prompt tokens, cache-read tokens, uncached prompt tokens, completion tokens, and total tokens. Cost calculation deducts cache reads from ordinary prompt pricing when the provider includes them in prompt totals. | OpenAI/Anthropic usage fixtures and `r5` cost reconciliation cover cache behavior and 100% pricing coverage. |
| H10: contribution matcher was unbounded | Added `maxAssertionTokenGap = 8` and clause splitting; milestone and contribution use the same matcher. | Tests reject distant and cross-clause token matches while accepting bounded unit insertions. |

## 4. Medium Findings

| Finding | Resolution | Verification |
|---|---|---|
| M1: tool duration was batch wall time | Tool start time is captured inside each adapter call and recorded by call ID. Hook contexts and plugin hook payloads receive per-tool duration. | Sequential and concurrent duration tests verify distinct elapsed values. |
| M2: milestone and contribution disagreed on identical values | Both use `containsRequiredAssertion`. | Shared behavior tests exercise the same phrase through both graders. |
| M3: delegation precision denominator was not unique | Precision uses unique delegated targets, while total call count remains available as a separate diagnostic. | Duplicate-target tests verify a bounded precision value and explicit unexpected-call count. |
| M4: comparison assigned one delta to two fault fields | Fault-injection and fault-observation deltas are calculated from their corresponding fields. | Compare tests cover divergent source values. |
| M5: fallback revived deliberately invalid gain | Removed availability inference from numeric zero; persisted validity flags govern comparison output. | Invalid-gain tests remain invalid after round-trip and comparison. |
| M6: Solo Two-Pass graded only the second pass | The second prompt requires a self-contained final answer containing every material claim and evidence reference. The measured estimand is the delivered final answer, while usage and cost include both passes. | Integration tests verify shared session context, two calls, combined usage, and self-contained final output. |
| M7: identity fallback swallowed store errors | Store failures fail closed. Filesystem fallback occurs only for `store.ErrNotFound`; missing/empty content receives a configuration-specific error. | Tests cover transient store errors, missing rows, legacy filesystem fallback, and empty files. |
| M8: exported prompt builder discarded identity errors | `BuildSystemPrompt` returns `(string, error)`; the turn validates once and passes the snapshot revision to the internal builder. | Compile-time call-site updates and identity contract tests. |
| M9: per-success cost used strict denominator | Cost per success and tokens per success use Team outcome success, matching the adjacent outcome rate. | Runner tests cover a strict-only failure with passing outcome. |
| M10: model-call sequence reflected completion order | Sequence numbers are reserved at call start and reports sort by that sequence. | Concurrent model-call test forces reverse completion and verifies invocation order. |
| M11: errored baselines still contribute resource cost | Retained intentionally: an errored provider call still consumes billable tokens and cost. Success and latency denominators exclude errors; resource ledgers include consumed resources and print the error count. | Documentation now states this distinction; `r5` has zero errors, so the primary result is unaffected. |

## 5. Low Findings and Residual Risk

| Finding | Decision |
|---|---|
| L1/L2: plural normalization collisions | Removed the second plural trim and exempted `-ss`, `-is`, and `-us` endings. The remaining morphology is intentionally lightweight and is covered only for suite vocabulary. |
| L3: hedges suppressed later positive claims | Hedges suppress a violation only when they occur before the candidate assertion; later `may/could` no longer masks a positive assertion. |
| L4: malformed `agentId` could appear concurrency-safe | Non-string and empty values return `false`. |
| L5: arguments parsed twice | Not functionally divergent after malformed-input fail-safe. Retained as a cleanup opportunity; no correctness claim depends on parser reuse. |
| L6: WAL sidecars affect backup semantics | Added explicitly to the project report. Deployment documentation should prescribe online backup or checkpoint-aware copying. |
| L7: defensive padding block was unreachable | Result construction now originates from the request list and explicitly synthesizes missing results. The defensive invariant remains useful if the SDK changes. |
| L8: SDK fan-out has no local semaphore | Residual risk. The internal bus has backpressure, but a very wide single model response can still generate avoidable failures. A per-turn sub-agent fan-out bound remains future work. |

## 6. Project Report Review and Remediation

The review correctly found that every generated report artifact predated the finance experiment and that the Markdown described a prospective four-mode study as unexecuted. The report has therefore been revised from the source of truth outward:

1. `project-report/fastclaw_project_report.md` now distinguishes the historical two-mode regression from the six-case four-mode confirmation.
2. The baseline section now defines `solo_open_book`, `solo_two_pass`, `team`, and `oracle_team`; outcome includes milestones and grounding.
3. Section VII reports `r5` quality, grounding, prompt/cache/output tokens, cost, latency, hashes, and the remaining grader limitation.
4. The discussion no longer claims an orchestration benefit: Team tied both matched Solo baselines at 83.3%.
5. SQLite WAL/immediate-transaction behavior, tool panic containment, exact production dedup, identity snapshots, per-tool duration, and start-order telemetry are documented.
6. `build_report.py` no longer hard-codes the historical result table; the Markdown table is the single source of truth.
7. The sequence figure now labels three parallel specialist turns and three correlated replies.
8. `project-report/artifact.md` no longer pins stale coverage or generated-page counts and now lists `r5` and this resolution record.

The DOCX and PDF must be regenerated only after Markdown and generator validation, then rendered and inspected page by page. Binary artifacts are not edited manually.

## 7. Final Experiment Record

| Item | Value |
|---|---|
| Primary raw artifact | `finance-runtime-formal-r5.json` |
| Artifact SHA-256 | `5366a91398ca575d303af56d62da179f2a3f1fb13a1d0f5aae5c1773debfbc00` |
| Suite SHA-256 | `4fbf54eca61dc7363342ea1db364cb84426e1541937a99c1e1266dbfb3e5dc44` |
| Team / Open / Two-Pass / Oracle | 5/6, 5/6, 5/6, 4/6 |
| Fair / compute-matched gain | 0.0 pp / 0.0 pp |
| Baseline errors | 0 |
| Team grounding | 44 assertions, 0 violations |
| Team tokens / cost | 41,219 / USD 0.008335 |
| Team P50 / P95 | 21.30 s / 22.49 s |
| Model calls / pricing coverage | 54 / 100% |

## 8. Claims Boundary

Safe claim: FastClaw implements and tests a real coordinator–specialist runtime with tenant scope, bounded delegation, concurrent specialist execution, error-aware evaluation, and coordinator/specialist token-cost-latency attribution. On a six-case fixed-evidence confirmation, Team tied evidence-matched one-pass and two-pass Solo at 83.3%, with no baseline execution errors and no configured grounding violations.

Unsafe claim: multi-agent orchestration improves financial decision quality, predicts markets, produces alpha, achieves an official benchmark score, or has been independently validated. The present evidence does not support these statements.

## 9. Final Verification

- `go test ./internal/eval ./internal/agent ./internal/agent/tools ./internal/store ./internal/plugin ./internal/evaltenant ./internal/api ./cmd/fastclaw -count=1`: passed.
- `go test -race ./internal/agent ./internal/agent/tools ./internal/store -count=1`: passed.
- `go test ./... -count=1`: passed.
- `python3 -m unittest -v` in `plugins/finance-tools`: 10/10 passed.
- `git diff --check`: passed.
- `r5` cost buckets reconcile to total cost within `1e-12`.
- Gateway port 18953: closed after the real run.
- Final DOCX: 20 rendered pages, SHA-256 `c42d1403d28fdefcc0524833fb6d02eeaa663276cbed255da9451d61649bdad5`.
- Final PDF: 20 Letter pages, SHA-256 `98f8f5ad540b1271435ffef9268fd6460b85d2eb3d446b98e9482f17bbe3edba`.
- Every final PDF page was visually inspected; no clipping, overlap, unreadable table, orphaned caption, or forced blank page remained.
