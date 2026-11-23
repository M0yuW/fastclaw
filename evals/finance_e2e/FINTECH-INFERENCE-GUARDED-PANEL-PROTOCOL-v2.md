# Guarded SEC answer-publication diagnostic (v2)

This protocol is frozen before any **v2** model request. It reuses the six
source-hashed SEC exhibits and three issuer packets from v1; those cases and
v1's observed errors are already known. Thus v2 is a post-failure engineering
diagnostic, **not** an unseen holdout or proof of stable quality. Do not edit
the v1 result directory, replace failed v1 observations, or pool v1 and v2
counts as independent cases.

GUARDED-V2-FROZEN-BEFORE-MODEL: yes

## Intervention

- The first research review uses the same Flash model, Gateway, finance tools,
  source packet and review-only policy as v1. It adds one required, source-
  derived check line: AFRM sequential revenue difference; SOFI Q3 GAAP-to-
  adjusted revenue equation; or UPST adjusted-net-loss year-over-year
  direction. The model must derive it, not be given the result.
- A local workflow gate checks that line and conservatively recognizable
  contradictory prose against the frozen packet. It never awards a financial-
  insight score. A candidate with a contradiction, an absent/wrong check, or
  a causal-bridge review flag is withheld from downstream acceptance.
- Exactly one additional answer-only turn may be requested in the **same
  session**, with issue codes but no correct answer supplied. No second
  review, alert update or trade is authorized; any tool call on the repair
  turn makes the publication candidate fail. Both candidate turns, costs,
  traces and the eventual ledger are retained. If the repair still fails,
  the answer is held rather than silently published.
- The Gateway API has returned the first candidate to this harness. The gate
  controls acceptance by this experiment workflow, **not** all Gateway or
  browser responses. This distinction must remain in the report.

## Execution and stops

- Three issuer clusters × five fresh session/Gateway/ledger repeats = 15
  observations in a new output directory, fixed shuffled seed 2246. Old v1
  answers are **not** inserted into model prompts. Only the code and protocol
  learn from the v1 diagnostic; report this adaptivity.
- Freeze code, packet, protocol, plugin, source files, binary, template DB and
  model pricing in the manifest. Run the raw SEC preflight before any model
  call. Reject an existing output directory. Hash raw results before manual
  judgment. Preserve all failures in the denominator.
- Estimated model spend cap USD 0.15, below the user's existing USD 10 outer
  authorization. Reserve USD 0.03 before a fresh observation and USD 0.01
  before an optional repair. Stop on request error, unpriced usage, uncertain
  cost or exhausted reserve; never loosen the cap during a run.
- Compare v2 with v1 on mechanical completion, first-candidate checker flags,
  repaired-or-held status, tool/ledger invariants, estimated cost and full
  first-pass F/I/R/S/U review of the final candidate. The original v1
  predeclared 4/5-per-issuer quality threshold may be reported as a diagnostic
  reference, not reinterpreted as a prospective independent test after v1.

## Claim boundary

The checker is intentionally narrow: it can miss unparsed free-text claims,
unsupported causality, metric-basis confusion, or an incorrect but well-
formatted answer outside its patterns. `candidate_for_manual_claim_review`
means only that these deterministic checks found no specified problem. It is
not `high_within_case`. A fresh, source-diverse, unseen multi-workflow panel
with claim-level review remains necessary for the goal of demonstrating
stable, high-quality financial insights.
