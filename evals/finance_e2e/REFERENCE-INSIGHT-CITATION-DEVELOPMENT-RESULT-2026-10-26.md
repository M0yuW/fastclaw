# Citation-development Flash run — 2026-10-26

This is a **seen-case development diagnostic**, not a source-distinct or
independent validation of high-quality financial insight. The user authorized
FITB, RELY, TFC, and VRSK twice each under a new USD 0.25 cumulative
**estimated** cost ceiling. The two append-only result directories and their
SHA-256 lists preserve every attempt:

- [Initial v2 directory](results/2026-10-26-reference-insight-citation-development-flash-v2/): the first scheduled TFC repetition 1 failed before a model turn because the isolated Gateway could not finish startup in the sandbox. It has zero model calls and zero estimated model cost. It was not retried.
- [Remaining-seven directory](results/2026-10-26-reference-insight-citation-development-flash-v2-remaining7/): the other seven scheduled IDs ran outside that sandbox against isolated Gateway and finance-ledger copies. A separate free scripted Gateway replay first passed with zero external requests.

| Observation boundary | Count |
| --- | ---: |
| Scheduled independent sessions | 8 |
| Actual model-backed sessions | 7 |
| Pre-model environment failure, retained | 1 |
| Model-backed runtime/ledger mechanical completion | 7/7 |
| Candidate for qualitative review under prospective v2 gate | 4/7 |
| Held by deterministic gate | 3/7 |
| Request errors / uncertain-cost / unpriced sequences in model-backed run | 0 / 0 / 0 |
| Cumulative estimated new model cost | USD 0.051838692 |

The seven model-backed sessions each persisted exactly one linked review and
acknowledged the corresponding alert; the ledger actionability agreed with the
persisted decision. In two FITB sessions, the trace shows two attempted review
tool calls but only one persisted linked review, so `mechanical completion`
must not be read as “no recoverable tool errors.” Both result manifests and all
listed outputs passed SHA-256 verification.

The initial pre-run protocol text is preserved separately in the
[initial snapshot](REFERENCE-INSIGHT-CITATION-DEVELOPMENT-PROTOCOL-v2-initial-snapshot.md)
because the working protocol gained a continuation addendum after the first
attempt. The two run manifests pin their respective protocol hashes.

The held cases were FITB repetition 1 (malformed final JSON despite a `stop`
finish reason), FITB repetition 2 (the saved rationale violated the strict
number-free prose contract, including period labels), and VRSK repetition 2
(same-direction GAAP profit evidence assigned opposing roles). The four
remaining responses—RELY repetitions 1 and 2, TFC repetition 2, and VRSK
repetition 1—are **candidates for claim-level review only**. A valid SEC
comparison ID and a consistent ledger state do not establish that the
interpretation, causal language, or omitted context is financially sound.
No response has `quality_pass=true`.

The prompt/gate change was developed after the earlier eight seen-case
observations. Comparing counts between those batches would confound a changed
prompt, changed gate, repeated issuers, and sampling noise; it is not an
estimated improvement effect. The source-distinct 30-issuer panel remains
unrun, and this result does not support a stability or high-quality claim.
