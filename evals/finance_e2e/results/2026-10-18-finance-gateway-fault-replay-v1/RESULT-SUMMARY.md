# Isolated Gateway fault replay (no paid model)

The actual local HTTP Gateway and finance plugin were exercised with a scripted provider bound only to localhost. The copied provider configuration was replaced in each temporary Gateway home before startup. No DeepSeek request was made, and these replays are not additional model observations or scored workflow successes. The frozen W01F-r1 result was not modified.

| Branch | Tool calls/results | Rejected malformed reviews | Persisted reviews | Final alert | Terminal result |
|---|---:|---:|---:|---|---|
| Error then correction | 3/3 | 1 `invalid_input` | 1 | `acknowledged` | Scripted completion |
| Repeated error | 8/8 | 8 `invalid_input` | 0 | `new` | Maximum tool-iteration fallback |

Every recorded branch check in `recovery.json` and `budget.json` passed. This confirms that invalid arguments are rejected without a ledger write, a later corrected call can finish the workflow, and a repeated-error run can stop with incomplete ledger state. It also confirms a diagnostic gap: the exhausted run returns normal-looking final text instead of a typed budget-exhausted error. The local scripted provider does not test whether a real model would recover.

`manifest.json` records script, plugin, Gateway binary, and template hashes. The replay is a Go Gateway-path test, not a Go/Python differential run.
