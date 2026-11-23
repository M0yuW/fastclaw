# Missing-evidence decision hold: repair and scope

The frozen 2026-10-19 80-observation panel revealed a state-rule gap: all five
E4 and all five C4 runs recorded `needs_review` for a missing required event
metric, yet the final thesis still had `decision_hold=false` and
`actionability=available`. The original ledger set a hold at ingestion for
`unresolved_conflicts`, and forced a `needs_review` decision for missing
metrics, but its state update included only `unresolved_conflicts` in the
hold predicate. A correct review decision therefore did not imply a blocked
thesis. The former panel and its original scores remain untouched.

The current plugin now:

1. Sets a decision hold **at stored alert ingestion** when any thesis-required
   metric is absent, just as it already did for unresolved source conflicts.
   Thus there is no available/actionable interval while awaiting the review.
2. Keeps status and conviction unchanged for a held review and blocks direct
   thesis status/conviction or required-metric changes, so a caller cannot
   remove the missing field from the thesis to bypass the hold.
3. Persists the missing metric list in the linked `needs_review` record and
   retains `actionability=blocked` after that review.
4. Allows a missing-metric hold to clear only after a substantive review of a
   *different stored alert* for the same market, symbol, event type and
   `as_of` period, with every required metric present, no unresolved
   conflicts, and source-hash continuity when the original alert had a
   source. A later-period alert, unsourced numeric claim or unrelated source
   cannot silently release it.

This is a **new-code behavior**, not a retroactive repair of historical
ledger snapshots. The sealed panel's manifest records the historical code
hashes; current plugin and harness source hashes necessarily differ after
the fix, while all 80 historical `result.json` hashes still match their
post-run audit records. A source hash establishes traceability to a stored
document; it does not by itself prove the document's external authenticity.
Unresolved source-conflict holds remain conservative and are not
auto-released by this missing-metric path. A model choosing `needs_review`
without an objectively missing required metric or stored conflict (for
example C3-r1/r4) is still a distinct policy case; such prose is not
automatically translated into a ledger hold by this repair.

Free verification: `plugins/finance-tools/test_plugin.py` includes missing
one metric, missing all metrics, hold-on-ingest, held-state review,
later-period rejection, unsourced input rejection, wrong-source rejection,
same-period sourced completion and hold release. The 16-case harness's
expected version/actionability checks were updated for the new ingestion
transition. No paid model call is part of these tests.
