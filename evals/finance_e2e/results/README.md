# Finance E2E Results

This directory stores reproducible, non-secret runtime reports and derived
diagnostics for the SEC-grounded longitudinal finance study.

Each report must retain the suite `source_sha256`. Analyze it only against the
exact suite snapshot whose SHA-256 matches that field. API keys, provider
credentials, local databases, and raw SEC cache files must never be stored here.

The strict team pass rate is not interpreted alone. Review fair Team/Solo
baselines, evidence-ID retention, unauthorized numeric derivations, latency,
tokens, cost, and grader failures together.

`2026-08-02-pilot-r7-4cases.json` is the final calibrated four-company pilot.
R2 through R6 are benchmark-development and grader-calibration artifacts and
must not be used for comparative inference. See
`2026-08-02-pilot-r7-summary.md` for the validity analysis and limitations.

The retrieval-mediated orchestration pilot is summarized in
`2026-08-02-retrieval-pilot-final-summary.md`. Its five final mode observations
are stored in `v8`, `v9`, and `v10`; each has the same suite and source-lock
hashes. Files `v1` through `v7` are engineering calibration artifacts and must
not be pooled with the final observations. The `team_raw_context` observation
inside `v9` is superseded by `v10`, which preserves batch delegation trace JSON.
The machine-readable file mapping, checksums, replay commands, and explicit
calibration exclusions are stored in
`2026-08-02-retrieval-pilot-final.manifest.json`.
