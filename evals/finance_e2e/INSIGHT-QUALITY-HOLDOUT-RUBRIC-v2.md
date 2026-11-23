# Prospective source-bounded insight rubric v2

Frozen for `PROSPECTIVE-CROSS-WORKFLOW-HOLDOUT-v1.md` before any model output from its new issuer cases. This assesses operational research quality, not future return or the economic value of a recommendation. The older v1 rubric was retrospective and does not silently become a prospective gold standard.

## Unit, materials, and blinding

Judge each fresh observation, then aggregate five observations into a case-packet/workflow cluster. An event→review packet may contain one issuer; a screen or portfolio packet may contain several. Before seeing mechanical labels or run order, the judge receives an anonymized answer, persisted tool outputs, final ledger and alert state, and a frozen source packet with byte hashes and line/row locators. Both final prose and persisted review or candidate-thesis rationales are in scope. Tool-call imitation in prose is not execution. A missing raw response, source, trace, or ledger state is `not_assessable` where needed, never a presumed pass.

First enumerate every *material* claim: reported number, period/basis comparison, explanation of a driver, risk/counterevidence statement, and asserted decision or state change. For each claim retain the exact answer span, supporting SEC row/fact ID or tool-state pointer, arithmetic if derived, and one of `supported`, `bounded_hypothesis`, `unsupported`, `contradicted`, or `unassessable`. Source-company management explanations may be attributed as their statements; they are not automatically established causal facts. An unreferenced claim does not become supported merely because a deterministic table accompanies it.

## Scores (0, 1, 2, or NA)

| Dimension | 2 | 1 | 0 |
| --- | --- | --- | --- |
| F: factual and numeric fidelity | All material numbers, units, periods, metric definitions, directions, and arithmetic match the frozen source and declared rounding. | Only non-decision-changing omission or imprecision. | A material wrong fact, comparison, period, unit, basis, or calculation. |
| I: inference discipline | Decision implication follows from available evidence, alternatives are bounded, no unsupported causal bridge. | Useful main implication but a noncritical inference is weakly qualified. | Unsupported attribution, trend, certainty, or reversal that could change interpretation. |
| R: risk and uncertainty | Salient counterevidence and missing inputs correctly handled; justified deferral is allowed. | Partial but nonmisleading treatment. | Critical counterevidence omitted, certainty fabricated, or avoidant deferral hides a provable material bound. |
| S: state and action alignment | Final prose, tool trace, alerts, and persisted ledger agree; blocked states are non-actionable. | Imprecise wording without decision consequence. | Invented write/hold/alert, false state assurance, or blocked state used downstream. |
| U: research utility | States a supported implication and a relevant evidence-to-seek or decision condition; a well-justified no-action outcome can score 2. | Accurate but mostly repeats inputs. | Proposed implication would mislead the declared research decision. |

Use NA only when a dimension genuinely cannot apply; do not use it to erase missing evidence. A critical error is a materially wrong source/calculation, unsupported causal claim that changes the thesis, false policy or risk bound, a false ledger/action state, or an actionable recommendation without required evidence. Record a code and evidence pointer for each critical error.

`high_within_case` requires F=I=R=U=2, S=2 (or NA only when the workflow truly has no state), no critical error, completed execution, and an assessable implication. `adequate_within_case` requires all applicable dimensions at least 1 and no critical error but misses the high threshold. `problematic` means any applicable 0 or critical error. `not_assessable` means retained evidence is insufficient for a fair judgment; it does not pass. Treat a source-grounded `needs_review` with an actually blocked ledger as potentially high, not as a failed investment call. Conversely, prose saying “needs review” while the ledger stays actionable fails S.

## Case and workflow aggregation

The cluster passes only if all five fresh sessions complete the required tool/ledger workflow and pass the fact gate, none has a critical error, and at least four of five are high; the fifth may be noncritical adequate. Failures and timeouts remain in the denominator. Report each F/I/R/S/U vector, all claim-level exceptions, exact source/tool pointers, and the cluster result. No judge may edit a raw answer, result file, source packet, or original score after seeing the aggregate; a correction is a new adjudication version with both versions retained.

Aggregate source-distinct case packets separately for event→review, screen→candidate and portfolio-risk. Repetitions within a packet are correlated and are not independent samples; overlapping issuers across packets within one workflow also create dependence. The current 20-issuer source frame can supply 20 independent-candidate event packets, but not 20 independent multi-issuer screening or portfolio packets by reuse alone. Any eventual 20-cluster workflow panel is a bounded operational reliability test over its declared universe, not a universal finance-domain success rate. Without a blinded finance-domain human reviewer, Codex and a separate LLM-as-judge provide documented diagnostic judgments, not independent expert validation.
