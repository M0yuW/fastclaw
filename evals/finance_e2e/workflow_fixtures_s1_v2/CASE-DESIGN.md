# S1 v2: synthetic screen to sandbox candidate record

This replaces the *design* of S1 for a possible future run; it does not rescore or overwrite S1 v1. The tool fixture remains explicitly synthetic and now supplies a period, as-of date, source identifier, and free-cash-flow unit. One candidate is complete and one lacks a required screen metric.

The task is to screen both names and write at most one **SYNTHETIC PRELIMINARY** candidate record in an isolated ledger for a retained, complete candidate. The record must preserve the exact P/E, free cash flow with unit and period, ROIC, synthetic provenance, and analytical limitations. It is not a real investment thesis or recommendation. A rejected candidate must not receive a record.

The deterministic oracle in `s1_candidate_case_v2.py` checks the screening call, only-complete-candidate selection, sandbox labeling in title and body, exact key values, no alert, and no trading tool. Runtime trace errors, typed incomplete terminals, and `cost_uncertain` calls are separate fail-closed checks in `workflow_runtime_audit_v2.py`. All checks are frozen before any new model observation. No paid S1 v2 observation has been run.
