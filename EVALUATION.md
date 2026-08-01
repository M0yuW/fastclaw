# Agent Evaluation

FastClaw includes a deterministic evaluation harness for measuring agent behavior
through its OpenAI-compatible HTTP API. It is the shared execution and reporting
layer for the planned benchmark adapters:

1. Project-specific self evaluation — implemented
2. BFCL V4 single-turn subset for function calling — implemented
3. τ-bench-style scripted-user subset for stateful tool interaction — implemented
4. SWE-bench-style local subset for repository issue resolution — implemented
5. MultiAgentBench-style collaboration subset — implemented

## Run a suite

Start the gateway, create an API key, and export it:

```bash
export FASTCLAW_API_KEY=your-api-key
go run ./cmd/fastclaw eval run evals/smoke.yaml
```

Generate a machine-readable report:

```bash
go run ./cmd/fastclaw eval run evals/smoke.yaml \
  --format json \
  --output baseline.json
```

Useful overrides:

```bash
go run ./cmd/fastclaw eval run evals/smoke.yaml \
  --base-url http://127.0.0.1:18953 \
  --agent-id default \
  --repetitions 5 \
  --timeout 90s \
  --fail-under 0.80
```

Each attempt receives a unique `x-fastclaw-session-key`, preventing previous
attempts from contaminating the result. API keys are never included in reports.

## Run the BFCL subset

The bundled subset contains three deterministic
[`simple_python`](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/bfcl_eval/data/BFCL_v4_simple_python.json)
records:

```bash
go run ./cmd/fastclaw eval run evals/bfcl-v4-simple-subset.yaml \
  --format json \
  --output bfcl-baseline.json
```

FastClaw sends the case's function definitions as request-scoped tools. The
gateway executes them with deterministic canned results and returns structured
`tool_call` and `tool_result` events in the response's `fastclaw.trace`
extension. Request-scoped tools replace the normal Agent tools for that turn
and never mutate the shared registry.

To generate a custom subset from the official BFCL V4 JSONL files:

```bash
go run ./cmd/fastclaw eval bfcl import \
  BFCL_v4_simple_python.json \
  possible_answer/BFCL_v4_simple_python.json \
  --ids simple_python_0,simple_python_1,simple_python_19 \
  --agent-id default \
  --output evals/my-bfcl-subset.yaml
```

The importer currently supports BFCL V4 single-turn records. It converts BFCL
`dict`/`float` schemas to JSON Schema `object`/`number` and preserves each
ground-truth argument's accepted values. See the
[official BFCL repository](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard)
for the complete data and evaluator.

This is a small, BFCL-derived regression subset, not an official leaderboard
submission. Report it as “BFCL V4 subset accuracy” with the case count, never as
the official BFCL overall score.

## Run the τ-bench-style subset

The bundled retail subset exercises multi-turn memory, tool-side state
transitions, required user communication, and policy constraints:

```bash
go run ./cmd/fastclaw eval tau run evals/tau-retail-subset.yaml \
  --format json \
  --output tau-baseline.json
```

Each turn uses the same isolated session and carries the previous turn's
returned state into the next request. Stateful tools support:

- Preconditions against a dot-separated state path
- Updates from constants or tool arguments
- Tool results read from the updated state
- `{argument}` interpolation in paths such as `orders.{order_id}.status`

The runner scores components inspired by the current
[τ³-bench evaluation model](https://github.com/sierra-research/tau2-bench/blob/main/docs/evaluation.md):

- **State accuracy:** exact or subset match against expected environment state
- **Communication accuracy:** required facts appear in agent messages
- **Policy compliance:** forbidden mutation tools are not called
- **End-to-end task success:** every configured component passes
- **Average turns:** scripted user turns consumed per attempt

The official benchmark derives target database state by replaying one reference
trajectory, but accepts other tool paths that reach an equivalent final state.
FastClaw follows that principle by grading state rather than requiring one exact
tool sequence. The original
[τ-bench repository](https://github.com/sierra-research/tau-bench) now directs
users to the maintained [τ³-bench repository](https://github.com/sierra-research/tau2-bench).

This is a hand-authored deterministic regression subset with scripted users,
not the official τ³-bench simulator or leaderboard score. Resume wording should
state the domain, case count, repetition count, and “τ-bench-style subset”.

## Run the SWE-bench-style subset

The bundled subset contains three offline Go repository issues. The agent sees
only editable source files through virtual `list_files`, `read_file`, and
`write_file` tools; test files remain hidden:

```bash
go run ./cmd/fastclaw eval swe run evals/swebench-local-subset.yaml \
  --format json \
  --output swe-baseline.json \
  --predictions-output swe-predictions.jsonl
```

For every case, the runner:

1. Confirms the fixture's baseline tests fail.
2. Gives the agent an isolated virtual repository state.
3. Materializes the returned files in a temporary Git repository.
4. Generates a real Git patch.
5. Runs the configured hidden test command with a timeout.
6. Records whether the instance was completed and resolved.

Test commands execute locally, so run only repository-owned or otherwise
trusted suite files.

Reports include submitted, completed, patched, and resolved instance counts;
patch-generation rate; test-execution rate; and resolution rate. The optional
predictions file uses the official `instance_id`, `model_name_or_path`, and
`model_patch` JSONL field names.

The official [SWE-bench evaluation guide](https://www.swebench.com/SWE-bench/guides/evaluation/)
applies model patches to real repository snapshots and evaluates them in
containerized environments. Its
[Docker harness](https://www.swebench.com/SWE-bench/reference/harness/) remains
the authority for official Lite or Verified scores. FastClaw's bundled fixtures
are intentionally small and offline; their prediction IDs do not belong to the
official dataset.

Report these results as “SWE-bench-style local subset resolution rate” and
include the task and repetition counts. Do not label them SWE-bench Lite,
Verified, or leaderboard results.

## Run the MultiAgentBench-style subset

The bundled subset contains incident response, release gating, and investment
committee tasks. Each specialist owns private evidence that is not included in
the coordinator prompt:

```bash
go run ./cmd/fastclaw eval multiagent run \
  evals/multiagent-collaboration-subset.yaml \
  --agent-id default \
  --format json \
  --output multiagent-baseline.json
```

By default, specialists are deterministic simulated workers. This isolates the
coordinator's planning, delegation, and synthesis behavior while keeping runs
reproducible. A multi-agent suite may declare these diagnostic modes:

- `solo_closed_book`: task only, without specialist evidence
- `solo_open_book`: the same evidence packet available to the team, anonymized
  and flattened, without delegation tools
- `solo_two_pass`: the same anonymous evidence packet across two coordinator
  passes, controlling for the team's additional planning/synthesis opportunity
- `team`: normal coordinator execution with simulated or real specialists
- `oracle_team`: named specialist reports delivered directly, measuring the
  synthesis ceiling when routing and delivery are perfect

The fair collaboration gain compares the team's milestone-and-grounding outcome
rate with `solo_open_book`, so both sides use the same evidence and output
grader. Compute-matched gain compares the same Team outcome with
`solo_two_pass`.
The team's strict success rate additionally requires correct delegation,
contribution use, and efficiency. The older
`team - solo_closed_book` gain remains in reports as an optimistic diagnostic,
but it must not be presented as proof that orchestration itself added value.
Suites with all five modes make several additional coordinator calls per attempt, so use a
case filter and one repetition for low-cost pilots. Each mode receives an
independent timeout and session key so a slow baseline cannot consume the
team's execution budget or contaminate its conversation history. A baseline
that times out or returns an execution error is reported as `errored` and is
excluded from that mode's evaluated-success denominator. Collaboration gain is
reported as `n/a` unless both modes have equal paired evaluated counts and zero
errors; an infrastructure failure is never converted into a model failure.
Tokens and cost from errored calls remain in the resource ledger because failed
provider calls can still consume billable resources.

Set `execution_mode: runtime` to use the coordinator's real built-in
`spawn_subagent` tool and FastClaw Gateway routing. Runtime mode measures real
coordinator delegation calls; the Gateway integration suite separately verifies
internal bus routing, task correlation, tenant isolation, call paths, and
cancellation propagation.

Add explicit per-million-token pricing to estimate cost reproducibly:

```yaml
pricing:
  provider/coordinator-model:
    input_per_million: 1.00
    output_per_million: 4.00
    cache_read_per_million: 0.10
    cache_write_per_million: 1.25
  provider/specialist-model:
    input_per_million: 0.25
    output_per_million: 1.00
```

Use the exact configured model name or its provider-prefix-stripped form. Rates
are suite inputs rather than hard-coded assumptions, so historical reports
remain comparable after vendor prices change. Calls without matching pricing
still report tokens and latency, have zero estimated cost, and reduce
`multi_agent_pricing_coverage`.

The report includes:

- **Milestone KPI:** achieved output milestones divided by configured milestones
- **Delegation precision/recall/F1:** correct unique specialists versus all
  calls and expected specialists
- **Contribution utilization:** delegated specialist evidence retained in the
  final synthesis
- **Coordination score:** mean of delegation F1 and contribution utilization
- **Per-mode baseline success:** closed-book solo, open-book solo, two-pass
  solo, team, and oracle-team when configured
- **Fair collaboration gain:** team success minus open-book solo success
- **Compute-matched gain:** team success minus two-pass solo success
- **Average delegations and unexpected calls**
- **Per-call usage tree:** phase, coordinator/sub-agent role, agent ID, model,
  call path, tokens, estimated USD cost, latency, and error
- **Cost split:** closed-book solo, open-book solo, two-pass solo, team, oracle team,
  coordinator, sub-agent, total evaluation cost, and cost per successful team
  run
- **Latency split:** average summed coordinator and sub-agent model-call
  latency per attempt, plus team-outcome P50/P95 latency
- **Token split:** team-only total and tokens per successful team run
- **Pricing coverage:** priced model calls divided by all captured model calls

The generic attempt latency and token fields include every configured baseline
mode because they describe the cost of the complete evaluation attempt. Use
`multi_agent_team_latency_p50_ms`,
`multi_agent_team_latency_p95_ms`,
`multi_agent_team_total_tokens`, and
`multi_agent_team_tokens_per_successful_run` when describing production team
execution rather than harness cost.

## Run the finance workflow evaluation

The finance suite uses six fixed evidence packets rather than future stock
returns:

```bash
go run ./cmd/fastclaw eval multiagent run \
  evals/multiagent-finance-workflow.yaml \
  --repetitions 1 \
  --format json \
  --output finance-workflow.json
```

It measures whether the runtime helps the coordinator:

- preserve dated primary-source facts;
- apply explicit catalyst and invalidation conditions;
- suppress duplicate alerts without losing occurrence counts;
- reject incomplete screening records;
- turn portfolio diagnostics into reversible controls;
- retain uncertainty when primary evidence conflicts.

Use `team - solo_open_book` as the fair collaboration gain. Both modes receive
the same evidence, while only the team must route work through specialists.
Use `team - solo_two_pass` as the compute-matched gain when `solo_two_pass` is
configured.
`team - solo_closed_book` also includes data-access advantage and is therefore
only a diagnostic. The suite measures evidence handling and orchestration, not
investment returns, alpha, or an official MultiAgentBench score.

## Run fault-injection evaluation

The bundled fault suite exercises specialist-local failures while preserving
the same OpenAI-compatible Gateway and request-scoped tool path:

```bash
go run ./cmd/fastclaw eval multiagent run \
  evals/multiagent-fault-injection.yaml \
  --repetitions 1 \
  --format json \
  --output multiagent-faults.json
```

Faults are declared on a collaborator:

```yaml
fault:
  type: timeout
  delay: 50ms
  message: logs specialist timed out
  expected_output_values: [logs specialist, timed out, root cause unknown]
  forbidden_output_values: [private-evidence-id, unsupported conclusion]
```

Supported types are `timeout`, `error`, `malformed`, and `contradictory`.
Timeout and error faults return explicit tool failures; malformed and
contradictory faults replace the specialist result. Fault injection is limited
to `simulated` execution so production runtime agents cannot be altered by an
evaluation request. Fault delays are capped at five minutes and still stop
immediately when the request context is cancelled.

Fault cases report:

- **Fault observation rate:** configured faults observed in correlated
  tool-result traces
- **Fault attribution rate:** failures correctly disclosed in the final answer
- **Graceful degradation rate:** required healthy milestones pass, injected
  failures are observed and attributed, and no forbidden claims appear
- **Unsupported claim rate:** injected faults for which at least one forbidden
  assertion appears, divided by injected faults; the rate cannot exceed 100%

Faulty specialists still count toward delegation recall because the coordinator
must attempt the call, but their nominal private evidence is excluded from
contribution-utilization requirements. If every specialist is faulted, the
zero-denominator contribution grader is skipped and coordination is based on
delegation. Tool results without a non-empty matching call ID are not attributed
to an arbitrary specialist and appear in
`multi_agent_uncorrelated_tool_results`.

Forbidden values are assertion-sensitive. Negated or explicitly uncertain
phrasing such as “not verified,” “cannot confirm,” or “unconfirmed” does not
count as an unsupported assertion. Suites should still prefer unique fabricated
evidence IDs over broad natural-language phrases whenever possible.

OpenAI-compatible providers are requested with streaming usage enabled, and
Anthropic message-start/message-delta usage is parsed directly. Provider
endpoints that omit token usage remain visible as zero-token calls rather than
being silently estimated.

The official
[MultiAgentBench paper](https://aclanthology.org/2025.acl-long.421/) evaluates
collaboration and competition across six environments, milestone KPIs,
communication/planning quality, and multiple coordination topologies. Its
[MARBLE repository](https://github.com/ulab-uiuc/MARBLE) is the official
framework. FastClaw currently covers deterministic shared-goal collaboration
and star-style delegation; its communication and planning metrics are
rule-based proxies rather than official LLM-judge scores.

Report this as “MultiAgentBench-style collaboration subset”, including task
count, repetitions, simulated/runtime mode, and the solo baseline. Do not claim
an official MultiAgentBench score.

## Provision the fixed runtime benchmark tenant

FastClaw includes an isolated benchmark tenant with one real coordinator, four
real specialists, and eight fixed-evidence tasks:

```text
bench-coordinator
bench-observer
bench-investigator
bench-policy
bench-operator
```

Provision it directly into the configured FastClaw database while the Gateway
is stopped:

```bash
go run ./cmd/fastclaw eval multiagent tenant provision \
  --coordinator-model provider/coordinator-model \
  --specialist-model provider/specialist-model \
  --output runtime-benchmark-tenant.json
```

Provisioning is idempotent. It creates or refreshes the fixed agents and their
private `SOUL.md` evidence, preserves the tenant identity, restricts a dedicated
API key to the five benchmark agents, and rotates that key on every run. The
generated JSON contains the new plaintext key exactly once. Restart a running
Gateway after provisioning so any cached user space is reloaded. Credential
files written with `--output` are forced to owner-only mode `0600`.

Model names must use `<provider-key>/<model-id>`. The provider key is the name
configured in FastClaw's Providers settings, while the model ID is the value
sent to that provider endpoint. The current runtime creates one provider client
per tenant, so coordinator and specialist models must use the same provider key.
Provisioning writes the coordinator model into the benchmark tenant's
`agents.defaults` to select that provider. The provider itself must be available
at system scope so the isolated tenant inherits its endpoint and credential.

Run a low-cost real-routing pilot:

```bash
export FASTCLAW_API_KEY="$(jq -r .api_key runtime-benchmark-tenant.json)"

go run ./cmd/fastclaw eval multiagent run \
  evals/multiagent-runtime-tenant.yaml \
  --repetitions 1 \
  --timeout 10m \
  --format json \
  --output runtime-pilot.json
```

During harness development, restrict the run to one or more cases before
spending on the full suite:

```bash
go run ./cmd/fastclaw eval multiagent run \
  evals/multiagent-runtime-tenant.yaml \
  --case checkout-incident \
  --case pipeline-schema-regression \
  --repetitions 1 \
  --format json \
  --output runtime-smoke.json
```

The fixed tenant provisions the coordinator with the `delegate-only` policy
and specialists with `no-tools`. Required identity files are verified before
each turn, and repeated delegation to the same target within one parent turn
reuses the first result.

The full baseline uses the suite default of three repetitions:

```bash
go run ./cmd/fastclaw eval multiagent run \
  evals/multiagent-runtime-tenant.yaml \
  --format json \
  --output runtime-baseline.json
```

The eight cases cover incident diagnosis, authorization release gating,
service-account access review, pipeline regression, duplicate-payment support,
privacy containment, capacity planning, and dependency rollout. Specialists
receive case-specific evidence through their own identity files. The
coordinator in `team` mode only sees the task and selected specialist IDs. The
suite also stores nominal reports so the open-book and oracle baselines can
receive equivalent evidence; those reports are not included in the normal team
prompt. Evidence IDs and milestone answers remain local grader inputs.

For reproducibility:

- provision a dedicated tenant rather than modifying production agents
- keep external search and changing business data out of these cases
- pin coordinator and specialist models
- retain the generated report, suite revision, model names, pricing, and commit
- use `--repetitions 1` for routing smoke tests and three or more for baselines
- run `eval compare` after prompt, model, or orchestration changes

## Compare changes

Run the same suite before and after a prompt, model, tool, or orchestration
change:

```bash
go run ./cmd/fastclaw eval compare baseline.json candidate.json
```

The comparison reports:

- Run pass-rate change in percentage points
- `pass@1` and `pass@k` change
- Consistency change across repeated runs
- P50 and P95 latency change
- Token usage per successful run
- Tool-trace accuracy and invalid-tool-call-rate change
- Stateful task, communication, and policy-compliance change
- SWE patch-generation, test-execution, and resolution-rate change
- Multi-agent per-mode baseline success, evidence-access/fair/compute-matched
  gain, milestone KPI, grounding, and coordination change
- Multi-agent fault observation, attribution, graceful degradation, and
  unsupported-claim change
- Multi-agent team P50/P95 latency, team tokens per success, team cost, cost per
  success, and coordinator/sub-agent token changes

This makes project claims reproducible. For example:

> Built a repeatable agent evaluation harness with isolated sessions and
> baseline comparison; improved task pass rate by 18.0 percentage points while
> reducing P95 latency by 12.4%.

Use measured values from saved reports instead of copying the example numbers.

## Suite format

```yaml
version: 1
name: example
defaults:
  agent_id: default
  repetitions: 3
  timeout: 2m
cases:
  - id: concise-answer
    prompt: Reply with only OK.
    tags: [instruction-following]
    graders:
      - type: exact
        value: OK
        case_sensitive: true
```

Case values override suite defaults. CLI flags override both.

Supported deterministic graders:

| Type | Configuration | Pass condition |
| --- | --- | --- |
| `exact` | `value` | Trimmed output equals the expected value |
| `contains` | `value` or `values` | Output contains every expected value |
| `not_contains` | `value` or `values` | Output contains none of the forbidden values |
| `regex` | `pattern` | Output matches a Go regular expression |
| `json_valid` | none | Trimmed output is valid JSON |
| `tool_trace` | `calls` | Function names and JSON arguments match the expected trace |

Text matching is case-insensitive by default. Set `case_sensitive: true` when
case is part of the requirement.

## Metrics

- **Run pass rate:** successful attempts divided by all attempts.
- **pass@1:** cases whose first attempt passes.
- **pass@k:** cases with at least one passing attempt.
- **Consistency:** cases where every repetition has the same pass/fail result.
- **P50/P95 latency:** end-to-end attempt latency. For a multi-agent suite this
  includes every configured baseline mode; use the MA team latency fields for
  team-only latency.
- **Tokens/success:** total reported attempt tokens divided by successful
  attempts. For multi-agent team-only cost, use the MA team token fields.
- **Tool-trace accuracy:** passing `tool_trace` graders divided by all
  `tool_trace` graders.
- **Invalid tool-call rate:** tool calls whose arguments are not a JSON object
  divided by all observed tool calls.
- **State accuracy:** passing turn/final state checks divided by all state
  checks.
- **Communication accuracy:** passing required-message checks divided by all
  communication checks.
- **Policy compliance:** passing forbidden-tool checks divided by all policy
  checks.
- **End-to-end task success:** attempts where every configured state,
  communication, and policy component passes.
- **Average turns:** mean scripted-user turns per stateful attempt.
- **SWE patch-generation rate:** attempts that produce a non-empty Git patch
  divided by submitted repository attempts.
- **SWE test-execution rate:** attempts whose hidden test command completes,
  including normal test failures.
- **SWE resolution rate:** attempts that produce a patch and pass hidden tests
  divided by submitted repository attempts.
- **Multi-agent milestone KPI:** achieved deterministic collaboration
  milestones divided by all configured milestones.
- **Delegation F1:** harmonic mean of valid unique-delegation precision and
  expected-specialist recall.
- **Contribution utilization:** specialist contributions preserved in the
  coordinator's final output.
- **Multi-agent coordination score:** mean of delegation F1 and contribution
  utilization.
- **Collaboration gain:** multi-agent team success minus isolated solo success.

The current FastClaw chat-completions endpoint returns zeroed usage values, so
token metrics remain zero until provider usage is propagated through the API.
Latency and correctness metrics are fully operational now.

## Adding benchmark adapters

Adapters reuse the same executor, trace schema, report metrics, and comparison
command. BFCL uses `eval.Suite` and `eval.Runner`; stateful scripted-user tasks
use `eval.TauSuite` and `eval.TauRunner`; repository tasks use `eval.SWESuite`
and `eval.SWERunner`; collaboration tasks use `eval.MultiAgentSuite` and
`eval.MultiAgentRunner`.
