# Testing Strategy

FastClaw uses layered automated checks so concurrency-heavy agent workflows are
verified at the narrowest useful level and again across runtime boundaries.

## Test layers

| Layer | Purpose | Command |
|---|---|---|
| Unit | MessageBus, TaskQueue, provider streaming, sandbox lifecycle | `make test` |
| Integration | Gateway agent flows plus API/Auth/Setup/Store/Eval HTTP and SQLite boundaries | `make test-integration` |
| Race detection | Agent tools, API trace, auth, Eval, cancellation, HTTP handlers, task snapshots | `make test-race` |
| Static analysis | Go correctness checks | `go vet ./...` |
| Frontend | ESLint and production compilation | `cd web && pnpm lint && pnpm build` |

## Sub-agent integration scenarios

The Gateway integration suite uses deterministic in-process LLM providers and
real Agent, MessageBus, TaskQueue, and Gateway components. It does not require
network access or external API credentials.

1. A coordinator delegates to a worker and receives the correlated reply.
2. A coordinator cannot target an agent owned by another tenant.
3. Caller cancellation propagates through the bus and marks the internal task
   as cancelled.

The round-trip test also asserts the model-call sequence, internal task metadata,
and immutable call path. The TaskQueue tests verify that observability snapshots
cannot mutate live queue state.

## Auth, Setup, and Store integration scenarios

The API suite runs the production route tree through `httptest` against a
temporary migrated SQLite database. It covers:

1. First-user onboarding, provider and agent persistence, and duplicate
   onboarding rejection.
2. Session-cookie login, logout, re-login, and disabled-account rejection.
3. Tenant-isolated agent listing and super-admin read-only `actAs`.
4. Agent-scoped API keys, token rotation, and denial of unlisted agents.
5. Tenant- and API-key-filtered task observability.
6. SQLite close/reopen durability and user-owned row cascades.

These tests found and now prevent regressions in API-key agent authorization and
cross-tenant task visibility.

## Agent Eval integration scenarios

The Eval suite runs without an external model by using an `httptest` OpenAI
chat-completions endpoint. It covers:

1. CLI to HTTP executor to deterministic grader to JSON report.
2. API-key, agent-ID, and isolated session headers.
3. Stable and flaky repeated runs.
4. `pass@1`, `pass@k`, consistency, latency, and token aggregation.
5. Non-2xx API error propagation.
6. Fresh session keys across separate Eval runs.
7. BFCL JSONL import and schema normalization.
8. Request-scoped tool isolation from the shared Agent registry.
9. OpenAI API to ReAct loop to deterministic tool execution to trace response.
10. Stateful API tool execution, final-state response, and cross-turn state carry.
11. Virtual repository editing, Git patch generation, and hidden test execution.
12. SWE-compatible prediction JSONL export and resolution-rate aggregation.
13. Tool-isolated solo versus simulated-specialist team execution.
14. Milestone, delegation, contribution, coordination, and collaboration-gain
    aggregation.
15. Runtime multi-agent mode preserving the real Gateway agent registry.
16. Function name, accepted argument, extra-call, and invalid-JSON grading.
17. OpenAI/Anthropic streaming token extraction and request-level model-call
    usage aggregation.
18. Coordinator/sub-agent token, cost, latency, role, and call-path splitting
    across the real MessageBus and TaskQueue route.
19. Idempotent fixed benchmark tenant provisioning, private identity files,
    API-key ACL assignment, and token rotation.
20. CLI provisioning into a migrated SQLite store and eight-case runtime suite
    validation.

The TaskQueue suite also verifies that internal tasks preserve request context
values while independently propagating request and queue cancellation. This is
what allows request-scoped telemetry to follow nested sub-agent work without
global mutable state.

## Measuring changes

Run:

```bash
make coverage
go tool cover -html=coverage.out -o coverage.html
```

Track both total statement coverage and the coverage of the package being
changed. Package coverage is the more useful review metric because FastClaw has
many adapter packages that require external services and currently report 0%.

The baseline before the Gateway integration suite was:

| Metric | Baseline | Current | Change |
|---|---:|---:|---:|
| Total statement coverage | 7.4% | 22.9% | +15.5 pp |
| `internal/api` statement coverage | 0.0% | 52.1% | +52.1 pp |
| `internal/auth` statement coverage | 0.0% | 65.0% | +65.0 pp |
| `internal/setup` statement coverage | 0.0% | 14.8% | +14.8 pp |
| `internal/store` statement coverage | 0.0% | 26.7% | +26.7 pp |
| `internal/gateway` statement coverage | 0.0% | 7.1% | +7.1 pp |
| `internal/taskqueue` statement coverage | 64.0% | 71.3% | +7.3 pp |
| `internal/eval` statement coverage | 0.0% | 73.8% | +73.8 pp |
| `internal/evaltenant` statement coverage | New | 75.3% | New package |
| CLI statement coverage | 0.0% | 15.0% | +15.0 pp |
| Go packages containing tests | 6 / 31 | 17 / 33 | +11 packages |
| Integration test functions | 0 | 19 | +19 tests |

CI runs unit and integration tests, focused race detection, `go vet`, frontend
lint, and a production frontend build on every pull request.
