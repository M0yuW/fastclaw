# Project Handoff

## Current branch

- Branch: `feat/wire-spawn-subagent`
- Goal: route `spawn_subagent` through an internal MessageBus/TaskQueue execution path instead of invoking sibling agents directly.

## Completed changes

### Internal MessageBus RPC

- Added trusted internal request, delivery, and reply types.
- Added correlated request/reply handling with unique correlation IDs.
- Added bounded pending capacity and non-blocking delivery backpressure.
- Added call-path and wait-graph cycle detection.
- Added shutdown handling that rejects new requests and releases pending callers.
- Added context helpers for root execution IDs and immutable sub-agent call paths.

### TaskQueue internal tasks

- Added internal/external response modes and the `cancelled` task state.
- Added `SubmitInternal` with source, owner, correlation, call-path, and parent execution metadata.
- Added validation for required internal task fields and same-lane re-entry.
- Added an internal-task capacity bound.
- Internal child tasks inherit the root execution slot, avoiding parent/child deadlock when global concurrency is one.
- Request cancellation and queue shutdown propagate to queued/running internal tasks.
- Completion callbacks run exactly once; callback panics are contained and do not leak capacity.
- Completed tasks release retained callback and request-context references.
- Handler panics are converted to task failures.

### Gateway and agent integration

- `spawn_subagent` now returns errors and sends requests through the internal MessageBus RPC path.
- Gateway validates source/target ownership, call paths, cycles, and target availability before queue submission.
- Internal requests execute through the target user's TaskQueue and return results through correlated replies.
- Agent session-bound registry state is protected by a per-agent turn gate.
- Internal sub-agent execution suppresses channel typing/outbound replies and media delivery.
- The external `message` tool is unavailable during internal execution.
- User-space loading wires each agent with an owner-scoped, source-aware sub-agent spawner.

### Observability

`GET /api/tasks` now exposes:

- `internal`
- `sourceAgentId`
- `correlationId`
- `callPath`
- `parentChatKey`

## Tests added

- Internal MessageBus round trip.
- Call-path and cross-root wait-cycle rejection.
- Shutdown releasing pending internal callers.
- `spawn_subagent` source/call metadata and error propagation.
- Internal TaskQueue execution inheritance at `maxConcurrent=1`.
- Exactly-once completion during shutdown.
- Required-field and parent re-entry validation.
- Defensive call-path copying.
- Completion panic containment and capacity release.

## Validation

The focused validation completed successfully:

```text
go test ./internal/taskqueue ./internal/bus ./internal/agent/tools ./internal/gateway ./internal/setup
go test -race ./internal/taskqueue ./internal/bus
go vet ./internal/taskqueue ./internal/bus ./internal/gateway ./internal/setup
git diff --check
```

## Follow-up considerations

- Add a Gateway integration test covering the full coordinator -> MessageBus -> TaskQueue -> sub-agent -> reply path.
- Consider making internal pending/queue capacity configurable if production workloads exceed the current fixed limits.
- Consider replacing TaskQueue's simple in-memory task retention/sorting with a bounded structure if task volume grows substantially.
