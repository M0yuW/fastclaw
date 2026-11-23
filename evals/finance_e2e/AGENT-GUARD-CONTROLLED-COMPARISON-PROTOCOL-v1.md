# Controlled attribution: model conclusions versus agent containment (v1)

Status: prospective design, written while the 30-issuer source-distinct Flash
baseline is running. This document is not a result or authorization for a new
paid arm. It does not alter that arm's frozen prompt, code, manifests or scores.

## Question and unit

The primary question is whether an agent-side publication/action guard can
detect and contain unsupported or contradictory research conclusions that the
fixed model still generates. The paired unit is one frozen model output and its
saved review/ledger state. Issuer clusters, not five correlated repetitions,
are the independent candidate units for any stability statement.

## Fixed evidence and two comparisons

1. **Generation diagnosis:** seal all raw baseline outputs, tool traces,
   sources, usage and ledger states. Mask outcome and run identity before
   claim-level F/I/R/S/U adjudication. Classify each exception as source
   extraction, arithmetic, inference, missing risk, false state, execution,
   or unassessable. Do not infer a model cause from a failed aggregate gate.
2. **Paired, zero-model-call containment replay:** feed each *unchanged* raw
   tool-call trace and final output to (A) the baseline path and (B) one frozen
   two-stage deterministic guard. Before `thesis_record_review`, B can veto
   only defects observable in the review arguments and source/ledger context;
   this prevents an unsafe state write. After the final answer, B may publish
   an assessable source-linked candidate only if its required reference/schema,
   numeric-lineage, semantic red-flag and actual-ledger checks pass. Otherwise
   B must hold the candidate and block downstream decision use. The second
   stage cannot claim to undo a previous review write. B preserves the raw
   output and original ledger observation; a separate counterfactual ledger
   records pre-commit veto effects. Execute the guard through the real local
   tool and publication/action boundaries in a scripted Gateway replay, not
   merely by changing a CSV label.

The existing review tool may already have changed status or conviction before
the post-hoc candidate card is produced. Writing a later `needs_review` would
block future decisions but would **not undo that earlier state change**. B
therefore needs a pre-commit veto (or a replay that intercepts the original
review write before it reaches the ledger). Check the preserved baseline and
counterfactual ledger separately; never call a post-hoc label a state rollback.

The guard implementation and its tests must be frozen before reading the
baseline's claim-level judgments. Existing seen-case development errors may
inform rules, but the 30 new issuers' answers may not be used to tune B. A
later online rerun, if useful, is a **separate** paid arm needing its own
authorization and manifest; it cannot be silently pooled with the baseline.

## Outcomes and interpretation

Report, by exception type and issuer cluster: critical conclusions generated;
critical conclusions released by A and B; guard true holds and false holds
against the blinded claim audit; mechanical completion; actual blocked versus
available ledger state; and cost/latency of the replay. A non-alert is never
an automatic quality pass. Missing raw evidence is unassessable, not safe.

Because the model output is identical in A and B, a reduction in erroneous
*release* can be attributed to the agent guard, not to improved model
reasoning. The replay cannot estimate whether the model would reason better
under a new prompt, whether another model would do better, or investment
value. To compare model capabilities, a different-model arm must separately
hold cases, prompt, tools, guard, limits and judging fixed. No broad
"stable high-quality financial insight" claim follows from runtime
completion or from a guard that simply holds every answer.
