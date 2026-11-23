# Stage 2 Go runtime revision (engineering record)

Date: 2026-10-10. This record describes changes made **after** the paused Stage 2A v1 confirmatory attempt. It does not amend that frozen run, replace its failed observations, or claim a new experimental result.

## Changes, in order

1. The finance runner now supplies raw-corpus or retrieved evidence in an eval-only `subagent_shared_context` request field. The Go runtime appends that field to each specialist task in both batch and single-agent delegation. The coordinator prompt asks for a short batch tool call containing the question, protocol, and role assignments rather than copying the evidence into `spawn_subagent` arguments.
2. The OpenAI-compatible provider preserves the final `finish_reason`. A truncated model response or invalid tool-argument JSON now ends the turn immediately instead of dispatching a malformed call and allowing repeated retries. The failure is recorded in model-call telemetry.
3. The finance runner gives the Gateway a server-side deadline slightly before the client deadline. On timeout, the Gateway can return its partial model-call record and an error trace. Errored model calls carry `cost_uncertain: true`; the Python batch runner halts on missing or uncertain cost instead of treating the reported estimate as a complete bill.

These are treatment/runtime changes. A future paid run must use a **new study version**, a freshly built executable, and a new content-hash manifest; it must not append to the existing v1 result directory. Preserve the v1 timeouts in the historical record. Verify the actual provider-billed balance separately: an estimate derived from incomplete usage cannot guarantee an exact USD 10 cap.

Local checks completed: Go tests for provider, agent, tools, API, and eval packages; 14 Python safety/artifact tests; and a Go CLI build. No external model call was made during these checks. The already-running Gateway has not been restarted with the revised binary.
