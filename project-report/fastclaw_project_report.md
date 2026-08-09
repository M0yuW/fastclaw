TITLE: FastClaw: Design and Evaluation of an Agent Runtime for Evidence-Grounded Financial Research
AUTHOR: Zheyu Wang
AFFILIATION: Faculty of Science and Technology, University of Macau
EMAIL: mc45505@um.edu.mo
REPORT DATE: August 2026

ABSTRACT: Large-language-model agents are increasingly deployed as long-running services rather than single prompts, yet reported evaluations commonly attribute outcomes to the model while treating the runtime as neutral infrastructure. This thesis argues that the runtime—the layer that constructs prompts, resolves identity, filters tools, routes delegation, allocates context, persists state, handles cancellation, and grades outputs—is itself part of the experimental treatment. FastClaw is a multi-tenant Go agent runtime with a bounded streaming execution state machine, per-chat FIFO scheduling, root-level concurrency admission, correlated internal request/reply, transitive wait-graph cycle detection, policy-filtered tools, panic containment, batch shared-context delegation, and coordinator/specialist telemetry. A financial research application adds deterministic tools and tenant-scoped state. Three experimental tracks are reported. A historical regression sequence is diagnostic because evidence visibility and the grader changed with the runtime. In a six-case evidence-matched confirmation, Team, Solo Open-Book, and Solo Two-Pass each passed 5/6 cases; the available sample did not establish an incremental Team accuracy effect. A retrieval-mediated SEC Pilot compared five modes on one medium-context longitudinal case. Shared-retrieval Team and staged Solo both achieved all milestones and 100% final evidence recall. Relative to staged Solo, the Team observation had 36.32% lower wall-clock latency and 42.06% lower frozen-price estimated cost, with 13.63% more provider-total tokens under heterogeneous model allocation. Relative to raw-context Team, it had 38.42% fewer tokens, 47.62% lower estimated cost, and numeric grounding of 98.28% rather than 94.87%. Non-random order, one repetition, provider variability, and heterogeneous allocation make these descriptive associations rather than causal or population estimates. The two empirical conclusions are therefore bounded: current evidence does not establish an evidence-matched Team accuracy advantage, and the single-case Pilot records limited latency–cost–grounding differences. The demonstrated contribution is an auditable runtime and evaluation method, not evidence of superior financial judgment, full factual correctness, investment performance, or inherent multi-agent superiority.

INDEX TERMS: LLM agents, agent runtime, multi-agent systems, tool calling, context allocation, evidence retrieval, financial research, evaluation harness, fault injection, tenant isolation, observability.
ABBREVIATION: ACL | Agent access-control list
ABBREVIATION: API | Application programming interface
ABBREVIATION: BFCL | Berkeley Function-Calling Leaderboard
ABBREVIATION: CI | Continuous integration
ABBREVIATION: DFS | Depth-first search
ABBREVIATION: FIFO | First in, first out
ABBREVIATION: LLM | Large language model
ABBREVIATION: MCP | Model Context Protocol
ABBREVIATION: P50/P95 | 50th/95th latency percentile
ABBREVIATION: RQ | Research question
ABBREVIATION: SSE | Server-sent events
ABBREVIATION: WAL | Write-ahead logging

# I. INTRODUCTION

Large language models (LLMs) can answer questions, generate code, and invoke external tools, but model capability alone does not produce a dependable software system. A practical agent must receive requests from multiple interfaces, preserve conversation state, decide which capabilities are available, execute tools under policy, recover from partial failure, stream progress to users, and leave an auditable record. In a multi-user deployment, these concerns expand to authentication, per-tenant data isolation, cancellation, concurrency control, and protection against cross-agent cycles or runaway delegation.

The reasoning–action–observation pattern introduced by ReAct [1] provides a useful conceptual basis: the model alternates between reasoning, external action, and observation until it can produce a final answer. However, ReAct describes an interaction pattern rather than a production runtime. The engineering challenge is to turn that pattern into a controlled state machine whose transitions are observable and testable. A model request can fail, a tool can time out, the client can disconnect, a session can contain an unmatched tool result, or a coordinator can repeatedly call the same specialist. Without runtime-level rules, these failures are easily mistaken for “model intelligence” problems.

Financial research is an appropriate application domain because it combines deterministic and probabilistic work. Price histories, ratios, portfolio concentration, event fingerprints, and duplicate suppression should be computed by deterministic programs. Interpretation of catalysts, contradictions, and invalidation conditions can benefit from an LLM, but every material claim should retain its source and timestamp. The target system is therefore a research copilot, not an autonomous trading engine: it assists evidence collection, prioritization, monitoring, and challenge while leaving portfolio actions to a human.

This report makes three bounded contributions:

1. **Auditable runtime artifact:** FastClaw implements authenticated ingress, bounded streaming turns, policy-filtered tools, correlated coordinator–specialist request/reply, tenant-scoped state, cancellation, and role-level telemetry as an inspectable Go artifact.
2. **Measurement method:** the evaluation separates evidence visibility, planning opportunity, orchestration, model allocation, runtime failure, context allocation, and grader behavior, while retaining content-addressed artifacts for offline replay.
3. **Limited empirical result:** the retained experiments do not establish an incremental accuracy advantage for evidence-matched Team execution. A single-case descriptive Pilot instead records bounded differences in latency, frozen-price estimated cost, and numeric grounding that are consistent with context-allocation effects but are not causal or population-level estimates.

The central research question is not whether a stronger model can improve a score. It is whether an engineered runtime can make an explicitly declared model allocation more reliable, cheaper, faster, and easier to diagnose. The present experiments only partially examine that question. The historical study changes runtime behavior, evidence visibility, and grading together; the fixed-evidence financial study changes orchestration mode while holding evidence visibility more carefully; and the retrieval-mediated pilot changes context allocation within a declared heterogeneous deployment. Their combination motivates a measurement method and identifies unresolved confounding, but it does not isolate a universal causal runtime effect.

# II. BACKGROUND AND DESIGN REQUIREMENTS

## A. From Tool Calling to an Agent Runtime

In structured tool calling, the model receives a list of functions with names, descriptions, and JSON schemas. It can either return natural-language content or emit one or more typed function calls. The application validates and executes those calls, appends each result to the conversation, and requests the next model step. This separates probabilistic planning from deterministic execution. The 28 July 2026 revision of the Model Context Protocol (MCP) standardizes hosts, clients, servers, resources, prompts, and model-controlled tools over a JSON-RPC 2.0 data layer [2], [3]. MCP defines an interoperability boundary; it does not define an application’s authorization policy, persistence model, queueing discipline, or experimental protocol. Those remain runtime responsibilities.

BFCL evaluates function selection, parameter construction, parallel calls, abstention, and stateful multi-step behavior with scalable structural comparison [4]. Its strength is that a tool call has a relatively objective representation. The limitation for runtime research is equally important: a correct call does not reveal whether a queue dropped work, whether a stream exposed an error, whether two tenants shared state, or whether the same model would behave differently under another capability policy. FastClaw therefore uses BFCL-style cases as protocol checks rather than reporting an official BFCL score.

A runtime adds controls not supplied by the model: provider adaptation, session ordering, capability policy, sandbox binding, timeouts, telemetry, and terminal consistency. FastClaw treats the LLM as a planning component inside this larger state machine rather than as the owner of execution.

## B. Stateful and Multi-Agent Evaluation

Single-turn function accuracy is necessary but insufficient. τ-bench evaluates multi-turn interaction among an agent, a user model, domain policy, and database tools [5]. Its policy-constrained trajectories demonstrate why the terminal answer alone is not enough: two agents may reach similar text through different, policy-relevant actions. SWE-bench evaluates repository issue resolution by applying patches and running repository tests [6], making the environment and executable oracle part of the benchmark. MultiAgentBench measures task milestones and communication structures across collaboration and competition scenarios [7]. These benchmarks progressively add state, environment, and coordination, but they still evaluate a model or agent system inside a chosen harness. They do not ordinarily treat queue semantics, cancellation propagation, tenant scope, event-stream convergence, or grader normalization as independent variables.

This omission defines the research gap addressed here. Agent scores are jointly produced by at least five factors: model parameters, visible evidence, available actions, runtime transition rules, and the outcome oracle. Changing any one can alter the observed score. A team can appear better than Solo because specialists see private evidence; a baseline timeout can appear as an inability; a negated forbidden phrase can become a false violation; and cached prompt tokens can change an efficiency comparison depending on accounting convention. A runtime benchmark must therefore expose these factors, preserve pair identifiers, separate execution errors from evaluated failures, and retain raw outputs for regrading.

FastClaw does not claim official scores on BFCL, τ-bench, SWE-bench, or MultiAgentBench. It implements small style subsets that exercise analogous runtime abilities under deterministic local conditions. The contribution is not a competing universal benchmark. It is an instrument for testing whether the harness itself preserves the preconditions under which a model score can be interpreted.

## C. Financial Research Requirements

Financial question-answering datasets such as FinQA [8] and TAT-QA [9] demonstrate the difficulty of numerical reasoning across narrative and tabular evidence. They primarily evaluate answer derivation from supplied documents. A deployable financial research assistant additionally requires temporal provenance, missingness semantics, persistent hypotheses, duplicate-event identity, and a boundary between research and portfolio action. The present project does not reproduce the official FinQA or TAT-QA evaluations. Instead, it derives system requirements relevant to a deployable research copilot:

- source-aware data with freshness and completeness metadata;
- deterministic calculation for screening, risk, and event identity;
- explicit uncertainty when evidence conflicts or is incomplete;
- persistent, tenant-scoped research state;
- human approval before portfolio action;
- repeatable evaluation that does not use future returns as a convenient but misleading ground truth.

The report uses **evidence attribution** to mean that a material output claim is linked to a supplied evidence identifier. This is narrower than factual truth or semantic entailment. Work on faithful knowledge-grounded generation distinguishes fidelity to supplied evidence from fluency and subjectivity [10]; accordingly, FastClaw’s lexical checks are described as configured attribution checks, not as proof that every generated sentence is true. BCBS 239 motivates accurate, complete, timely, and traceable risk-data aggregation at an institutional level [11], but it does not prescribe FastClaw’s `observed_at`, `as_of`, or `source_id` fields. Those fields are an engineering operationalization inspired by provenance requirements rather than a direct implementation of the banking standard.

## D. Engineering Requirements

The resulting runtime requirements are:

1. **Isolation:** every request resolves to a real user, an authorized agent, a session, and a bounded workspace.
2. **Correctness:** assistant tool calls and tool results must remain correctly paired in persisted history.
3. **Control:** tools are filtered by policy, sandbox execution must not silently fall back to the host, and evaluation-only behavior must not affect production requests.
4. **Liveness:** cancellation, timeouts, bounded queues, and loop detection prevent requests from waiting indefinitely.
5. **Observability:** model calls, tool traces, call paths, token usage, latency, and estimated cost must be attributable to coordinator and specialist roles.
6. **Evaluability:** Team/Solo comparisons must control evidence visibility, and infrastructure errors must not be counted as model failures.

## E. Validity Preconditions and Empirical Questions

The study uses two validity preconditions, two primary empirical questions, and one prospective validation question.

1. **VP1—Selected runtime control paths:** Do executable tests support the specific tenant-scope, tool-call ordering, terminal-streaming, cancellation, and bounded-execution paths used by the experiments?
2. **RQ2—Orchestration benefit:** Across fixed-evidence and retrieval-mediated conditions, does coordinator–specialist execution improve deterministic task outcomes relative to an evidence-matched staged Solo baseline?
3. **RQ3—Context allocation and efficiency:** Under a fixed task, source snapshot, and declared model allocation, how do monolithic, staged, shared-retrieval, and raw-context execution trade evidence retention, grounding, token consumption, latency, and estimated cost?
4. **Prospective RQ4—Fault tolerance:** Can the coordinator identify specialist-local failure, attribute missing evidence correctly, avoid unsupported claims, and still produce a safe partial answer in a future retained fault study?
5. **VP2—Selected financial-workflow invariants:** Do deterministic tests support the specific provenance, completeness, version-transition, alert-identity, and human-decision boundaries exercised by the evaluation fixtures?

VP1 and VP2 are validity preconditions supported only for selected tested paths and invariants; they are not empirical claims of production reliability or complete workflow validity. RQ2 and RQ3 are the primary empirical questions. Prospective RQ4 is operationalized in the harness but is not an executed research question. None of the model experiments executes a live portfolio action.

TABLE_CAPTION: Mapping from validity preconditions and empirical questions to evaluation propositions, estimands, evidence, and present status.

| Question | Related propositions | Operational estimand | Primary evidence | Present status |
|---|---|---|---|---|
| VP1 | EP1 | Correct terminal state, scope, cancellation, and bounded execution on selected paths | Go unit/integration tests | Partially supported for selected paths; not production assurance |
| RQ2 | EP2 | Paired Team minus evidence-matched staged Solo success and milestone retention | Six-case r5, longitudinal SEC extension, and retrieval-mediated Pilot | No incremental accuracy effect established; Stage 2 proposed |
| RQ3 | EP3, EP6 | Evidence retention, grounding, tokens, latency, and frozen-price estimated cost | Per-call usage trace and five-mode retrieval Pilot | Descriptive one-case evidence; capacity-matched confirmation proposed |
| Prospective RQ4 | EP4 | Safe output under observed and attributed specialist faults | Instrumentation and deterministic harness tests only | Not tested by a retained primary financial artifact |
| VP2 | EP5 | Selected provenance and deterministic ledger invariants | Plugin tests and source/oracle records | Supported only for selected deterministic invariants |

## F. Threat Model and Design Principles

The protected assets are tenant identity, API credentials, conversation history, agent identity files, workspace objects, plugin-managed financial state, and the authority to execute tools. Trust boundaries occur at HTTP and channel ingress, provider responses, model-generated tool arguments, external tool and MCP results, plugin subprocesses, sandbox exits, store adapters, and internal sub-agent messages. The model and all retrieved content are treated as untrusted planners or data, not as authorization principals.

The principal abuse cases are: an unauthenticated or under-authorized caller selecting another agent; a model invoking a capability outside its policy; a plugin trusting model-supplied tenant identifiers; an indirect prompt injection propagating from evidence into a privileged tool call; a sub-agent cycle exhausting concurrency; a malformed provider stream producing a false successful terminal event; a stale or partial session corrupting subsequent tool-call order; and a long-running or repeatedly delegated task exhausting cost or queue capacity. FastClaw is not designed to resist a compromised host operating system, a malicious database administrator, or a provider that deliberately violates its API contract.

The design follows fail-safe defaults, complete mediation, and least privilege as classical protection principles [12]. Every protected ingress must resolve an identity; agent selection is checked after default resolution; policy removes denied tools before the model sees them; trusted user scope is carried outside model-controlled arguments; and sandbox startup failure does not silently enable host execution. OWASP guidance for agent systems similarly recommends per-tool authorization, untrusted-data separation, bounded tool chains, structured audit records, and human approval for high-impact actions [13]. FastClaw’s six-pattern prompt scanner is only an unvalidated heuristic layer. It cannot substitute for authorization, policy filtering, parameter validation, or human review.

Residual risks remain. Session reads currently fail open to an in-memory copy if the durable store returns an error, whereas required identity loading fails closed. These are different consistency policies and must not be described as one guarantee. API-key ACL checks are implemented for resolved OpenAI-compatible chat targets, but future endpoints still require complete-mediation regression tests. Native plugins and local MCP servers inherit subprocess and supply-chain risk; policy can reduce exposed tools but cannot prove that an allowed tool is benign. These limitations are revisited in Section IX.

# III. FASTCLAW SYSTEM ARCHITECTURE

## A. Layered Architecture

FastClaw is a Go-based, multi-user agent platform. The default executable starts the Gateway, database-backed store, workspace object store, plugin manager, task queue, channel manager, cron scheduler, setup/API server, and the embedded web interface. User spaces and agents are loaded lazily after authentication rather than preloading every tenant at startup.

Figure 1 locates the runtime controls between external ingress, model providers, extensible capabilities, and durable tenant state. The layer boundaries are logical rather than process-isolation claims: native plugins and the core runtime can share a host process, whereas MCP servers and sandbox commands may cross process or container boundaries.

[[FIGURE_1]]

The architecture is divided into six logical layers.

1. **Ingress layer:** web chat, an OpenAI-compatible `/v1/chat/completions` API, WebSocket, Telegram, Discord, Slack, webhook, and scheduled messages.
2. **Identity and scope layer:** cookie sessions or Bearer API keys resolve a caller; an API key carries an explicit agent access list; the runtime stamps the effective user identity into the request context.
3. **Gateway orchestration layer:** a `MessageBus` normalizes inbound, outbound, and internal messages; a `TaskQueue` provides per-chat FIFO execution and process-wide concurrency control; a lazy `UserSpace` binds tenant configuration, agents, providers, skills, plugins, storage, and sandbox resources.
4. **Agent runtime layer:** a context builder assembles identity, policy, Skills, memory, and runtime metadata; the ReAct loop calls an LLM provider, executes tools, appends observations, and emits versioned events.
5. **Capability layer:** built-in tools, MCP tools, native JSON-RPC plugin tools, provider chains, Skills, and Docker or E2B sandbox executors.
6. **Persistence and telemetry layer:** SQLite by default or PostgreSQL for production state; local, S3-compatible, or Aliyun-backed artifact storage; session history, agent files, scoped configuration, usage, traces, and evaluation reports.

## B. Ingress, Authentication, and Tenant Scope

All protected HTTP routes pass through the authentication resolver. The web UI uses a database-backed, HTTP-only session cookie. Programmatic callers use Bearer API keys stored as hashes; plaintext is shown only when a key is created or rotated. The resolved `Identity` includes `UserID`, role, authentication method, and the API key’s authorized agents. Agent authorization is mediated after the OpenAI-compatible endpoint resolves either an explicit or fallback target, so omitting the agent header cannot bypass an API key allowlist; an unknown explicit target is not silently replaced by a fallback. A super administrator may inspect another user through read-only `actAs` scope, but mutation is rejected.

The Gateway does not invent a default tenant. Channel messages either carry a trusted owner from cron or webhook execution, or resolve ownership from a stored channel credential. If ownership cannot be established, the message is dropped. This fail-closed rule is important because a convenient “local user” fallback would convert an authentication failure into cross-tenant data exposure.

User configuration is layered by scope. System defaults, user-level settings, and agent-level overrides are merged when a `UserSpace` is loaded. The manager creates agents with a tenant-specific session store, memory adapter, workspace store, policy, provider, Skills configuration, and plugin tools.

## C. MessageBus and TaskQueue

External messages enter buffered Go channels as normalized `InboundMessage` values. The TaskQueue creates a FIFO channel for each chat key and a goroutine that drains that queue serially. A counting semaphore limits independent root executions across the process. A task records state (`pending`, `running`, `done`, `failed`, or `cancelled`), timestamps, result, owner, agent, and observability metadata. It does not carry an independent deadline field; execution is bounded by the queue-wide `taskTimeout` and request cancellation.

Internal sub-agent work inherits the root execution identifier. It does not acquire a second global semaphore slot, which prevents a coordinator from deadlocking when the configured maximum concurrency is one. Two independent bounds apply: the TaskQueue owns a 256-slot internal admission channel, and the MessageBus owns a separate 256 pending-correlation cap. They protect different resources and must be tuned together. Completion is exactly once through `sync.Once`. Context values are preserved with `context.WithoutCancel`, while two `context.AfterFunc` callbacks link request cancellation and queue shutdown into one derived cancellation source. Passing the original request context would cancel nested telemetry as soon as the parent lifecycle ends; using `WithoutCancel` alone would lose the cancellation edge. The paired construction retains values while rebuilding both lifecycle edges.

Recent task views return defensive snapshots rather than live pointers. The API authenticates the caller, filters tasks by accessible agent, and only then applies the response limit. This prevents ordinary callers from observing unauthorized task metadata and avoids concurrent reads of mutable task fields; a super administrator intentionally retains broader read access, including read-only `actAs` inspection.

A counting semaphore was selected instead of a fixed worker pool because root-turn durations vary with provider latency and tool fan-out. A small worker pool would add head-of-line blocking between unrelated chat lanes, whereas a semaphore admits one independent goroutine per root up to the configured bound. Alternatives include `errgroup.Group.SetLimit`, `semaphore.Weighted`, or a work-stealing pool. The present design favors direct cancellation propagation and per-chat ordering over centralized worker lifecycle management.

## D. Provider Abstraction and Streaming

The provider interface exposes `Chat` and `ChatStream`. OpenAI-compatible and Anthropic adapters convert FastClaw messages and tools into provider-specific wire formats. The adapters are not symmetric: the OpenAI-compatible path reconstructs a synthetic `RawAssistant` payload from accumulated role, content, and tool-call fragments rather than preserving a byte-exact provider wire message. The Anthropic path retains provider-specific raw material only when a thinking block is present and stores that block rather than a complete assistant message. Replaying this material is useful for prompt caching and signed reasoning blocks, but callers cannot assume one lossless or cross-provider raw-payload contract.

The streaming reader accumulates text, tool-call fragments, reasoning, signatures, and usage before publishing an atomic terminal `Response`. OpenAI-compatible requests ask for streaming usage and fall back when an endpoint rejects the usage option; Anthropic usage is assembled from message-start and message-delta events. The application-level event contract distinguishes incremental `content_delta`, convergent full `content` snapshots, `error`, and terminal `done`. Deltas are opportunistic UI updates; the latest versioned snapshot is authoritative if a client misses one. A required-identity failure is emitted through the turn emitter before return, so streaming clients receive the same useful configuration error as non-streaming callers. A failed or cancelled stream closes without a false successful terminal chunk.

## E. Tools, Plugins, MCP, and Skills

FastClaw uses one registry abstraction for tool definitions and executable functions. The built-in registry includes shell execution, file operations, messaging, memory search, and web fetching, with optional provider-backed web search, image generation, and text-to-speech. MCP servers can contribute tools to the same registry. Native plugins run as subprocesses that communicate through JSON-RPC 2.0 [3] over standard input/output and can provide tools, channels, providers, or hooks.

The plugin protocol includes a trusted `ToolCallContext` containing `userId`, `agentId`, and `sessionId`. This scope is generated by the runtime after routing and is not visible as model-controlled tool input. A stateful plugin can therefore reject calls without trusted context and query data by the authenticated tenant.

Skills are reusable instruction and workflow packages stored in layered directories. Five path classes are effective in the current loader: agent, team, user, managed, and extra; the nominal bundled collection is presently empty. The loader applies operating-system, binary, and environment gates and injects configured environment variables. Only two fixed Skill roots are mounted into sandbox paths; team and extra paths can enter the prompt without receiving equivalent filesystem mounts. The current implementation injects the full content of every enabled Skill into the system prompt. Source code for a `load_skill` registration helper exists, but no production registration call reaches it, so on-demand progressive disclosure is not an available runtime capability. This distinction matters: Skills describe methods, while tools perform atomic execution. The financial design in Section V intentionally keeps deterministic data retrieval in tools and research methodology in Skills.

## F. Persistence and Workspace Storage

The database is mandatory. SQLite with write-ahead logging is the zero-configuration default. PostgreSQL dialect branches are implemented as an intended deployment path, but they are not exercised by the current automated test suite and therefore are not claimed as production-verified. Every SQLite DSN is normalized case-insensitively to enable WAL, foreign keys, a 5-second busy timeout, and immediate write transactions unless an equivalent pragma is already present. The immediate transaction mode addresses the read-then-write upgrade pattern exercised by session persistence; a busy timeout alone cannot reliably recover that transaction shape. WAL creates `-wal` and `-shm` sidecars, so backups must use the SQLite backup API or checkpoint and copy all required files rather than copying only the main database file. The unified store persists users, web sessions, API keys, agent ACLs, agents, conversation sessions, layered agent files, scoped configuration, channel credentials, and cron jobs.

Conversation sessions are keyed by channel and chat identifier and scoped by user and agent. In store-backed mode, the manager attempts to reload the session on every access. If the store returns an error and an in-memory copy exists, the read fails open to that potentially stale copy; it improves cross-replica freshness in the normal path but does not guarantee that every request observes the latest durable history. This differs from required identity files, whose load failure stops the turn. Identity files are stored separately from user artifacts; workspace objects are namespaced by agent and optional session to prevent concurrent chats from overwriting one output name.

# IV. AGENT RUNTIME EXECUTION MECHANISM

## A. One Turn as a Controlled State Machine

The runtime uses a bounded ReAct loop. The key behavior is summarized below.

[[ALGORITHM_1]]

ALGORITHM_CAPTION: Controlled execution of one FastClaw agent turn.

ALGORITHM_STEP: 1. Acquire the agent turn gate; refresh Skills; load the tenant-scoped session.
ALGORITHM_STEP: 2. Repair prior tool-call history; bind the session sandbox; validate required identity files.
ALGORITHM_STEP: 3. Build the system prompt from the validated identity revision; append the user message; compact history if required.
ALGORITHM_STEP: 4. Copy or override the registry; apply policy; expose only permitted tool definitions.
ALGORITHM_STEP: 5. Invoke the streaming provider once and collect content, terminal payload, usage, and error.
ALGORITHM_STEP: 6. If no tool call exists, persist the assistant message, flush the session, emit `done`, and return.
ALGORITHM_STEP: 7. Otherwise execute allowed tool calls concurrently; contain panics; append exactly one result for every call.
ALGORITHM_STEP: 8. Reject repeated exact calls, honor cancellation, and continue until a final answer or the iteration bound.
ALGORITHM_STEP: 9. Normalize and flush session state on every terminal path.

Before the first model call, the agent acquires a turn gate because the current tool registry stores session-bound executor and workspace state. It refreshes Skills from durable storage, obtains the session, repairs tool-call ordering, binds a session-specific sandbox executor, validates required identity files once, builds the system prompt from that immutable identity snapshot, appends the user message, and optionally compacts long history.

The tool registry for the turn is then copied or overridden by request-scoped evaluation tools and filtered through the agent’s policy. The model never receives tools that the policy denies. This is stronger than allowing every tool and asking the prompt not to use some of them. The core state-machine invariant is that every persisted assistant tool-call block has one corresponding tool-result block before the next provider call. `NormalizeToolResults` repairs an interrupted prior history at turn entry and runs again before terminal persistence. This mechanism is important but under-tested: the dedicated `session` package has no measured statement coverage in the repository-wide profile.

For each iteration, the runtime calls `ChatStream` exactly once, forwards content deltas, reads the terminal response, records model usage, and decides between two transitions:

- **Final-answer transition:** append one complete assistant message, run post-turn hooks, flush the session, emit `done`, and return.
- **Tool transition:** append the assistant’s tool calls, emit trace events, execute the calls concurrently, append one matched tool result for each call identifier, and continue to the next model iteration.

The runtime detects three consecutive identical tool name/argument pairs and adds a loop warning. It also caps the number of tool iterations. Tool panics are recovered inside their execution goroutines and converted into explicit error results rather than terminating the Gateway process. Results are correlated by a consume-once call identifier; empty or duplicate identifiers produce explicit failures instead of silently copying another tool's result. Each tool records its own start time, duration, and hook context rather than inheriting a batch-level wall-clock duration.

## B. System Prompt and Identity Contract

The context builder combines runtime information, a user-message isolation policy, optional sandbox guidance, bootstrap files, Skills, long-term memory, group context, and reasoning-mode guidance. User text is wrapped in `<user_message>` tags only in the provider payload; the stored history remains clean for the UI.

Benchmark specialists can declare required identity files. Before a model call, FastClaw loads those files once, rejects missing or empty content, and computes a short SHA-256-based revision identifier. The same validated snapshot is used to build the prompt, avoiding duplicate database reads and time-of-check/time-of-use drift inside a turn. Store failures fail closed; only a confirmed not-found condition permits the legacy filesystem fallback. The revision proves that the expected identity material was loaded without exposing its contents in telemetry. A configuration failure is emitted through both non-streaming and streaming error paths.

## C. Tool Policy and Sandbox Binding

Policy presets include permissive, standard, restricted, `no-tools`, and `delegate-only`. The evaluation coordinator uses `delegate-only`, while fixed-evidence specialists use `no-tools`. When no file tools are allowed, related prompt guidance is also removed so the system prompt does not advertise capabilities the model cannot use.

If a sandbox pool is configured, the registry binds a session-specific executor at turn start. File and shell tools are re-registered against that executor. A `sandboxRequired` flag prevents silent fallback to host execution when the pool fails. Docker and E2B backends can therefore be exchanged behind one executor interface while retaining the same agent loop.

## D. Session Correctness and Streaming Semantics

Provider APIs require every assistant tool-call block to be followed by matching tool results. Client cancellation or a crash during tool execution can leave invalid history. `NormalizeToolResults` rebuilds the session: it places available tool results immediately after their assistant call, synthesizes results for interrupted calls, and drops duplicate or orphaned tool messages. The normalizer runs when a turn begins and before terminal persistence.

Web streaming uses versioned events carrying `turnId`, `messageId`, iteration `round`, and sequence number. `content_delta` events update the current assistant message; full `content` snapshots correct missed deltas; `tool_call` and `tool_result` share stable identifiers; and `done` is emitted only after the final assistant message has been persisted. Nested agents receive a context that preserves cancellation and telemetry values but hides the parent chat event channel, so a specialist cannot terminate the coordinator’s stream.

## E. Internal Multi-Agent Delegation

The `spawn_subagent` tool is not a direct in-process function call. It sends a trusted request through the MessageBus with owner, source agent, target agent, immutable call path, and correlation identifier. The Gateway verifies that the source and target exist and belong to the same tenant, rejects target reuse in the call path, submits an internal task, and resolves the correlated reply.

The bus stores a wait graph between tenant-agent lanes. Before accepting a request, it checks whether the target already waits—directly or transitively—on the source. Call-path validation alone cannot detect the following cross-root case: root R1 has lane A waiting for B, while root R2 independently asks B to wait for A. Neither immutable path contains a repeated target, yet the combined graph has A→B→A. A depth-first reachability check rejects the second edge before the circular wait is established.

The maintained invariant is that the directed lane wait graph is acyclic. If every blocked internal request corresponds to one graph edge, acyclicity rules out a circular wait among sub-agent lanes. The DFS executes while the bus mutex is held; its cost is linear in the current lane-and-edge graph, acceptable under the pending-correlation cap but not free at larger fan-out. Alternatives include a static acyclic agent topology, a global lock order, or timeout-only recovery. Static topology reduces flexibility; timeout-only recovery detects a deadlock after consuming latency rather than preventing it. Pending internal calls are capped; a non-blocking publish returns backpressure rather than waiting forever; shutdown rejects new work and releases all waiters.

Every production turn applies exact duplicate suppression keyed by `(target agent, task)`, so an identical retry reuses the first result while two distinct tasks for the same specialist still execute independently. Evaluation requests may additionally enable target-only suppression because the fixed benchmark contract expects at most one delegation to each specialist. This stronger evaluation policy is request-scoped and does not change production semantics.

Figure 2 shows the corresponding message path. In particular, delegation is mediated by both the MessageBus and TaskQueue rather than bypassing the scheduler through a direct coordinator-to-specialist function call.

[[FIGURE_2]]

## F. Telemetry and Cost Attribution

Each model call records agent, role, model, call path, prompt tokens, completion tokens, cache tokens, latency, error, and estimated cost. Sequence numbers are reserved when calls begin, so concurrent traces preserve invocation order rather than completion order. The collector identifies the root agent as coordinator and nested agents as specialists. Pricing is supplied by the evaluation suite instead of hard-coded in the runtime, preserving historical reproducibility when vendor prices change.

For one model call, the estimated cost is

`C = (Tin × Pin + Tout × Pout + Tcache-read × Pcache-read + Tcache-write × Pcache-write) / 10^6`,

where cached prompt tokens are removed from ordinary prompt tokens when the provider reports that they are already included. Reports aggregate coordinator and specialist cost, Team and Solo cost, full-harness cost, and cost per successful Team case.

Every monetary value in this thesis is an estimate computed from the frozen
suite price table. It is not a provider invoice and is not presented as a general
cost law outside the recorded model allocation and date.

# V. FINANCIAL RESEARCH APPLICATION

## A. Product Position and Design

The application is a portfolio and watchlist research copilot. It gathers structured evidence, applies repeatable research methods, maintains thesis state, and calls an independent challenger when disagreement or downside analysis is valuable. It does not place orders, promise returns, or treat a model-generated score as an investment recommendation.

Figure 3 summarizes the intended separation of concerns: deterministic tools construct a typed evidence envelope, research Skills provide reusable analytical procedure, the coordinator and optional challenger interpret evidence, and a human remains responsible for any portfolio action.

[[FIGURE_3]]

The design separates three concerns:

1. deterministic market data and calculations;
2. reusable research methods;
3. selective model reasoning and multi-agent challenge.

This replaces an earlier architecture in which a coordinator always spawned one stock-selection agent and one news agent. Data acquisition is not an opinion and therefore should not consume a specialist model call. A sub-agent is reserved for an independent interpretation, parallel deep dive, contradiction check, or risk challenge.

## B. Native Finance Tools

The `finance-tools` native plugin wraps scripts from the external, unvendored Finskills directory and exposes seventeen typed tools. Plugin tests replace subprocess execution with controlled fixtures, so they verify argument handling, envelopes, caching, and ledger behavior without proving that a clean clone contains every external executable. The r5 multi-agent confirmation did not invoke these tools at all; its eighteen trace calls were exclusively `spawn_subagent`. The tools are grouped as follows.

TABLE_CAPTION: Finance capability groups exposed by the native plugin.

| Category | Tools | Purpose |
|---|---|---|
| Data and status | `toolkit_status`, `stock_snapshot`, `market_events`, `macro_snapshot` | Check capability availability and fetch timestamped market evidence. |
| Deterministic analysis | `screen_stocks`, `portfolio_risk`, `serenity_scorecard` | Apply completeness gates, portfolio diagnostics, and reproducible research-priority scoring. |
| Thesis state | `thesis_save`, `thesis_get`, `thesis_list`, `thesis_match_event`, `thesis_record_review` | Persist hypotheses, catalysts, invalidations, evidence, and immutable reviews. |
| Monitoring state | `watchlist_save`, `watchlist_list`, `event_alert_ingest`, `alert_list`, `alert_update` | Configure monitoring, deduplicate events, and manage alert lifecycle. |

Every tool returns a `finance.tool.v1` envelope containing success state, request identifier, `as_of`, staleness boundary, data, sources, quality completeness, flags, structured errors, and cache metadata. External scripts are launched without a shell, with validated symbols, bounded arguments, captured output, and a timeout. A failure becomes structured evidence for graceful degradation instead of an invitation to invent missing facts.

Stock screening includes a completeness gate. If a candidate appears to satisfy the numerical filters but a required metric is missing, it moves to the rejected set with `reason=insufficient_data`. This prevents missing data from being interpreted as zero or from silently improving a ranking.

## C. Serenity as a Research Skill

The project uses a locally inspected Serenity research Skill. Verification of its supplied SHA-256 list produced 24 successful checks and two failures for `README.md` and `README.zh-CN.md`; executable content and `SKILL.md` matched, but the repository as a whole is therefore not described as fully version-pinned. The Skill is used to map a value chain, identify difficult-to-expand bottlenecks, grade evidence, rank research priority, and define failure conditions. It is not a market-data source, a price predictor, a valuation engine, or an automatic buy/sell rule.

Serenity scorecard inputs are analyst judgments on bounded scales. The bundled script makes the arithmetic deterministic and repeatable, but cannot make subjective inputs objective. The output is therefore labelled a research-priority score. A valid experiment must hold the data, candidate universe, model, and prompt budget constant when comparing no Skill, Serenity, and Serenity plus an independent challenger.

## D. Tenant-Isolated Thesis Ledger

The plugin maintains a separate SQLite database for research state. Every stateful call requires the trusted runtime context. Records are filtered by `userId`, allowing a coordinator and specialists owned by the same user to share a ledger while preventing cross-tenant reads.

A thesis records market, symbol, text, conviction, assumptions, catalysts, invalidation conditions, evidence snapshots, status, review schedule, creator agent/session, and an integer version. Review records are immutable and retain the reviewing agent and session. Updates require an `expected_version`; a stale write is rejected rather than overwriting a newer conclusion.

The event-to-thesis workflow is:

1. obtain an event through a deterministic data tool;
2. match market, symbol, catalyst, invalidation, and assumption terms;
3. let the model assess source strength, contradiction, and impact;
4. record the review against the previously observed version;
5. require human approval for any portfolio action.

Keyword matching is a trigger, not sentiment analysis. Invalidation terms receive greater deterministic weight, but the final interpretation remains evidence-backed human or model review.

## E. Watchlists and Deduplicated Alerts

A watchlist item stores market, symbol, optional same-symbol thesis, accepted event types, weighted keywords, minimum match score, duplicate window, and lifecycle state (`active`, `paused`, or `archived`). Event ingestion normalizes the record and computes a stable SHA-256 fingerprint.

Only active watches for the same tenant, market, and symbol are considered. Events below the threshold are reported as skipped and do not create alerts. If the same fingerprint appears within the configured window, the existing alert’s occurrence count, latest evidence, and `last_seen_at` are updated. No duplicate model-review task is created. Alerts use `new`, `acknowledged`, and `dismissed` states with optimistic version checks.

This pipeline—data tool, deterministic match, agent evidence judgment, versioned persistence—keeps model reasoning focused on interpretation rather than identity, storage, or deduplication.

## F. Evidence Governance and Analytical Boundaries

The financial application follows an evidence-first rather than answer-first design. Each observation is treated as a tuple

`e = (source, observed_at, as_of, payload, completeness, freshness, error_state)`.

The distinction between `observed_at` and `as_of` is material. `observed_at` records when the runtime acquired the evidence, whereas `as_of` identifies the time to which the evidence applies. A later observation may describe an earlier accounting period, and a historical experiment must not expose information published after the simulated decision time. This requirement is consistent with established risk-data principles that emphasize lineage, timeliness, completeness, and traceability [11].

The runtime assigns different responsibilities to deterministic and probabilistic components.

TABLE_CAPTION: Allocation of responsibilities in the financial research workflow.

| Analytical operation | Primary mechanism | Reason |
|---|---|---|
| Data retrieval and normalization | Typed finance tool | Inputs, sources, and timestamps must be inspectable. |
| Ratios, thresholds, fingerprints, and concentration | Deterministic script | The same inputs should produce the same result. |
| Evidence completeness and duplicate suppression | Runtime policy and state | Missing values and duplicate events are data-quality problems, not language tasks. |
| Catalyst, contradiction, and invalidation interpretation | Coordinator or specialist model | The task requires contextual comparison and uncertainty handling. |
| Thesis and alert persistence | Versioned ledger operation | State transitions must be atomic, tenant-scoped, and auditable. |
| Portfolio action | Human decision | The application is decision support rather than autonomous execution. |

This decomposition is a safety and evaluation choice. If data retrieval, numerical calculation, and interpretation are merged into one free-form model response, a failed result cannot be attributed to a specific layer. With the decomposition above, the evaluator can distinguish missing evidence, incorrect deterministic state, routing failure, unsupported synthesis, and an explicitly deferred human decision.

## G. Scenario 1: Completeness-Aware Equity Screening

The first scenario evaluates whether the application can produce a research shortlist without converting missing data into a favorable signal. A candidate has an observed price-to-earnings ratio of 14 and return on equity of 16 percent, while free cash flow and the debt-to-asset ratio are absent. A naive language model may infer that the observed metrics are attractive and place the security in the shortlist. The FastClaw path instead invokes `screen_stocks` with `require_complete=true`.

The deterministic contract checks every metric used by the configured screen. Because two required fields are missing, the candidate is emitted in the rejected set with `reason=insufficient_data`. The coordinator must preserve the observed values, name the missing fields, exclude the candidate from ranking, and request a source refresh. It must not estimate the missing values from pretrained knowledge. The corresponding evaluator checks for evidence identifier `DAT-401`, the completeness rule `MET-411`, the state `insufficient_data`, and the absence of an invented estimate.

This scenario isolates a common financial-analysis failure: apparent ranking quality can be improved by silently dropping difficult or incomplete records. The correct runtime behavior is therefore not “select the best-looking candidate,” but “maintain the validity of the comparison set.”

## H. Scenario 2: Earnings Catalyst Review and Versioned Thesis Update

The second scenario begins with a dated quarterly filing. The fixed evidence states that services revenue grew by 18 percent and gross margin expanded by 220 basis points. The stored thesis, at version 4, names services acceleration as a catalyst and services growth below hardware as an invalidation condition. The research task is to compare the filing with the thesis and persist a bounded update without recommending a trade.

The coordinator can obtain three complementary reports: a filing specialist extracts the dated facts, a thesis specialist applies the stored conditions, and a risk specialist specifies the allowed state transition. A valid synthesis must cite the filing evidence, state that the catalyst is confirmed, state that the invalidation is not observed, and propose a positive review that changes conviction from 3 to 4 while retaining active status. Persistence is attempted with `expected_version=4`; if another reviewer has already updated the thesis, the stale write is rejected and the analysis must be repeated against the newer state.

This flow demonstrates why the Thesis Ledger is not merely conversational memory. The thesis is a domain object with explicit assumptions, catalysts, invalidations, evidence snapshots, and concurrency semantics. The model proposes an interpretation, but the ledger determines whether the transition is valid.

## I. Scenario 3: Explicit Thesis Invalidation

The third scenario tests whether the system can act conservatively when evidence crosses a pre-registered failure condition. An exchange filing reports that customer C-17, representing 31 percent of revenue, will not renew its contract. Thesis version 2 is invalidated if any customer contributing more than 25 percent of revenue is lost.

The expected outcome is not an open-ended negative summary. The system must connect the 31-percent disclosure to the 25-percent rule, persist decision `invalidate` with `expected_version=2`, set status `invalidated`, and request a new evidence review. Target-price prediction is explicitly forbidden because the evidence supports a thesis-state conclusion but not a valuation conclusion.

This scenario tests condition application, not sentiment classification. In r5, a fluent answer that describes the customer loss but leaves the thesis active fails the configured decision milestone assertion; it does not fail a separately populated state-transition grader. Likewise, prohibited valuation wording is checked through configured textual assertions. Deterministic state and policy enforcement belong to the plugin-test track rather than to r5's prose-only oracle.

## J. Scenario 4: Duplicate Event Alert Suppression

Financial announcements are frequently syndicated by exchanges, news wires, and data vendors. Processing each copy as a new event increases model cost and can create contradictory duplicate reviews. In the fourth scenario, two feeds carry external event identifier `SSE-688981-77` inside a 24-hour duplicate window. The watchlist already contains alert `FA-9` with duplicate count 1.

The runtime normalizes the event, computes a stable fingerprint, and queries active watches for the same tenant, market, and symbol. The expected update is to retain alert `FA-9`, increment its duplicate count to 2, refresh `last_seen_at`, and run thesis review only once. No second alert is created. Because fingerprinting and state mutation are deterministic, model reasoning is not required until the unique event reaches the thesis-review stage.

The experiment therefore measures both functional correctness and cost containment. Duplicate suppression is successful only if the audit trail preserves the repeated observation while avoiding a second model-review task.

## K. Scenario 5: Portfolio Concentration and Reversible Risk Control

The fifth scenario converts a deterministic risk snapshot into a bounded decision-support response. Semiconductor positions account for 62 percent of portfolio weight, the top three holdings have average pairwise correlation 0.89, and a configured sector shock produces an estimated 17-percent portfolio drawdown against a 10-percent risk limit.

The coordinator must report the concentration, correlation, stress result, and limit before proposing a response. The expected response is a staged and reversible control: reduce semiconductor exposure below 45 percent, then rerun concentration and stress checks before any execution. The grader rejects promises of improved returns because the stress result supports a risk-control proposal, not a performance guarantee.

This scenario illustrates the intended use of multi-agent challenge. A portfolio specialist can quantify exposure, a stress specialist can explain the configured scenario, and a risk specialist can test whether the proposed control is measurable and reversible. If all evidence is already available and the coordinator can synthesize it reliably, the open-book Solo baseline may be preferable because it avoids specialist cost.

## L. Scenario 6: Contradictory Primary Evidence

The final scenario tests uncertainty preservation. A dated exchange filing states that annual capital-expenditure guidance was reduced from 8 billion to 5 billion yuan. A later official call transcript states that the original 8-billion-yuan expansion plan remains unchanged. Both are treated as primary evidence, and the task supplies no authoritative reconciliation.

A valid response must present both claims, label the evidence as contradictory, keep conviction unchanged, set the thesis review state to `needs_review`, and request clarification before any upgrade or downgrade. Selecting the more convenient source is a failure. The forbidden-claim matcher is negation-aware so that statements such as “the reduction is not verified” are not misclassified as assertions that the reduction is verified.

This case is particularly important for financial analysis because source authority alone does not eliminate temporal or semantic conflict. The runtime cannot solve the contradiction deterministically; it can only ensure that disagreement remains visible and that the persisted state does not imply false certainty.

## M. Scenario-to-Mechanism Mapping

The six cases collectively cover the principal domain mechanisms.

TABLE_CAPTION: Mapping from financial scenarios to runtime mechanisms and safe outcomes.

| Case | Primary mechanism under test | Required safe outcome |
|---|---|---|
| Earnings catalyst | Dated evidence and thesis comparison | Versioned positive review; no trade authorization. |
| Thesis invalidation | Explicit failure-condition application | Status becomes invalidated; no unsupported price target. |
| Duplicate event | Fingerprint and optimistic state update | One alert, incremented occurrence count, one review. |
| Incomplete screening | Data completeness gate | Exclusion with `insufficient_data`; no imputation. |
| Portfolio concentration | Deterministic risk diagnostics | Reversible control and mandatory re-check. |
| Contradictory evidence | Uncertainty and governance | `needs_review`, unchanged conviction, clarification request. |

The cases are intentionally fixed-evidence tasks rather than return-prediction tasks. They evaluate whether the application handles research evidence and state correctly. Predictive validity is a separate question that requires point-in-time market data, survivorship-bias controls, transaction assumptions, and a clearly specified investment objective.

# VI. EVALUATION METHODOLOGY

## A. Research Design and Evaluation Propositions

The evaluation follows a controlled artifact-evaluation design. The execution unit is one isolated case–repetition–mode attempt. For the retrieval suite, the company–task pair is an analysis cluster: corpus loads and repeated provider calls derived from the same source records are not treated as independent financial cases, but the eight clusters are not claimed to be strictly independent draws from a population. The principal independent variable depends on the experimental track. Fixed-evidence comparisons vary orchestration while holding evidence and model assignment constant. Retrieval-mediated comparisons vary execution topology and context allocation under an explicitly declared model assignment. The dependent variables are deterministic task success, evidence retention, numeric grounding, collaboration quality, fault-handling quality, token usage, latency, and estimated cost under a frozen price table.

The evaluation propositions are directional design expectations with explicit evidence states, not externally registered population hypotheses:

1. **EP1:** selected runtime controls are executable and observable on the tested paths;
2. **EP2:** shared-retrieval Team preserves strict outcome and final evidence recall relative to staged Solo while reducing wall-clock latency through parallel specialist execution;
3. **EP3:** sharing one bounded evidence packet reduces tokens, frozen-price estimated cost, and unsupported numeric assertions relative to sending the raw corpus through the same Team topology;
4. **EP4:** fault-aware coordination reduces unsupported claims relative to a coordinator that treats failed specialists as successful;
5. **EP5:** deterministic finance controls achieve exact selected state and policy invariants even when open-ended wording varies;
6. **EP6:** unnecessary delegation or repeated context replication increases tokens, frozen-price estimated cost, and latency without improving milestone outcome.

The design separates infrastructure failure from model failure. A timeout, transport error, or unavailable provider is marked `errored` and excluded from the completed-output conditional-success denominator, while remaining in the assigned-attempt system-success denominator. The report shows assigned, evaluated, errored, and unavailable counts together; an errored attempt is not interpreted as a model failure.

## B. Evaluation Stack

FastClaw uses layered evaluation because no single score covers runtime quality.

TABLE_CAPTION: Evaluation layers and the capability measured by each layer.

| Layer | Implemented suite or test | Capability measured |
|---|---|---|
| Unit and integration | Go package tests and Python finance plugin tests | Selected auth, store, queue, provider, routing, cancellation, ledger, and alert paths; coverage is non-uniform. |
| Project self-eval | `evals/smoke.yaml` | Exact output, JSON format, extraction, forbidden content. |
| BFCL-style | Three BFCL V4 `simple_python` records | Function selection, JSON arguments, extra and invalid calls. |
| τ-bench-style | Three retail state-machine cases | Multi-turn state accuracy, communication, and policy compliance. |
| SWE-bench-style | Three local Go repository issues | Patch generation, hidden test execution, and resolution. |
| MultiAgentBench-style | Collaboration, real-runtime, and fault suites | Milestones, routing, evidence use, graceful degradation, Team/Solo comparison. |
| Finance workflow | Six fixed-evidence cases | Catalyst, invalidation, duplicate alerts, incomplete data, concentration, and conflicting evidence. |
| Finance retrieval | Twenty-four source-locked SEC configurations | Retrieval recall and precision, evidence compression, specialist summary retention, synthesis grounding, latency, and cost under increasing corpus load. |

The style subsets are regression tests for the FastClaw harness. They are not official benchmark scores because they use fewer tasks, local fixtures, and project-specific graders.

## C. Repetition and General Metrics

Each case runs in an isolated session with a configurable timeout and number of repetitions. The report records run pass rate, `pass@1`, `pass@k`, consistency, P50/P95 latency, tokens per successful run, invalid tool-call rate, and suite-specific outcomes. `pass@k` is the fraction of cases with at least one successful attempt among `k` repetitions; consistency is the fraction whose attempts all have the same pass/fail result.

For suites that configure state, communication, or policy graders, final success requires those populated components to pass. This is a harness capability, not a description of every suite: r5 populated text, milestone, contribution, and grounding checks but left the state, communication, policy, and tool-trace grader families empty. For local software tasks, success requires a non-empty patch and passing hidden tests.

## D. Fair Team/Solo Baselines

A naive comparison between a Team and a closed-book Solo agent is unfair when specialists possess evidence unavailable to Solo. It measures both evidence access and orchestration. The financial suite therefore defines four evidence-matched or diagnostic modes:

- `solo_open_book`: one coordinator pass over the same evidence packet, anonymized and flattened, without delegation tools;
- `solo_two_pass`: two coordinator passes over the same anonymous evidence, controlling for the additional planning/synthesis opportunity;
- `team`: two coordinator calls plus three real specialist calls through the runtime;
- `oracle_team`: named specialist reports delivered directly, representing a routed-synthesis diagnostic candidate rather than a theoretical upper bound.

The fair collaboration gain is

`Gfair = S(team) − S(solo_open_book)`,

where `S` is outcome success under the same milestone and attribution graders. Planning-opportunity-matched gain is `S(team) − S(solo_two_pass)`. This label is deliberately narrower than compute matching: Two-Pass matches an additional coordinator planning opportunity but does not match Team's three specialist calls. The older `team − solo_closed_book` value remains an evidence-access diagnostic in legacy suites but is not evidence that orchestration itself added value. Each mode receives an independent session and timeout. If a baseline times out, returns an empty output, exposes a streamed turn error, or otherwise fails at the infrastructure layer, it is marked `errored`; it remains in the assigned-attempt denominator but is excluded from completed-output conditional task success, and any dependent paired effect is unavailable. Infrastructure errors are not interpreted as model failures. The thesis constructs paired tables explicitly from case and repetition keys before computing paired statistics.

## E. Multi-Agent Metrics

For expected specialist set `E` and unique valid delegated set `D`,

`Precision = |D ∩ E| / |D|`, `Recall = |D ∩ E| / |E|`,

and delegation F1 is their harmonic mean. Contribution utilization is the fraction of expected healthy specialist evidence retained in the final answer. Coordination score is the mean of delegation F1 and contribution utilization. Milestone KPI is achieved deterministic output milestones divided by configured milestones.

Fault-injection cases add timeout, explicit error, malformed output, contradictory evidence, multiple partial failure, and non-critical failure. Metrics include fault observation, fault attribution, graceful degradation, and unsupported claim rate. Unsupported claims are counted per fault, not per phrase, so the rate cannot exceed 100%. Matching is assertion-sensitive: a negated statement such as “refund is not authorized” does not trigger the forbidden assertion “refund is authorized.”

## F. Runtime Experiment Design

The historical controlled real-runtime experiment uses one dedicated tenant, one coordinator, four specialists—five agents in total—eight fixed-evidence tasks, and an agent-scoped API key. The model configuration is constant:

- coordinator: `deepseek/deepseek-v4-pro`;
- specialists: `deepseek/deepseek-v4-flash`.

The cases cover incident diagnosis, release authorization, service-account access, schema regression, duplicate payment, privacy export, capacity planning, and dependency upgrade. The historical before/after reports were produced on 28 July 2026 with one repetition and the then-current two modes (`solo_closed_book` and `team`). Therefore their total tokens and end-to-end latency measure the complete two-mode attempt and must not be directly compared with a future four-mode attempt.

The changed factor is a harness bundle: required identity validation, enforced tool policy, prompt/tool consistency for no-tool agents, per-turn evaluation deduplication, a structured specialist contract, normalized graders, and suite pricing. The model names, task set, and repetition count remain unchanged, but the output oracle and evidence visibility are not isolated from the runtime changes. The study is consequently a historical regression sequence rather than a causal before/after experiment.

## G. Financial Workflow Experiment

The financial suite contains six cases and three specialists—four runtime agents including the coordinator. The frozen post-fix confirmation used one repetition and four independently isolated modes, yielding 24 case–mode executions and 54 model calls after including the specialists and the two-pass baseline. Session keys are unique by case, repetition, and mode so that a prior answer cannot leak into another baseline. The same deterministic milestones and forbidden assertions are used for all four modes.

The evidence source is deliberately controlled. `FIN-01` through `FIN-06` are compiled into the benchmark tenant as a string lookup table, and each specialist’s generated `SOUL.md` instructs it to copy the matching evidence line verbatim. The calls traverse the real Gateway, TaskQueue, MessageBus, agent loop, provider, correlation, and telemetry paths, but they do not measure document retrieval or specialist evidence reasoning. In r5, the coordinator’s delegate-only policy and specialist no-tools policy produced eighteen `spawn_subagent` calls and zero `finance-tools.*` calls.

The finance experiment reports five groups of measures:

1. **Outcome validity:** strict case success and milestone completion;
2. **attribution wording:** required evidence-identifier recall, forbidden-assertion rate, and explicit uncertainty under contradiction;
3. **governance wording:** whether the answer states the expected thesis, watchlist, or alert action and optimistic-version requirement;
4. **orchestration validity:** delegation precision, recall, contribution utilization, fair collaboration gain, and oracle gap;
5. **efficiency:** Team-only tokens, Team P50/P95 latency, coordinator/specialist cost, and cost per successful Team case.

The six case oracles are specified before execution.

TABLE_CAPTION: Fixed evidence and deterministic oracle for the financial workflow experiment.

| Case | Core evidence | Deterministic oracle |
|---|---|---|
| Earnings catalyst | 18% services growth; 220-bp margin expansion; thesis version 4 | Positive review, conviction 3→4, active status, no trade. |
| Thesis invalidation | Customer loss equals 31% of revenue; invalidation threshold 25% | Invalidate version 2, request fresh review, no target price. |
| Duplicate alert | Same external event ID inside 24 hours; existing alert count 1 | Keep one alert, count becomes 2, update `last_seen_at`. |
| Incomplete screen | PE and ROE present; free cash flow and leverage absent | Reject as `insufficient_data`; request refresh; no imputation. |
| Portfolio concentration | 62% sector weight; 0.89 correlation; 17% stress loss versus 10% limit | Staged reduction below 45% and mandatory re-test. |
| Contradictory evidence | Filing says capex 8→5 billion; later transcript says 8 billion unchanged | `needs_review`, unchanged conviction, clarification required. |

Functional feasibility is defined conservatively. All configured wording and policy assertions must hold across repetitions; baseline infrastructure errors must be zero or separately disclosed; unsupported claims must be zero for cases with incomplete or contradictory evidence; and any Team advantage must be computed against `solo_open_book`, not against an evidence-deprived closed-book baseline. Actual ledger mutation is tested separately by the Python plugin suite and is not inferred from r5 prose. A positive return is not an acceptance criterion.

## H. Retrieval-Mediated SEC Experiment

The retrieval track introduces evidence acquisition as an explicit stage rather than assuming that a complete evidence packet is already available. Its frozen suite contains four companies—NVIDIA, AMD, Intel, and NIKE—crossed with two task families and three corpus loads. Point-in-time cases require one bounded observation and declared calculations. Longitudinal cases require chronology reconstruction, accounting-basis checks, cross-observation calculations, a contiguous research-state chain, and a bounded governance decision. Small, medium, and large loads add progressively more same-company, adjacent-period, peer, and irrelevant records. The resulting 24 configurations are treatment combinations, not 24 independent issuers.

All records are extracted from archived SEC filing material and carry a source identifier, accession, filing date, locator, source hash, and record identifier. The suite and source lock are content-addressed. A unified provenance table covers all 44 human-oracle facts with company, symbol, concept, value, unit, basis, explicitly available scope, reporting period, filing date, SEC acceptance timestamp, accession, form, document type, URL, locator, and source SHA-256. A separate acceptance-time lock records SEC submissions API metadata for all twelve source accessions. The point-in-time generator excludes candidate records accepted after the target gold-record timestamp; all twelve point-in-time configurations pass this machine check. A separate 17-row derived-value table preserves formulas, input fact identifiers, unit, rounding rule, and expected result. Gold evidence is represented as 37 equivalence groups so overlapping source windows can satisfy the same factual requirement without penalizing a semantically correct retrieval. The human oracle—not model output or grader consensus—is the declared ground truth. Expected calculation outputs remain hidden from non-Oracle modes; all modes receive the same formulas, rounding rules, output sections, and bounded decision protocol. Independent human verification of the acceptance metadata remains part of the pre-freeze audit.

The five modes are:

1. `solo_monolithic`: one Pro call receives the raw corpus and performs retrieval, analysis, and synthesis in one context;
2. `solo_staged`: one Pro agent performs retrieval, three sequential analytical passes, and synthesis in isolated sessions;
3. `team_shared_retrieval`: one Flash retriever constructs a bounded packet, a Pro coordinator delegates the packet once to three parallel Flash specialists, and the coordinator synthesizes their summaries;
4. `team_raw_context`: the same Team topology receives the full raw corpus as shared context, isolating the effect of retrieval compaction;
5. `oracle_evidence`: one Pro synthesis call receives the gold evidence packet and provides a diagnostic ceiling rather than a deployable baseline.

The primary quality outcomes are strict pass, final evidence recall, milestone completion, and numeric grounding accuracy. Retrieval recall and precision, specialist-summary retention, synthesis retention, evidence-compression ratio, delegation precision and recall, infrastructure-error rate, tokens, estimated cost, and wall-clock latency are secondary mechanism and efficiency outcomes. Stage service times are retained for attribution, but specialist service times are summed across parallel calls and therefore are not substituted for end-to-end wall-clock latency.

The first executed observation is a one-repetition medium-context longitudinal NVDA pilot. It is an engineering and measurement pilot because earlier attempts informed thinking-mode, prompt, batching, trace, and grader corrections. The second-stage protocol freezes these mechanisms before executing the complete matrix. Within each case–repetition block, primary mode order must be seeded and randomized; sessions must remain isolated; source, suite, grader, and pricing hashes must remain unchanged; and baseline infrastructure errors must be reported separately. The full protocol is stored in `evals/finance_e2e/STAGE2-EXPERIMENT-PROTOCOL.md`.

## I. Fault-Injection Protocol

Fault injection is limited to the simulated evaluation path and cannot modify production agents. The suite injects timeout, explicit error, malformed output, contradictory evidence, multiple partial failures, and a non-critical specialist failure. Delay injection obeys request cancellation and has a configured upper bound.

For configured fault set `F`, observed-fault set `O`, and correctly attributed set `A`,

`FaultObservation = |O| / |F|`, `FaultAttribution = |A| / |F|`.

Graceful degradation requires the coordinator to identify unavailable or conflicting evidence, preserve contributions from healthy specialists, avoid the forbidden unsupported assertion, and provide a bounded next action. Unsupported-claim rate is defined per fault rather than per matching phrase:

`UnsupportedClaimRate = |{f ∈ F : an unsupported assertion is produced for f}| / |F|`.

This definition keeps the rate within `[0,1]`. Assertion matching also considers local negation so that “the refund is not authorized” does not count as the forbidden assertion “the refund is authorized.” An all-faulted case is evaluated on safe degradation rather than healthy-contribution utilization.

## J. Runtime and Grader Ablations

The historical comparison changes several runtime controls together. A stronger follow-up study should isolate their contribution through cumulative ablation:

TABLE_CAPTION: Proposed cumulative ablation of runtime controls.

| Configuration | Identity validation | Tool policy | Structured specialist contract | Evaluation deduplication | Normalized grader |
|---|---:|---:|---:|---:|---:|
| A0: unrestricted baseline | No | No | No | No | No |
| A1: identity contract | Yes | No | No | No | No |
| A2: capability boundary | Yes | Yes | No | No | No |
| A3: output contract | Yes | Yes | Yes | No | No |
| A4: bounded coordination | Yes | Yes | Yes | Yes | No |
| A5: complete harness | Yes | Yes | Yes | Yes | Yes |

For each adjacent pair, the study should report the change in strict success, duplicate delegation count, specialist tool-call count, Team tokens, and P95 latency. This design separates three mechanisms that can otherwise be conflated: improved evidence delivery, reduced action space, and more permissive grading of semantically equivalent correct answers.

A second finance-specific ablation compares (i) deterministic tools without a research Skill, (ii) the same tools and data with Serenity methodology, and (iii) the same configuration plus an independent challenger. Candidate universe, evidence packet, coordinator model, timeout, and token budget must remain constant. The comparison tests whether the Skill improves coverage of value-chain and invalidation reasoning, and whether a challenger improves contradiction detection enough to justify its additional cost. Neither runtime-control ablation has yet been executed.

One zero-model-call grader ablation is implemented in `project-report/analysis`. It reloads the frozen suite, regrades r1–r5 outputs, and changes one matching feature at a time: negation scope, hedge scope, conditional scope, the eight-token per-step gap, plural morphology, and a lightweight `-ed`/`-ing`/`-ion` inflection stem. The first five switches remove one current guard; the sixth adds a deliberately permissive morphology rule. This is not a search for the highest score. It tests whether headline conclusions remain stable when plausible lexical design choices change.

The replay duplicates the production matcher in an independent analysis program and has regression tests for the audited pooled counts and drift cells. Duplication risks implementation disagreement, but it also avoids mutating the production grader simply to analyze itself. A future release should expose a versioned grader API so the same implementation can be called with an explicit configuration and preserved in each artifact.

## K. Statistical Reporting and Reproducibility

The primary result is the raw case-level paired outcome table with assigned, evaluated, errored, and unavailable counts. Historical r2–r5 Wilson intervals and exact-binomial/McNemar calculations are retained only as naive descriptive sensitivity analyses: pooling repeated versions and treating the cases as independent does not model their dependence or post hoc selection. If there are no discordant pairs, the exact test is undefined rather than evidence of equality. Stage 2 prespecifies company–task cluster bootstrap intervals, but with only eight analysis clusters those intervals remain descriptive. Latency and token distributions are summarized by median, P95, and individual-case values because a mean can hide delegation loops.

The retrieval suite requires an additional dependence correction. Three corpus loads and repeated calls derived from one company–task pair share source material and cannot be counted as independent cases. Stage 2 therefore reports paired effects at every configuration but constructs uncertainty intervals by resampling company–task clusters. Load-specific effects are reported as within-cluster contrasts. With only eight company–task clusters in the initial four-company matrix, these intervals remain descriptive; expansion to additional issuers is required before a population-level superiority or non-inferiority claim.

The six-case confirmation has one repetition. Even the most extreme possible paired result—six Team-only successes and no Solo-only successes—has two-sided exact probability `2/2^6 = 0.03125`. Any smaller discordance cannot cross a conventional 0.05 threshold. Consequently the experiment is structurally underpowered for modest differences, and an observed 0.0-point difference means “not detected at this resolution,” not “equivalent.”

Every reported run should record the model names, provider endpoint class, suite name, baseline modes, repetition count, timeout, pricing table date, execution mode, case filter, and whether specialists were simulated or executed through the real runtime. Evidence fixtures and graders should remain unchanged during one comparison. Reports should retain per-call role, call path, token counts, latency, and error state so aggregate cost can be audited. The r5 sidecar records that the suite default was three repetitions but the command overrode it to one, and records the four mode names, ten-minute timeout, runtime execution mode, empty case filter, pricing date, endpoint class, Go version, HEAD, critical file hashes, and secret-free command.

The historical eight-case experiment predates the four-mode protocol and contains one repetition. It is therefore reported descriptively without a significance test. The six-case financial confirmation also contains one repetition and is reported with raw counts and an explicit power bound. Earlier financial runs were used to identify grader defects and calibrate narrowly scoped assertion alternatives; consequently the final run is a frozen post-fix confirmation, not an untouched holdout or independent validation set. Pooling r2–r5 is reported only as post hoc sensitivity analysis because the decision to pool followed inspection of the runs. Retrieval runs `v1` through `v7` are likewise excluded from comparative inference because they informed the final runtime and grader. The retained `v8` through `v10` observations share source hashes but still contain only one case and one repetition.

# VII. RESULTS

## A. Engineering Verification

The remediation was verified first with focused package tests covering the evaluation harness, agent loop, sub-agent tools, store, plugins, tenant provisioning, API, and command layer, followed by `go test ./... -count=1`, which passed across the repository. Behavioral tests exercise assertion direction and negation, error-aware denominators, streamed turn errors, tool panic containment, duplicate call identifiers, production and evaluation deduplication semantics, per-tool duration, model-call ordering, and SQLite contention through the public Store API. Race-enabled tests for `internal/agent`, `internal/agent/tools`, and `internal/store` also passed and are reported separately from ordinary functional tests because they detect synchronization faults rather than semantic failures.

The finance plugin passes ten Python tests covering typed tool discovery, subprocess argument validation, cache behavior, completeness gating, trusted tenant context, thesis isolation and versioning, event review persistence, watchlist filtering, alert deduplication, and user isolation.

Statement coverage measured with `go test ./... -coverprofile` is approximately 27.2% for runtime and production packages, or 28.4% when `project-report/analysis` is included. Coverage is strongly non-uniform: `policy`, `scope`, `session`, `plugin`, `mcp`, and `skills` are among the packages at 0.0%, while `agent/tools`, `gateway`, `sandbox`, `setup`, and `store` remain partial. These gaps affect mechanisms used in the design argument, especially policy-filtered registries, session normalization, and prompt-injection scanning. The test results establish functional feasibility of selected principal paths; they do not constitute comprehensive code coverage, a production load test, an adversarial security certification, or evidence of investment performance.

## B. Historical Runtime Regression Sequence

TABLE_CAPTION: Historical two-mode real-runtime regression sequence (one repetition per case).

| Metric | Initial | Intermediate | Final observed |
|---|---:|---:|---:|
| Strict task success | 0/8 | 4/8 | 8/8 |
| Milestone KPI | 16.7% | 83.3% | 100% |
| Coordination score | 38.2% | 93.1% | 100% |
| Contribution utilization | 17.2% | 86.2% | 100% |

TABLE_CAPTION: Initial-to-final efficiency observations in the historical two-mode sequence.

| Metric | Initial | Final observed | Descriptive change |
|---|---:|---:|---:|
| Delegation precision | 42.0% | 100% | +58.0 pp |
| Delegation recall | 100% | 100% | unchanged |
| Total tokens | 1,274,742 | 73,729 | −94.2% |
| Model calls | 194 | 53 | −72.7% |
| P50 end-to-end latency | 110.1 s | 46.0 s | −58.2% |
| P95 end-to-end latency | 201.6 s | 60.0 s | −70.2% |
| Pricing coverage | 0% | 100% | +100 pp |
| Estimated total cost | N/A | USD 0.019599 | reported |

The intermediate artifact prevents a selective binary “before/after” presentation. The three points show that the optimized configuration itself was iterated. Token and latency fields include both `solo_closed_book` and `team`, so they are not directly comparable with the four-mode financial attempt.

The sequence is consistent with a substantial change in the realized agent system, but it cannot allocate that change to the runtime. Evidence visibility differed between modes, the grader changed with the harness, and the initial outputs have not been replayed under the final historical rubric. Baseline traces show irrelevant specialist tools, repeated delegation, weak fixed-evidence enforcement, and lexical false negatives. The final bundle addressed all four simultaneously.

The reduction from 1,274,742 to 73,729 tokens and from 194 to 53 model calls is consistent with fixed-evidence specialists avoiding file/tool loops, exact repeated coordinator delegations reusing a result, and structured specialist output reducing recovery turns. P95 latency declined from 201.6 to 60.0 seconds. These are descriptive associations with the bundled harness change, not estimates of any component’s isolated causal effect.

The optimized two-mode run cost an estimated USD 0.019599 under the pricing embedded in the suite. Team execution accounted for USD 0.013751 and closed-book Solo for USD 0.005848. Coordinator Team calls cost USD 0.009911 and specialists USD 0.003840, or USD 0.001719 per successful Team case. Pricing coverage rose from 0% to 100%, which means every captured model call matched a declared price.

## C. Mechanism-Level Interpretation

The experiment establishes a strong within-suite association between the runtime configuration and realized quality and efficiency while the model assignment remains constant. It does not identify the isolated causal contribution of each runtime change because identity validation, policy filtering, specialist contracts, deduplication, grading, and pricing support were introduced together. Evidence visibility also differs between the legacy modes. The ablation design in Section VI-I is required for component-level attribution.

The failure traces nevertheless support a mechanism-level explanation. Required identity files make evidence delivery observable; policy filtering prevents fixed-evidence specialists from entering irrelevant file or shell loops; structured specialist contracts reduce synthesis ambiguity; and evaluation-only deduplication prevents repeated delegation from becoming a cost and latency multiplier. The normalized grader corrects false negatives caused by equivalent numeric forms, but it does not alter the underlying model output.

The experiment does not prove a 100-percent general multi-agent success rate. The task set contains eight deterministic evidence cases, each run once. The graders measure configured milestones and evidence strings. A stronger study requires repeated paired trials, isolated ablations, and case-level reporting.

## D. Implemented Financial Verification

The financial application has four forms of implemented evidence:

1. the runtime and plugin compile and pass their unit/integration tests;
2. the stateful plugin implements trusted tenant scope, versioned theses, immutable reviews, watchlists, and alert deduplication;
3. the six-case finance suite encodes the behaviors expected from an evidence-grounded research copilot;
4. the suite has been executed through the real runtime under four matched baselines with per-mode grounding, tokens, cost, and latency.

The finance suite intentionally avoids future stock returns. It evaluates whether the coordinator preserves dated primary facts, applies catalysts and invalidations, suppresses duplicate alerts without losing occurrence counts, rejects incomplete screens, converts concentration diagnostics into reversible controls, and retains uncertainty under contradictory evidence.

The implemented test evidence and the model-evaluation evidence must be distinguished.

TABLE_CAPTION: Current evidence status and the claims supported by each artifact.

| Evidence type | Current status | Claim supported |
|---|---|---|
| Plugin unit tests | Ten tests pass | Tool discovery, argument validation, caching, completeness, tenant isolation, versioning, and deduplication operate as implemented. |
| Runtime integration tests | Relevant Go packages pass | Authenticated routing, task execution, provider parsing, internal calls, and evaluation reporting are executable. |
| Six finance case specifications | Implemented | Financial invariants and deterministic graders are defined before model execution. |
| Four-mode finance confirmation | One repetition; no baseline errors | Descriptive matched-baseline quality, grounding, token, cost, and latency results are available; no statistical or holdout claim is made. |
| Point-in-time return study | Not implemented | No claim is made about excess return, hit rate, Sharpe ratio, or investment performance. |

## E. Four-Mode Financial Runtime Result

The final frozen post-fix confirmation was executed on 1 August 2026.

`Suite SHA-256: 4fbf54eca61dc7363342ea1db364cb84426e1541937a99c1e1266dbfb3e5dc44`

`Artifact SHA-256: 5366a91398ca575d303af56d62da179f2a3f1fb13a1d0f5aae5c1773debfbc00`

The secret-free run configuration is archived in `evals/finance-runtime-formal-r5.manifest.json`. It records that the suite default of three repetitions was overridden to one, the four modes, ten-minute timeout, runtime execution mode, empty case filter, endpoint class, pricing date, model roles, Go version, and source identifiers. The model run came from a dirty working tree. Critical evaluator and tenant files are hashed, but the complete dirty patch was not archived at execution time; the outputs can be regraded exactly, whereas exact regeneration of the provider trajectories cannot be claimed from the recorded HEAD alone. All 24 mode executions completed without infrastructure error, and all 54 model calls were priced. The effective r5 oracle contained 18 milestone checks and 44 grounding assertions; `state_graders`, `communication_graders`, `policy_graders`, and `tool_trace_graders` were each zero. Their reported zero accuracies are therefore vacuous rather than evidence that those four capabilities were tested in r5.

TABLE_CAPTION: Frozen post-fix financial confirmation, one repetition and six cases.

| Mode | Assigned | Evaluated | Errored | Unavailable | Conditional passed | Billable-like tokens | Provider total tokens | Frozen-price estimated cost (USD) | Mean latency |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Solo Open-Book | 6 | 6 | 0 | 0 | 5/6 | 6,557 | 9,885 | 0.005510 | 13.65 s |
| Solo Two-Pass | 6 | 6 | 0 | 0 | 5/6 | 23,910 | 30,822 | 0.017798 | 42.65 s |
| Team | 6 | 6 | 0 | 0 | 5/6 | 13,955 | 41,219 | 0.008335 | 19.45 s |
| Routed Team Diagnostic | 6 | 6 | 0 | 0 | 4/6 | 5,062 | 8,902 | 0.004320 | 11.32 s |

Billable-like tokens are uncached prompt plus completion tokens and are presented first. Provider total tokens include cache-read tokens inside prompt totals and therefore answer a different telemetry question. By the billable-like measure, Team used 2.13 times the Open-Book tokens and 41.6% fewer tokens than Two-Pass. By provider totals, the same comparisons are 4.17 times and 33.7% more. The Team/Two-Pass direction therefore reverses under the two accounting conventions. Team cost 51.3% more than Open-Book but 53.2% less than Two-Pass; model assignment, completion length, cache treatment, and provider prices all contribute, so the difference is not attributed solely to Flash specialists.

TABLE_CAPTION: Team coordination and attribution metrics in r5.

| Metric | Result | Interpretation |
|:---|---:|:---|
| Milestone KPI | 17/18 (94.4%) | One configured decision assertion failed |
| Delegation precision | 100% | No unexpected unique specialist target |
| Delegation recall | 100% | All expected specialist targets called |
| Contribution utilization | 17/18 (94.4%) | One specialist contribution assertion failed |
| Coordination score | 97.2% | Mean of perfect delegation F1 and contribution utilization |
| Routed-diagnostic gap | −16.7 pp | Diagnostic minus Team; not an upper-bound gap |
| Faults expected | 0 | Fault metrics are undefined/vacuous for this run |

Team P50/P95 latency was 21.30/22.49 seconds. The P50 exceeds the 19.45-second mean because several short cases pull the arithmetic mean below the midpoint of the six ordered values. Coordinator calls consumed 22,236 provider-total tokens and USD 0.007060; specialist calls consumed 18,983 and USD 0.001276. Cost per successful Team outcome was USD 0.001667.

Across each mode, 44 configured forbidden assertions were evaluated and zero violations were recorded. One Team output nevertheless contained the forbidden phrase “higher evidentiary weight” in “the filing may carry higher evidentiary weight.” The five-token hedge rule suppresses a violation when `may`, `might`, `could`, `possible`, or `possibly` precedes the phrase. The reported 100% configured attribution accuracy therefore includes one explicit hedge exemption. It is a lexical policy result, not factual accuracy or proof of entailment.

The failed Team case was `incomplete-screening-data`, and it produced two grader failures from one rubric value. The `decision` milestone and the finance-governance contribution both required `not estimate || instead of estimating`; the answer wrote “must not be imputed, inferred, or estimated.” The current normalizer does not map `estimated` to `estimate`. The case therefore achieved 2/3 milestones, utilized 2/3 contributions, and received coordination 0.8333 despite making the correct conservative decision, citing all three evidence records, requesting source refresh, and rejecting imputation. The failure is an inflectional morphology gap, not a clause-distance failure. This trade-off is substantive: conservative stemming limits false matches but can reject a semantically appropriate inflected form.

The preceding r1–r4 artifacts are calibration and diagnostic runs. Replaying all five artifacts through the current independent matcher changes 4, 1, 2, 1, and 0 stored outcome cells respectively. That drift quantifies the danger of mixing grader evolution with runtime conclusions. Because fixes were informed by earlier outputs, r5 is a frozen post-fix confirmation, not a holdout estimate.

### Longitudinal SEC Difficulty Extension

The four-company initial-observation study reached a 4/4 ceiling in Team, Open-Book, Two-Pass, and routed-diagnostic modes. That result verified evidence-bounded runtime execution but could not identify incremental collaboration accuracy because the outcome contained no mode-level variance. A second suite therefore combined three locked SEC observations per company and required chronology reconstruction, declared cross-observation calculations, a contiguous `0→1→2→3` state chain, a final governance decision, and rejection of a stale control candidate. Evidence was held constant across all modes; only Team could call the three runtime specialists.

TABLE_CAPTION: Frozen longitudinal SEC extension, one repetition and four companies.

| Mode | Assigned | Evaluated | Errored | Unavailable | Conditional passed | Provider total tokens | Frozen-price estimated cost (USD) | Mean latency |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|
| Solo Open-Book | 4 | 4 | 0 | 0 | 3/4 | 27,847 | 0.018099 | 57.32 s |
| Solo Two-Pass | 4 | 4 | 0 | 0 | 1/4 | 51,556 | 0.029369 | 94.31 s |
| Team | 4 | 4 | 0 | 0 | 3/4 | 78,800 | 0.022718 | 65.31 s |
| Routed Team Diagnostic | 4 | 4 | 0 | 0 | 1/4 | 24,021 | 0.014562 | 48.69 s |

Team achieved 100% delegation F1, 91.7% specialist-contribution utilization, 95.6% contribution-item coverage, 100% configured grounding accuracy, and no unauthorized numeric value. Team and Open-Book each passed 75%, so the fair collaboration gain was zero. Their paired outcomes contained one Team-only success, one Open-Book-only success, and two ties. Team exceeded Two-Pass by 50 percentage points, but only two pairs were discordant and the sample is not adequate for an inferential claim. Relative to Open-Book, Team used 183.0% more tokens, cost 25.5% more, and increased mean latency by 13.9% without improving strict success. Relative to Two-Pass, Team cost 22.6% less and reduced mean latency by 30.8% despite using 52.8% more provider-total tokens.

The Team failure occurred on AMD. The coordinator selected the correct governance specialist but received an empty result, retried until five delegations had been issued against a configured maximum of three, and synthesized without the required STATE and STALE evidence. This case demonstrates that routing accuracy is not sufficient for collaboration success: sub-agent response validity and bounded recovery are part of the runtime treatment. The frozen primary report is `evals/finance_e2e/results/2026-08-02-hard-r3-final.json`; earlier longitudinal runs are calibration artifacts because their outputs informed grader corrections. The extension removes the simple-task ceiling but does not support a claim that Team is more accurate than an evidence-matched strong Solo coordinator.

### Retrieval-Mediated Context Allocation Pilot

The preceding experiments begin after evidence has already been compiled. A realistic financial-research workflow introduces an earlier bottleneck: source acquisition consumes context, retrieved passages vary in relevance, and analytical reasoning must operate on an imperfect intermediate representation. A retrieval-mediated pilot was therefore added to test the complete information path from a locked SEC corpus to a bounded research memorandum. The research question is narrower than “are multiple agents more accurate?”: under a fixed evidence source and analysis protocol, does retrieving one compact packet before role-specialized analysis reduce context interference and execution cost without reducing evidence retention or conclusion quality?

Five runtime modes operationalize the treatment. `solo_monolithic` gives one Pro agent the 30,518-character corpus and asks it to retrieve, analyze three perspectives, and synthesize in a single context. `solo_staged` uses the same Pro agent in isolated retrieval, three sequential analysis, and synthesis stages. `team_shared_retrieval` uses a Flash retriever to construct one bounded evidence packet, sends that packet once through a batch delegation to three parallel Flash specialists, and uses a Pro coordinator for orchestration and synthesis. `team_raw_context` preserves the same coordinator-specialist topology but shares the full corpus rather than a retrieved packet. `oracle_evidence` gives a Pro synthesis call the perfect evidence packet and serves only as a diagnostic reference; perfect retrieval does not guarantee perfect synthesis.

The case, task wording, required report sections, calculation protocol, evidence identifiers, rounding rule, and 95% numeric-grounding threshold were held constant. Expected calculation answers were withheld from every non-oracle mode. The source was locked by suite SHA-256 `7b73f4b82a3f97cb1151b372dcf8172eb88c04d37e1e137ed80b2a87bfb44e20` and source-lock SHA-256 `a4d4b4dc3be440238e3d428d60d04fb4a4a9d21d8c0b4eec4cb313e2e181fe22`. Thinking mode was disabled. Because Team assigns Flash to retrieval and specialist work while staged Solo uses Pro in every stage, this is a comparison of deployable heterogeneous systems rather than a model-capacity-matched experiment.

TABLE_CAPTION: Retrieval-mediated NVDA medium-context pilot, one repetition.

| Mode | Assigned | Evaluated | Errored | Unavailable | Conditional strict pass | Milestones | Final evidence recall | Grounding | Latency | Provider-total tokens | Frozen-price estimated cost (USD) | Compression |
|:---|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| Solo monolithic | 1 | 1 | 0 | 0 | No | 2/3 | 100% | 98.29% | 55.96 s | 15,259 | 0.008263 | N/A |
| Solo staged | 1 | 1 | 0 | 0 | Yes | 3/3 | 100% | 95.45% | 141.04 s | 37,693 | 0.020690 | 6.12x |
| Team shared retrieval | 1 | 1 | 0 | 0 | Yes | 3/3 | 100% | 98.28% | 89.81 s | 42,829 | 0.011987 | 7.58x |
| Team raw context | 1 | 1 | 0 | 0 | No | 3/3 | 100% | 94.87% | 104.61 s | 69,553 | 0.022884 | N/A |
| Oracle evidence | 1 | 1 | 0 | 0 | Yes | 3/3 | 100% | 100% | 37.89 s | 7,095 | 0.002464 | N/A |

The staged Solo and shared-retrieval Team both passed every milestone and retained every gold evidence group. This observation therefore provides no incremental final-answer accuracy result for collaboration. It does reveal an efficiency and evidence-discipline difference. Relative to staged Solo, shared-retrieval Team reduced end-to-end latency by 36.32% and estimated cost by 42.06%, despite using 13.63% more provider-total tokens. The cost direction follows from heterogeneous model allocation rather than token reduction. Retrieval precision increased from 66.67% to 100%, evidence compression increased from 6.12x to 7.58x, and numeric grounding increased by 2.82 percentage points.

The raw-context ablation was associated with a context-allocation difference within the same multi-agent topology. Both Team modes issued one parallel batch delegation and reached perfect target precision and recall. Shared retrieval was associated with 14.15% lower latency, 38.42% fewer tokens, and 47.62% lower frozen-price estimated cost than raw-context Team, alongside a 3.40-percentage-point grounding difference. Raw-context Team produced eight unsupported or unrequested numeric forms and missed the prespecified grounding threshold by 0.128 percentage points; shared-retrieval Team produced two such forms. Because mode order was not randomized, provider conditions could vary, and the model allocation was heterogeneous, these observations do not identify a causal context-allocation effect. The monolithic mode was faster and cheaper than either complete pipeline but omitted the required separation of sourced fact, declared calculation, and analyst judgment. Its failure is therefore one of research-process compliance, not evidence recall.

These findings support only a bounded descriptive claim: on one medium-context filing task, explicit retrieval and shared-context delegation were associated with a different latency–cost–grounding profile from sequential staged Solo and raw-context Team. They do not establish that multiple agents intrinsically improve financial accuracy. The observation has one company and one repetition, mode order was not randomized, provider conditions could vary, and the grounding evaluator checks numeric support rather than full semantic entailment. Confirmatory work must freeze the suite and grader, cross four companies with small, medium, and large corpus loads, use at least three randomized repetitions, retain paired case-repetition identifiers, and report bootstrap intervals. A separate capacity-matched ablation should hold model assignment constant across Team and Solo.

For Team modes, reported analysis latency is the sum of specialist model-service times, whereas specialists execute concurrently. End-to-end mode latency is the wall-clock quantity and must not be reconstructed by summing stage totals. The complete descriptive record and calibration exclusions are documented in `evals/finance_e2e/results/2026-08-02-retrieval-pilot-final-summary.md`.

## F. Post Hoc Sensitivity and Grader Ablation

Runs r2–r5 share the same suite SHA-256, model assignments, and nine model calls per case. Regrading their retained outputs with the current matcher yields the following post hoc sensitivity result. The pooling decision was made after inspecting the runs, so the table is not independent validation and must not replace r5 as the primary result.

TABLE_CAPTION: Post hoc pooled r2–r5 outcomes under the current grader.

| Mode | Passed | Rate | Wilson 95% interval |
|:---|---:|---:|---:|
| Solo Open-Book | 15/24 | 62.5% | [42.7%, 78.8%] |
| Solo Two-Pass | 16/24 | 66.7% | [46.7%, 82.0%] |
| Team | 18/24 | 75.0% | [55.1%, 88.0%] |
| Routed Team Diagnostic | 18/24 | 75.0% | [55.1%, 88.0%] |

The paired Team/Open table has six Team-only and three Open-only outcomes, giving +12.5 percentage points and exact two-sided p=0.5078. Team/Two-Pass has five Team-only and three Two-Pass-only outcomes, giving +8.3 points and p=0.7266. Team and the routed diagnostic each have three exclusive successes, giving 0.0 points and p=1.0000. These p-values do not support superiority. They show that the r5 zero-point estimate is not a stable estimate of direction when additional retained runs are included.

TABLE_CAPTION: Case-level passes across post hoc pooled r2–r5, current grader.

| Case | Team | Open-Book | Two-Pass | Routed Diagnostic |
|:---|---:|---:|---:|---:|
| Thesis invalidation | 4/4 | 2/4 | 2/4 | 4/4 |
| Portfolio concentration | 3/4 | 1/4 | 1/4 | 2/4 |
| Earnings catalyst | 4/4 | 3/4 | 3/4 | 4/4 |
| Duplicate event | 3/4 | 3/4 | 3/4 | 2/4 |
| Contradictory evidence | 4/4 | 3/4 | 4/4 | 4/4 |
| Incomplete screening | 0/4 | 3/4 | 3/4 | 2/4 |

The heterogeneity is more informative than the aggregate. Team is consistently stronger on thesis invalidation and portfolio concentration, but is 0/4 on incomplete screening because the same morphology gap recurs. The aggregate therefore combines a plausible coordination advantage on some mechanisms with a systematic measurement defect on another.

Figure 4 visualizes the grader sensitivity experiment. Its purpose is not to select the rule set that maximizes Team performance, but to show how much the reported conclusion depends on lexical measurement design even when no additional model call is made.

[[FIGURE_4]]

TABLE_CAPTION: Zero-model-call grader ablation over r1–r5, thirty outputs per mode.

| Matcher configuration | Open-Book | Two-Pass | Team | Routed Diagnostic |
|:---|---:|---:|---:|---:|
| Current | 20/30 | 21/30 | 23/30 | 22/30 |
| Without negation scope | 12/30 | 13/30 | 14/30 | 13/30 |
| Without hedge scope | 20/30 | 21/30 | 22/30 | 22/30 |
| Without conditional scope | 20/30 | 21/30 | 22/30 | 22/30 |
| Without bounded token gap | 20/30 | 21/30 | 23/30 | 22/30 |
| Without plural morphology | 19/30 | 21/30 | 23/30 | 22/30 |
| With extended inflections | 25/30 | 21/30 | 27/30 | 21/30 |

Negation scope has the largest protective effect because disabling it converts correct denials into forbidden positive assertions. Hedge and conditional scope each move one Team cell. Removing the token-gap guard has no effect on these artifacts, directly contradicting the earlier diagnosis that r5 failed because related phrases were too far apart. The permissive inflection switch raises Team to 27/30 and Open-Book to 25/30 while reducing the routed diagnostic to 21/30, illustrating that a linguistically plausible normalizer can change both absolute scores and relative conclusions. The ablation supports a measurement-validity finding, not a recommendation to select the switch that maximizes Team.

## G. Validity Preconditions and Answers to the Empirical Questions

**VP1—Selected runtime control paths.** The passing unit and integration tests, together with explicit tests for cancellation, stream failure, task snapshots, tenant scope, and session normalization, support the feasibility of selected runtime control paths. The result is functional verification rather than formal proof or production certification.

**RQ2—Orchestration benefit.** The present instrument does not establish an incremental accuracy effect. The simple four-company SEC study saturated at 4/4 in every mode. The longitudinal extension removed that ceiling, but Team and evidence-matched Open-Book each passed 3/4 cases, with one paired win and one paired loss for Team. r5 likewise recorded equal 5/6 counts, while post hoc r2–r5 pooling moves the point estimates to +12.5 and +8.3 points for Team without statistical support. In the retrieval-mediated Pilot, shared-retrieval Team and staged Solo both passed all milestones and retained every gold evidence group. These results do not establish superiority, inferiority, or equivalence. A repeated, randomized study with a frozen grader and more company–task analysis clusters is required.

**RQ3—Context allocation and efficiency.** The historical sequence is consistent with substantial harness-level reductions but does not isolate causes. In r5, Team was more expensive and slower than one-pass Open-Book Solo. Relative to Pro-only Two-Pass Solo, Team was cheaper and faster and used 41.6% fewer billable-like tokens, even though provider totals were 33.7% higher. The retrieval pilot provides a more direct context-allocation contrast. Shared-retrieval Team reduced latency by 36.32% and cost by 42.06% relative to staged Solo, but used 13.63% more provider-total tokens because Flash specialists replaced Pro analytical stages. Relative to raw-context Team, shared retrieval reduced tokens by 38.42%, cost by 47.62%, and latency by 14.15%, while improving grounding by 3.40 percentage points. These are deployment-level point estimates under declared heterogeneous allocation, not a capacity-matched causal effect.

**Prospective RQ4—Fault tolerance.** The harness implements bounded simulated faults, error-aware denominators, negation-aware unsupported-claim checks, and graceful-degradation metrics. r5 configured `faults_expected=0`, so its zero fault metrics are vacuous. This work contributes an instrument but does not execute the question in a retained primary financial artifact.

**VP2—Selected financial-workflow invariants.** The evidence is split. Ten plugin tests exercise deterministic ledger and alert behavior. r5 exercises real coordinator–specialist routing over compiled evidence fixtures and grades whether the final prose states expected governance actions; it performs no finance-tool call and no ledger mutation. The evidence supports selected attribution and wording behavior, not end-to-end persistent state validity. The incremental value of Serenity or an independent challenger remains prospective.

## H. Evaluation-Proposition Resolution

The declared evaluation propositions are resolved against the retained evidence rather than inferred from the direction of a preferred result:

| Proposition | Current resolution | Evidence boundary |
|---|---|---|
| EP1 | Partially supported for selected paths | Executable tests cover selected control paths, but the historical 0/8 to 8/8 sequence changed evidence delivery, runtime behavior, and grading together. |
| EP2 | Descriptively supported in one Pilot; not confirmed | Shared-retrieval Team and staged Solo preserved the same observed milestones and evidence recall while Team was faster, but the result has one case, one repetition, non-random order, and heterogeneous model allocation. |
| EP3 | Descriptively supported in one Pilot; not confirmed | Shared retrieval reduced raw-Team tokens, frozen-price estimated cost, and unsupported numeric forms on one NVDA medium case; Stage 2 load-stratified confirmation has not run. |
| EP4 | Not tested by a retained primary financial artifact | The harness and deterministic tests implement fault injection, but r5 expected zero faults and no repeated formal fault run is retained. |
| EP5 | Supported only for selected deterministic invariants | Plugin tests exercise versioning, isolation, and alert invariants; r5 and the SEC runs perform zero finance-tool calls and zero ledger mutations. |
| EP6 | Partially supported descriptively; not confirmed | Raw-context replication increased tokens and frozen-price estimated cost without improving milestone completion in the Pilot, while other comparisons remain confounded by model allocation and task differences. |

These labels are `not tested`, `descriptively supported`, `partially supported`, or `supported only for a bounded layer`; none is a population-level confirmation. Stage 2 remains proposed/draft and may yield zero or negative Team effects.

## I. Required Validation Before External Claims

A validation experiment should freeze the current rubric, add an untouched holdout of at least 24 cases, execute all four baseline modes for at least three repetitions, and report case-level outputs, paired gains, uncertainty intervals, grounding, Team tokens, Team P50/P95 latency, and cost per successful Team case. It should separately compare no Skill, Serenity with the same data, and Serenity plus challenger.

The minimum reporting table should include, for every case and mode, evaluated attempts, errored attempts, strict successes, milestone success, missing evidence identifiers, forbidden assertions, every actually configured grader result, token count, latency, and estimated cost. A state-transition result is reported only when a state grader or deterministic mutation oracle is populated. Aggregate gain is reported only when both compared modes have evaluated attempts.

# VIII. DISCUSSION

## A. The Runtime as an Experimental Intervention

Agent evaluation is often framed as a comparison between models, but the observed output is produced by a coupled system. Prompt assembly determines which evidence is visible; the tool registry determines which actions are possible; the queue and cancellation model determine whether a plan completes; session repair determines whether the next provider call is valid; and the grader determines whether an equivalent answer is accepted. The runtime is therefore part of the experimental treatment rather than neutral infrastructure.

This observation explains why the same coordinator and specialist models can produce materially different results under two harness configurations. It also constrains interpretation: the historical sequence is consistent with improvement in the realized system, not increased latent model capability. Academic reporting should identify model, runtime, evidence, policy, and grader as separate experimental factors.

The regrading study provides direct evidence for this claim. No model was called, yet replaying old text through the current matcher changed four cells in r1 and one or two cells in three later runs. Likewise, the extended-inflection switch changes mode totals without changing a prompt, action, or answer. The measured object is therefore not merely the generated text; it is the ordered pair of retained trajectory and versioned oracle. A benchmark artifact that omits the oracle version is incomplete in the same way that a software test report without the tested revision is incomplete.

This framing changes what “runtime improvement” should mean. Lower latency is a runtime property only if provider load, model output length, and baseline call count are controlled. Higher success is a runtime property only if evidence and grader are controlled. Better attribution may result from a clearer specialist contract rather than a more capable specialist. The thesis consequently treats observability and replay as prerequisites for causal claims, not as supporting conveniences.

## B. When Multi-Agent Execution Is Justified

The financial scenarios show that multi-agent execution should be selective. A specialist is justified when it provides independent evidence interpretation, a parallel deep dive, a formal challenge, or a distinct policy perspective. It is not justified merely because a tool has a financial label. Market-data retrieval, ratio calculation, threshold comparison, fingerprinting, and state persistence are deterministic operations and should remain tools.

The `solo_open_book`, `solo_two_pass`, and routed-diagnostic baselines provide a practical decomposition. If Team does not exceed Open-Book, delegation adds overhead without detected outcome benefit. If Team does not exceed Two-Pass, additional synthesis compute rather than role specialization may explain the outcome. If the routed diagnostic exceeds Team, routing or specialist execution is a candidate bottleneck; if Team exceeds it, named roles, the diagnostic prompt, or direct evidence presentation may alter synthesis. The diagnostic is therefore a candidate comparison, not an oracle upper bound.

The contrast between the initial-observation and longitudinal SEC suites clarifies the role of task difficulty. The simple suite was saturated by all four modes and could not measure incremental accuracy. The longitudinal suite created mode-level failures, but the frozen Team and Open-Book rates remained equal. Difficulty is therefore a necessary condition for avoiding a ceiling effect, not sufficient evidence that collaboration adds value. The AMD failure further shows that a correctly routed specialist can still return no usable evidence; a multi-agent treatment includes availability, response validation, and retry policy as well as nominal role decomposition.

The retrieval-mediated Pilot further distinguishes role count from information flow descriptively. Shared-retrieval Team and staged Solo reached the same strict quality outcome, whereas raw-context Team missed the numeric-grounding threshold despite using the same coordinator, specialists, and one batch delegation. Shared retrieval generated a smaller specialist evidence packet, fewer unsupported numeric forms, lower wall-clock latency, and lower estimated cost than raw-context Team. This single-case pattern is consistent with selective retrieval and one-copy shared context being relevant mechanisms; it does not identify their causal contribution or show that adding agents is sufficient.

Case-level replay shows why one aggregate recommendation would be premature. Team achieved 4/4 on thesis invalidation versus 2/4 Open-Book and 3/4 on portfolio concentration versus 1/4. These cases require combining threshold evidence with a governance action and are consistent with the prespecified proposition that role separation may help. In contrast, Team achieved 0/4 on incomplete screening while Open-Book achieved 3/4, but the failure is traceable to `estimate` versus `estimated` rather than to an unsafe decision. A domain-adaptive router should therefore be evaluated against mechanism classes, not only a global mean.

Selective delegation is the practical implication. A coordinator can first classify whether the task requires independent evidence extraction, methodology application, or adversarial challenge. Deterministic data collection and state mutation remain tools. A specialist is admitted only when its information or role is expected to change a measurable decision. This admission rule converts multi-agent orchestration from a default architecture into a bounded experimental treatment.

## C. Financial Value Without Autonomous Trading

The application’s value proposition is research-process quality rather than direct return prediction. The system can reduce repeated data collection, expose missing fields, preserve thesis history, surface invalidation conditions, suppress duplicate alerts, and structure disagreement. These outputs are useful even when the final investment decision remains human.

This boundary is also methodologically useful. Return prediction introduces market regime, benchmark selection, turnover, transaction cost, corporate actions, survivorship, and look-ahead confounders. Workflow correctness can be evaluated first with deterministic evidence and state oracles. Predictive evaluation may then be added as a separate layer after the data pipeline satisfies point-in-time requirements.

The fixed-evidence finance experiment occupies an intentionally narrow position in that stack: it measures whether the coordinator reproduces supplied evidence and states a bounded governance decision. The retrieval track extends the boundary to source-locked archived SEC records, explicit evidence selection, specialist summaries, and final synthesis. It still does not measure live-web retrieval, semantic entailment, execution of the seventeen finance tools, persistent ledger mutation, or subsequent portfolio outcomes. This separation improves diagnosis while limiting product claims: neither a 5/6 fixed-fixture result nor a successful SEC retrieval pilot validates investment advice.

Return-based analysis should be added only after the data pipeline supports point-in-time constituent universes, dated `as_of` snapshots, corporate-action adjustment, delisting coverage, and explicit look-ahead prevention. It must remain separate from workflow correctness: a system can preserve evidence correctly without profitable forecasts, while a profitable backtest can still be invalid if it leaks future information.

## D. Quality–Cost Trade-off

The historical sequence indicates that poor coordination can dominate model cost. Duplicate delegation, unrestricted specialist tools, and recovery turns coincided with more than one million tokens across eight cases. The final bundle reduced this overhead while constraining capabilities and reusing evaluation-only duplicate results, but the sequence does not identify each mechanism’s causal share.

However, lower cost is not inherently better. The appropriate objective is the minimum cost that satisfies a fixed evidence and outcome standard. The frozen finance confirmation separates uncached prompt, cache-read, completion, provider total, latency, and cost. Team cost USD 0.008335, compared with USD 0.005510 for one-pass Open-Book and USD 0.017798 for Two-Pass, while all three passed 5/6 cases. Under billable-like token accounting Team used 41.6% fewer tokens than Two-Pass; under provider total accounting it used 33.7% more. This sign reversal shows why one undocumented token field cannot support an efficiency claim.

A practical deployment should optimize a Pareto surface rather than one scalar. The relevant dimensions include strict task outcome, configured attribution, latency percentile, priced cost, and infrastructure error rate. A mode is dominated only if another mode is no worse on every required dimension and better on at least one. With r5 point estimates, Open-Book is cheaper and faster than Team at the same pass count, whereas Team is cheaper and faster than Two-Pass at the same pass count. The post hoc case matrix suggests possible Team benefits on selected mechanisms, but the evidence is too weak to justify routing every request through specialists.

The retrieval pilot adds context allocation to this surface. Shared-retrieval Team and staged Solo have the same strict outcome, but the Team is faster and cheaper under heterogeneous model allocation while consuming more provider-total tokens. Shared-retrieval Team dominates raw-context Team on the observed strict outcome, grounding, latency, tokens, and cost, but only for one case. This pattern motivates a load-stratified confirmation rather than a universal Team default. A routing policy should admit retrieval and specialists when expected context reduction or parallel analysis exceeds coordination overhead.

## E. Generalizability

The architecture generalizes to domains that combine deterministic state with interpretive judgment, such as compliance review, incident response, customer operations, and scientific evidence synthesis. The financial scenarios are nevertheless domain specific. Thesis invalidation, portfolio concentration, and announcement deduplication encode assumptions that may not transfer directly to credit underwriting, high-frequency trading, or personal financial advice.

Generalization should therefore be tested at the mechanism level. Tenant isolation, bounded execution, tool-call pairing, correlated delegation, fault attribution, and evidence provenance are domain-independent mechanisms. The finance case oracles and research methodology are domain-specific configurations layered on top of them.

## F. Threats to Validity

TABLE_CAPTION: Principal threats to validity and mitigation status.

| Validity class | Threat | Consequence | Current mitigation or required action |
|:---|:---|:---|:---|
| Construct | Lexical matcher approximates semantic attribution | Correct inflections fail; hedged forbidden phrases pass | Preserve outputs, version grader, report ablation; validate entailment separately |
| Construct | r5 “state” grader observes prose, not mutation | Workflow wording can be mistaken for ledger correctness | Separate plugin tests from runtime text results |
| Construct | Fixed-evidence specialists copy compiled evidence verbatim | r5 does not measure retrieval or specialist evidence selection | Keep fixture and archived-SEC tracks separate; do not pool their claims |
| Construct | Numeric corpus membership approximates grounding | Supported-looking values may lack semantic entailment | Preserve claim/value diagnostics; add human-reviewed claim-to-evidence labels |
| Construct | Provider total includes cache reads inside prompt | Efficiency direction can reverse | Report billable-like and provider totals together |
| Internal | Historical runtime and grader changed together | 0/8→8/8 cannot be causally attributed | Report as regression sequence; execute cumulative ablation |
| Internal | r2–r5 pooling selected post hoc | Positive direction may reflect analysis choice | Keep r5 primary; label sensitivity analysis |
| Internal | Gain guard checks counts, not pair identifiers | Misaligned cases could produce invalid gain | Pair manually by case/repetition; add identifier guard |
| Internal | Retrieval Pilot modes were not randomized | Provider load, cache state, or order can confound latency | Seed and randomize mode order within case–repetition blocks |
| Internal | The researcher authored the runtime, suite, and deterministic graders | Design choices or post hoc interpretation may favor the artifact under study | Content-address artifacts; retain raw outputs; require two independent source/oracle reviewers; report disagreements and sensitivity analyses |
| External | Fixed suite has six cases; retrieval pilot has one executed case and one model family | Results may not transfer to other issuers, loads, or providers | Execute frozen 24-configuration matrix, then expand company–task clusters |
| External | No finance-tool calls in r5 | End-to-end application generalization is unsupported | Add retrieval-and-mutation integration suite |
| Conclusion | r5 has n=6; retrieval Pilot has n=1; both use one repetition | Modest paired effects and variance are not estimable | Three randomized repetitions and cluster-aware paired reporting |
| Conclusion | Graders and retrieval runtime were calibrated on earlier outputs | Final observations are not independent holdouts | Freeze suite, grader, runtime settings, and exclusions before Stage 2 |

The table makes the central limitation explicit: measurement and capability are entangled. The present evidence is strongest where executable tests define a transition and weakest where natural-language wording stands in for semantic or persistent state correctness. The recommended next experiment is therefore not simply “more cases.” It is a prespecified separation of evidence source, runtime policy, orchestration mode, and grader version.

# IX. SECURITY, ETHICS, LIMITATIONS, AND FUTURE WORK

## A. Security Controls

FastClaw applies defense in depth and treats risk management as a lifecycle activity rather than a single filter [14]:

- authenticated cookie or API-key ingress with tenant scope;
- agent ownership and API-key ACL checks on management, observability, and resolved OpenAI-compatible chat targets;
- a six-pattern prompt-injection heuristic before the agent loop and user-message isolation inside the provider payload;
- policy-filtered tool definitions;
- session-scoped sandbox executors with no silent host fallback;
- validated internal source and target ownership for sub-agent calls;
- bounded queues, timeouts, wait-graph cycle detection, and shutdown release;
- trusted plugin execution context and user-filtered financial state;
- optimistic version checks for concurrent thesis and alert updates.

These controls reduce risk but do not prove complete security. The prompt-injection scanner has no dedicated test coverage and is described as an unvalidated heuristic, not a security control with measured detection performance. XML isolation is an instruction boundary, not a cryptographic one; and a permissive policy still exposes powerful tools. Production deployment should use least-privilege presets, network allowlists, secret management, audit retention, parameter validation, human approval for destructive actions, and adversarial testing [13].

The API-key ACL defect identified during review illustrates complete mediation in practice. The former chat path checked explicit agent headers in middleware but could resolve an omitted header to an inaccessible fallback. The handler now authorizes the resolved target and returns 403 for an inaccessible fallback; an unknown explicit identifier returns 404 instead of falling through. Behavioral tests cover omitted, inaccessible, unknown, and permitted targets. The correction improves the current endpoint but does not remove the need to audit each new route.

## B. Financial Ethics and Human Oversight

FastClaw is a research assistant, not an investment adviser or execution engine. It may organize evidence, apply deterministic calculations, maintain a thesis record, and propose a reversible review action. It must not promise return, infer suitability, size a position for a client, or place an order. NIST AI RMF emphasizes explicit human roles and responsibilities for decisions and oversight [14]. In this application, a human remains accountable for accepting evidence, changing portfolio policy, and authorizing any irreversible external action.

Auditability does not eliminate responsibility. A trace can show which evidence identifier, policy preset, agent, model, and tool call contributed to an answer, but it does not certify that the evidence was licensed, complete, current, or fair. Real deployments must document data rights, retention, market-data terms, and whether generated commentary is shown to a client. Sensitive account or portfolio information must not be placed in model prompts or logs without an approved data-processing basis.

The fixed benchmark evidence is synthetic and avoids personal or client data. This reduces privacy risk but also removes realistic retrieval ambiguity. A future archived-data experiment should preserve publication time and source licenses, redact personal information, and separate research evaluation from any live portfolio workflow. Human reviewers should see evidence and proposed state changes before acceptance, not only a fluent final narrative.

## C. Current Limitations

First, the agent-level turn gate serializes all sessions of one agent because the registry stores mutable session-bound state. The TaskQueue can run different agents concurrently, but true per-session concurrency for one agent requires immutable per-turn registries or a per-session gate.

Second, session appends are individually persisted rather than committed as one transaction. Normalization repairs interrupted histories, but transactional batch append would provide a stronger consistency model. Store-backed reads can fail open to a stale in-memory session on store error, so cross-replica freshness is best effort rather than guaranteed.

Third, Skills are currently injected in full. Installing a large financial Skill library can consume context and distract the model. The existing `load_skill` helper is unreachable in production, and some Skill paths are prompt-visible without equivalent sandbox mounts. Progressive disclosure should initially expose only names and descriptions, then register and test on-demand loading for one to three selected methods.

Fourth, all retained real-runtime studies use one repetition. The historical study has eight cases and two unmatched evidence modes; the fixed-evidence confirmation has six cases and four matched modes; and the final retrieval pilot has one executed case across five modes. The retrieval suite defines 24 treatment configurations, but unexecuted configurations are not evidence and configurations sharing one company–task source set are not independent issuers. None of these tracks is an official benchmark or a population estimate. Earlier outputs informed both the fixed-evidence rubric and retrieval runtime, so the retained runs are confirmations after calibration rather than untouched holdouts.

Fifth, the configured attribution and numeric-grounding graders are lexical and local. The fixed-evidence matcher handles direction, negation, quotation, decimal punctuation, conditional scope, and conservative plural normalization, but rejects `estimated` for required `estimate` and exempts a forbidden phrase after `may`. The retrieval grader checks whether numeric forms are authorized by source records or declared calculations; it does not prove that the surrounding sentence is entailed. Claim-level evidence linking and human validation are required for broader factuality claims.

Sixth, SQLite WAL improves concurrent runtime behavior but changes backup semantics: the main database file is not a complete live backup while uncheckpointed changes remain in sidecars. Operational documentation and deployment automation must account for this.

Seventh, the financial layer lacks persistent portfolio holdings and policy limits, outbound alert delivery and retry state, and exchange-calendar-aware scheduling. It also lacks a point-in-time market data store suitable for unbiased backtesting. Finskills remains an external, unvendored dependency, and the Serenity hash manifest did not verify two documentation files.

Finally, r5 uses compiled, verbatim-copy specialist evidence, while the retrieval pilot uses archived SEC records and model-based evidence selection. Both execute zero finance-tool calls, zero ledger mutations, and zero injected faults. The combined evidence validates controlled orchestration and one archived-document retrieval path, not live source discovery, persistent workflow execution, or graceful degradation. Authorization should also be continuously audited across every API surface as the OpenAI-compatible API evolves.

## D. Future Work

The highest-priority engineering work is:

1. complete and freeze the proposed second-stage SEC protocol, then execute all 24 existing configurations with three seeded, randomized repetitions;
2. add claim-to-evidence links and separately validate rubric or semantic entailment judges against human labels while retaining deterministic state, policy, and evidence-identifier checks;
3. randomize mode order, preserve company–task cluster identifiers, and add a capacity-matched Team/Solo ablation before interpreting heterogeneous cost differences;
4. expand the SEC panel with JPMorgan Chase, Visa, PayPal, and Microsoft after the four-company matrix passes source and grader audit;
5. add in-flight budgets for model calls, tokens, cost, and latency;
6. aggregate identity revision, policy preset, and deduplication hits directly into the report;
7. bound wide specialist fan-out below the internal bus backpressure limit;
8. introduce immutable per-turn registries and per-session concurrency;
9. add transactional session append, progressive Skill loading, portfolio policy state, alert delivery adapters, and exchange calendars;
10. build point-in-time financial datasets before evaluating returns.

# X. CONCLUSION

This thesis treated an LLM agent as a controlled software runtime rather than a prompt wrapper. FastClaw turns a reasoning–action loop into an authenticated, tenant-scoped, stateful, streaming execution system. Its principal mechanisms are a per-chat FIFO TaskQueue with bounded root admission, a correlated MessageBus with transitive wait-graph cycle prevention, a policy-filtered tool registry, a terminally consistent turn emitter, session normalization, fail-closed required identity loading, request-scoped evaluation tools, and per-call role, token, cost, and latency attribution. The implementation also demonstrates why these mechanisms require explicit invariants: every assistant tool call must receive one result, every protected target must be authorized after resolution, and every waiting sub-agent lane must preserve an acyclic graph.

VP1 is satisfied only for selected tested control paths. Focused unit and integration tests execute authentication, provider parsing, cancellation, tool panic containment, internal calls, task snapshots, storage contention, evaluation reporting, and the corrected OpenAI-compatible ACL path. They show that these selected mechanisms are executable and that several previously silent failures are observable. They do not provide formal verification, exhaustive path coverage, or production assurance. Statement coverage is approximately 27.2% for the runtime and production packages, or 28.4% when the report's own analysis program is included. Important packages such as policy, scope, session, plugin, MCP, and Skills have no measured test coverage in that profile.

RQ2 remains not determinable as an accuracy claim. In the primary six-case confirmation, Team, Open-Book, and Two-Pass each passed 5/6 cases. A zero-point difference at one repetition does not establish equivalence. Post hoc replay produces a positive but unsupported Team direction, while the incomplete-screening case shows that one morphology defect can reverse a mode comparison. The longitudinal SEC extension again produced equal Team and evidence-matched Open-Book totals. In the retrieval pilot, shared-retrieval Team and staged Solo both passed all milestones and retained every gold evidence group. Across three designs, no result establishes that multiple agents intrinsically improve financial answer accuracy.

RQ3 has only descriptive evidence. In r5, Team had higher frozen-price estimated cost than one-pass Open-Book and lower estimated cost than Pro-only Two-Pass, while billable-like versus provider-total token definitions produced opposite directional comparisons. In the single-case retrieval Pilot, shared-retrieval Team and staged Solo reached the same strict outcome; the Team observation had 36.32% lower latency and 42.06% lower estimated cost but 13.63% more provider-total tokens under heterogeneous allocation. Against raw-context Team, shared retrieval was associated with 14.15% lower latency, 38.42% fewer tokens, 47.62% lower estimated cost, and a 3.40-percentage-point grounding difference. These observations are consistent with a limited latency–cost–grounding difference, but non-random order, provider variability, one repetition, and heterogeneous allocation prevent a causal or general Pareto claim.

Prospective RQ4 is not an executed empirical question. FastClaw implements simulated, request-scoped fault injection, error-aware denominators, fault observation and attribution, unsupported-claim checks, and graceful-degradation metrics. However, r5 has `faults_expected=0`; its zero fault rates are empty values rather than evidence of robust coordinator behavior. A repeated retained fault suite remains required.

VP2 is satisfied only for selected deterministic invariants. Plugin tests exercise tenant-isolated theses, optimistic versioning, immutable reviews, watchlist filtering, and alert deduplication. The fixed-evidence runtime experiment supports controlled routing and governance wording but not retrieval. The SEC Pilot supports archived-record selection, evidence compression, specialist analysis, and bounded synthesis for one case. Neither model experiment invokes finance tools or mutates the ledger. The evidence therefore does not validate a complete live financial-research transaction.

The principal contribution is consequently a measurement-oriented, auditable agent runtime and an inconclusive accuracy result: no incremental Team effect was detected at the present resolution. FastClaw makes runtime policy, evidence visibility, execution errors, role-specific frozen-price estimated cost, and grader behavior inspectable. The analysis can change a lexical feature and replay retained outputs without purchasing another model call, exposing how much of an apparent capability result belongs to the oracle. This is stronger evidence for auditability than for financial intelligence.

Future work should complete and freeze the proposed second-stage protocol before executing it across the existing 24 SEC configurations with three seeded repetitions, randomized mode order, preserved company–task cluster identifiers, and paired cluster-bootstrap reporting. It should then expand the issuer panel and run a capacity-matched Team/Solo ablation. A separate mutation track should invoke deterministic finance tools, write versioned ledger state, and use human-reviewed claim-to-evidence links. Return-based evaluation should remain separate until the dataset controls publication time, constituent membership, corporate actions, delisting, turnover, and transaction costs. Until those conditions are met, FastClaw should be presented as a research copilot and runtime evaluation platform—not an autonomous adviser, an official benchmark submission, or evidence of investment performance.

# APPENDIX A. FINANCIAL CASE ACCEPTANCE CHECKLIST

The following checklist converts the six financial scenarios into auditable acceptance conditions.

TABLE_CAPTION: Case-level evidence, state, and policy acceptance conditions.

| Case | Evidence checks | Governance wording checks | Policy checks |
|---|---|---|---|
| Earnings catalyst | Filing ID, date, 18% growth, and 220-bp margin expansion retained | Review references thesis version 4; conviction 3→4; active status | No trade authorization |
| Thesis invalidation | Customer C-17, 31% revenue share, and 25% threshold retained | Decision `invalidate`; expected version 2; invalidated status | No unsupported target price |
| Duplicate event | External event ID and 24-hour window retained | Existing alert reused; duplicate count 1→2; `last_seen_at` updated | Thesis review executed once |
| Incomplete screen | Observed PE/ROE separated from missing free-cash-flow and leverage fields | Candidate excluded with `insufficient_data` | No imputation from model knowledge |
| Portfolio concentration | 62% sector weight, 0.89 correlation, 17% stress loss, and 10% limit retained | Proposed exposure target below 45%; checks scheduled again | No return guarantee; no automatic execution |
| Contradictory evidence | Both dated primary-source claims retained | `needs_review`; conviction unchanged | No convenient-source selection; clarification requested |

For each attempt, failure classification should identify one primary layer: evidence retrieval, deterministic calculation, tool routing, specialist execution, coordinator synthesis, state persistence, policy compliance, or infrastructure. This classification prevents all unsuccessful outputs from being grouped under a generic “model failure.”

# APPENDIX B. REPRODUCIBILITY CHECKLIST

Before execution:

1. freeze the suite, source lock, evidence fixtures, graders, randomization seed, timeout, and repetition count;
2. record coordinator and specialist model names and provider endpoint class;
3. record baseline modes, execution mode, pricing table date, Skill condition, and tool policy;
4. verify that each mode uses an independent session and the same relevant evidence;
5. verify that no baseline begins with cached conversation history;
6. record company–task cluster identifiers and the planned pair key.

The repository-level evidence entrypoint is `evals/thesis-evidence-manifest.json`.
It separates confirmatory, descriptive-Pilot, and proposed artifacts and hashes the
suite, source lock, raw report, analysis, summary, grader/analysis source, and
sub-manifest chain. From a clean checkout, run
`python3 evals/finance_e2e/thesis_evidence_manifest.py --check`. A missing file,
hash drift, stale generated manifest, or confirmatory-status mixing fails the
check. This supports offline reconstruction and regrading of retained outputs;
it does not claim exact regeneration of historical stochastic provider trajectories.

During execution:

1. retain case, repetition, mode, session identifier, and root execution identifier;
2. retain model-call role, call path, token usage, cache usage, latency, and error state;
3. retain tool-call identifiers, tool results, delegation targets, and fault observations;
4. distinguish model/tool failure from timeout, transport, authentication, or provider failure;
5. retain the realized randomized mode order;
6. stop the run if sources, evidence fixtures, graders, model aliases, or pricing change.

After execution:

1. report evaluated and errored attempts separately;
2. report raw counts with rates and confidence intervals where repetition permits;
3. calculate only the track-specific predeclared paired effects;
4. report Team-only latency and tokens in addition to full-harness totals;
5. disclose simulated specialists, fault injection, omitted cases, reruns, and pricing assumptions;
6. use company–task cluster-aware intervals for retrieval configurations;
7. archive machine-readable results together with a human-readable failure analysis.

# APPENDIX C. R5 REPRODUCTION RECORD

TABLE_CAPTION: Recorded configuration for the primary financial confirmation.

| Item | Recorded value |
|:---|:---|
| Suite | `evals/multiagent-finance-runtime.yaml` |
| Suite SHA-256 | `4fbf54eca61dc7363342ea1db364cb84426e1541937a99c1e1266dbfb3e5dc44` |
| Artifact | `finance-runtime-formal-r5.json` |
| Artifact SHA-256 | `5366a91398ca575d303af56d62da179f2a3f1fb13a1d0f5aae5c1773debfbc00` |
| Baselines | `solo_open_book`, `solo_two_pass`, `team`, `oracle_team` |
| Repetitions | Suite default 3; actual CLI override 1 |
| Timeout / execution | 10 minutes / real runtime |
| Case filter | None; all six cases |
| Coordinator | `bench-coordinator`, `deepseek/deepseek-v4-pro` |
| Specialists | Three agents, `deepseek/deepseek-v4-flash` |
| Endpoint class | OpenAI-compatible chat-completions API through local Gateway |
| Pricing date | 1 August 2026 |
| Go toolchain | `go1.26.4 darwin/arm64` |

The complete secret-free command and critical source-file hashes are in `evals/finance-runtime-formal-r5.manifest.json`. The executable source changed during calibration, and the complete local patch was not archived when r5 was produced. Therefore a reader can verify suite and artifact integrity, replay the current grader over retained outputs, and reproduce the analysis tables, but cannot regenerate exactly the same provider trajectories from the retained manifest alone. This limitation is retained rather than replaced with a false reproducibility claim.

The benchmark evidence is a compiled lookup table, specialists are instructed to copy the matching line, and r5 contains eighteen `spawn_subagent` calls but no finance-tool call. Finskills is external and unvendored. The API credential is intentionally excluded from every report and manifest.

# APPENDIX D. STAGE 2 PRE-EXECUTION PROTOCOL RECORD

Stage 2 is not a completed result. This appendix records the analysis decisions that must be frozen before the first formal provider request. The complete operational protocol is stored in `evals/finance_e2e/STAGE2-EXPERIMENT-PROTOCOL.md`.

TABLE_CAPTION: Pre-execution design record for the retrieval-mediated Stage 2 study.

| Item | Prespecified design |
|:---|:---|
| Status | Draft until the freeze checklist passes; immutable after first formal request |
| Stage 2A panel | NVIDIA, AMD, Intel, and NIKE |
| Task and load matrix | Point-in-time and longitudinal × small, medium, and large context |
| Configurations / analysis clusters | 24 treatment configurations / 8 company–task analysis clusters |
| Observation ID | `(company, task_family, corpus_load, repetition, mode)` |
| Pair key | `(company, task_family, corpus_load, repetition)`; mode is excluded |
| Counts | 72 case–repetition blocks; 216 primary observations; 48 diagnostics; 24 ablation observations; 288 total |
| Primary modes | `solo_staged`, `team_shared_retrieval`, `team_raw_context` |
| Repetitions | Three per primary mode and configuration |
| Diagnostics | `solo_monolithic` and `oracle_evidence`, once per configuration |
| Randomization | Seed `20260802`; randomized primary-mode order within each case–repetition block |
| Quality floors | 95% numeric grounding; 90% final evidence recall; 75% retrieval recall and summary retention |
| Primary comparisons | Shared Team versus staged Solo; shared Team versus raw-context Team |
| Dependence correction | Pair within configuration; bootstrap company–task clusters; report load interactions |
| Capacity ablation | All-Pro shared Team on eight prespecified medium-longitudinal and large-point configurations |
| Point-in-time gate | Record `as_of_timestamp`; verify every included `accepted_at <= as_of_timestamp`; list later excluded filings |
| Human audit | Two reviewers on prespecified outputs; supported, derived, unsupported, or not assessable claims |
| Resource gate | Pause at USD 10 or twelve serial hours pending review |
| Invalidation | Any source, suite, grader, model-alias, pricing, or treatment change creates a new study version |

The 24 configurations must not be reported as 24 independent issuers, and the eight company–task analysis clusters are not asserted to be strictly independent population draws. Diagnostics and the separately reported all-Pro ablation do not enter the primary analysis. Stage 2 remains proposed/draft until the two-reviewer 98-item source/oracle audit is complete and every non-PASS item is adjudicated. Stage 2B adds JPMorgan Chase, Visa, PayPal, and Microsoft only after source and oracle audit, increasing business-model diversity without changing the frozen Stage 2A result.

# REFERENCES

[1] S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan, and Y. Cao, “ReAct: Synergizing reasoning and acting in language models,” in Proc. Int. Conf. Learn. Representations (ICLR), 2023. [Online]. Available: https://openreview.net/forum?id=WE_vluYUL-X

[2] Model Context Protocol, “Specification, protocol revision 2026-07-28,” Jul. 2026. [Online]. Available: https://modelcontextprotocol.io/specification/2026-07-28. Accessed: Aug. 1, 2026.

[3] JSON-RPC Working Group, “JSON-RPC 2.0 Specification,” origin Mar. 2010, updated Jan. 2013. [Online]. Available: https://www.jsonrpc.org/specification. Accessed: Aug. 1, 2026.

[4] S. G. Patil, H. Mao, F. Yan, C. C.-J. Ji, V. Suresh, I. Stoica, and J. E. Gonzalez, “The Berkeley Function Calling Leaderboard (BFCL): From tool use to agentic evaluation of large language models,” in Proc. 42nd Int. Conf. Machine Learning, PMLR, vol. 267, pp. 48371–48392, 2025. [Online]. Available: https://proceedings.mlr.press/v267/patil25a.html

[5] S. Yao, N. Shinn, P. Razavi, and K. Narasimhan, “τ-bench: A benchmark for tool-agent-user interaction in real-world domains,” in Proc. Int. Conf. Learn. Representations (ICLR), 2025. [Online]. Available: https://openreview.net/forum?id=roNSXZpUDN

[6] C. E. Jimenez, J. Yang, A. Wettig, S. Yao, K. Pei, O. Press, and K. Narasimhan, “SWE-bench: Can language models resolve real-world GitHub issues?” in Proc. Int. Conf. Learn. Representations (ICLR), 2024. [Online]. Available: https://openreview.net/forum?id=VTF8yNQM66

[7] K. Zhu et al., “MultiAgentBench: Evaluating the collaboration and competition of LLM agents,” in Proc. 63rd Annu. Meeting Assoc. Comput. Linguistics, Vienna, Austria, pp. 8580–8622, Jul. 2025, doi: 10.18653/v1/2025.acl-long.421.

[8] Z. Chen et al., “FinQA: A dataset of numerical reasoning over financial data,” in Proc. Conf. Empirical Methods Natural Language Processing, pp. 3697–3711, 2021, doi: 10.18653/v1/2021.emnlp-main.300.

[9] F. Zhu, W. Lei, Y. Huang, C. Wang, S. Zhang, J. Lv, F. Feng, and T.-S. Chua, “TAT-QA: A question answering benchmark on a hybrid of tabular and textual content in finance,” in Proc. 59th Annu. Meeting Assoc. Comput. Linguistics and 11th Int. Joint Conf. Natural Language Processing, pp. 3277–3287, 2021, doi: 10.18653/v1/2021.acl-long.254.

[10] H. Rashkin, D. Reitter, G. S. Tomar, and D. Das, “Increasing faithfulness in knowledge-grounded dialogue with controllable features,” in Proc. 59th Annu. Meeting Assoc. Comput. Linguistics and 11th Int. Joint Conf. Natural Language Processing, pp. 704–718, 2021. [Online]. Available: https://aclanthology.org/2021.acl-long.58/

[11] Basel Committee on Banking Supervision, “Principles for effective risk data aggregation and risk reporting,” Bank for International Settlements, Jan. 9, 2013. [Online]. Available: https://www.bis.org/publ/bcbs239.htm

[12] J. H. Saltzer and M. D. Schroeder, “The protection of information in computer systems,” Proc. IEEE, vol. 63, no. 9, pp. 1278–1308, Sep. 1975.

[13] OWASP Foundation, “AI Agent Security Cheat Sheet,” OWASP Cheat Sheet Series, 2026. [Online]. Available: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html. Accessed: Aug. 1, 2026.

[14] National Institute of Standards and Technology, “Artificial Intelligence Risk Management Framework (AI RMF 1.0),” NIST AI 100-1, Jan. 2023, doi: 10.6028/NIST.AI.100-1.

[15] E. B. Wilson, “Probable inference, the law of succession, and statistical inference,” J. Amer. Statist. Assoc., vol. 22, no. 158, pp. 209–212, 1927.

[16] Q. McNemar, “Note on the sampling error of the difference between correlated proportions or percentages,” Psychometrika, vol. 12, no. 2, pp. 153–157, Jun. 1947, doi: 10.1007/BF02295996.

[17] B. Efron, “Bootstrap methods: Another look at the jackknife,” Ann. Statist., vol. 7, no. 1, pp. 1–26, Jan. 1979, doi: 10.1214/aos/1176344552.
