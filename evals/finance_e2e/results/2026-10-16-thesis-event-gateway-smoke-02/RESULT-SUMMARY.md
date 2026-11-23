# SEC Event to Thesis Gateway Smoke: AMD Q3 2024

Status: **one model-in-the-loop integration attempt passed**. This is an
engineering smoke test, not a formal accuracy estimate or Team/Solo comparison.

The Gateway listened on `127.0.0.1:18955` with a fresh SQLite snapshot and a
separate `finance-tools` ledger. It used the Q2 and Q3 AMD SEC artifacts whose
SHA-256 values are fixed in `source-lock.json`. The Q3 event was ingested as a
fixture before the agent turn. The agent's available runtime tools were limited
to finance thesis/alert review operations; no trading or portfolio tool was
exposed.

The agent made four provider calls and four plugin calls:

1. `finance-tools__thesis_get`
2. `finance-tools__alert_list`
3. `finance-tools__thesis_record_review`
4. `finance-tools__alert_update`

The ledger contains exactly one new review, thesis version `1 → 2`, unchanged
`active` status and conviction `3`, the Q3 SEC source ID and artifact hash, and
an acknowledged alert. All six predeclared state checks in `result.json`
passed. The final text also described higher revenue and gross margin alongside
lower Gaming revenue, with no trade action. Elapsed wall time was 15.071 s.

Usage was 14,242 prompt tokens (including 8,832 reported cache-read tokens)
and 1,214 completion tokens. The runtime did **not** have pricing configured
for this request: all four model calls report `priced=false` and a displayed
estimated cost of zero. Zero is **not** a billing claim. At the earlier frozen
study's Pro rates, a cache-adjusted estimate is USD 0.003442; charging all
prompt tokens at the uncached input rate gives USD 0.007251. Neither number is
the provider invoice.

The previous attempt in `2026-10-16-thesis-event-gateway-smoke-01` failed
before model inference because a dotted plugin tool name was rejected by the
provider's function-name validation. It made no ledger review or alert-state
change. The runtime now exposes provider-safe names of the form
`plugin-id__tool-name`; the gateway integration and full Go test suite passed
after this correction.

Limitations: the prompt explicitly required conservative status/conviction
preservation, and the Q3 event was seeded rather than autonomously retrieved.
This result validates tool exposure, agent execution, and persisted-state
verification for one case. It does not establish independent insight quality,
robust duplicate-review handling, retrieval quality, or general success rate.
