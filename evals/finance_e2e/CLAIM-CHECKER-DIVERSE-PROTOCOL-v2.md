# Diverse financial-claim checker feasibility panel (v2 draft)

This is a **diagnostic** of whether a second model can catch material research-interpretation errors. It is not a production guard, an independent human review, a correction of the original answers, or evidence of profitable insight. The earlier SEC-case authorization did not cover archived internal outputs. The user separately authorized sending these ten masked historical answers and short source contexts to the configured DeepSeek service for this diagnostic, with an estimated USD 0.03 ceiling, on 2026-10-23.

ARCHIVED-OUTPUT-EGRESS-AUTHORIZED: yes

## Why v2 is separate

The unrun v1 checker prompt names the Intel charge-bundle/gross-margin failure mode explicitly; seven of its ten examples are Intel-related. That makes a good result vulnerable to prompt leakage and cluster correlation. v2 keeps v1 intact and uses five **different material-error mechanisms** with five previously judged sound controls: conflicting point claims cast as a range, unsupported capacity inference from a capex correction, operating-expense accrual confused with revenue, unproved bitcoin mix explanation, and an invented crypto-specific growth comparison. Controls span corresponding or adjacent case families. The labels remain Codex judgments, so this is not an independent gold standard.

## Freeze, masking, and audit

- `claim_checker_diverse_cases_v2.json` lists 10 retained observations by anonymous letter, archived result path, context and private oracle. Before a run, verify every archived `result.json` hash, relevant SEC source hash or synthetic fixture identity, and the selected final-answer field. Freeze a pre-run manifest of the corpus, source packets, model/prompt, runner, Gateway and template DB. Mask experiment case/observation IDs in the answer; issuer names and financial facts remain visible. Do not send the `result_dir`, first-pass label, oracle, judge notes, or any source document beyond the selected neutral context to the checker.
- Same generic prompt and fresh Flash session for each letter, fixed randomized order/seed. The checker returns JSON `verdict` (`material_issue`, `no_material_issue`, or `not_assessable`), `issue_type`, `reason`, `source_pointer`, `corrected_sentence` and `confidence`. The generic prompt must not teach any one case's answer. An unsupported negative or positive verdict is an error. The checker may mark evidence insufficient instead of guessing.
- Ten planned calls, estimated cap USD 0.03, reserve USD 0.005 before the next call; stop on request error, unpriced or cost-uncertain usage. Preserve all raw outputs, errors and estimates, including malformed JSON, with no replacement runs or prompt tuning after results.
- Score a confusion matrix against the frozen first-pass labels, separately count abstentions, malformed outputs, execution failures, and false positives/negatives. A 5/5 sensitivity and 5/5 specificity target is exploratory and deliberately stringent; any miss is informative. Because several cases share issuers and source packets, these ten outputs do not estimate general checker reliability.

Passing this tiny diagnostic would justify only a **prospective, broader checker experiment** with unseen issuer cases and a separately evaluated intervention in the runtime. A checker verdict cannot silently rewrite a research answer or ledger state. The original broad goal still requires the agent itself to produce stable, source-grounded insight across workflows; detecting some known past errors is not a substitute.
