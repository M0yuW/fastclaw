# Developmental pre-commit attribution replay

This is a zero-external-provider A/B replay on two saved model review calls,
first against the finance plugin and then through a locally scripted Gateway.
It does not change the sealed 150 observations or estimate guard performance
on unseen issuers. The v3 rule was written after inspecting some of these
answers, so the result is a mechanism check only.

Reproduce with the bundled Python runtime:

`python3 evals/finance_e2e/replay_reference_precommit_guard_v1.py`

The script loads the original masked review-call arguments and the frozen
source-distinct fixtures. It creates separate fresh ledgers for A and B. A
forwards the recorded model call unchanged. In B, the opt-in finance-plugin
guard checks the proposed review rationale against a trusted, source-hash-bound
comparison catalog *inside* `thesis_record_review`, before any review or thesis
write. When it detects an explicit arithmetic contradiction, the plugin rejects
the original call; the replay then records a deterministic source-linked
`needs_review` hold. This is a tool-boundary intervention, not a post-final
label or a rollback of an earlier write. The guard is off by default and covers
only the stated arithmetic patterns; it is not a general inference judge.

| Fixed saved answer | A original review | B guarded review | What the paired replay shows |
| --- | --- | --- | --- |
| JKHY `J-a43fcf41e603f011` | `maintain`, `actionability=available`, no hold | Arithmetic veto; `needs_review`, `actionability=blocked`, status `active` and conviction 3 unchanged | The original model's review incorrectly said operating-income growth exceeded revenue growth; the frozen rows are USD 28.368m and 29.366m respectively. B prevented that review from leaving the thesis actionable. |
| MQ `J-12d921bb4b32208c` | `needs_review`, blocked | No veto; same `needs_review`, blocked | This correctly bounded positive case was not held *because of a false arithmetic alert*. |

Both arms wrote exactly one review linked to the newly ingested alert in each
fresh ledger. The direct plugin replay's explicit checks passed on both cases.
No model or Gateway requests occurred in that replay; external cost was zero.
A script exit code of zero is conditional on all checks passing.

The separate [Gateway A/B result](results/2026-10-27-reference-precommit-gateway-ab-development-v2/SUMMARY.json)
used a locally scripted provider, the same saved review arguments, two fresh
isolated cases and two arms per case. Its four branches passed their checks,
including matched tool-call/results, alert acknowledgement, source-bound veto
visibility, and persisted ledger state. JKHY's unguarded branch remained
`maintain`/available; in the guarded branch, the unsafe write was rejected and
the scripted recovery wrote `needs_review`/blocked without changing active
status or conviction 3. MQ remained blocked in both arms without a false veto.
The [result hashes](results/2026-10-27-reference-precommit-gateway-ab-development-v2/RESULT-SHA256.txt)
were verified after the run. There were zero external provider requests, zero
new model observations, and zero estimated external cost.

The outcome separates one model-generated arithmetic error from one possible
agent-side containment mechanism. The Gateway replay proves that this opt-in
plugin configuration can intercept this particular saved call on the real
tool path. It does **not** show that the existing production Gateway has the
guard enabled or that the guard works broadly. Earlier post-final publication
checks could hold a card, but could not undo an already available ledger state.
A genuinely unseen-case comparison is still required before claiming
containment effectiveness or a false-hold rate. The 100 currently reviewed
answers were not selected as an unbiased sample for those estimates.

The companion read-only comparison script
`compare_reference_insight_screens_v3.py` uses the same 100 locally reviewed
saved answers (93 parseable final JSON objects). Relative to v2, v3 removes
seven broad tax-direction flags and adds an explicit effective-rate flag on
ACIW plus two arithmetic-bridge flags on JKHY and BLK. The mechanical gate
already held BLK; the JKHY case changes from candidate to held. Six answers
change from held to candidate because the broad tax flag is removed, including
two EWBC answers labelled problematic for *other* reasons. This trade-off
shows why a semantic screen cannot be advertised as a general financial
quality judge: neither a flag nor the absence of one identifies every
material inference or risk-state defect.

The later [archival scope audit](results/2026-10-27-reference-precommit-archival-scope-v2/SUMMARY.json)
verified the hashes of all 150 saved observations and the 30-issuer source
catalog, then applied this exact plugin guard to each saved review rationale
without changing a ledger. All 150 source pairs were checkable. It found two
explicit arithmetic reversals: JKHY r2, whose original `maintain` review left
the thesis available and would have been vetoed, and BLK r2, whose original
`needs_review` review already blocked the thesis and is outside the current
guard's write-veto condition. Both had earlier local `problematic` labels.
The other 148 rationales were not flagged, including 50 whose masked scores
remain blank. This is a pattern-coverage finding, not evidence that those 148
answers were correct. The rule was developed after some outputs were seen, and
the 100 reviewed outputs were not sampled for a prospective guard-accuracy
estimate; no false-hold, missed-error, or general quality rate follows from
this scan.

Within those 100 non-randomly reviewed answers, 47 received a local
`problematic` label. A separate read-only join to their saved ledgers found
19 `maintain`/available and 28 `needs_review`/blocked outcomes. Only the JKHY
case among the 19 actionable problematic outcomes matched this guard's
explicit pre-commit arithmetic pattern. This is a concrete scope limit: the
guard cannot be substituted for broader evidence, inference, and state-policy
review, and the 19/47 split is not a population error-rate estimate.
The v1 archival scan is retained; v2 adds the saved-ledger actionability
cross-tab without changing the two flags or any original observation.

## Later narrow guard extension (developmental, not a new quality result)

After a response-blind four-observation diagnostic review found a false
research-hold assurance in BOKF and a reversed signed tax contribution in
TOST, the opt-in precommit guard was extended to these two explicit patterns.
The earlier archival result above remains a **historical code-version result**;
rerunning its old script against the current guard code will not reproduce its
two-flag count. The current source and its developmental checks are documented
in [the v2 replay summary](results/2026-10-27-reference-precommit-guard-v2-development/RESULT-SUMMARY.md).

The new direct-plugin A/B uses the same saved model call in each pair. BOKF
and TOST are actionable in the default arm, but their proposed writes are
vetoed before persistence in the guarded arm and replaced by a linked
`needs_review` hold. MQ remains correctly blocked with no veto. EFX is also
blocked in both arms: its material tax explanation error still persists in the
review text in the initial v4 guard. That historical result is retained. The
current opt-in guard instead preserves the `needs_review` hold while replacing
an explicitly contradicted rationale with a neutral warning. It still cannot
certify the rest of the content or the final chat response.

A subsequent [scripted Gateway A/B](results/2026-10-27-reference-precommit-gateway-ab-development-v4/SUMMARY.json)
replayed those four proposals through eight isolated branches. All branch
checks passed and the saved traces show both proposed-write errors and
fallback review calls. It used a local scripted provider, not a live model;
its [hash manifest](results/2026-10-27-reference-precommit-gateway-ab-development-v4/RESULT-SHA256.txt)
was verified. The default/guarded state difference therefore also appears on
the actual local Gateway-to-plugin path, but still only for these seen calls.

The later [v5 Gateway replay](results/2026-10-27-reference-precommit-gateway-ab-development-v5/SUMMARY.json)
tests the safe deferred-review behavior on the same four saved proposals.
All eight branches pass, with EFX's incorrect original text preserved in the
default arm and replaced by a flagged neutral review in the guarded arm;
both remain blocked. MQ's sound deferred-review rationale is unchanged.
The [v5 hash list](results/2026-10-27-reference-precommit-gateway-ab-development-v5/RESULT-SHA256.txt)
was verified. This is containment of a *known explicit pattern*, not model
reasoning improvement or unseen-case guard validation.

After hardening the tax pattern against the correct phrase "not a larger tax
charge", the [v6 Gateway replay](results/2026-10-27-reference-precommit-gateway-ab-development-v6/SUMMARY.json)
again passed all eight branches. Its [hash list](results/2026-10-27-reference-precommit-gateway-ab-development-v6/RESULT-SHA256.txt)
was verified. This v6 artifact, not v4 or v5, corresponds to the current
opt-in guard code.

The read-only current-code scan verified all 150 archived observations and
flagged eight saved rationales, five of which had originally written an
actionable `maintain` review. The rules were built after seeing some of the
same answers, so neither five nor eight estimates prospective detection,
false-positive or reliability rates. No paid provider calls or original result
changes were involved.
