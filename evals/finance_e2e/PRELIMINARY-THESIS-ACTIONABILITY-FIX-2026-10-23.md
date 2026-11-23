# Preliminary thesis actionability: runtime rule and free replay

The historical live Skill-to-ledger v2 result is retained unchanged. It stored a price-only AMD thesis with `status=researching`, `decision_hold=false`, and the old derived `actionability=available`, even though fundamentals and valuation were explicitly unverified. This is a state-presentation/decision-eligibility defect, not a claim that the price calculation was wrong. The source result, ledger, and earlier adjudication remain historical artifacts.

The finance state serializer now derives `actionability` from both the event hold and thesis lifecycle status:

| State | Returned actionability |
| --- | --- |
| Any status with `decision_hold=true` | `blocked` |
| `researching` or `watch`, no hold | `research_only` |
| `invalidated` or `archived`, no hold | `closed` |
| `active`, no hold | `available` |

The serialized `decision_hold` flag is unchanged; a preliminary thesis is not falsely called an event-driven missing-metric hold. The rule applies to both `thesis_save` and later `thesis_get`/list responses through the shared serializer. The isolated plugin test creates a `researching` thesis, checks `research_only` on creation and retrieval, then activates it and checks `available`. The full 24-test plugin suite passed. A read-only replay against the archived AMD SQLite row returned `research_only` with the new serializer and did not mutate the archived ledger. This is a **free deterministic replay**, not a new model observation or a retroactive change to the old result.

This fix blocks a misleading affordance for draft/closed theses, but does **not** prove the underlying financial insight is high quality. In particular, it does not establish that an `active` thesis has complete fundamentals or valuation: that needs a separately specified evidence-eligibility policy, and the final model prose still needs claim-level checking. No standing user Gateway was restarted, so any already-running process may continue using its previously loaded plugin until restarted in a separate authorized deployment step.
