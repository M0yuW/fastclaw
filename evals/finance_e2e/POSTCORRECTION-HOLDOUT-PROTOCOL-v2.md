# Post-correction SEC event holdout protocol v2

Status: **candidate frame and source eligibility complete (20/20); model-free 100-observation run-order preflight, all-20 local scripted Gateway replay and price checks complete; payment authorization and model observations pending**. This is a new experiment, not a retrospective repair or replacement score for the failed v1 event panel.

## Question and bounded claim

Can the existing agent runtime, with a deterministic source-audited numeric context and an enforced `needs_review` decision hold, repeatedly produce source-grounded, decision-useful **financial research-state updates**? The target is operational insight quality under the frozen SEC event→thesis review workflow. It does not test investment returns, price prediction, or whether Team is more intelligent than Solo.

The original v1 five-issuer/25-session result stays in the record. GS-r5 and BNY-r2 contained material reasoning errors; FISV-r3 recorded `needs_review` while remaining actionable. Those issuers cannot be reclassified as fresh v2 cases. The v1 20-of-20 all-success gate is not recoverable by swapping them out.

## New candidate frame

`postcorrection_holdout_frame_v2.json` identifies **20 source-distinct issuers** (five per business stratum), 100 planned observations at five fresh sessions each. It retains all 15 v1 primary issuers without model output, includes the four unused v1 reserves in this separately declared study, and adds WFC as the top SHA-256-ranked issuer from a frozen bank extension pool. No issuer with v1 model output is eligible. The ranking verifier reads and checks all 25 v1 raw-result hashes and the frozen SEC ticker snapshot. It reports the selected CIKs and extension order without making a model call.

All 20 candidates now have selected-row source audits against locked SEC exhibits and have passed the model-free numeric preflight. A source-ineligible candidate may be replaced only by the next unused pre-ranked extension in the same stratum, with the reason recorded before any answer for that candidate. Model failure, inconvenient facts, or a low judge score are never replacement reasons. FOUR uses its adjacent Q4 2024/Q1 2025 EX-99.1 pair; its later EX-99.2 material is not silently treated as an eligible EX-99.1 source.

## Intervention to freeze before paid execution

1. Archive original SEC exhibit bytes and hashes; manually audit the selected rows and cross-filing comparators. A SHA-256 alone does not prove transcription or accounting comparability.
2. Host code computes same-metric differences and, where a total and selected components are declared, the **unlisted residual**. The model-facing numeric context may include only fact IDs, displayed source values, period/basis/unit labels, computed deltas, residuals, and source hashes. It must exclude the packet's private `precommitted_interpretation_checks`, judge labels, and v1 model answers. An arithmetic mix is not a business-causal explanation.
3. The agent must still independently identify a supported implication, a material counterpoint, missing evidence, and a research-state decision; it reads and writes the real ledger/alert tools. The finance plugin's new `needs_review` rule must yield `actionability=blocked` and be tested in the actual Gateway before v2 calls. Neither a host table nor tool success automatically earns a quality pass.
4. Freeze exact prompt, code hashes, source hashes, model alias/version observability, Gateway build, case order, price source, and spend stop in a new run manifest **before** any paid call. Do not mutate v1 manifests or raw answers.

## Execution and judgment

- Five isolated sessions and ledgers per eligible issuer, no outcome-based retries, all errors/timeouts retained. Run order must be frozen before calls. Do not share a single ledger across repetitions.
- The unchanged `INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md` assesses every material claim in both final prose and persisted review against SEC rows, calculations, and tool state. Each observation gets F/I/R/S/U, critical-error codes, and `high`, `adequate`, `problematic`, or `not_assessable`; the case gate requires all five execution/fact passes, no critical error, and at least four high with at most one adequate. The 20-case all-success gate is the previously declared route to a Bonferroni-adjusted one-sided 95% lower bound above 80%, **conditional on the stated source universe**. A single failed cluster falsifies that strict gate; do not revise it after outputs.
- Codex self-review or an independent LLM-as-judge is a documented diagnostic, **not** a blinded finance-professional assessment. Mask run order and mechanical outcomes before qualitative rating where possible. If no expert reviewer becomes available, any resulting conclusion must explicitly be bounded as source-grounded operational research quality, not proven economic value.
- Judge source-grounding against facts and scope information that the agent could actually see in its prompt, ledger, or available tools. The private source packet remains the external correctness oracle, but an undisclosed narrative footnote must not be treated as a fact the agent was required to recite. An assertion that *goes beyond* the visible evidence (such as constant-scope organic growth from a raw quarter-on-quarter level change) can still be penalized as an unsupported inference.
- Screening→candidate and portfolio-risk remain separate workflow claims. Reusing overlapping issuers in multiple packets does not provide independent 20-case evidence for either; build source-disjoint frames or use a weaker dependence-aware analysis. Passing this event arm alone cannot establish general cross-workflow financial insight reliability.

No new paid calls are authorized by this protocol. Obtain a specific call/spend cap after source and Gateway preflight, and stop if pricing or usage becomes uncertain.
