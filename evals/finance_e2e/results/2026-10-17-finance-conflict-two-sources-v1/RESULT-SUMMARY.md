# Independent-source conflict addendum (exploratory)

This addendum addresses a limitation of W02 in the four-workflow v2 panel: two conflicting claims there shared one fixture-document hash. Here simulated management statements A and B were frozen in separate files with distinct SHA-256 hashes, dated 2025-02-10 and 2025-02-12, respectively. They claim USD 8 billion and USD 5 billion for the same FY2025 capex plan, with no explicit correction. The alert stored both source references and both observed metrics. These are synthetic business documents, not SEC filings or real market data.

Two isolated model-backed repetitions completed with no request/provider error. In both, the tool trace and persisted review linked both distinct hashes, preserved the 8B/5B conflict, advanced the thesis one version, and acknowledged the alert. Estimated model cost was USD 0.008402 under the frozen pricing table, below the USD 0.03 stop.

The research-state behavior diverged:

| Attempt | Persisted decision | Persisted thesis state | Interpretation |
|---|---|---|---|
| W02S-r1 | `needs_review` | `researching`, conviction 3 | The agent deferred the decision but changed status from `active`; the current plugin permits this when all required metrics are present. |
| W02S-r2 | `invalidate` | `invalidated`, conviction 1 | The agent preserved both claims but treated “unreconciled spending-plan change” as an invalidation. |

Neither met the addendum's predeclared combined expectation of `needs_review` with unchanged status and conviction. However, the seeded thesis itself combined “preserve both claims and request clarification” with “unreconciled spending-plan change” as an invalidation condition. That ambiguity makes W02S-r2 a **case-design / decision-calibration ambiguity**, not a clean runtime defect. W02S-r1 exposes a narrower application invariant gap: the deterministic finance guard constrains state change for *missing required metrics*, but not for complete yet contradictory evidence. The core runtime executed the permitted tool calls and stored both outcomes as requested. Do not report this addendum as a 0/2 model quality score or silently replace it with a revised passing case.

Before a confirmatory conflict test, define a non-contradictory business rule for whether unresolved source disagreement mandates `needs_review` and whether state must be held unchanged. If that rule is safety-critical, enforce it in the trusted finance layer rather than relying only on a model instruction. The source identity and conflict metadata should be checked against the two independently hashed input documents; a model-provided conflict flag alone would not be sufficient.
