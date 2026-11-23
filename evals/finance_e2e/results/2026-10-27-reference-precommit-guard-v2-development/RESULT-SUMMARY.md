# Narrow precommit guard v2: developmental A/B and archival scope

This is a zero-model-call direct-plugin replay of four saved proposals, plus a
read-only scan of the 150-result, 30-issuer source-distinct archive. It is not
a fresh issuer holdout or a prospective quality estimate. The rules were
created after inspecting some of these same answers. The original sealed
answers and ledgers remain unchanged.

| Saved observation | Default arm A | Opt-in guard arm B | Mechanism |
| --- | --- | --- | --- |
| BOKF r5 | `maintain`, `available`, no hold | Original write vetoed before persistence; fallback `needs_review`, `blocked` | Rationale says the research hold is preserved when the stored thesis has no hold. |
| TOST r4 | `maintain`, `available`, no hold | Original write vetoed before persistence; fallback `needs_review`, `blocked` | Rationale interprets a signed tax contribution of `-3` to `+1` USD million as a larger charge. |
| MQ selected high-case answer | `needs_review`, `blocked` | Same; no veto | Correctly bounded control. |
| EFX r5 | `needs_review`, `blocked`, wrong tax explanation saved | `needs_review`, `blocked`, erroneous explanation replaced with deterministic warning | The original tool argument remains in the trace, but the durable review no longer presents the wrong tax direction as accepted analysis. |

All eight replay branches passed the script's assertions: exactly one linked
review per branch; active status and conviction 3 preserved; both vetoes
happened before any review write; each fallback blocked downstream action.
`python3 -m unittest test_plugin.py test_review_arithmetic_guard.py -q`
passed 38 tests, including preservation of a hold when the trusted source
catalog lacks the pair. `replay_reference_precommit_guard_v2.py` reproduces the
paired direct-plugin check using isolated temporary ledgers and no provider.

The current-code [scripted Gateway A/B](../2026-10-27-reference-precommit-gateway-ab-development-v6/SUMMARY.json)
also passed all eight branches. It used the compiled Gateway from this checkout
and a read-only source configuration DB cloned to isolated temporary homes;
the model interface was a local scripted loopback provider, not DeepSeek.
Each guarded BOKF/TOST trace contains the `review_arithmetic_contradiction`
tool result followed by a `needs_review` tool call. The linked review, alert
acknowledgement, final hold/actionability and one-to-one tool-call/result
checks passed. MQ stays blocked with its review text unchanged. EFX stays
blocked, but only the guarded arm replaces its wrong tax explanation with a
neutral, flagged rationale. The [Gateway artifact hashes](../2026-10-27-reference-precommit-gateway-ab-development-v6/RESULT-SHA256.txt)
were independently verified. The earlier v4 replay is retained as the
historical pre-sanitization behavior; v5 preceded the negation-phrase
false-positive hardening. The initial sandboxed v3 attempt could not bind
loopback and generated no completed branch. There were zero external provider
requests and zero new model observations in the v6 replay.

`audit_reference_precommit_guard_offline_v2.py` re-verifies the raw result
and masked-packet hashes, then checks all 150 saved review rationales using
the current guard. It flagged eight (BLK r2, BOKF r5, EFX r5, HIG r2,
JKHY r2, RJF r2, TOST r4 and r5); five original decisions were actionable
`maintain` writes and three were already blocked `needs_review` writes.
Flags outside the four-item diagnostic set are not new quality judgments.
In particular, unflagged results are not presumed correct, and a flagged
saved rationale is not an observed model recovery.

Important boundary: the guarded path checks the **stored review proposal**
against a trusted source-bound catalog and state; it does not check the final
chat answer or resolve every inference. The local A/B separates a model's
specific bad proposal from a tool-boundary containment mechanism. It does
not establish that this opt-in guard is enabled in the production Gateway,
that model reasoning has improved, or that unseen issuers would be protected.

Current-code SHA-256 at this replay version:

```text
1b900bc643ef23c1743915e59694a5666c60a3817d643e5c86134500644c948a  plugins/finance-tools/review_arithmetic_guard.py
62132d3726ada77640da4ad4008ead8465b71bf18407a124d1f65a5da2c9eded  plugins/finance-tools/plugin.py
ad78f5d7d6af79da5c767243fd75080c275ef8a854d93191474f53301f3de7a0  evals/finance_e2e/replay_reference_precommit_guard_v2.py
a1d088aa174fa73a62b3016d4ae0c68a69ca27fe3980b5da5faf3ba93927192f  evals/finance_e2e/audit_reference_precommit_guard_offline_v2.py
7d2090f17fd2ba0948f04a983fc15ed40f973f939820349d1b70d36622937f5b  evals/finance_e2e/run_reference_precommit_gateway_ab_v2.py
```
