# Masked financial-claim checker feasibility experiment

This is a **diagnostic**, not a production guard or proof of financial-insight quality. Ten previously retained research outputs are frozen in `causal_claim_checker_cases_v1.json`: five material-error cases and five controls previously judged sound for the tested issue. Their source `result.json` hashes and the primary-source SEC cache hashes must be verified before calls. The checker sees an anonymous case letter, the text under review, a neutral source excerpt, and the stated thesis invalidation terms where relevant. It must not see the original observation ID, label, or oracle. The scoring oracle stays in the case file but is never included in the prompt.

**Authorization status:** not yet authorized to send these archived internal research
outputs to the external DeepSeek service. An attempted launch was rejected by
the environment's egress review before the runner started; no checker result
directory was created and no model call was made. Earlier permission to send
SEC case materials and prompts does not cover this additional payload. The
runner now requires an explicit archived-output-egress flag, and execution
must still await direct user authorization and any required sandbox approval.

The checker is a fresh `deepseek/deepseek-v4-flash` session per item on the existing Gateway and responds only with JSON: `verdict` (`material_issue` or `no_material_issue`), `issue_type`, `reason`, `corrected_sentence`, and `confidence`. Use the same prompt for every case. No tools, ledger mutation, market data or external lookup should be needed. Ten calls are planned; retain all raw outputs and terminal/model metadata. Stop before a new call at USD 0.03 estimated cumulative spend, and stop on any request error or unpriced/uncertain usage.

The 5/5 error sensitivity and 5/5 control specificity targets are intentionally strict for this tiny feasibility panel. Report a confusion matrix and exact failures. Do not tune the prompt after seeing the first output or silently retry. Repeated Intel examples are correlated and the labels come from the same Codex reviewer, so even a perfect result would only justify a broader, prospective, cross-issuer checker experiment. A checker verdict is not allowed to overwrite an original research result, and an error it detects is not itself a corrected financial insight.
