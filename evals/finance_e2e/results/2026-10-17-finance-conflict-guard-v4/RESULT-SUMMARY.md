# Independent-source conflict guard: bounded regression

This is a synthetic business case, not a real security, SEC filing, or investment recommendation. Two separately frozen and hashed statements provide incompatible FY2025 capital-expenditure plans (USD 8 billion and USD 5 billion). Neither document explicitly corrects the other. The revised thesis defines invalidation only after a final below-USD-7-billion plan is verified following source reconciliation.

The trusted event-ingestion path stored both source-linked claims, detected one same-metric/same-period conflict, and placed the thesis on `decision_hold` before model review. The review tool then required the original alert ID and allowed only `needs_review` with unchanged thesis status and conviction. The persisted thesis therefore remains `active`, conviction 3, with `actionability=blocked`; this means the conclusion is retained as a historical research state but cannot be treated as cleared for downstream decisions.

| Attempt | Linked review | Decision | Thesis state | Hold | Alert | Estimated model cost |
|---|---|---|---|---|---|---:|
| W02G-r1 | Both source hashes and conflict | `needs_review` | `active`, conviction 3 | blocked | acknowledged | USD 0.005318832 |
| W02G-r2 | Both source hashes and conflict | `needs_review` | `active`, conviction 3 | blocked | acknowledged | USD 0.004540820 |

Both attempts passed all seven predeclared mechanical checks. Combined estimated model cost was USD 0.009859652, below the isolated USD 0.03 stop. In r1, the agent first omitted `alert_id`; the tool rejected that write with `alert_required`, and the agent retried successfully. Thus the successful result includes one visibly enforced guard, not merely compliant model behavior. The earlier v3 run had revealed that omission path and remains a separate non-passing development run; its results were not overwritten or counted as this regression.

The control proves a narrow application invariant for this fixture and plugin version, not the factual reliability of the underlying ingestion pipeline or general model quality. Source hashes identify the supplied fixture files, but the plugin does not independently parse their bytes; a trusted ingester must construct correct `source_claims`. A held thesis cannot undergo substantive state/conviction changes through the current finance tools. Releasing the hold requires a separately designed trusted reconciliation and authorization path; merely acknowledging or dismissing an alert does not release it.
