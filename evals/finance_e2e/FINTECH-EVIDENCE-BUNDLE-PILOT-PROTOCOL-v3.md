# Source-derived evidence-bundle engineering pilot (v3)

This protocol is frozen before the v3 model calls. AFRM, SOFI and UPST are
previously used development cases, not an unseen quality holdout. The purpose
is only to test whether a source-derived numeric bundle, tool-backed research
review and host-assembled note work together. Do not pool these outputs with
v1 or v2 as independent samples or call a schema pass high-quality insight.

EVIDENCE-BUNDLE-V3-FROZEN-BEFORE-MODEL: yes

## Fixed inputs and behavior

- Use the same six byte-hashed SEC Exhibit 99.1 files and selected 38 audited
  facts as v1, with a fresh Gateway/session/ledger for each issuer, one Flash
  attempt per issuer, in fixed order SOFI→AFRM→UPST. No repair or replacement.
- Before a model call, `financial_evidence_bundle_v1.py` checks adjacent
  reported quarters, computes same-metric sequential and explicit prior-year
  comparisons with `Decimal`, and carries both source hashes. SOFI's Q3
  reconciliation adds the stored **signed** adjustments exactly once. Rounded
  input remains marked approximate; the host omits meaningless percentages.
- Give the verified bundle to the agent. It must still read the thesis/alert,
  record one guarded review, acknowledge the alert and choose its own
  decision. Its final message is an exact JSON envelope: qualitative
  implication, counterpoint, next evidence, valid comparison IDs, bounded
  causal status and the stored decision. New numeric claims in those free-
  text fields are rejected. The host, not the model, renders all table values.
- Reject an unknown comparison ID, unsupported causal-bridge label, invalid
  JSON, extra fields, numerical prose, or decision inconsistent with the
  retained review. A failed assembly remains in the denominator and is not
  published by this workflow. Record raw answer and ledger regardless.

## Controls, budget and interpretation

- Fail-closed source preflight and tool-setup rehearsal before the first paid
  call; hash protocol, code, source files, plugin, binary, template DB, model
  and raw results. New output directory only. Stop on request error, unpriced
  usage or uncertain pricing.
- Estimated model spend cap USD 0.05, with USD 0.015 reserved before the next
  attempt, under the user's existing USD 10 outer authorization. Cost estimates
  and all failed attempts remain visible.
- Report tool/ledger completion, envelope assembly, source-derived arithmetic,
  content review and cost separately. A passed envelope has not been judged
  financially useful. No investment returns or expert-quality claim follows
  from this engineering pilot.
- If the pipeline works, use **different, prospectively frozen source-diverse
  cases** across event→thesis, screening→candidate and portfolio-risk
  workflows for the substantive stability experiment; do not promote these
  three development cases to an unseen holdout.
