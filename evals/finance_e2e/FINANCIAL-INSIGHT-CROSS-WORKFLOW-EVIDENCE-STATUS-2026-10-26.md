# Financial-insight quality evidence across workflows — 2026-10-26

This is a **status map**, not a pooled score. The three historical arms below
used different cases, prompts and engineering revisions. Their raw-result
SHA-256 lists were rechecked on this date; content judgments are the archived
non-independent Codex reviews, not finance-expert or investment-outcome labels.

| Tested workflow and frozen arm | Mechanical execution | High content labels | Predeclared case clusters passing | What it shows |
| --- | ---: | ---: | ---: | --- |
| [SEC event → thesis review, first five issuers](results/2026-10-23-prospective-event-batch1-flash-v1/FIRST-BATCH-CLAIM-ADJUDICATION-SUMMARY-v1.md) | 24/25 | 10/25 | 0/5 | Source-linked review and alert workflow mostly ran, but wrong comparisons, over-attribution and one actionability mismatch prevented a stable-quality claim. |
| [Historical SEC screening → preliminary candidate, COIN/HOOD/SQ](results/2026-10-22-fintech-sec-screen-output-limit-flash-v2/RESULT-SUMMARY.md) | 15/15 | 5/15 | 0/3 | Correct screen inclusion/exclusion and state did not prevent unsupported base/mix claims or one material top-line/expense confusion. |
| [Historical SEC + partial portfolio policy bound, two fictional cases](results/2026-10-22-fintech-sec-portfolio-bound-retest-flash-v3-policy-fix/RESULT-SUMMARY.md) | 10/10 | 3/10 | 0/2 | The typed bound tool fixed the policy conclusion, but qualitative issuer-risk inferences still fell short. The same two cases were reused after development. |

These arms are **adverse or insufficient evidence** for “the current system
stably produces high-quality financial insights.” Mechanical completion is an
engineering result and is not the content success rate. The screening and
portfolio arms are too small, source-overlapping and partly development-tuned
to support population reliability. No result can be rescued by pooling five
repetitions as independent cases or by silently dropping a failed cluster.

The [new 30-issuer source-distinct event arm](REFERENCE-SOURCE-DISTINCT-INSIGHT-CONFIRMATION-PROTOCOL-v1.md)
is prepared but **has zero paid model observations** until separately
authorized. It tests only the event workflow. Even if it meets its 28/30
event-only or 29/30 three-workflow-adjusted case threshold after claim-level
adjudication, a broader cross-workflow statement still requires new
source-distinct screening and portfolio case packets. A 20-cluster panel of
three-issuer packets needs 60 issuer events per workflow if packets are
source-disjoint within that workflow; overlapping reuse within an arm cannot
be called 20 independent cases. Reusing a frozen issuer universe across
different arms creates cross-workflow dependence that must be disclosed;
Bonferroni simultaneous bounds do not require the arms themselves to be
independent. The absence of blinded finance-domain review remains a limit on
any subjective high-quality claim.

A deterministic [source-packet allocation](results/2026-10-26-cross-workflow-packet-allocation-v1/ALLOCATION.json)
now assigns all 30 qualified issuers exactly once to ten three-issuer packets,
each spanning three business strata. This is **only an allocation**, not a
screening or portfolio experiment: prompts, fictional holdings/policies,
adjudication checks and extra sources are not frozen. Reaching the 20-packet
target within either workflow still requires ten additional source-disjoint
packets, i.e. 30 more qualified issuer events. The same packet identities may
be reused across the two workflow arms if their dependence is disclosed, but
no issuer is reused within an arm's independent-packet denominator.
