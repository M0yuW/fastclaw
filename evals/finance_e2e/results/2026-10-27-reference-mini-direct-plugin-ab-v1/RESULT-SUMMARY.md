# New-issuer direct-plugin pre-commit A/B

Developmental test with **injected** review rationales, not saved model output. Three identical tool proposals were replayed against separate temporary ledgers. Arm A disabled the optional review-arithmetic guard; arm B enabled it with the same case's trusted SEC source hashes and comparison catalog. Initial thesis, alert, decision (`maintain`), rationale and evidence were the same in both arms. No Gateway or external model request was made.

| Source case and fixed proposed claim | Guard-off A | Guard-on B | Interpretation |
| --- | --- | --- | --- |
| CSGP: “Operating profit rose by more than revenue.” | `maintain` saved; thesis available | `operating_revenue_increment_reversed` veto; no original write; subsequent deterministic `needs_review` hold saved, thesis blocked | Narrow arithmetic contradiction successfully intercepted. |
| CSGP: “The tax expense created a larger tax drag.” | `maintain` saved; thesis available | `signed_tax_contribution_reversed` veto; subsequent `needs_review` hold saved, thesis blocked | Signed tax-expense/benefit direction successfully intercepted. |
| RPAY: “The GAAP loss improvement proves recurring operating recovery.” | `maintain` saved; thesis available | Same wrong rationale and `maintain` saved; thesis available | **Uncaught inference error.** Q2's disclosed impairment prevents this selected evidence from proving recurring recovery, but the lexical arithmetic guard has no rule for that causal inference. |

Both arms linked exactly one review to the seeded alert; the comparison concerns the pre-commit decision on deliberately bad prose. A pre-commit veto is an error return, not itself a saved hold: the blocked B state for the first two rows required the explicitly scripted safe follow-up write. An autonomous agent may or may not take that recovery step. The third row is a concrete boundary: a configured guard and correct source hashes do not make the full analysis safe. It remains an adjudication target in any future model-generated RPAY answer; do not count this A/B as prospective model quality or as a completed end-to-end experiment.
