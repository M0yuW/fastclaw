# Three-issuer free Gateway preflight, 2026-10-27

This is a local, scripted-provider seam check **before** any new paid or model-generated observation. It does not assess financial insight quality. The three fixtures came from `preflight_reference_mini_panel_v1.py` and were inserted, one at a time, into the existing `run_reference_source_distinct_gateway_replay_v1.py` harness. The second pass enabled `reviewArithmeticGuardCatalogPath` in each isolated copied Gateway DB using a catalog bound to that case's source hashes. Neither pass modified the user's running Gateway or the original source exhibits.

| Fixture | Guard off: six checks | Guard on: six checks | External-provider requests |
| --- | --- | --- | --- |
| MTB Q2→Q3 | 6/6 | 6/6 | 0 |
| RPAY Q2→Q3 | 6/6 | 6/6 | 0 |
| CSGP Q2→Q3 | 6/6 | 6/6 | 0 |

Each scripted pass checked five local provider steps, source hashes and all comparison IDs in the provider prompt, four paired finance-tool calls/results, one linked review, a blocked thesis with acknowledged alert, and a rendered reference candidate whose quality status remained unset. The guard-on pass shows that a valid `needs_review` write is not falsely rejected in these three scripted examples. It does **not** establish guard sensitivity to wrong financial claims on these new issuers; existing four-case seen-data A/B tests are separate developmental evidence.

Inputs: Gateway binary SHA-256 `16059290d3b755779bbafca077b2dc563573d89c3bb2423b4933c9ed19820414`; isolated template DB SHA-256 `92e2fc07e45a0f6ab1cf502bf25a5f57d1da987ad59f505b50a0271666b5648f`; source-selection SHA-256 `b201677bf3ff3beaf1617249ed941edacc0ca3f212ec4808eb27cfc2a23247bc`. The source-row verifier reported 15 MTB, 12 RPAY and 14 CSGP comparable rows plus one RPAY Q2-only impairment row. All six scripted passes completed locally with no DeepSeek request and zero estimated external cost. The expected run order for any later model sessions is SHA-256 `d7d1e7eb6efc7ae85bd2e445bc81813073f9be183c2ffb9d25ef6f7747fe1fc9`.

The remaining experiment is to obtain **new model answers**, retain all six attempts, score final prose and persisted state claim by claim, and (only where a wrong first write occurs) replay the saved proposal with the guard off/on on fresh isolated ledgers. This summary is not a substitute for that experiment.
