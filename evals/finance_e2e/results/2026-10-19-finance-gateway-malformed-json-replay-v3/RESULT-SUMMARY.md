# Malformed finance-tool JSON: final local Gateway replay

This is deterministic fault injection against an isolated local Gateway and finance ledger with a scripted localhost provider. No DeepSeek request or paid model call was made. The frozen C3 observation remains failed and unchanged.

Both branches passed all replay checks. In `repair.json`, the first malformed review call received a paired tool error; a corrected review and alert acknowledgement then completed. In `exhausted.json`, a second malformed review call produced the typed trace terminal `malformed_tool_arguments_exhausted`; no review was written and the alert remained new. Every emitted tool call had a correlated result. The manifest records the final Gateway binary and script hashes.

This verifies recovery and failure reporting on the local HTTP path. It does not prove that the real model would correct its own C3 output, nor does it identify whether the original malformed bytes came from model generation or provider-stream assembly.
