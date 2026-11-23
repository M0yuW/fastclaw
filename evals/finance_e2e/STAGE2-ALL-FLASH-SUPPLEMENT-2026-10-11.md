# Stage 2A all-Flash supplement

This is a separate, capacity-matched supplement to the frozen v2 study. It
uses the same owner-reviewed SEC evidence, source lock, task wording, grader,
runtime, and eight cases prespecified for the v2 capacity ablation: one medium
longitudinal and one large point-in-time case for each of four companies.

Each case has three repetitions. Both `solo_staged` and
`team_shared_retrieval` use `deepseek/deepseek-v4-flash` for all model calls,
giving 8 x 3 x 2 = 48 planned observations. Preserve paired case/repetition
identifiers and randomized mode order. Report quality, end-to-end latency,
tokens, estimated cost, and infrastructure errors; do not pool these results
with v2 primary observations or substitute them for the prespecified all-Pro
ablation. This comparison isolates model allocation more effectively, but
architecture still bundles orchestration, prompting, and parallel execution.

Use the isolated local Gateway and a separately hashed result directory.
Retain every failure. Pause on any unmetered cost, an infrastructure-error
rate above 5%, or the conservative combined spending guard. The user's
earlier USD 10 authorization is a total ceiling across related Stage 2 runs,
not a fresh budget for this supplement; estimated cost is not provider billing.

The first attempted supplement case used the existing 18955 Gateway. Its
`finance-coordinator` and `finance-solo` Agent records still selected Pro,
despite the all-Flash suite declaration. The model-allocation manifest check
rejected the case. Preserve that JSON as a nonconforming pilot, exclude all
six observations, and count its estimated cost. The corrected v2 supplement
uses a separate 18956 Gateway and database snapshot with every research Agent
configured for Flash; its results go to a distinct directory and study ID.
