TITLE: Design and Evaluation of an Auditable Agent Runtime
AUTHOR: Zheyu Wang
AFFILIATION: Faculty of Science and Technology, University of Macau
EMAIL: mc45505@um.edu.mo
REPORT DATE: October 2026

ABSTRACT: Large-language-model agents are increasingly deployed as services rather than single prompts, yet evaluations often attribute outcomes to the model while treating the runtime as neutral infrastructure. This report designs and evaluates an auditable, multi-tenant Go agent runtime that supports both staged single-agent execution and optional coordinator–specialist delegation. The runtime combines authenticated ingress, tenant-scoped state, bounded streaming turns, per-chat FIFO scheduling, root-level admission, policy-filtered tools, cancellation, cycle prevention, and role-specific telemetry. Evaluation combines executable control-path tests with repeated, source-locked workloads and a matched-model comparison of Solo and Team execution. The experiments show a configuration-dependent trade-off: Team reduced end-to-end latency in the matched comparison, whereas Solo attained higher strict completion; neither mode was best on every measured outcome. The principal contribution is an inspectable execution and evaluation framework, not a claim of superior reasoning, complete domain-level factual correctness, or production-level reliability.

INDEX TERMS: LLM agents, agent runtime, multi-agent systems, tool calling, context allocation, evidence retrieval, evaluation harness, tenant isolation, observability.
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

1. **Auditable runtime artifact:** The implemented agent runtime provides authenticated ingress, bounded streaming turns, policy-filtered tools, correlated coordinator–specialist request/reply, tenant-scoped state, cancellation, and role-level telemetry as an inspectable Go artifact.
2. **Measurement method:** the evaluation separates evidence visibility, planning opportunity, orchestration, model allocation, runtime failure, context allocation, and grader behavior, while retaining content-addressed artifacts for offline replay.
3. **Execution-mode evidence:** a source-locked, repeated SEC study and a separate all-Flash matched comparison expose the completion, latency, evidence-retention, and resource trade-offs between staged Solo and shared-retrieval Team execution. Neither mode is asserted to be universally superior.

The central research question is not whether a stronger model can improve a score or whether Team must outperform Solo. It is whether one engineered runtime can support both execution paths with observable, bounded behavior, and what each path trades in completion, latency, evidence retention, and resources. The fixed-evidence study holds evidence visibility constant; the source-locked SEC study tests multiple execution topologies under a declared heterogeneous deployment; and the separate all-Flash comparison reduces model-allocation confounding for the Team/Solo contrast. These results characterize the tested configurations, not a universal causal runtime effect across providers or domains.

# II. BACKGROUND AND DESIGN REQUIREMENTS

## A. From Tool Calling to an Agent Runtime

In structured tool calling, the model receives a list of functions with names, descriptions, and JSON schemas. It can either return natural-language content or emit one or more typed function calls. The application validates and executes those calls, appends each result to the conversation, and requests the next model step. This separates probabilistic planning from deterministic execution. The 28 July 2026 revision of the Model Context Protocol (MCP) standardizes hosts, clients, servers, resources, prompts, and model-controlled tools over a JSON-RPC 2.0 data layer [2], [3]. MCP defines an interoperability boundary; it does not define an application’s authorization policy, persistence model, queueing discipline, or experimental protocol. Those remain runtime responsibilities.

BFCL evaluates function selection, parameter construction, parallel calls, abstention, and stateful multi-step behavior with scalable structural comparison [4]. Its strength is that a tool call has a relatively objective representation. The limitation for runtime research is equally important: a correct call does not reveal whether a queue dropped work, whether a stream exposed an error, whether two tenants shared state, or whether the same model would behave differently under another capability policy. This project therefore uses BFCL-style cases as protocol checks rather than reporting an official BFCL score.

A runtime adds controls not supplied by the model: provider adaptation, session ordering, capability policy, sandbox binding, timeouts, telemetry, and terminal consistency. The proposed system treats the LLM as a planning component inside this larger state machine rather than as the owner of execution.

## B. Stateful and Multi-Agent Evaluation

Single-turn function accuracy is necessary but insufficient. τ-bench evaluates multi-turn interaction among an agent, a user model, domain policy, and database tools [5]. Its policy-constrained trajectories demonstrate why the terminal answer alone is not enough: two agents may reach similar text through different, policy-relevant actions. SWE-bench evaluates repository issue resolution by applying patches and running repository tests [6], making the environment and executable oracle part of the benchmark. MultiAgentBench measures task milestones and communication structures across collaboration and competition scenarios [7]. These benchmarks progressively add state, environment, and coordination, but they still evaluate a model or agent system inside a chosen harness. They do not ordinarily treat queue semantics, cancellation propagation, tenant scope, event-stream convergence, or grader normalization as independent variables.

This omission defines the research gap addressed here. Agent scores are jointly produced by at least five factors: model parameters, visible evidence, available actions, runtime transition rules, and the outcome oracle. Changing any one can alter the observed score. A team can appear better than Solo because specialists see private evidence; a baseline timeout can appear as an inability; a negated forbidden phrase can become a false violation; and cached prompt tokens can change an efficiency comparison depending on accounting convention. A runtime benchmark must therefore expose these factors, preserve pair identifiers, separate execution errors from evaluated failures, and retain raw outputs for regrading.

This project does not claim official scores on BFCL, τ-bench, SWE-bench, or MultiAgentBench. It implements small style subsets that exercise analogous runtime abilities under deterministic local conditions. The contribution is not a competing universal benchmark. It is an instrument for testing whether the harness itself preserves the preconditions under which a model score can be interpreted.

## C. Financial Research Requirements

Financial question-answering datasets such as FinQA [8] and TAT-QA [9] demonstrate the difficulty of numerical reasoning across narrative and tabular evidence. They primarily evaluate answer derivation from supplied documents. A deployable financial research assistant additionally requires temporal provenance, missingness semantics, persistent hypotheses, duplicate-event identity, and a boundary between research and portfolio action. The present project does not reproduce the official FinQA or TAT-QA evaluations. Instead, it derives system requirements relevant to a deployable research copilot:

- source-aware data with freshness and completeness metadata;
- deterministic calculation for screening, risk, and event identity;
- explicit uncertainty when evidence conflicts or is incomplete;
- persistent, tenant-scoped research state;
- human approval before portfolio action;
- repeatable evaluation that does not use future returns as a convenient but misleading ground truth.

The report uses **evidence attribution** to mean that a material output claim is linked to a supplied evidence identifier. This is narrower than factual truth or semantic entailment. Work on faithful knowledge-grounded generation distinguishes fidelity to supplied evidence from fluency and subjectivity [10]; accordingly, the evaluation's lexical checks are described as configured attribution checks, not as proof that every generated sentence is true. BCBS 239 motivates accurate, complete, timely, and traceable risk-data aggregation at an institutional level [11], but it does not prescribe the implementation's `observed_at`, `as_of`, or `source_id` fields. Those fields are an engineering operationalization inspired by provenance requirements rather than a direct implementation of the banking standard.

## D. Engineering Requirements

The resulting runtime requirements are:

1. **Isolation:** every request resolves to a real user, an authorized agent, a session, and a bounded workspace.
2. **Correctness:** assistant tool calls and tool results must remain correctly paired in persisted history.
3. **Control:** tools are filtered by policy, sandbox execution must not silently fall back to the host, and evaluation-only behavior must not affect production requests.
4. **Liveness:** cancellation, timeouts, bounded queues, and loop detection prevent requests from waiting indefinitely.
5. **Observability:** model calls, tool traces, call paths, token usage, latency, and estimated cost must be attributable to coordinator and specialist roles.
6. **Evaluability:** Team/Solo comparisons must control evidence visibility, and infrastructure errors must not be counted as model failures.

## E. Validity Preconditions and Empirical Questions

The study uses two validity preconditions and two primary empirical questions.

1. **VP1—Selected runtime control paths:** Do executable tests support the specific tenant-scope, tool-call ordering, terminal-streaming, cancellation, and bounded-execution paths used by the experiments?
2. **RQ2—Execution-mode trade-offs:** Across fixed-evidence and retrieval-mediated conditions, how do coordinator–specialist Team and evidence-matched staged Solo differ in deterministic completion, evidence retention, latency, and resource use?
3. **RQ3—Context allocation and efficiency:** Under a fixed task and source snapshot, how do monolithic, staged, shared-retrieval, and raw-context execution trade grounding, token consumption, latency, and estimated cost, and which contrasts also hold model allocation fixed?
4. **VP2—Selected financial-workflow invariants:** Do deterministic tests support the specific provenance, completeness, version-transition, alert-identity, and human-decision boundaries exercised by the evaluation fixtures?

VP1 and VP2 are validity preconditions supported only for selected tested paths and invariants; they are not empirical claims of production reliability or complete workflow validity. RQ2 and RQ3 are the primary empirical questions. None of the model experiments executes a live portfolio action.

TABLE_CAPTION: Mapping from validity preconditions and empirical questions to evaluation propositions, estimands, evidence, and present status.

| Question | Related propositions | Operational estimand | Primary evidence | Present status |
|---|---|---|---|---|
| VP1 | EP1 | Correct terminal state, scope, cancellation, and bounded execution on selected paths | Go unit/integration tests | Partially supported for selected paths; not production assurance |
| RQ2 | EP2 | Paired Team–Solo completion, evidence retention, latency, and resource use | Fixed-evidence studies, 24-configuration SEC study, and 24-pair all-Flash comparison | Mode-specific trade-offs observed; no universal winner |
| RQ3 | EP3, EP6 | Grounding, tokens, latency, and frozen-price estimated cost by context topology | Five-mode SEC reports and per-call usage traces | Repeated, configuration-bounded evidence; model allocation differs in the main study |
| VP2 | EP5 | Selected provenance and deterministic ledger invariants | Plugin tests and source/oracle records | Supported only for selected deterministic invariants |

## F. Threat Model and Design Principles

The protected assets are tenant identity, API credentials, conversation history, agent identity files, workspace objects, plugin-managed financial state, and the authority to execute tools. Trust boundaries occur at HTTP and channel ingress, provider responses, model-generated tool arguments, external tool and MCP results, plugin subprocesses, sandbox exits, store adapters, and internal sub-agent messages. The model and all retrieved content are treated as untrusted planners or data, not as authorization principals.

The principal abuse cases are: an unauthenticated or under-authorized caller selecting another agent; a model invoking a capability outside its policy; a plugin trusting model-supplied tenant identifiers; an indirect prompt injection propagating from evidence into a privileged tool call; a sub-agent cycle exhausting concurrency; a malformed provider stream producing a false successful terminal event; a stale or partial session corrupting subsequent tool-call order; and a long-running or repeatedly delegated task exhausting cost or queue capacity. The system is not designed to resist a compromised host operating system, a malicious database administrator, or a provider that deliberately violates its API contract.

The design follows fail-safe defaults, complete mediation, and least privilege as classical protection principles [12]. Every protected ingress must resolve an identity; agent selection is checked after default resolution; policy removes denied tools before the model sees them; trusted user scope is carried outside model-controlled arguments; and sandbox startup failure does not silently enable host execution. OWASP guidance for agent systems similarly recommends per-tool authorization, untrusted-data separation, bounded tool chains, structured audit records, and human approval for high-impact actions [13]. The implementation's six-pattern prompt scanner is only an unvalidated heuristic layer. It cannot substitute for authorization, policy filtering, parameter validation, or human review.

Residual risks remain. Session reads currently fail open to an in-memory copy if the durable store returns an error, whereas required identity loading fails closed. These are different consistency policies and must not be described as one guarantee. API-key ACL checks are implemented for resolved OpenAI-compatible chat targets, but future endpoints still require complete-mediation regression tests. Native plugins and local MCP servers inherit subprocess and supply-chain risk; policy can reduce exposed tools but cannot prove that an allowed tool is benign. These limitations are revisited in Section IX.

# III. AGENT RUNTIME SYSTEM ARCHITECTURE

## A. Layered Architecture

The system is a Go-based, multi-user agent platform. The default executable starts the Gateway, database-backed store, workspace object store, plugin manager, task queue, channel manager, cron scheduler, setup/API server, and the embedded web interface. User spaces and agents are loaded lazily after authentication rather than preloading every tenant at startup.

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

All protected HTTP routes pass through the authentication resolver. The web UI uses a database-backed, HTTP-only session cookie. Programmatic callers use Bearer API keys stored as hashes; plaintext is shown only when a key is created or rotated. The resolved identity carries the user, role, authentication method, and API key’s authorized agents. Agent authorization occurs after the OpenAI-compatible endpoint resolves an explicit or fallback target, so omitting the agent header cannot bypass an API key allowlist; an unknown explicit target is not silently replaced by a fallback. A super administrator may inspect another user through read-only delegated scope, but mutation is rejected.

The Gateway does not invent a default tenant. Channel messages either carry a trusted owner from cron or webhook execution, or resolve ownership from a stored channel credential. If ownership cannot be established, the message is dropped. This fail-closed rule is important because a convenient “local user” fallback would convert an authentication failure into cross-tenant data exposure.

User configuration is layered by scope. System defaults, user-level settings, and agent-level overrides are merged when a `UserSpace` is loaded. The manager creates agents with a tenant-specific session store, memory adapter, workspace store, policy, provider, Skills configuration, and plugin tools.

## C. MessageBus and TaskQueue

External messages enter buffered channels in a normalized format. The TaskQueue creates a FIFO channel for each chat key and a goroutine that drains that queue serially. A counting semaphore limits independent root executions across the process. Each task records its state, timestamps, result, owner, agent, and observability metadata. Execution is bounded by the queue-wide timeout and request cancellation rather than an independent task deadline.

Internal sub-agent work inherits the root execution identifier. It does not acquire a second global semaphore slot, which prevents a coordinator from deadlocking when the configured maximum concurrency is one. Two independent bounds apply: the TaskQueue owns a 256-slot internal admission channel, and the MessageBus owns a separate 256 pending-correlation cap. They protect different resources and must be tuned together. The local completion callback is published at most once, but model calls, external side effects, and network delivery are not guaranteed to occur exactly once [20]. Internal tasks retain request metadata while rebuilding cancellation links to both the request and queue shutdown [19]. Retaining only the original cancellation chain could end nested telemetry too early; detaching it without new links would leave internal work running after its parent stops.

Recent task views return defensive snapshots rather than live pointers. The API authenticates the caller, filters tasks by accessible agent, and only then applies the response limit. This prevents ordinary callers from observing unauthorized task metadata and avoids concurrent reads of mutable task fields; a super administrator intentionally retains broader read access, including read-only `actAs` inspection.

A counting semaphore was selected instead of a fixed worker pool because root-turn durations vary with provider latency and tool fan-out. A small worker pool would add head-of-line blocking between unrelated chat lanes, whereas a semaphore admits one independent goroutine per root up to the configured bound. Channels and mutexes provide the synchronization edges required by the Go memory model; mutable task maps and wait-graph state are not assumed to become visible merely because goroutines happen to run in sequence [18]. Alternative designs include bounded workers or weighted admission. The present design favors direct cancellation propagation and per-chat ordering over centralized worker lifecycle management.

## D. Provider Abstraction and Streaming

The provider interface supports both complete-response and streaming calls. OpenAI-compatible and Anthropic adapters convert runtime messages and tools into provider-specific wire formats. Their retained raw material is not equivalent: the OpenAI-compatible path reconstructs an assistant payload from streamed fragments, while the Anthropic path retains a thinking block when present rather than a complete assistant message. These records can assist caching and replay, but they are not a lossless cross-provider wire contract.

The streaming reader accumulates text, tool-call fragments, reasoning, signatures, and usage before publishing a terminal response. OpenAI-compatible requests ask for streaming usage and fall back when an endpoint rejects that option; Anthropic usage is assembled from streamed lifecycle events. The application distinguishes incremental content, convergent full snapshots, errors, and a terminal completion event. Deltas are opportunistic UI updates; the latest versioned snapshot is authoritative if a client misses one. A required-identity failure reaches streaming clients as an error, and a failed or cancelled stream cannot close with a false success event.

## E. Tools, Plugins, MCP, and Skills

The runtime uses one registry abstraction for tool definitions and executable functions. The built-in registry includes shell execution, file operations, messaging, memory search, and web fetching, with optional provider-backed web search, image generation, and text-to-speech. MCP servers can contribute tools to the same registry. Native plugins run as subprocesses that communicate through JSON-RPC 2.0 [3] over standard input/output and can provide tools, channels, providers, or hooks.

The plugin protocol carries trusted user, agent, and session identities. The runtime creates this scope after routing, outside model-controlled tool arguments. A stateful plugin can therefore reject calls without trusted context and query data by the authenticated tenant.

Skills are reusable instruction and workflow packages stored in layered directories. Five path classes are effective in the current loader: agent, team, user, managed, and extra; the nominal bundled collection is presently empty. The loader applies operating-system, binary, and environment gates and injects configured environment variables. Only two fixed Skill roots are mounted into sandbox paths; team and extra paths can enter the prompt without equivalent filesystem mounts. The current implementation injects every enabled Skill in full. An on-demand loading helper exists in source code but is not connected to the production registry, so progressive disclosure is not yet an available runtime capability. Skills describe methods, while tools perform atomic execution. The financial design in Section V therefore keeps deterministic data retrieval in tools and research methodology in Skills.

## F. Persistence and Workspace Storage

The database is mandatory. SQLite with write-ahead logging is the zero-configuration default. PostgreSQL dialect branches are implemented as an intended deployment path, but they are not exercised by the current automated test suite and therefore are not claimed as production-verified. SQLite connections enable foreign keys, a five-second busy timeout, and immediate write transactions unless equivalent settings are already present. Immediate transactions address the read-then-write upgrade pattern in session persistence; a busy timeout alone cannot reliably recover that shape. WAL permits readers and one writer to proceed concurrently but retains a single-writer boundary and requires explicit checkpoint operation at larger loads [21]. Backups must use the SQLite online backup API or account for WAL sidecars rather than copying only the main database file [22]. The pinned driver and embedded engine versions are recorded in the repository for reproducibility. The unified store persists users, web sessions, API keys, agent ACLs, agents, conversation sessions, layered agent files, scoped configuration, channel credentials, and cron jobs.

Conversation sessions are keyed by channel and chat identifier and scoped by user and agent. In store-backed mode, the manager attempts to reload the session on every access. If the store returns an error and an in-memory copy exists, the read fails open to that potentially stale copy; it improves cross-replica freshness in the normal path but does not guarantee that every request observes the latest durable history. This differs from required identity files, whose load failure stops the turn. Identity files are stored separately from user artifacts; workspace objects are namespaced by agent and optional session to prevent concurrent chats from overwriting one output name.

## G. Deployment and Failure Recovery Boundary

The implemented deployment unit is one Gateway process. It owns an in-memory MessageBus, TaskQueue, pending-correlation map, lazy user-space registry, channel manager, scheduler, plugin manager, and sandbox lifecycle pool. Durable state is externalized through the SQL store and workspace object store, but queue position, in-flight correlations, deduplication memory, and active cancellation relationships are process-local. Pointing two Gateway processes at PostgreSQL does not by itself create a distributed queue, a shared wait graph, or single-consumer channel semantics. Multi-instance active-active operation is therefore outside the demonstrated architecture.

Startup opens and optionally migrates the store, constructs the object store and usage meter, discovers enabled plugins, loads task-queue configuration, registers stored channel rows, and then starts background ingress and scheduling loops. Agents are loaded lazily only after an authenticated request resolves a real user. Configuration combines database-scoped settings with operations-managed environment overrides; credentials must remain in the environment or secret store rather than report artifacts.

On `SIGINT` or `SIGTERM`, the Gateway cancels its root context, waits for ingress, channel, scheduler, and cleanup loops, rejects and releases pending internal requests, stops the TaskQueue, stops plugins, and closes live sandboxes. Pending TaskQueue entries are marked cancelled, but the current shutdown path does not persist an externally replayable queue. A daemon wrapper can restart a crashed child with exponential backoff up to ten consecutive crashes, and launchd/systemd service templates can supervise the process. Restart supervision is availability assistance, not transparent request replay: clients must treat an interrupted request as outcome-unknown if an external tool may already have produced a side effect.

Durable SQL and workspace state can be reloaded after restart, whereas pending queues, correlation waiters, and deduplication entries are process-local and are lost on a crash. An interrupted provider or external-tool request can therefore have an uncertain outcome and must not be retried as if exactly-once execution were guaranteed. SQLite deployments also require a coordinated checkpoint or online backup because the main database file alone may omit changes still present in WAL sidecars [21], [22].

For a single-host development or small deployment, SQLite and the local workspace provide the shortest operational path. A larger deployment should use a tested PostgreSQL configuration and remote object store, but it still requires a separate distributed-admission and ownership design before multiple active Gateway replicas can safely share work. PostgreSQL supplies transaction isolation and locking primitives [23]; the implementation has not yet converted those primitives into a verified distributed scheduler.

# IV. AGENT RUNTIME EXECUTION MECHANISM

## A. One Turn as a Controlled State Machine

The runtime uses a bounded ReAct loop. The key behavior is summarized below.

[[ALGORITHM_1]]

ALGORITHM_CAPTION: Controlled execution of one agent turn.

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

Session-history compaction is a bounded-context safeguard, not a replacement for durable conversation storage. The current Go implementation estimates tokens from message text and tool-call arguments and checks an 80,000-token threshold at turn entry. When the estimate crosses that threshold, it first logs the full history and replaces long tool results older than the most recent 20 messages with a short marker. If pruning is insufficient, it asks the configured model to summarize the older messages while retaining those recent messages. A summarization failure falls back to the pruned history. This two-stage policy reduces repeated tool-output payloads before it abstracts conversational decisions, but its approximate token estimate and model-generated summary do not guarantee preservation of every earlier fact. It is distinct from the SEC experiment's retrieval stage, which selects source records into an Evidence Bundle; the experiment uses isolated sessions and does not evaluate session-history compaction as a treatment.

The tool registry for the turn is then copied or overridden by request-scoped evaluation tools and filtered through the agent’s policy. The model never receives tools that the policy denies. This is stronger than allowing every tool and asking the prompt not to use some of them. The core state-machine invariant is that every persisted assistant tool-call block has one corresponding tool-result block before the next provider call. The history normalizer repairs interrupted calls at turn entry and runs again before terminal persistence.

For each iteration, the runtime makes one streaming model call, forwards content deltas, reads the terminal response, records usage, and decides between two transitions:

- **Final-answer transition:** append one complete assistant message, run post-turn hooks, flush the session, emit `done`, and return.
- **Tool transition:** append the assistant’s tool calls, emit trace events, execute the calls concurrently, append one matched tool result for each call identifier, and continue to the next model iteration.

### Runtime Invariants and Repair Algorithms

Three invariants concentrate the intended correctness boundary.

1. **Accepted-enqueue FIFO invariant:** for one `chatKey`, tasks are executed serially in the order in which they are successfully sent to that chat queue. This is channel-enqueue order, not a guarantee that two concurrent callers are ordered by wall-clock invocation time or task identifier, because registration and channel send are separate operations.
2. **Wait-graph invariant:** while the MessageBus lock is held, adding a source-to-target wait edge is permitted only when no target-to-source path already exists. Every accepted blocked internal call contributes one reference-counted edge, and completion, cancellation, publication failure, or shutdown removes it.
3. **History-shape invariant:** after normalization, each assistant tool-call position is immediately followed by one matching tool result; the first unused matching result is retained, a missing result is synthesized as interrupted, and duplicate or orphan tool messages are dropped. This is structural provider validity, not proof that a tool executed exactly once or that its result is semantically correct.

Task admission, delegation, and history repair preserve these invariants. A chat lane accepts one task at a time; independent root tasks consume global capacity, while nested tasks inherit their root admission. An internal delegation adds a correlation waiter and a wait-graph edge only after checking ownership, capacity, and cycle freedom. The edge and waiter are released on reply, cancellation, backpressure, or shutdown. Before another provider call, history repair places each available tool result after its matching assistant call, inserts an interrupted-result marker when needed, and removes duplicate or orphan results.

The runtime detects three consecutive identical tool name/argument pairs and adds a loop warning. It also caps the number of tool iterations. Tool panics are recovered inside their execution goroutines and converted into explicit error results rather than terminating the Gateway process. Results are correlated by a consume-once call identifier; empty or duplicate identifiers produce explicit failures instead of silently copying another tool's result. Each tool records its own start time, duration, and hook context rather than inheriting a batch-level wall-clock duration.

## B. System Prompt and Identity Contract

The context builder combines runtime information, a user-message isolation policy, optional sandbox guidance, bootstrap files, Skills, long-term memory, group context, and reasoning-mode guidance. User text is wrapped in `<user_message>` tags only in the provider payload; the stored history remains clean for the UI.

Benchmark specialists can declare required identity files. Before a model call, the runtime loads those files once, rejects missing or empty content, and computes a short SHA-256-based revision identifier. The same validated snapshot is used to build the prompt, avoiding duplicate database reads and time-of-check/time-of-use drift inside a turn. Store failures fail closed; only a confirmed not-found condition permits the legacy filesystem fallback. The revision proves that the expected identity material was loaded without exposing its contents in telemetry. A configuration failure is emitted through both non-streaming and streaming error paths.

## C. Tool Policy and Sandbox Binding

Policy presets include permissive, standard, restricted, `no-tools`, and `delegate-only`. The evaluation coordinator uses `delegate-only`, while fixed-evidence specialists use `no-tools`. When no file tools are allowed, related prompt guidance is also removed so the system prompt does not advertise capabilities the model cannot use.

If a sandbox pool is configured, the registry binds a session-specific executor at turn start. File and shell tools are re-registered against that executor. A `sandboxRequired` flag prevents silent fallback to host execution when the pool fails. Docker and E2B backends can therefore be exchanged behind one executor interface while retaining the same agent loop.

## D. Session Correctness and Streaming Semantics

Provider APIs require every assistant tool-call block to be followed by matching tool results. Client cancellation or a crash during tool execution can leave invalid history. The runtime repairs that history by matching available results to calls, marking interrupted calls, and removing duplicate or orphaned tool messages. Repair runs when a turn begins and before terminal persistence.

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

Every monetary value in this report is an estimate computed from the frozen
suite price table. It is not a provider invoice and is not presented as a general
cost law outside the recorded model allocation and date.

## G. Operational Bounds and Claim Semantics

The runtime uses three different classes of bounds. A **correctness invariant** must hold for every accepted state, such as wait-graph acyclicity or authorization after target resolution. A **safety bound** guarantees termination or finite resource exposure but may be configured per deployment, such as the tool-iteration or task-timeout limit. An **operational default** is a provisional capacity choice, not a theorem or benchmark-derived optimum. Conflating these categories would turn arbitrary constants into unsupported scalability claims.

The current implementation applies configurable limits to root concurrency, task lifetime, and tool iterations, together with bounded in-memory queues and correlation maps. These limits provide backpressure and finite resource exposure; their present values are operational defaults rather than experimentally derived capacity optima.

The terms used elsewhere in the report are correspondingly narrow. Local completion publication occurs at most once, and a live correlation accepts at most one reply. Neither implies exactly-once provider execution, external tool effects, durable message delivery, or transparent replay after process failure. Terminal stream consistency means that this process signals success only after persisting its final assistant message; it is not a distributed commit protocol between the browser, Gateway, provider, and external tools.

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

The `finance-tools` native plugin wraps scripts from the external, unvendored Finskills directory and exposes eighteen typed tools. Plugin tests replace subprocess execution with controlled fixtures, so they verify argument handling, envelopes, caching, and ledger behavior without proving that a clean clone contains every external executable. The six-case multi-agent confirmation did not invoke these tools; its trace calls were exclusively coordinator-to-specialist delegation. The tools are grouped as follows.

TABLE_CAPTION: Finance capability groups exposed by the native plugin.

| Category | Tools | Purpose |
|---|---|---|
| Data and status | `toolkit_status`, `stock_snapshot`, `market_events`, `macro_snapshot` | Check capability availability and fetch timestamped market evidence. |
| Deterministic analysis | `screen_stocks`, `portfolio_risk`, `portfolio_policy_bound`, `serenity_scorecard` | Apply completeness gates, full-vector diagnostics, partial-information policy bounds, and reproducible research-priority scoring. |
| Thesis state | `thesis_save`, `thesis_get`, `thesis_list`, `thesis_match_event`, `thesis_record_review` | Persist hypotheses, catalysts, invalidations, evidence, and immutable reviews. |
| Monitoring state | `watchlist_save`, `watchlist_list`, `event_alert_ingest`, `alert_list`, `alert_update` | Configure monitoring, deduplicate events, and manage alert lifecycle. |

Every tool returns a `finance.tool.v1` envelope containing success state, request identifier, `as_of`, staleness boundary, data, sources, quality completeness, flags, structured errors, and cache metadata. External scripts are launched without a shell, with validated symbols, bounded arguments, captured output, and a timeout. A failure becomes structured evidence for graceful degradation instead of an invitation to invent missing facts.

Stock screening includes a completeness gate. If a candidate appears to satisfy the numerical filters but a required metric is missing, it moves to the rejected set with `reason=insufficient_data`. This prevents missing data from being interpreted as zero or from silently improving a ranking.

For an incomplete long-only holdings map, `portfolio_policy_bound` can prove or withhold a strict single-issuer limit result using declared known weights, a same-denominator residual and an explicit overlap condition. It does not infer exact concentration, HHI or factor exposure from missing holdings; `portfolio_risk` retains that refusal. The bound is a deterministic policy calculation, not an assessment of whether the investment thesis is sound.

## C. Research and Data Skills

The project uses a locally inspected Serenity research Skill to map a value chain, identify difficult-to-expand bottlenecks, grade evidence, rank research priority, and define failure conditions. The Skill provides a reusable analytical procedure; it is not a market-data source, price predictor, valuation engine, or automatic buy/sell rule.

Serenity scorecard inputs are analyst judgments on bounded scales. The bundled script makes the arithmetic deterministic and repeatable, but cannot make subjective inputs objective. The output is therefore labelled a research-priority score. A valid experiment must hold the data, candidate universe, model, and prompt budget constant when comparing no Skill, Serenity, and Serenity plus an independent challenger.

A separate installed FinData Toolkit Skill packages market-data acquisition scripts and their usage instructions. In the tested path, the agent invokes its stock-history script through the runtime's generic `exec` tool, receives dated daily bars and a source URL, and then uses a native finance-tool call to persist a research artifact. The Skill is the reusable capability description and script package; `exec` is the actual runtime action; the finance plugin owns the tenant-scoped thesis ledger. Keeping these boundaries distinct makes it possible to verify a genuine source fetch and a separate state mutation rather than treating a final answer as proof that either occurred. This integration is demonstrated in an isolated Gateway, not yet governed by a command-level Skill allowlist.

## D. Tenant-Isolated Thesis Ledger

The plugin maintains a separate SQLite database for research state. Every stateful call requires the trusted runtime context. Records are filtered by `userId`, allowing a coordinator and specialists owned by the same user to share a ledger while preventing cross-tenant reads.

A thesis records market, symbol, text, conviction, assumptions, catalysts, invalidation conditions, evidence snapshots, status, review schedule, creator agent/session, and an integer version. Review records are immutable and retain the reviewing agent and session. Updates require an `expected_version`; a stale write is rejected rather than overwriting a newer conclusion.

The finance plugin includes an opt-in evidence-completeness guard. A thesis can declare required event metrics, and the event-ingestion path stores the metric observations in the linked alert. At review-write time, the plugin compares the thesis requirements with the **stored alert**, not with fields supplied in the model's proposed review. If a required metric is absent, a substantive decision is rejected; only `needs_review` with unchanged status and conviction can be persisted. The rejected call creates no review or version increment, and a successful deferred review records the missing metric names and alert identifier. This is a deterministic control over a declared condition, not proof that the ingestion process extracted a source correctly. The bounded event-to-thesis panel below ran with this guard enabled.

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

## G. Representative Financial Scenarios

Two representative scenarios illustrate the boundary between deterministic control and model interpretation. In completeness-aware screening, a candidate has observed price-to-earnings and return-on-equity values but lacks free-cash-flow and leverage fields. The deterministic screen rejects the candidate as `insufficient_data`, and the coordinator must preserve the missingness rather than estimate values from pretrained knowledge.

In the contradictory-evidence scenario, a filing states that capital-expenditure guidance fell from 8 billion to 5 billion yuan, while a later official transcript states that the original 8-billion-yuan plan remains unchanged. Because the supplied primary sources are not reconciled, the model must retain both claims, keep conviction unchanged, mark the thesis `needs_review`, and request clarification. This scenario tests uncertainty preservation rather than deterministic calculation.

## H. Scenario-to-Mechanism Mapping

TABLE_CAPTION: Mapping from financial scenarios to runtime mechanisms and safe outcomes.

| Case | Primary mechanism under test | Required safe outcome |
|---|---|---|
| Earnings catalyst | Dated evidence and thesis comparison | Versioned positive review; no trade authorization. |
| Thesis invalidation | Explicit failure-condition application | Status becomes invalidated; no unsupported price target. |
| Duplicate event | Fingerprint and optimistic state update | One alert, incremented occurrence count, one review. |
| Incomplete screening | Data completeness gate | Exclusion with `insufficient_data`; no imputation. |
| Portfolio concentration | Deterministic risk diagnostics | Reversible control and mandatory re-check. |
| Contradictory evidence | Uncertainty and governance | `needs_review`, unchanged conviction, clarification request. |

The cases are fixed-evidence tasks rather than return-prediction tasks. They evaluate evidence handling, deterministic state rules, and bounded governance decisions. Predictive validity is a separate question that requires point-in-time market data, survivorship-bias controls, transaction assumptions, and a clearly specified investment objective.

# VI. EVALUATION METHODOLOGY

## A. Research Design and Evaluation Propositions

The evaluation follows a controlled artifact-evaluation design. The execution unit is one isolated case–repetition–mode attempt. For the retrieval suite, the company–task pair is an analysis cluster: corpus loads and repeated provider calls derived from the same source records are not treated as independent financial cases. Fixed-evidence comparisons vary orchestration while holding evidence and model assignment constant. Retrieval-mediated comparisons vary execution topology and context allocation under an explicitly declared model assignment. The dependent variables are deterministic task success, evidence retention, numeric grounding, collaboration quality, token usage, latency, and estimated cost under a fixed price table.

The evaluation propositions are directional design expectations with explicit evidence states, not externally registered population hypotheses:

1. **EP1:** selected runtime controls are executable and observable on the tested paths;
2. **EP2:** shared-retrieval Team and staged Solo exhibit measurable, possibly opposing trade-offs in strict outcome, final evidence recall, and wall-clock latency;
3. **EP3:** sharing one bounded evidence packet reduces tokens, frozen-price estimated cost, and unsupported numeric assertions relative to sending the raw corpus through the same Team topology;
4. **EP5:** deterministic finance controls achieve exact selected state and policy invariants even when open-ended wording varies;
5. **EP6:** unnecessary delegation or repeated context replication increases tokens, frozen-price estimated cost, and latency without improving milestone outcome.

The design separates infrastructure failure from model failure. A timeout, transport error, or unavailable provider is marked `errored` and excluded from the completed-output conditional-success denominator, while remaining in the assigned-attempt system-success denominator. The report shows assigned, evaluated, errored, and unavailable counts together; an errored attempt is not interpreted as a model failure.

## B. Evaluation Stack

The project uses layered evaluation because no single score covers runtime quality.

TABLE_CAPTION: Evaluation layers and the capability measured by each layer.

| Layer | Implemented suite or test | Capability measured |
|---|---|---|
| Unit and integration | Go package tests and Python finance plugin tests | Selected auth, store, queue, provider, routing, cancellation, ledger, and alert paths; coverage is non-uniform. |
| Project self-eval | `evals/smoke.yaml` | Exact output, JSON format, extraction, forbidden content. |
| BFCL-style | Three BFCL V4 `simple_python` records | Function selection, JSON arguments, extra and invalid calls. |
| τ-bench-style | Three retail state-machine cases | Multi-turn state accuracy, communication, and policy compliance. |
| SWE-bench-style | Three local Go repository issues | Patch generation, hidden test execution, and resolution. |
| MultiAgentBench-style | Collaboration and real-runtime suites | Milestones, routing, evidence use, and Team/Solo comparison. |
| Finance workflow | Six fixed-evidence cases | Catalyst, invalidation, duplicate alerts, incomplete data, concentration, and conflicting evidence. |
| Finance tool workflow | Sixteen frozen cases, five isolated Flash repetitions each | Model-selected finance-tool calls, trace pairing, evidence blocking, and persisted thesis or risk state across four workflow families. |
| Skill-to-ledger path | One isolated live-price case | Market-data script execution through the Gateway, source and arithmetic checks, and subsequent finance-plugin ledger creation. |
| Finance retrieval | 24 source-locked SEC configurations with three repetitions of each primary mode; separate eight-configuration all-Flash comparison | Retrieval recall and precision, evidence compression, specialist summary retention, synthesis grounding, latency, and cost under increasing corpus load. |

The style subsets are regression tests for the project's evaluation harness. They are not official benchmark scores because they use fewer tasks, local fixtures, and project-specific graders.

The evaluation subsystem is part of the implemented system, not an external spreadsheet of answers. A YAML or JSON suite declares cases, expected behavior, repetitions, timeouts, and, where applicable, comparison modes. The evaluation CLI loads and validates the suite; the selected runner then creates a separate session for each case–repetition–mode execution. The generic runner covers direct output, BFCL-derived function-call, and tool-trace tasks, while dedicated τ-style, SWE-style, multi-agent, and finance-retrieval runners apply their respective interaction and scoring rules. The HTTP executor submits an evaluation-scoped request to the real Gateway, which invokes the agent runtime and returns a final answer together with trace events, usage, and optional state. Deterministic tool responses and simulated specialist faults can be injected within a request; these controlled fixtures test particular decisions but do not by themselves establish behavior under an uncontrolled production outage. The report layer aggregates attempts and compares saved baseline and candidate results.

Three evidence channels have distinct meanings. Final text supports outcome, milestone, and grounding checks; a tool trace records process events such as calls, results, and errors, with call identifiers available to associate the events; and per-model-call usage records agent role, call path, tokens, cache-token categories, estimated cost, latency, and call errors. A correct-looking answer alone cannot establish that the intended tool or specialist was used, while a valid tool trace alone cannot establish that the synthesis is factually correct. The evaluators therefore combine output, trace, state, and, for local repository tasks, hidden-test results.

The six-case fault-injection suite separately exercises specialist timeout, explicit error, malformed output, contradictory evidence, multiple partial failures, and noncritical dependency failure. Its controlled fault behaviors and graders measure whether a failure is observed, attributed, and handled without unsupported claims; they are not a service-availability or chaos-engineering result. This separation matters because a runtime or transport error, a model's unsupported assertion, a mismatched source fact, and an overly narrow grader are different failure classes requiring different remedies.

## C. Repetition and General Metrics

Each case runs in an isolated session with a configurable timeout and number of repetitions. The report records run pass rate, `pass@1`, `pass@k`, consistency, P50/P95 latency, tokens per successful run, invalid tool-call rate, and suite-specific outcomes. `pass@k` is the fraction of cases with at least one successful attempt among `k` repetitions; consistency is the fraction whose attempts all have the same pass/fail result.

For suites that configure state, communication, or policy graders, final success requires those populated components to pass. The financial confirmation populated text, milestone, contribution, and grounding checks; persistent state mutation was evaluated separately through deterministic plugin tests.

## D. Fair Team/Solo Baselines

A naive comparison between a Team and a closed-book Solo agent is unfair when specialists possess evidence unavailable to Solo. It measures both evidence access and orchestration. The financial suite therefore defines four evidence-matched or diagnostic modes:

- `solo_open_book`: one coordinator pass over the same evidence packet, anonymized and flattened, without delegation tools;
- `solo_two_pass`: two coordinator passes over the same anonymous evidence, controlling for the additional planning/synthesis opportunity;
- `team`: two coordinator calls plus three real specialist calls through the runtime;
- `oracle_team`: named specialist reports delivered directly, representing a routed-synthesis diagnostic candidate rather than a theoretical upper bound.

The fair collaboration gain is

`Gfair = S(team) − S(solo_open_book)`,

where `S` is outcome success under the same milestone and attribution graders. Planning-opportunity-matched gain is `S(team) − S(solo_two_pass)`. This label is deliberately narrower than compute matching: Two-Pass matches an additional coordinator planning opportunity but does not match Team's three specialist calls. The older `team − solo_closed_book` value remains an evidence-access diagnostic in legacy suites but is not evidence that orchestration itself added value. Each mode receives an independent session and timeout. If a baseline times out, returns an empty output, exposes a streamed turn error, or otherwise fails at the infrastructure layer, it is marked `errored`; it remains in the assigned-attempt denominator but is excluded from completed-output conditional task success, and any dependent paired effect is unavailable. Infrastructure errors are not interpreted as model failures. Paired tables are constructed from case and repetition keys before computing statistics.

## E. Multi-Agent Metrics

For expected specialist set `E` and unique valid delegated set `D`,

`Precision = |D ∩ E| / |D|`, `Recall = |D ∩ E| / |E|`,

and delegation F1 is their harmonic mean. Contribution utilization is the fraction of expected healthy specialist evidence retained in the final answer. Coordination score is the mean of delegation F1 and contribution utilization. Milestone KPI is achieved deterministic output milestones divided by configured milestones.

## F. Financial Workflow Experiment

The financial suite contains six cases and three specialists—four runtime agents including the coordinator. The final confirmation used one repetition and four independently isolated modes, yielding 24 case–mode executions and 54 model calls after including the specialists and the two-pass baseline. Session keys are unique by case, repetition, and mode so that a prior answer cannot leak into another baseline. The same deterministic milestones and forbidden assertions are used for all four modes.

The evidence source is deliberately controlled. `FIN-01` through `FIN-06` are compiled into the benchmark tenant as a string lookup table, and each specialist is instructed to return the matching evidence. The calls traverse the real Gateway, TaskQueue, MessageBus, agent loop, provider, correlation, and telemetry paths, but they do not measure document retrieval or specialist evidence reasoning. The coordinator uses a delegate-only policy and specialists use a no-tools policy.

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

Functional feasibility is defined conservatively. All configured wording and policy assertions must hold across repetitions; baseline infrastructure errors must be zero or separately disclosed; unsupported claims must be zero for cases with incomplete or contradictory evidence; and any Team advantage must be computed against `solo_open_book`, not against an evidence-deprived closed-book baseline. Actual ledger mutation is tested separately by the Python plugin suite and is not inferred from generated prose. A positive return is not an acceptance criterion.

## G. Retrieval-Mediated SEC Experiment

The retrieval track introduces evidence acquisition as an explicit stage rather than assuming that a complete evidence packet is already available. The executed Stage 2A v2 suite crosses four companies—NVIDIA, AMD, Intel, and NIKE—with two task families and three corpus loads. Point-in-time cases require one bounded observation and declared calculations. Longitudinal cases require chronology reconstruction, accounting-basis checks, cross-observation calculations, a contiguous research-state chain, and a bounded governance decision. Small, medium, and large loads add progressively more same-company, adjacent-period, peer, and irrelevant records. The 24 configurations are treatment combinations, not 24 independent issuers; each primary mode has three repetitions per configuration.

All records are extracted from archived SEC filing material and carry a source identifier, accession, filing date, locator, source hash, and record identifier. A provenance table records the concept, value, unit, accounting basis, reporting period, filing date, SEC acceptance timestamp, accession, source URL, and locator for each expected fact. Point-in-time cases exclude records accepted after the target observation time, while a separate derived-value table preserves formulas, input facts, units, rounding rules, and expected results. The declared ground truth comes from this source-locked oracle rather than model output or grader consensus, and expected calculation answers remain hidden from non-Oracle modes.

Before a confirmatory run, the source and oracle packet is checked separately from model behavior. The revised Stage 2 packet contains 103 tasks: 44 SEC source-fact checks, 17 calculation checks, and 42 evidence-equivalence-group checks. Source-fact review compares the quoted filing passage with the claimed value, unit, reporting period, and accounting basis; calculation review independently recomputes the declared formula from checked inputs; group review asks whether every candidate passage supports the same target fact. A technical re-review of the corrected packet found 42/42 evidence groups acceptable, including the repaired Intel third-quarter impairment passage. On 10 October 2026, the project owner also reported personally checking all 103 revised tasks. This is a single-reviewer confirmation, not a completed two-reviewer blind audit: the two reviewer CSVs do not contain per-item independent results. Neither the owner confirmation nor the group check establishes that subsequent model-generated analysis is factually correct.

The five modes are:

1. `solo_monolithic`: one Pro call receives the raw corpus and performs retrieval, analysis, and synthesis in one context;
2. `solo_staged`: one Pro agent performs retrieval, three sequential analytical passes, and synthesis in isolated sessions;
3. `team_shared_retrieval`: one Flash retriever constructs a bounded packet, a Pro coordinator delegates the packet once to three parallel Flash specialists, and the coordinator synthesizes their summaries;
4. `team_raw_context`: the same Team topology receives the full raw corpus as shared context, isolating the effect of retrieval compaction;
5. `oracle_evidence`: one Pro synthesis call receives the gold evidence packet and provides a diagnostic ceiling rather than a deployable baseline.

The primary quality outcomes are strict pass, final evidence recall, milestone completion, and numeric grounding accuracy. Retrieval recall and precision, specialist-summary retention, synthesis retention, evidence-compression ratio, delegation precision and recall, infrastructure-error rate, tokens, estimated cost, and wall-clock latency are secondary mechanism and efficiency outcomes. Stage service times are retained for attribution, but specialist service times are summed across parallel calls and therefore are not substituted for end-to-end wall-clock latency.

The executed Stage 2A v2 main study assigns three repetitions of each primary mode—staged Solo, shared-retrieval Team, and raw-context Team—to all 24 configurations, for 216 assigned primary observations. One monolithic Solo and one Oracle diagnostic are also run per configuration, adding 48 observations. Mode order is seeded within case–repetition blocks, sessions are isolated, and each case report has a hash manifest. The main study uses the declared heterogeneous allocation above; the prespecified 24-observation all-Pro ablation was not run and is not part of the results.

A separate all-Flash supplement holds the model family and tier fixed across staged Solo and shared-retrieval Team. It selects eight prespecified configurations across the four issuers, runs each mode three times, and contributes 24 paired blocks or 48 valid observations. The selected results come from four complete configurations in the original supplement run and four complete configurations in a targeted continuation; incomplete or invalid pilot files are excluded. The supplement is not pooled with the main study because the model assignment and run batches differ.

## H. Statistical Reporting and Reproducibility

The primary result is the raw case-level paired outcome table with assigned, evaluated, errored, and unavailable counts. If there are no discordant pairs, an exact paired test is undefined rather than evidence of equality. Latency and token distributions are summarized by median, P95, and individual-case values because a mean can hide delegation loops. Corpus loads and repeated calls derived from one company–task pair share source material and therefore cannot be counted as independent financial cases.

The six-case confirmation has one repetition. Even the most extreme possible paired result—six Team-only successes and no Solo-only successes—has two-sided exact probability `2/2^6 = 0.03125`. Any smaller discordance cannot cross a conventional 0.05 threshold. Consequently the earlier fixed-evidence study is structurally underpowered for modest differences, and an observed 0.0-point difference means “not detected at this resolution,” not “equivalent.” The later SEC study adds repetition and load variation, but repeated calls and loads within a company–task cluster are not independent issuer draws.

Every reported run records the model roles, endpoint class, baseline modes, repetition count, timeout, pricing date, execution mode, token usage, latency, and error state. Evidence fixtures and graders remain unchanged within a comparison. The six-case confirmation and original retrieval Pilot contain one repetition; the Stage 2A v2 and all-Flash comparisons have three repetitions per selected configuration. Given only eight company–task clusters, one provider family, and two separate run batches for the all-Flash supplement, the later estimates remain configuration-bounded rather than population effects.

The finance-retrieval protocol additionally records the suite and source-lock hashes, a seeded mode order where configured, and a retained machine-readable report and manifest. These artifacts make the executed configuration inspectable; they do not remove provider variability, single-case dependence, possible grader error, or the need to freeze sources and oracles before confirmatory repetition.

# VII. RESULTS

## A. Engineering Verification

The implementation was verified with focused package tests covering the evaluation harness, agent loop, sub-agent tools, store, plugins, tenant provisioning, API, and command layer, followed by the full Go test suite. Behavioral tests exercise assertion direction and negation, error-aware denominators, streamed turn errors, tool panic containment, duplicate call identifiers, production and evaluation deduplication semantics, per-tool duration, model-call ordering, and SQLite contention through the public Store API. Race-enabled tests for the agent, sub-agent tools, and store packages also passed and are reported separately because they detect synchronization faults rather than semantic failures.

The finance plugin passes 35 Python tests in the current checkout, covering typed tool discovery, subprocess argument validation, cache behavior, completeness gating, trusted tenant context, thesis isolation and versioning, event review persistence, watchlist filtering, alert deduplication, user isolation, required-event-metric state gating, and the partial-portfolio policy bound.

Statement coverage measured with `go test ./... -coverprofile` is approximately 27.2% for runtime and production packages, or 28.4% when `project-report/analysis` is included. Coverage is strongly non-uniform: `policy`, `scope`, `session`, `plugin`, `mcp`, and `skills` are among the packages at 0.0%, while `agent/tools`, `gateway`, `sandbox`, `setup`, and `store` remain partial. These gaps affect mechanisms used in the design argument, especially policy-filtered registries, session normalization, and prompt-injection scanning. The test results establish functional feasibility of selected principal paths; they do not constitute comprehensive code coverage, a production load test, an adversarial security certification, or evidence of investment performance.

A small scheduler-only load test (`TestSmallSyntheticSchedulerLoad`, run with `go test ./internal/taskqueue -run '^TestSmallSyntheticSchedulerLoad$' -count=5 -v`) exercises the actual TaskQueue with 48 synthetic internal tasks distributed over 12 chat keys, four tasks per chat. Each handler waits 15 ms; no Gateway HTTP request, database, provider, or external tool is involved. Five local repetitions on Go 1.27.1 (Darwin/arm64) compared root-concurrency limits of one and four. All tasks completed, each chat retained submission order, and observed peak handler concurrency equaled but never exceeded the configured limit. A separate race-detector run passed. The timings below are ranges across the five ordinary repetitions, not service-capacity estimates.

TABLE_CAPTION: Queue-only synthetic load check, 48 tasks across 12 chats, five repetitions per limit.

| Root concurrency limit | Elapsed time | Queue-wait P50 | Queue-wait P95 | Observed peak handlers |
|---|---:|---:|---:|---:|
| 1 | 767–773 ms | 367–372 ms | 703–708 ms | 1 |
| 4 | 192–194 ms | 80–81 ms | 176–177 ms | 4 |

The test supports bounded root admission and per-chat serialization under this small controlled workload. Since the handler duration is artificial and dominates the run, these elapsed times do not quantify provider latency, production throughput, database contention, memory use, or behavior at queue saturation.

## B. Implemented Financial Verification

The financial application has six forms of implemented evidence:

1. the runtime and plugin compile and pass their unit/integration tests;
2. the stateful plugin implements trusted tenant scope, versioned theses, immutable reviews, watchlists, and alert deduplication;
3. the six-case finance suite encodes the behaviors expected from an evidence-grounded research copilot;
4. the fixed-evidence suite has been executed through the real runtime under four matched baselines with per-mode grounding, tokens, cost, and latency;
5. the source-locked SEC study and separate all-Flash comparison exercise retrieval, staged Solo execution, and Team delegation across repeated configurations;
6. an isolated model-backed event-to-thesis panel exercises finance-tool calls, missing-evidence gating, and durable ledger transitions.

The finance suite intentionally avoids future stock returns. It evaluates whether the coordinator preserves dated primary facts, applies catalysts and invalidations, suppresses duplicate alerts without losing occurrence counts, rejects incomplete screens, converts concentration diagnostics into reversible controls, and retains uncertainty under contradictory evidence.

The implemented test evidence and the model-evaluation evidence must be distinguished.

TABLE_CAPTION: Current evidence status and the claims supported by each artifact.

| Evidence type | Current status | Claim supported |
|---|---|---|
| Plugin unit tests | 35 tests pass in the current checkout | Tool discovery, argument validation, caching, completeness, tenant isolation, versioning, deduplication, required-event-metric gating, and partial-portfolio bounds operate as implemented. |
| Runtime integration tests | Relevant Go packages pass | Authenticated routing, task execution, provider parsing, internal calls, and evaluation reporting are executable. |
| Revised Stage 2 source/oracle audit packet | 103 tasks; owner reports one personal review; 42/42 evidence groups pass AI technical re-review | The candidate SEC facts, formulas, and evidence groupings have been checked as experiment inputs; this is neither independent two-reviewer adjudication nor a model-output score. |
| Six finance case specifications | Implemented | Financial invariants and deterministic graders are defined before model execution. |
| Four-mode finance confirmation | One repetition; no baseline errors | Descriptive matched-baseline quality, grounding, token, cost, and latency results are available; no statistical or holdout claim is made. |
| Stage 2A v2 SEC main study | 24 configurations; three repetitions per primary mode; two Solo provider timeouts retained | Completion, evidence, latency, token, and estimated-cost differences can be described under the declared heterogeneous deployment. |
| Same-model all-Flash comparison | Eight configurations; 24 paired repetitions; 48 valid observations | Team/Solo speed, completion, evidence-retention, and resource trade-offs can be compared without a model-tier difference. |
| Source-locked event-to-thesis workflow | Four cases, two isolated repetitions each; eight durable reviews and alert acknowledgements | Selected Gateway-to-finance-ledger state transitions and missing-evidence handling are executable; broad insight quality and autonomous retrieval remain untested. |
| Point-in-time return study | Not implemented | No claim is made about excess return, hit rate, Sharpe ratio, or investment performance. |

## C. Four-Mode Financial Runtime Result

The final confirmation was executed on 1 August 2026 with one repetition, four independently isolated modes, and a ten-minute timeout. All 24 mode executions completed without infrastructure error, and all 54 model calls were covered by the frozen pricing table. The oracle contained 18 milestone checks and 44 grounding assertions. Persistent state, communication-policy, and tool-trace behavior were not evaluated by this run and are not inferred from its prose scores.

TABLE_CAPTION: Financial confirmation, one repetition and six cases.

| Mode | Assigned | Evaluated | Errored | Unavailable | Conditional passed | Billable-like tokens | Provider total tokens | Frozen-price estimated cost (USD) | Mean latency |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Solo Open-Book | 6 | 6 | 0 | 0 | 5/6 | 6,557 | 9,885 | 0.005510 | 13.65 s |
| Solo Two-Pass | 6 | 6 | 0 | 0 | 5/6 | 23,910 | 30,822 | 0.017798 | 42.65 s |
| Team | 6 | 6 | 0 | 0 | 5/6 | 13,955 | 41,219 | 0.008335 | 19.45 s |
| Routed Team Diagnostic | 6 | 6 | 0 | 0 | 4/6 | 5,062 | 8,902 | 0.004320 | 11.32 s |

Billable-like tokens are uncached prompt plus completion tokens and are presented first. Provider total tokens include cache-read tokens inside prompt totals and therefore answer a different telemetry question. By the billable-like measure, Team used 2.13 times the Open-Book tokens and 41.6% fewer tokens than Two-Pass. By provider totals, the same comparisons are 4.17 times and 33.7% more. The Team/Two-Pass direction therefore reverses under the two accounting conventions. Team cost 51.3% more than Open-Book but 53.2% less than Two-Pass; model assignment, completion length, cache treatment, and provider prices all contribute, so the difference is not attributed solely to Flash specialists.

TABLE_CAPTION: Team coordination and attribution metrics in the six-case confirmation.

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

The Team failure occurred on AMD. The coordinator selected the correct governance specialist but received an empty result, retried beyond the intended delegation count, and synthesized without the required state-chain and stale-candidate evidence. This case demonstrates that routing accuracy is not sufficient for collaboration success: sub-agent response validity and bounded recovery are part of the runtime treatment. The extension removes the simple-task ceiling but does not support a claim that Team is more accurate than an evidence-matched strong Solo coordinator.

### Retrieval-Mediated Context Allocation Pilot

The preceding experiments begin after evidence has already been compiled. A realistic financial-research workflow introduces an earlier bottleneck: source acquisition consumes context, retrieved passages vary in relevance, and analytical reasoning must operate on an imperfect intermediate representation. A retrieval-mediated pilot was therefore added to test the complete information path from a locked SEC corpus to a bounded research memorandum. The research question is narrower than “are multiple agents more accurate?”: under a fixed evidence source and analysis protocol, does retrieving one compact packet before role-specialized analysis reduce context interference and execution cost without reducing evidence retention or conclusion quality?

Five runtime modes operationalize the treatment. `solo_monolithic` gives one Pro agent the 30,518-character corpus and asks it to retrieve, analyze three perspectives, and synthesize in a single context. `solo_staged` uses the same Pro agent in isolated retrieval, three sequential analysis, and synthesis stages. `team_shared_retrieval` uses a Flash retriever to construct one bounded evidence packet, sends that packet once through a batch delegation to three parallel Flash specialists, and uses a Pro coordinator for orchestration and synthesis. `team_raw_context` preserves the same coordinator-specialist topology but shares the full corpus rather than a retrieved packet. `oracle_evidence` gives a Pro synthesis call the perfect evidence packet and serves only as a diagnostic reference; perfect retrieval does not guarantee perfect synthesis.

The case, task wording, required report sections, calculation protocol, evidence identifiers, rounding rule, and 95% numeric-grounding threshold were held constant. Expected calculation answers were withheld from every non-oracle mode, and the source corpus and evaluation suite were content-addressed before execution. Because Team assigns Flash to retrieval and specialist work while staged Solo uses Pro in every stage, this is a comparison of deployable heterogeneous systems rather than a model-capacity-matched experiment.

All five Pilot modes had one assigned and evaluated attempt, with zero infrastructure errors and zero unavailable outputs. The compact table reports their completed-output measures; its strict-pass column is conditional on evaluation, not a population pass rate.

TABLE_CAPTION: Retrieval-mediated NVDA medium-context pilot, one repetition.

| Mode | Strict pass | Milestones | Evidence recall | Grounding | Latency | Total tokens | Cost (USD) | Compression |
|:---|:---:|---:|---:|---:|---:|---:|---:|---:|
| Solo monolithic | No | 2/3 | 100% | 98.29% | 55.96 s | 15,259 | 0.008263 | N/A |
| Solo staged | Yes | 3/3 | 100% | 95.45% | 141.04 s | 37,693 | 0.020690 | 6.12x |
| Team shared retrieval | Yes | 3/3 | 100% | 98.28% | 89.81 s | 42,829 | 0.011987 | 7.58x |
| Team raw context | No | 3/3 | 100% | 94.87% | 104.61 s | 69,553 | 0.022884 | N/A |
| Oracle evidence | Yes | 3/3 | 100% | 100% | 37.89 s | 7,095 | 0.002464 | N/A |

The staged Solo and shared-retrieval Team both passed every milestone and retained every gold evidence group. This observation therefore provides no incremental final-answer accuracy result for collaboration. It does reveal an efficiency and evidence-discipline difference. Relative to staged Solo, shared-retrieval Team reduced end-to-end latency by 36.32% and estimated cost by 42.06%, despite using 13.63% more provider-total tokens. The cost direction follows from heterogeneous model allocation rather than token reduction. Retrieval precision increased from 66.67% to 100%, evidence compression increased from 6.12x to 7.58x, and numeric grounding increased by 2.82 percentage points.

The raw-context ablation was associated with a context-allocation difference within the same multi-agent topology. Both Team modes issued one parallel batch delegation and reached perfect target precision and recall. Shared retrieval was associated with 14.15% lower latency, 38.42% fewer tokens, and 47.62% lower frozen-price estimated cost than raw-context Team, alongside a 3.40-percentage-point grounding difference. Raw-context Team produced eight unsupported or unrequested numeric forms and missed the prespecified grounding threshold by 0.128 percentage points; shared-retrieval Team produced two such forms. Because mode order was not randomized, provider conditions could vary, and the model allocation was heterogeneous, these observations do not identify a causal context-allocation effect. The monolithic mode was faster and cheaper than either complete pipeline but omitted the required separation of sourced fact, declared calculation, and analyst judgment. Its failure is therefore one of research-process compliance, not evidence recall.

These Pilot findings motivated the source-locked, repeated study below; they are not pooled with it. The Pilot had one company and one repetition, mode order was not randomized, provider conditions could vary, and the grounding evaluator checked numeric support rather than full semantic entailment.

For Team modes, reported analysis latency is the sum of specialist model-service times, whereas specialists execute concurrently. End-to-end mode latency is the wall-clock quantity and must not be reconstructed by summing stage totals.

### Stage 2A Source Locked Main Study

All 24 configuration reports and matching hash manifests were retained. The primary analysis assigns 72 attempts to each of staged Solo, shared-retrieval Team, and raw-context Team; the 24 monolithic and 24 Oracle observations are diagnostics rather than additional repetitions of those modes. The table reports assigned attempts, strict passes, separately identified infrastructure errors, mean wall-clock latency over completed outputs, provider-total tokens per assigned attempt, and total frozen-price estimated cost. The two Solo timeouts are retained in the assigned denominator but excluded from its completed-output latency mean; their provider-billed cost is unknown and is not imputed into the estimate.

TABLE_CAPTION: Stage 2A v2 main-study results across 24 configurations, with three repetitions per primary mode.

| Mode | Assigned | Strict pass | Infrastructure errors | Mean completed latency | Mean tokens per assigned attempt | Total estimated cost |
|---|---:|---:|---:|---:|---:|---:|
| Staged Solo | 72 | 55/72 | 2 | 70.17 s (70 completed) | 36,564 | USD 1.087207 |
| Shared-retrieval Team | 72 | 56/72 | 0 | 31.38 s | 43,158 | USD 0.625114 |
| Raw-context Team | 72 | 63/72 | 0 | 26.51 s | 76,663 | USD 0.872993 |
| Monolithic Solo diagnostic | 24 | 0/24 | 0 | 27.15 s | 15,760 | USD 0.191063 |
| Oracle-evidence diagnostic | 24 | 21/24 | 0 | 19.94 s | 6,195 | USD 0.082876 |

The main deployment uses Pro for staged Solo and the Team coordinator, with Flash for Team retrieval and specialists. Therefore its latency and cost contrasts combine execution topology with model allocation; they cannot establish a model-independent architecture effect. Shared-retrieval Team finished faster than staged Solo in all 72 assigned pairs, including the two Solo timeout pairs. Their strict outcomes were mixed: 46 pairs passed in both modes, ten passed only in Team, nine only in Solo, and seven in neither. The near-equal aggregate pass counts must not be described as equivalent quality. Raw-context Team passed more attempts than shared-retrieval Team (63 versus 56) and was faster on this run, but consumed substantially more tokens and estimated cost. Thus evidence compression lowered resource use in this configuration without dominating raw context on completion or latency. Monolithic and Oracle diagnostics probe pipeline and evidence constraints; neither is a fair replacement for the complete staged workflow.

### Capacity Matched All Flash Comparison

The separate supplement uses Flash for every actual model call in both modes. It covers eight prespecified configurations, three repetitions per configuration, and 24 Team/Solo pairs. All 48 selected observations completed without infrastructure errors. Four configurations came from the complete portion of the original supplement run and four from a targeted continuation; the incomplete configuration and an earlier incorrect-model pilot are excluded. Hash manifests are retained for the selected reports.

TABLE_CAPTION: Same-model all-Flash Team and Solo comparison over 24 paired repetitions.

| Mode | Strict pass | Mean end-to-end latency | Mean provider-total tokens | Total estimated cost | Mean final evidence recall |
|---|---:|---:|---:|---:|---:|
| Staged Solo | 24/24 | 33.62 s | 41,514 | USD 0.130359 | 1.000 |
| Shared-retrieval Team | 19/24 | 22.42 s | 47,029 | USD 0.133224 | 0.975 |

Team was faster in all 24 paired blocks, with an 11.20-second lower mean latency (33.3% relative to Solo's mean). It used approximately 13.3% more provider-total tokens and 2.2% more frozen-price estimated cost; it was cheaper in only eight of the 24 pairs. Two Team failures omitted declared calculations, and three occurred in the same AMD point-in-time large-corpus configuration with final evidence recall of 0.8. This is a latency gain with a completion and evidence-retention cost on the selected tasks, not a general multi-agent quality advantage. The eight configurations share source material within four issuers and ran across two batches, so the 24 pairs are not independent draws from a broad task population. Estimated costs use the frozen experiment price table rather than the provider bill.

### Source-Locked SEC Event-to-Thesis Ledger Workflow

To test runtime use in a financial-research application beyond generated prose, a separately frozen panel connected SEC event packets to the native thesis ledger through the Gateway. Four neutral-ID cases represented growth with a recovery caveat, company-level growth with segment risk, matching-fiscal-quarter deterioration, and a packet omitting a thesis-required metric. Each case was repeated twice, with a fresh tenant-isolated ledger and session per attempt. Case IDs revealed no intended decision. Baseline theses, source-linked event observations, required metrics, decision ranges, and run order were fixed before model calls. The model read an existing thesis and alert, calculated changes, chose its own impact and research-state decision, wrote a versioned review linked to the stored alert and SEC source hash, then acknowledged the alert. A deterministic finance-tool guard required `needs_review` without a status or conviction change if the linked stored alert lacked a required metric. No trade or portfolio operation was exposed.

TABLE_CAPTION: Source-locked event-to-thesis panel, two isolated model-backed attempts per case.

| Case | Evidence and research condition | Persisted decisions | Frozen decision rubric |
|---|---|---|---:|
| C01 | AMD Q3→Q4 2024: revenue +12.3%, gross margin +1 pp, Gaming +21.9%; sustained recovery needs more than one observation | Maintain; upgrade | 2/2 |
| C02 | AMD Q2→Q3 2024: revenue +16.9% and margin +1 pp, but Gaming −28.7% | Maintain; needs_review | 1/2 |
| C03 | Nike Q4 FY2024→Q4 FY2025: matching-quarter revenue −12.0%, margin −4.4 pp, digital YoY rate −16 pp | Invalidate; invalidate | 2/2 |
| C04 | NVIDIA Q1→Q2 FY2025: event packet includes revenue and Data Center growth but omits required gross margin | needs_review; needs_review | 2/2 |

All eight requests completed without transport or provider errors. Independent inspection of the eight SQLite copies found one thesis, one immutable review, and one alert in each. In every attempt, the thesis advanced exactly one version, the review linked the stored alert and source hash, and the alert was acknowledged; no trade or portfolio tool was called. Both C04 attempts preserved active status and conviction 3 under the required-evidence guard. The frozen decision/status rubric passed 7/8; C02's second run chose a cautious `needs_review` outside the permitted maintain/downgrade range, although its state transition completed correctly. Post-run semantic inspection found one additional unsupported inference: C01's second run called one observed Gaming increase a “second consecutive improvement” and treated the sustained-recovery condition as met. The eight calculations and period pairings otherwise matched the frozen source facts to the stated precision. These two observations concern decision calibration and analysis, not a failure to execute or persist the workflow.

The panel used 35 priced model calls, 124.061 seconds of summed Gateway wall time (mean 15.508 seconds), and USD 0.029961 in frozen-price estimated model cost, not a provider invoice. The suite, response traces, hash manifest, and per-attempt ledger copies are retained in the v2 result directory. Events were source-locked but pre-ingested, so this study did not measure autonomous filing retrieval, live source verification, Team-mode ledger mutation, or investment outcomes. It supports a bounded engineering claim: the runtime can carry a model-proposed financial review through policy-filtered tools, deterministic evidence gating, and durable state transitions. It does not establish broadly reliable financial insight quality.

### Cross-Workflow Finance Tool Panel

The event-to-thesis panel was extended to four application families: SEC event review, conflicting-source resolution, preliminary candidate screening, and portfolio-risk diagnosis. The post-fix exploratory panel ran 16 distinct frozen cases once each. A separate repetition panel then ran those 16 cases five times each with independent Gateway sessions and finance ledgers. The event cases used locked SEC excerpt packets; conflict, screen, and portfolio cases used declared synthetic fixtures. All 80 assigned repetitions completed, with 77 original mechanical passes and three retained case-execution failures. Two failures printed a would-be tool call in prose without sending an actual tool invocation; one explained a corrected 8,000-to-5,000 claim in the final answer but omitted the current 5,000 value from the persisted review rationale. No request or pricing uncertainty was recorded. In the ten repetitions whose event packets lacked required evidence, the ledger recorded `needs_review` and `decision_hold=true`, kept status and conviction unchanged, and exposed `actionability=blocked`. This is evidence that the tested state guard can operate across repeated tool-backed sessions, not a population reliability rate or a full assessment of financial prose.

### Claim-Level Quality and Source-Novelty Checks

A separate Codex LLM-as-judge pass used a declared factual fidelity, inference, risk, ledger-alignment and research-utility rubric on retained answers and traces. In the 80-attempt four-workflow panel, it labelled 54 answers high within their case, 13 adequate and 13 problematic. This is a non-independent first-pass content review, not an expert gold standard; the five repetitions within a case share source material. Mechanical completion (77/80) is therefore reported separately from content quality. The problematic answers included treating two conflicting capex point claims as a range, inferring a production-capacity change from a capex correction without a bridge, misnaming a growth metric, and missing a provable bound on a partially observed portfolio.

Additional historical and forward panels tested whether these issues generalized beyond the initial fixtures. A fresh-issuer SEC event-to-thesis panel across Apple, Microsoft and Starbucks completed 14/15 workflows, but its content review found zero high, 13 adequate and two problematic answers; it failed the prespecified high-quality gate. An offline SEC-source screening panel across four issuer clusters returned 20 adequate but no high answers: it executed a threshold-and-ledger process without much incremental interpretation beyond the tool fields. These panels differ in task, source selection and case novelty, so their counts are not pooled into a single reliability percentage. The results support auditable application execution but do not establish stable high-quality financial insight.

A later same-case partial-portfolio retest added the deterministic policy-bound tool described above. In ten fresh Flash sessions, the agent used the source-linked screen and bound tools with paired traces, and the bound conclusion matched both declared residual/overlap semantics in all ten. The content review nevertheless found only three high, six adequate and one problematic answer: one response asserted an issuer-specific crypto growth comparison that the selected SEC packet did not provide. This is evidence of a narrow tool-supported policy improvement on reused cases, not a new-issuer holdout or a cure for unsupported financial inference. The first integration attempt, in which an older Gateway binary rejected the new tool, remains a separate retained failure arm rather than being merged into the corrected retest.

### Distinct SEC Source Research Case Study

To examine whether the full research workflow can produce a useful analysis rather than merely complete its tool calls, a later source-distinct panel froze selected SEC disclosures for 30 issuers and ran five isolated Flash sessions per issuer. All 150 responses and ledger copies were retained. The mechanical workflow checks recorded 101 candidates for qualitative review and 49 held outcomes, with no recorded request error. These statuses say whether the configured path executed and what state it saved; they do not judge the financial argument. The planned presentation is deliberately smaller than the execution panel: one fully reviewed positive issuer cluster, a limited number of contrasting answers, and an explicit failure boundary. Selecting examples after inspection does not turn them into a representative quality estimate.

Marqeta (MQ) supplies the positive case. The frozen comparison was the third quarter of 2025 against the second quarter, using displayed sequential values rather than the year-over-year change column in the archived SEC earnings exhibits [24], [25]. A read-only check against both exhibits confirmed the selected values and their units. Net revenue increased from USD 150.392 million to 163.306 million and gross profit from USD 104.061 million to 114.557 million. Company-reported processing volume rose from USD 91.386 billion to 97.962 billion, and company-defined Adjusted EBITDA increased from USD 28.509 million to 30.312 million. Yet operating expenses rose by USD 11.638 million, exceeding the USD 10.496 million gross-profit increase; the GAAP operating loss widened from USD 9.228 million to 10.370 million. The displayed operating bridge is exact: `+10.496 - 11.638 = -1.142` USD million. The GAAP net loss also widened from USD 0.647 million to 3.624 million. The answer kept the non-GAAP improvement separate from GAAP profitability, identified the unresolved reconciliation as a research question, and proposed review rather than an upgrade on growth alone or invalidation on the loss alone. Each of the five saved sessions wrote a source-linked `needs_review` review, acknowledged its alert, and left the thesis `decision_hold=true` and `actionability=blocked`.

A local claim-level review of the five MQ answers rated four high and one adequate under the frozen factual fidelity, inference, risk, state-alignment and utility rubric. This is a diagnostic judgment by the project assistant, not independent finance-expert validation or a claim that the company's securities merit investment. It demonstrates that this runtime can carry a source-bounded, two-sided analysis into an appropriately deferred durable research state. The boundary is visible in a contrasting ACI Worldwide answer: its stored review correctly held the thesis, but its prose said the improvement was not tax-assisted even though the selected tax expense and pretax income imply that the effective tax rate fell from about 31.7% to 22.8%. A correct hold did not make the financial interpretation correct. Other reviewed issuers also include unsupported inferences and cases in which a problematic answer remained available. Those failures remain visible in the retained panel and prevent a claim of stable high-quality insight. As of this report revision, 100 of the 150 answers have local masked claim-level reviews; because that reviewed set was not prospectively sampled, its class frequencies are not used as a population quality rate. The raw runs and masked review records remain in the evaluation archive.

A second selected answer, for AIG, shows a different kind of useful restraint. The frozen inputs were selected rows from its second- and third-quarter 2025 SEC earnings exhibits [26], [27]. In one saved session, General Insurance adjusted pretax income rose by USD 241 million; the displayed underwriting and segment investment-income changes were USD 167 million and USD 74 million, respectively. The answer checked that arithmetic while keeping it separate from the USD 625 million decline in consolidated GAAP net income attributable to common shareholders. It also noted that the reported General Insurance combined ratio improved from 89.3% to 86.8%, while the company-defined adjusted accident-year combined ratio barely changed from 88.4% to 88.3% and written premiums fell. The agent requested a GAAP-to-adjusted and underwriting-driver reconciliation, wrote a `needs_review` review, and left the thesis blocked without changing conviction. The masked local review rated this particular answer high within the selected-source case. Across AIG's five runs, however, one other answer was rated problematic because it left an unresolved basis conflict actionable; another was initially unreviewed and was checked only later with the issuer identity known. AIG therefore illustrates both an attainable analysis and its variability, not a passing issuer cluster or a general quality rate. The later unblinded check is retained separately from the masked scores.

### Small New-Issuer Research Panel

To test whether a similarly useful answer could arise on previously unrun issuers, a prospective mini-panel selected M&T Bank (MTB), Repay Holdings (RPAY), and CoStar Group (CSGP) by reporting-period eligibility before inspecting model outputs. For each issuer, selected second- and third-quarter 2025 SEC exhibit rows were frozen and source checked [28]–[33]. Two isolated Flash sessions per issuer used the same event-to-review contract and a source-bound arithmetic guard. All six sessions completed the tool-backed workflow without a recorded request error; each left a linked review and acknowledged alert in its isolated ledger. A local, unblinded claim-level review rated one answer high within its selected-source case, three adequate, and two problematic. Four stored decisions were `needs_review` and blocked; the two MTB decisions maintained the thesis and remained available. The six outcomes are reported together because post hoc selection of only the best answer would exaggerate quality. Their shared issuer inputs and small sample do not support a reliability percentage.

The strongest answer was RPAY's second repetition. It identified a USD 103.781 million second-quarter impairment and recognized that the narrowing GAAP operating loss, from USD 104.904 million to 3.009 million, did not by itself establish recurring recovery. Company-defined adjusted EBITDA instead edged down from USD 31.811 million to 31.202 million [30], [31]. Its displayed operating bridge was arithmetically correct in USD thousands: revenue +2,099, total operating expenses −99,796, and operating result +101,895. The agent distinguished the impairment base effect from underlying operating leverage, sought fuller driver and reconciliation evidence, and saved `needs_review` with `decision_hold=true`, `actionability=blocked`, and unchanged conviction. This is an illustrative source-bounded analysis carried through to durable state, not a validated investment recommendation.

The contrasting failures delimit that result. RPAY's first answer and persisted review incorrectly said both cost of services and selling, general and administrative expense rose more than revenue: the respective changes were only +1.531 million, +2.295 million, and +2.099 million, so the first comparison was false [30], [31]. CSGP's first final answer incorrectly said a tax-line change did not offset a USD 23.9 million operating-result decline. The tax contribution improved by USD 30.3 million, while a separate USD 37.0 million unfavorable other-income/expense swing helped explain the fall in net income [32], [33]. Both ledgers correctly held their research decisions, but a correct state transition did not certify the analysis. A free replay of the saved review calls showed that the arithmetic guard missed RPAY's false comparison inside the review, whereas CSGP's erroneous sentence appeared only in post-tool final prose. The former is a guard-coverage gap; the latter lies outside a pre-commit guard's scope. Thus the panel demonstrates that a useful report is attainable and that the runtime can preserve cautious decisions, while also exposing concrete semantic failure boundaries. The raw answers, copied ledgers, hashes, and diagnostic review are retained in the evaluation archive.

### Real-Source Candidate and Live Skill-to-Ledger Paths

Two smaller cases extended the input boundary beyond synthetic tools. A historical AMD/Intel screening replay used locally frozen and SHA-256-checked SEC disclosures, passed two declared GAAP thresholds to `screen_stocks`, and saved one source-linked preliminary AMD thesis while rejecting Intel. Its original mechanical checks and independent read-only adjudication passed. It did not call a live market-data source or validate a general seven-factor investment screen.

A separate online AMD case exercised a longer runtime path within one isolated Go Gateway session: the agent used an installed FinData Toolkit Skill through `exec` to retrieve five dated Nasdaq daily bars, used a second `exec` call for local arithmetic, and called `thesis_save` to create one tenant-scoped preliminary research thesis. The first and latest closes were 570.82 on 14 October 2026 and 534.74 on 20 October 2026. Independent recomputation gives a first-to-latest change of -6.3207%; the persisted evidence rounded this to -6.32% and retained the source URL, dates, closes, and one-day bar interval. The source payload did not specify currency or adjustment basis, so the thesis labelled USD as an inference and did not cite earnings or valuation data. The ledger copy contains one `researching`, conviction-1 thesis, no alert, and no review; the trace contains one market-data Skill fetch, one arithmetic execution, one thesis save, and a matching result for each call. All four model calls were priced, with USD 0.002679208 in estimated model cost. The original result was marked `needs_review` because the first scorer counted the legitimate arithmetic `exec` as a second fetch and recognized only one of two equivalent percentage field names. An independent read-only adjudication of the retained result and SQLite ledger passed its eleven execution, source, arithmetic, and state checks without altering the original result.

This online case demonstrates that a Skill-packaged external data script and the native finance ledger can participate in one model-driven workflow. It is one selected feasibility observation, not evidence of stable live availability or investment insight. The first observation's final prose contained an incorrect adjacent-day direction; the independent second observation corrected that direction, but neither establishes broad semantic quality. In the archived observation, a price-only `researching` thesis was stored with `decision_hold=false` and `actionability=available` despite explicitly missing fundamental and valuation evidence. A subsequent serializer change returns `research_only` for `researching` or `watch` theses and `closed` for invalidated or archived theses, while an event decision hold still returns `blocked`. Plugin tests and a read-only replay against the archived ledger confirm the new state presentation; the original model result was not revised or rerun. The event-review missing-metric guard still cannot be claimed for new preliminary theses, and an `active` thesis is not automatically proof of complete fundamentals or valuation.

## D. Validity Preconditions and Answers to the Empirical Questions

**VP1—Selected runtime control paths.** The passing unit and integration tests, together with explicit tests for cancellation, stream failure, task snapshots, tenant scope, and session normalization, support the feasibility of selected runtime control paths. The result is functional verification rather than formal proof or production certification.

**RQ2—Execution-mode trade-offs.** The fixed-evidence studies did not establish a Team accuracy advantage. In the 24-configuration SEC main study, shared-retrieval Team passed 56/72 assigned attempts and staged Solo passed 55/72, including two Solo infrastructure timeouts; paired outcomes included ten Team-only passes and nine Solo-only passes. The separate all-Flash comparison isolates model tier more closely: Team passed 19/24 versus Solo's 24/24, but Team was faster in all 24 pairs. The current runtime thus offers two useful but non-dominating execution paths. No result establishes universal superiority or equivalence.

**RQ3—Context allocation and efficiency.** The Stage 2A main study found shared-retrieval Team lower in aggregate tokens and frozen-price estimated cost than raw-context Team, but raw-context Team had more strict passes and shorter mean latency. Relative to staged Solo, shared-retrieval Team was faster, while the main-study model assignments differed. Under the separate all-Flash comparison, shared-retrieval Team remained faster but used more tokens and had lower strict completion. The Pilot's single-case cost and grounding differences remain historical calibration observations rather than the principal result. No tested mode dominates every required quality and efficiency dimension.

**VP2—Selected financial-workflow invariants.** Thirty-five current plugin tests cover ledger, alert, evidence, and partial-portfolio-bound rules. The six-case fixture study validates delegation and prose but makes no finance-tool call. In eight SEC event-to-thesis attempts, every isolated ledger held one versioned review and acknowledged alert. The 80-attempt tool panel extends execution to four workflows, including ten blocked missing-evidence reviews; one online Skill run fetched market data and saved a preliminary thesis. None tests broad decision accuracy, repeated-event idempotency, Team-mode state mutation, or price-only thesis eligibility.

## E. Evaluation-Proposition Resolution

The declared evaluation propositions are resolved against the retained evidence rather than inferred from the direction of a preferred result:

| Proposition | Current resolution | Evidence boundary |
|---|---|---|
| EP1 | Partially supported for selected paths | Executable tests cover selected control paths, but do not constitute formal verification or production assurance. |
| EP2 | Partially supported as a trade-off, not a quality gain | Team was faster in the all-Flash comparison, but Solo had higher strict completion and evidence retention. The main study mixed model tiers. |
| EP3 | Partially supported for resource use, not overall dominance | Shared retrieval reduced main-study raw-Team tokens and estimated cost, but raw Team had more passes and shorter mean latency. |
| EP5 | Partially supported for bounded workflows | Plugin tests cover state rules; eight event reviews persisted, and a repeated tool panel plus one live Skill case widened execution coverage. Decision quality and preliminary-thesis eligibility remain unproved. |
| EP6 | Partially supported for resource use | Raw-context Team used more tokens and estimated cost than shared-retrieval Team in the main study, but also achieved more strict passes; context replication was not waste under every outcome criterion. |

These labels describe support within the tested configurations; none is a population-level confirmation.

# VIII. DISCUSSION

## A. The Runtime as an Experimental Intervention

Agent evaluation is often framed as a comparison between models, but the observed output is produced by a coupled system. Prompt assembly determines which evidence is visible; the tool registry determines which actions are possible; the queue and cancellation model determine whether a plan completes; session repair determines whether the next provider call is valid; and the grader determines whether an equivalent answer is accepted. The runtime is therefore part of the experimental treatment rather than neutral infrastructure.

This observation constrains interpretation: academic reporting should identify model, runtime, evidence, policy, and grader as separate experimental factors. The measured object is not merely the generated text, but the retained trajectory interpreted by a declared outcome oracle.

This framing changes what “runtime improvement” should mean. Lower latency is a runtime property only if provider load, model output length, and baseline call count are controlled. Higher success is a runtime property only if evidence and grader are controlled. Better attribution may result from a clearer specialist contract rather than a more capable specialist. The report therefore treats observability and replay as prerequisites for causal claims.

## B. When Multi-Agent Execution Is Justified

The financial scenarios show that multi-agent execution should be selective. A specialist is justified when it provides independent evidence interpretation, a parallel deep dive, a formal challenge, or a distinct policy perspective. It is not justified merely because a tool has a financial label. Market-data retrieval, ratio calculation, threshold comparison, fingerprinting, and state persistence are deterministic operations and should remain tools.

The `solo_open_book`, `solo_two_pass`, and routed-diagnostic baselines provide a practical decomposition. If Team does not exceed Open-Book, delegation adds overhead without detected outcome benefit. If Team does not exceed Two-Pass, additional synthesis compute rather than role specialization may explain the outcome. If the routed diagnostic exceeds Team, routing or specialist execution is a candidate bottleneck; if Team exceeds it, named roles, the diagnostic prompt, or direct evidence presentation may alter synthesis. The diagnostic is therefore a candidate comparison, not an oracle upper bound.

The contrast between the initial-observation and longitudinal SEC suites clarifies the role of task difficulty. The simple suite was saturated by all four modes and could not measure incremental accuracy. The longitudinal suite created mode-level failures, but the frozen Team and Open-Book rates remained equal. Difficulty is therefore a necessary condition for avoiding a ceiling effect, not sufficient evidence that collaboration adds value. The AMD failure further shows that a correctly routed specialist can still return no usable evidence; a multi-agent treatment includes availability, response validation, and retry policy as well as nominal role decomposition.

The completed SEC study distinguishes role count from information flow more clearly than the earlier Pilot. In the main heterogeneous deployment, shared retrieval reduced Team token use and frozen-price estimated cost relative to raw-context Team, but raw context achieved more strict passes and lower mean latency. In the capacity-matched all-Flash subset, shared-retrieval Team was consistently faster than staged Solo, whereas Solo completed every selected task and retained all required final evidence. Evidence compression and parallelism are therefore engineering controls with measurable benefits and failure modes, not automatic improvements to every metric.

Selective delegation is the practical implication. The same runtime can execute a staged Solo workflow when completeness and evidence retention are paramount, or admit parallel specialists when latency matters and their outputs can be checked for missing calculations and evidence groups. Deterministic data collection and state mutation remain tools. Team and Solo are operating modes of the artifact, not rival products; a future admission policy should select by task constraints rather than defaulting to delegation.

## C. Financial Value Without Autonomous Trading

The application’s value proposition is research-process quality rather than direct return prediction. The system can reduce repeated data collection, expose missing fields, preserve thesis history, surface invalidation conditions, suppress duplicate alerts, and structure disagreement. These outputs are useful even when the final investment decision remains human.

This boundary is also methodologically useful. Return prediction introduces market regime, benchmark selection, turnover, transaction cost, corporate actions, survivorship, and look-ahead confounders. Workflow correctness can be evaluated first with deterministic evidence and state oracles. Predictive evaluation may then be added as a separate layer after the data pipeline satisfies point-in-time requirements.

The fixed-evidence finance experiment occupies an intentionally narrow position in that stack: it measures whether the coordinator reproduces supplied evidence and states a bounded governance decision. The retrieval track extends the boundary to source-locked archived SEC records, explicit evidence selection, specialist summaries, and final synthesis. The tool-backed panels add actual finance-tool calls and persistent ledger mutations, while the isolated live Skill case adds one external market-data fetch before thesis creation. The latter does not validate autonomous filing discovery, all financial tools, broad semantic accuracy, or subsequent portfolio outcomes. Its unblocked price-only thesis is a concrete gap between preliminary research capture and decision eligibility. These separate tests improve diagnosis without validating investment advice.

Return-based analysis should be added only after the data pipeline supports point-in-time constituent universes, dated `as_of` snapshots, corporate-action adjustment, delisting coverage, and explicit look-ahead prevention. It must remain separate from workflow correctness: a system can preserve evidence correctly without profitable forecasts, while a profitable backtest can still be invalid if it leaks future information.

## D. Quality–Cost Trade-off

However, lower cost is not inherently better. The appropriate objective is the minimum cost that satisfies a fixed evidence and outcome standard. The frozen finance confirmation separates uncached prompt, cache-read, completion, provider total, latency, and cost. Team cost USD 0.008335, compared with USD 0.005510 for one-pass Open-Book and USD 0.017798 for Two-Pass, while all three passed 5/6 cases. Under billable-like token accounting Team used 41.6% fewer tokens than Two-Pass; under provider total accounting it used 33.7% more. This sign reversal shows why one undocumented token field cannot support an efficiency claim.

A practical deployment should optimize a Pareto surface rather than one scalar. The relevant dimensions include strict task outcome, configured attribution, latency percentile, priced cost, and infrastructure error rate. A mode is dominated only if another mode is no worse on every required dimension and better on at least one. In the six-case confirmation, Open-Book is cheaper and faster than Team at the same pass count, whereas Team is cheaper and faster than Two-Pass at the same pass count. The evidence is too limited to justify routing every request through specialists.

The repeated SEC study adds context allocation to this surface. In the heterogeneous main run, shared retrieval reduced aggregate Team token use and estimated cost relative to raw context but did not dominate it on strict pass or latency. In the all-Flash subset, Team reduced latency relative to staged Solo but had lower strict completion and slightly higher token use and estimated cost. A routing policy should select execution mode according to a declared completion threshold and latency budget, then verify calculations and evidence before accepting a faster Team response.

## E. Generalizability

The architecture generalizes to domains that combine deterministic state with interpretive judgment, such as compliance review, incident response, customer operations, and scientific evidence synthesis. The financial scenarios are nevertheless domain specific. Thesis invalidation, portfolio concentration, and announcement deduplication encode assumptions that may not transfer directly to credit underwriting, high-frequency trading, or personal financial advice.

Generalization should therefore be tested at the mechanism level. Tenant isolation, bounded execution, tool-call pairing, correlated delegation, and evidence provenance are domain-independent mechanisms. The finance case oracles and research methodology are domain-specific configurations layered on top of them.

## F. Threats to Validity

TABLE_CAPTION: Principal threats to validity and mitigation status.

| Validity class | Threat | Consequence | Current mitigation or required action |
|:---|:---|:---|:---|
| Construct | Lexical matcher approximates semantic attribution | Correct inflections fail; hedged forbidden phrases pass | Preserve outputs, version grader, report ablation; validate entailment separately |
| Construct | The confirmation observes prose, not state mutation | Workflow wording can be mistaken for ledger correctness | Separate plugin tests from runtime text results |
| Construct | Fixed-evidence specialists copy compiled evidence verbatim | The confirmation does not measure retrieval or specialist evidence selection | Keep fixture and archived-SEC tracks separate; do not pool their claims |
| Construct | Numeric corpus membership approximates grounding | Supported-looking values may lack semantic entailment | Preserve claim/value diagnostics; add human-reviewed claim-to-evidence labels |
| Construct | Declared evidence-completeness rule depends on trusted ingestion metadata | A false `observed_metrics` claim could bypass the missing-field check | Keep event ingestion outside the review agent's tool policy and check fact IDs against the source-locked packet; plugin guard alone does not verify source content |
| Construct | Provider total includes cache reads inside prompt | Efficiency direction can reverse | Report billable-like and provider totals together |
| Internal | Gain guard checks counts, not pair identifiers | Misaligned cases could produce invalid gain | Pair manually by case/repetition; add identifier guard |
| Internal | Retrieval Pilot modes were not randomized | Provider load, cache state, or order can confound latency | Seed and randomize mode order within case–repetition blocks |
| Internal | The researcher authored the runtime, suite, and deterministic graders | Design choices or post hoc interpretation may favor the artifact under study | Freeze source and grader inputs; retain content-addressed outputs; disclose the single-reviewer source/oracle check and sensitivity limits |
| Internal | All-Flash selected reports span two run batches | Provider conditions may affect latency despite within-case pairing | Preserve batch identity and avoid a provider-invariant latency claim |
| External | SEC study has four issuers, eight company–task clusters, and one provider family | Results may not transfer to other issuers, task types, loads, or providers | Extend the task and provider panel before generalizing |
| External | Main Team/Solo model experiments did not call finance tools; a later eight-attempt Solo panel used pre-ingested events | Live ingestion and Team-mode ledger mutation remain untested | Extend the bounded ledger panel to autonomous event retrieval and Team/Solo execution |
| Conclusion | Repetitions and corpus loads reuse eight company–task source clusters | Treating all observations as independent overstates precision | Report paired counts and cluster-aware uncertainty; do not claim a population effect |

The table makes the central limitation explicit: measurement and capability are entangled. The present evidence is strongest where executable tests define a transition and weakest where natural-language wording stands in for semantic or persistent state correctness. The recommended next experiment is therefore not simply “more cases.” It is a prespecified separation of evidence source, runtime policy, orchestration mode, and grader version.

# IX. SECURITY, ETHICS, LIMITATIONS, AND FUTURE WORK

## A. Security Controls

The system applies defense in depth and treats risk management as a lifecycle activity rather than a single filter [14]:

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

The financial research application is an assistant, not an investment adviser or execution engine. It may organize evidence, apply deterministic calculations, maintain a thesis record, and propose a reversible review action. It must not promise return, infer suitability, size a position for a client, or place an order. NIST AI RMF emphasizes explicit human roles and responsibilities for decisions and oversight [14]. In this application, a human remains accountable for accepting evidence, changing portfolio policy, and authorizing any irreversible external action.

Auditability does not eliminate responsibility. A trace can show which evidence identifier, policy preset, agent, model, and tool call contributed to an answer, but it does not certify that the evidence was licensed, complete, current, or fair. Real deployments must document data rights, retention, market-data terms, and whether generated commentary is shown to a client. Sensitive account or portfolio information must not be placed in model prompts or logs without an approved data-processing basis.

The fixed benchmark evidence is synthetic and avoids personal or client data. This reduces privacy risk but also removes realistic retrieval ambiguity. Any expanded archived-data experiment should preserve publication time and source licenses, redact personal information, and separate research evaluation from any live portfolio workflow. Human reviewers should see evidence and proposed state changes before acceptance, not only a fluent final narrative.

## C. Current Limitations

First, the agent-level turn gate serializes all sessions of one agent because the registry stores mutable session-bound state. The TaskQueue can run different agents concurrently, but true per-session concurrency for one agent requires immutable per-turn registries or a per-session gate.

The per-chat FIFO guarantee begins at successful channel enqueue. Two callers that submit concurrently can acquire task identifiers under the mutex and then race when sending after the mutex is released, so identifier order is not a formal enqueue-order guarantee. This does not permit two tasks from one chat channel to execute simultaneously, but callers must not infer a total order from wall-clock invocation or task identifiers under concurrent submission.

Second, session appends are individually persisted rather than committed as one transaction. Normalization repairs interrupted histories, but transactional batch append would provide a stronger consistency model. Store-backed reads can fail open to a stale in-memory session on store error, so cross-replica freshness is best effort rather than guaranteed.

Third, Skills are currently injected in full. Installing a large financial Skill library can consume context and distract the model. On-demand loading is not connected to the production registry, and some Skill paths are prompt-visible without equivalent sandbox mounts. Progressive disclosure should initially expose only names and descriptions, then register and test on-demand loading for one to three selected methods.

Fourth, the fixed-evidence confirmation and original retrieval Pilot have one repetition and remain exploratory. The later SEC study executes 24 configurations with three repetitions per primary mode; the all-Flash supplement covers eight selected configurations. These observations are not official benchmark scores or population estimates. Loads and repetitions derived from a company–task source set must not be counted as independent issuers, and the all-Flash selected reports span two batches.

Fifth, the configured attribution and numeric-grounding graders are lexical and local. The fixed-evidence matcher handles direction, negation, quotation, decimal punctuation, conditional scope, and conservative plural normalization, but rejects `estimated` for required `estimate` and exempts a forbidden phrase after `may`. The retrieval grader checks whether numeric forms are authorized by source records or declared calculations; it does not prove that the surrounding sentence is entailed. Claim-level evidence linking and human validation are required for broader factuality claims.

Sixth, SQLite WAL improves concurrent runtime behavior but changes backup semantics: the main database file is not a complete live backup while uncheckpointed changes remain in sidecars. Operational documentation and deployment automation must account for this.

The MessageBus wait graph, TaskQueue, correlation map, and deduplication cache are process-local. The daemon can restart a failed Gateway, but it cannot replay volatile work or determine whether an interrupted external side effect occurred. PostgreSQL support does not make the scheduler distributed, and active-active Gateway replicas do not yet have lease, partition ownership, or durable-queue semantics.

Seventh, the financial layer lacks persistent portfolio holdings and policy limits, outbound alert delivery and retry state, and exchange-calendar-aware scheduling. It also lacks a point-in-time market data store suitable for unbiased backtesting, and Finskills remains an external, unvendored dependency.

Finally, the fixed-evidence confirmation uses compiled, verbatim-copy specialist evidence, while the SEC Pilot and repeated Stage 2A study use archived records and model-based evidence selection. Those studies did not invoke finance tools or mutate the ledger. Later tool-backed panels persist reviews, alerts, screens, and preliminary theses, but their SEC events are pre-ingested or historical and other inputs include synthetic fixtures. The online Skill observation verifies one live market-data fetch and ledger creation, not autonomous filing discovery, repeatability across upstream outages, or a broadly reliable financial workflow. Its isolated agent used a broad tool preset rather than a command-level Skill allowlist, and price-only preliminary theses are not automatically held from downstream decisions. These are engineering gaps, separate from the subjective value of financial insight.

## D. Future Work

The highest-priority future work is:

1. extend the SEC experiment beyond four issuers and one provider family, preserving paired, randomized execution and cluster-aware reporting;
2. add claim-to-evidence links and validate semantic judgments against independent human labels;
3. optionally repeat the matched Team/Solo comparison with other model tiers to test transfer beyond the completed all-Flash subset;
4. extend the finance-tool and live-Skill paths to autonomous event acquisition, repeated-event idempotency, adverse evidence, and paired Team/Solo execution; add a narrow Skill-command policy and a decision-eligibility guard for price-only preliminary theses;
5. add in-flight model-call, token, cost, and latency budgets together with per-session concurrency;
6. add transactional session append, progressive Skill loading, portfolio policy state, alert delivery, and exchange-calendar support;
7. design durable admission, lease ownership, idempotency, and replay semantics before active-active deployment;
8. construct point-in-time financial datasets before evaluating investment performance.

# X. CONCLUSION

This report treated an LLM agent as a controlled software runtime rather than a prompt wrapper. The implemented runtime turns a reasoning–action loop into an authenticated, tenant-scoped, stateful, streaming execution system. Its principal mechanisms are per-chat FIFO scheduling with bounded root admission, correlated internal messaging with cycle prevention, policy-filtered tools, consistent terminal events, session-history repair, fail-closed identity loading, request-scoped evaluation tools, and per-call usage attribution. These mechanisms require explicit invariants: every assistant tool call must receive one result, every protected target must be authorized after resolution, and every waiting sub-agent lane must preserve an acyclic graph.

VP1 is supported only for selected tested control paths. Unit and integration tests exercise authentication, provider parsing, cancellation, panic containment, internal calls, task snapshots, storage contention, and evaluation reporting. They demonstrate functional feasibility, not formal verification or production assurance; measured statement coverage remains approximately 27.2% for runtime and production packages.

RQ2 is resolved as a bounded execution-mode comparison, not a claim that Team improves financial judgment. In the six-case fixed-evidence confirmation, Team, Open-Book, and Two-Pass each passed 5/6 cases. In the repeated SEC main study, shared-retrieval Team passed 56/72 assigned attempts and staged Solo 55/72, including two Solo provider timeouts. In the separate 24-pair all-Flash comparison, Solo passed 24/24 and Team 19/24, while Team completed every pair faster. These observations show different operating advantages within one runtime, not an inherent ranking of agents.

RQ3 has repeated but configuration-bounded evidence. The Stage 2A main study shows that shared retrieval reduced Team tokens and frozen-price estimated cost relative to raw-context Team, whereas raw context produced more strict passes and lower mean latency. In the all-Flash subset, Team mean latency was 22.42 seconds against Solo's 33.62 seconds, but Team used more tokens and estimated cost and had lower strict completion. The main study's heterogeneous model allocation, the supplement's limited eight configurations and two run batches, and provider variability prevent a general model-independent or causal claim.

VP2 has bounded end-to-end support beyond deterministic plugin tests. An eight-attempt event-to-thesis panel persisted source-linked reviews and alerts; a 16-case, five-repetition panel produced 77/80 mechanical passes, including ten missing-evidence holds; one live Nasdaq Skill run retrieved prices, calculated a return, and saved an isolated preliminary thesis; and a policy-bound retest completed ten source-linked partial-portfolio observations. These paths demonstrate tool and state integration, not analytical reliability. A non-independent content review identified 13 problematic answers in the 80-attempt panel; the fresh-issuer SEC panel produced no high-within-case answers and two problematic answers in 15 attempts; and the policy-bound retest still had one unsupported core inference. The archived price-only thesis also exposed a mistaken `actionability=available` state; a later deterministic serializer fix addresses that presentation defect but is not a prospective quality result. These findings constrain any claim of stable financial insight quality.

The principal contribution is a measurement-oriented, auditable agent runtime that permits both Solo and Team operation. The system makes runtime policy, evidence visibility, execution errors, and role-specific cost and latency inspectable. The results favor selective mode choice: Solo offers stronger strict completion in the tested all-Flash subset, while Team offers lower latency at a measurable quality and resource trade-off. The later preliminary-thesis actionability fix addresses one state-presentation defect but has not been evaluated in a new model-backed workflow panel. The evidence remains stronger for engineering auditability and execution-mode characterization than for superior financial judgment.

The revised 103-task SEC source/oracle packet has the owner's single-reviewer confirmation and a 42/42 AI technical pass for evidence groups. This improves input traceability, not certification of generated analysis. All 24 configuration reports and manifests are retained. The optional 24-observation all-Pro ablation was not run.

Future work should test other providers, autonomous ingestion, repeated events, human-reviewed claim-to-evidence links, and decision eligibility for price-only stubs. Return-based evaluation also requires point-in-time data, corporate-action and delisting coverage, and trading-cost controls. The system is a research copilot and runtime evaluation platform, not evidence of investment performance.

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

During execution:

1. retain case, repetition, mode, session identifier, and root execution identifier;
2. retain model-call role, call path, token usage, cache usage, latency, and error state;
3. retain tool-call identifiers, tool results, and delegation targets;
4. distinguish model/tool failure from timeout, transport, authentication, or provider failure;
5. retain the realized randomized mode order;
6. stop the run if sources, evidence fixtures, graders, model aliases, or pricing change.

After execution:

1. report evaluated and errored attempts separately;
2. report raw counts with rates and confidence intervals where repetition permits;
3. calculate only the track-specific predeclared paired effects;
4. report Team-only latency and tokens in addition to full-harness totals;
5. disclose simulated specialists, omitted cases, reruns, and pricing assumptions;
6. use company–task cluster-aware intervals for retrieval configurations;
7. archive machine-readable results together with a human-readable failure analysis.

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

[18] The Go Authors, “The Go Memory Model,” version Jun. 6, 2022. [Online]. Available: https://go.dev/ref/mem. Accessed: Sep. 23, 2026.

[19] The Go Authors, “Package context,” Go Packages. [Online]. Available: https://pkg.go.dev/context. Accessed: Sep. 23, 2026.

[20] The Go Authors, “Package sync,” Go Packages. [Online]. Available: https://pkg.go.dev/sync. Accessed: Sep. 23, 2026.

[21] SQLite Consortium, “Write-Ahead Logging.” [Online]. Available: https://www.sqlite.org/wal.html. Accessed: Sep. 23, 2026.

[22] SQLite Consortium, “SQLite Backup API.” [Online]. Available: https://www.sqlite.org/backup.html. Accessed: Sep. 23, 2026.

[23] PostgreSQL Global Development Group, “Concurrency Control,” PostgreSQL 17 Documentation, ch. 13. [Online]. Available: https://www.postgresql.org/docs/17/mvcc.html. Accessed: Sep. 23, 2026.

[24] Marqeta, Inc., “Second Quarter 2025 Earnings Release,” exhibit to SEC filing accession 0001522540-25-000020, Aug. 6, 2025. [Online]. Available: https://www.sec.gov/Archives/edgar/data/1522540/000152254025000020/mqearningsrelease-q2x2025.htm

[25] Marqeta, Inc., “Third Quarter 2025 Earnings Release,” exhibit to SEC filing accession 0001522540-25-000033, Nov. 5, 2025. [Online]. Available: https://www.sec.gov/Archives/edgar/data/1522540/000152254025000033/mqearningsrelease-q3x2025.htm

[26] American International Group, Inc., “Second Quarter 2025 Earnings Release,” SEC exhibit, Aug. 6, 2025. [Online]. Available: https://www.sec.gov/Archives/edgar/data/5272/000000527225000077/q22025earningsrelease.htm

[27] American International Group, Inc., “Third Quarter 2025 Earnings Release,” SEC exhibit, Nov. 4, 2025. [Online]. Available: https://www.sec.gov/Archives/edgar/data/5272/000000527225000156/q32025earningsrelease.htm

[28] M&T Bank Corporation, “Second Quarter 2025 Earnings Release,” SEC exhibit. [Online]. Available: https://www.sec.gov/Archives/edgar/data/36270/000162828025034994/ex991release2q25.htm

[29] M&T Bank Corporation, “Third Quarter 2025 Earnings Release,” SEC exhibit. [Online]. Available: https://www.sec.gov/Archives/edgar/data/36270/000003627025000018/ex991release3q25.htm

[30] Repay Holdings Corporation, “Second Quarter 2025 Earnings Release,” SEC exhibit. [Online]. Available: https://www.sec.gov/Archives/edgar/data/1720592/000172059225000010/rpay-ex99_1.htm

[31] Repay Holdings Corporation, “Third Quarter 2025 Earnings Release,” SEC exhibit. [Online]. Available: https://www.sec.gov/Archives/edgar/data/1720592/000119312525274223/rpay-ex99_1.htm

[32] CoStar Group, Inc., “Second Quarter 2025 Earnings Release,” SEC exhibit. [Online]. Available: https://www.sec.gov/Archives/edgar/data/1057352/000105735225000095/q22025earningspressrelease.htm

[33] CoStar Group, Inc., “Third Quarter 2025 Earnings Release,” SEC exhibit. [Online]. Available: https://www.sec.gov/Archives/edgar/data/1057352/000105735225000116/q32025earningspressrelease.htm
