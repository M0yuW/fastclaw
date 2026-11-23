# Qualitative source-explicit lineage: tool-contract clarification

In the frozen same-case fresh-SEC recovery diagnostic, both AAPL answers kept GAAP and adjusted EPS distinct but omitted the source-explicit qualitative tax-to-GAAP-EPS link from structured `causal_claims`. The result summary records that the agent appeared to treat a numerical attribution as required for any causal claim. This left a useful official-source link in prose but not in the guarded ledger rationale. The diagnostic is historical and remains unchanged.

The accounting-lineage validator already distinguishes a qualitative `directly_stated` claim from a quantified contribution: the former requires a trusted stored fact with `source_explicit_targets` naming the target; the latter additionally requires a reconciled attribution. The tool schema now states this distinction next to `causal_claims.strength` and in the array description. It does not loosen validation, infer a tax-to-EPS amount, or manufacture a source link. The plugin's schema regression and complete 36-test discovery pass.

This is only a **contract-clarity repair**. No new model observation has tested whether the agent now records the AAPL link, and the three-issuer diagnostic cannot be converted into a prospective new-issuer result. The pending Affirm/SoFi/Upstart source-frozen panel is the next planned generalization check.
