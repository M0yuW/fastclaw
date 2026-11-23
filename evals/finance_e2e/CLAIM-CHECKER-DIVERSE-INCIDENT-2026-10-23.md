# Diverse claim checker: interrupted attempt (2026-10-23)

This is **not a scored checker result**. The user authorized transmission of at most ten masked archived answers and brief contexts to the configured DeepSeek service for this diagnostic, with an estimated USD 0.03 ceiling. The frozen corpus and source preflight passed (10 items, five material-error labels and five controls, three SEC exhibits hash-verified). The prompt did not include the first-pass label or oracle.

Two new result directories were created; neither was overwritten:

| Directory suffix | Observation | Provider call | Retained outcome |
| --- | --- | --- | --- |
| `2026-10-23-claim-checker-diverse-flash-v2` | S | None | Isolated Gateway startup did not complete in the sandbox. `S/result.json` records the startup/cleanup failure and USD 0 estimated model use. The original result-hash writer also failed on a relative path, so this directory has no generated `RESULT-SHA256.txt`. |
| `2026-10-23-claim-checker-diverse-flash-v2-recovery` | S | **One** Flash call to `https://api.deepseek.com/chat/completions` | The Gateway log records the outbound call and model response, but the runner raised `FileExistsError` after copying the log and before writing `S/result.json`. No checker verdict, token usage or priced estimate was retained. The manifest and log remain; the generated hash list contains only the manifest. |

Read-only SHA-256 values for the first directory are `fe7a9f0db2325f79d817777c23525e79c56c893f18a04335f94db562c3a1708a` (`manifest.json`) and `235bf330aed3ab2b56f3e996a4dcb27b584885018ce95e6f352e162614c714f6` (`S/result.json`). For the recovery directory they are `16c05b5a8a0fda99c5c01be4109b975cd53c5fad22f0b85a8a8374ddff3e7cbb` (`manifest.json`) and `19db206c8e19a5d01613d3410e024074dd4260ef9657e6dd05520c1a7beaf30d` (`S/gateway.log`). The log line reporting `hook: after model call` establishes that a response arrived, not what its answer or cost was.

The runner now accepts an already-created per-item log directory, writes a raw-response checkpoint before Gateway shutdown or scoring, and hashes relative result paths correctly; three free tests and source preflight pass. **No further provider call was made** after the unpriced response. The prespecified stop-on-cost-uncertainty rule applies, and the lost response is not reconstructed, replaced, labelled, or counted as a successful observation. A future run requires a separately defined cost treatment and a fresh result directory; this incident cannot establish checker sensitivity, specificity or financial-insight quality.
