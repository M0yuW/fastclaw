TITLE: Design and Evaluation of an Agent Runtime with Financial Research Applications
AUTHOR: Zheyu Wang
AFFILIATION: Faculty of Information Science and Computing, University of Macau
EMAIL: mc45505@um.edu.mo
REPORT DATE: October 2026

ABSTRACT: Large language model agents need a runtime to manage conversations, execute tools, coordinate tasks, and save application state. This report presents the design and evaluation of a multi-tenant agent runtime with financial research applications. The runtime supports staged single-agent execution and optional collaboration between a coordinator and specialists. Both modes use the same session, scheduling, tool, and storage mechanisms. Authentication, execution limits, cancellation, and traces help control and inspect each task. Four financial workflows use these mechanisms: earnings-event review, candidate screening, portfolio risk diagnosis, and review of conflicting or incomplete evidence. Deterministic tools process data and calculations, while the model interprets the evidence and proposes research decisions. Evaluation covers runtime tests, repeated Solo and Team comparisons, and end-to-end application cases. The results show trade-offs in completion, latency, evidence retention, and resource use. Selected analyses of public disclosures also show how the system can produce useful research outputs. Their quality still depends on the model, available evidence, and task design.

INDEX TERMS: LLM agents, agent runtime, financial research, multi-agent systems, tool calling, session management, workflow execution, tenant isolation, observability.
ABBREVIATION: ACL | Agent access-control list
ABBREVIATION: API | Application programming interface
ABBREVIATION: BFCL | Berkeley Function-Calling Leaderboard
ABBREVIATION: CI | Continuous integration
ABBREVIATION: DFS | Depth-first search
ABBREVIATION: FIFO | First in, first out
ABBREVIATION: LLM | Large language model
ABBREVIATION: MCP | Model Context Protocol
ABBREVIATION: P50/P95 | 50th/95th latency percentile
ABBREVIATION: SSE | Server-sent events
ABBREVIATION: WAL | Write-ahead logging

# I. INTRODUCTION

Large language models (LLMs) can answer questions, generate code, and invoke tools. A dependable agent also needs software to manage the work around those calls. It must receive requests, preserve conversation history, enforce tool permissions, handle failures, and stream progress to users. A multi-user service must also authenticate callers, isolate their data, control concurrency, and cancel work when requested. Delegation adds another concern: agents must not create circular waits or repeat tasks without limit.

ReAct [1] describes a cycle in which a model reasons, takes an external action, and uses the resulting observation to decide what to do next. A runtime turns this interaction pattern into an execution process that can be controlled and tested. It must handle failed model requests, tool timeouts, client disconnections, and incomplete conversation histories. It must also manage repeated specialist calls. These are execution problems that cannot be assessed from the final answer alone.

Financial research combines data processing with judgment. An earnings release may prompt a review of an investment thesis. Screening may identify a candidate for further research, while a portfolio query may require a concentration or risk calculation. The application connects these tasks to tools, reusable research procedures, and persistent records. It supports evidence collection, analysis, and monitoring; a human remains responsible for portfolio actions. The runtime is separate from the financial tools, so the same execution mechanisms can serve other workflows.

This report makes three contributions:

1. **Runtime design and implementation:** the runtime manages authenticated requests, tenant-scoped sessions, scheduling, and tool permissions. It also supports coordinator–specialist communication, cancellation, and execution traces. Solo and Team are alternative execution modes within the same runtime.
2. **Financial research applications:** four workflow families connect financial evidence and deterministic calculations to model interpretation, research records, alerts, and decision holds. Selected analyses of public disclosures illustrate the analytical work supported by these mechanisms.
3. **Engineering and application evaluation:** executable tests examine runtime controls, repeated experiments measure execution-mode trade-offs, and end-to-end cases check tool use, evidence, analytical outputs, and persistent state. The evaluation distinguishes successful execution from the quality of the resulting analysis.

The project asks how an agent runtime can control stateful execution and support financial research. The report describes the architecture and execution mechanisms, then explains the financial workflows built on them. Evaluation covers runtime controls, Solo and Team trade-offs, and application outcomes. Solo and Team are two execution choices within the same system.

# II. BACKGROUND AND DESIGN REQUIREMENTS

## A. From Tool Calling to an Agent Runtime

In structured tool calling, the model receives a list of functions with names, descriptions, and JSON schemas. It can either return natural-language content or emit one or more typed function calls. The application validates and executes those calls, appends each result to the conversation, and requests the next model step. This separates probabilistic planning from deterministic execution. The 28 July 2026 revision of the Model Context Protocol (MCP) standardizes hosts, clients, servers, resources, prompts, and model-controlled tools over a JSON-RPC 2.0 data layer [2], [3]. MCP defines an interoperability boundary; it does not define an application’s authorization policy, persistence model, queueing discipline, or experimental protocol. Those remain runtime responsibilities.

BFCL evaluates function selection, parameter construction, parallel calls, abstention, and stateful multi-step behavior with scalable structural comparison [4]. Tool calls have a structured form that can be checked directly. However, call accuracy does not reveal whether a queue dropped work, a stream hid an error, or tenant data was mixed. It also does not isolate the effect of tool permissions on model behavior. This project therefore uses BFCL-style cases as protocol checks rather than reporting an official BFCL score.

A runtime adds controls not supplied by the model: provider adaptation, session ordering, capability policy, sandbox binding, timeouts, telemetry, and terminal consistency. The proposed system treats the LLM as a planning component inside this larger state machine rather than as the owner of execution.

## B. Stateful and Multi-Agent Evaluation

Single-turn function accuracy is necessary but insufficient. τ-bench evaluates multi-turn interaction among an agent, a user model, domain policy, and database tools [5]. Two agents may produce similar answers while taking different actions. The recorded interaction shows whether those actions follow the domain policy. SWE-bench evaluates repository issue resolution by applying patches and running repository tests [6], making the environment and executable oracle part of the benchmark. MultiAgentBench measures task milestones and communication structures across collaboration and competition scenarios [7]. These benchmarks progressively add state, environment, and coordination, but they still evaluate a model or agent system inside a chosen harness. They do not ordinarily treat queue semantics, cancellation propagation, tenant scope, event-stream convergence, or grader normalization as independent variables.

These evaluation approaches motivate two related engineering needs: explicit runtime controls and measurements that reveal how those controls affect execution. Model parameters, visible evidence, available actions, runtime transition rules, and the grading criteria can all alter an observed result. The runtime therefore records tool calls, state transitions, timing, and resource use, while the evaluation preserves paired conditions and distinguishes execution errors from answer failures. This makes both application behavior and execution-mode comparisons inspectable.

The project uses small test subsets inspired by BFCL, τ-bench, SWE-bench, and MultiAgentBench to exercise selected protocol and execution behaviors; it does not report official benchmark scores. These checks support the runtime implementation. Financial application studies then examine whether its mechanisms work together across complete research workflows.

## C. Financial Research Requirements

Financial question-answering datasets such as FinQA [8] and TAT-QA [9] demonstrate the difficulty of numerical reasoning across narrative and tabular evidence. They primarily evaluate answer derivation from supplied documents. A financial research assistant also needs to record when evidence applies, identify missing data, save hypotheses, and recognize duplicate events. Research decisions must remain separate from portfolio actions. The present project does not reproduce the official FinQA or TAT-QA evaluations. Instead, it derives system requirements relevant to a deployable research copilot:

- source-aware data with freshness and completeness metadata;
- deterministic calculation for screening, risk, and event identity;
- explicit uncertainty when evidence conflicts or is incomplete;
- persistent, tenant-scoped research state;
- human approval before portfolio action;
- repeatable evaluation that does not use future returns as a convenient but misleading ground truth.

The report uses **evidence attribution** to mean that a material output claim is linked to a supplied evidence identifier. This is narrower than factual truth or semantic entailment. Research on knowledge-grounded generation distinguishes fidelity to evidence from fluency and subjectivity [10]. The lexical checks used here test attribution to supplied evidence. They do not verify every generated claim. BCBS 239 motivates accurate, complete, timely, and traceable risk-data aggregation at an institutional level [11], but it does not prescribe the implementation's `observed_at`, `as_of`, or `source_id` fields. The fields serve these provenance needs; they are not prescribed by the banking standard.

## D. Engineering Requirements

The resulting runtime requirements are:

1. **Isolation:** every request resolves to a real user, an authorized agent, a session, and a bounded workspace.
2. **Correctness:** assistant tool calls and tool results must remain correctly paired in persisted history.
3. **Control:** tools are filtered by policy, sandbox execution must not silently fall back to the host, and evaluation-only behavior must not affect production requests.
4. **Liveness:** cancellation, execution timeouts, bounded queues, and loop detection constrain admitted work; downstream calls must honor cancellation for execution deadlines to be effective.
5. **Observability:** model calls, tool traces, call paths, token usage, latency, and estimated cost must be attributable to coordinator and specialist roles.
6. **Evaluability:** Team/Solo comparisons must control evidence visibility, and infrastructure errors must not be counted as model failures.

## E. Validity Preconditions and Empirical Questions

The study uses two validity preconditions (VP1 and VP2) and two primary research questions (RQ1 and RQ2). These labels identify the checks and questions used throughout the evaluation.

1. **VP1—Selected runtime control paths:** Do executable tests support the specific tenant-scope, tool-call ordering, terminal-streaming, cancellation, and bounded-execution paths used by the experiments?
2. **RQ1—Execution-mode trade-offs:** Across fixed-evidence and retrieval-mediated conditions, how do coordinator–specialist Team and evidence-matched staged Solo differ in deterministic completion, evidence retention, latency, and resource use?
3. **RQ2—Context allocation and efficiency:** With tasks and source documents fixed, how do the four execution approaches differ in grounding, tokens, latency, and estimated cost? Which comparisons also hold model allocation fixed?
4. **VP2—Selected financial-workflow invariants:** Do deterministic tests support the specific provenance, completeness, version-transition, alert-identity, and human-decision boundaries exercised by the evaluation fixtures?

VP1 and VP2 are validity preconditions supported only for selected tested paths and invariants; they are not empirical claims of production reliability or complete workflow validity. RQ1 and RQ2 are the primary empirical questions. None of the model experiments executes a live portfolio action.

TABLE_CAPTION: Evaluation questions and the evidence used to address them.

| Question | What is measured | Principal evidence |
|---|---|---|
| VP1 Runtime control paths | Isolation, ordering, cancellation, terminal state, and bounded execution | Unit and integration tests; scheduler load check |
| RQ1 Execution modes | Paired completion, evidence retention, latency, and resource use | Repeated SEC main study and comparison using the same model |
| RQ2 Context allocation | Grounding, tokens, estimated cost, and latency by context topology | Shared-retrieval and raw-context runs; per-call telemetry |
| VP2 Financial workflows | Source links, ledger transitions, missing-evidence holds, and analytical content | Tool-backed panels, retained ledgers, and selected SEC case reviews |

## F. Threat Model and Design Principles

The protected assets are tenant identity, API credentials, conversation history, agent identity files, workspace objects, plugin-managed financial state, and the authority to execute tools. Trust boundaries occur at HTTP and channel ingress, provider responses, model-generated tool arguments, external tool and MCP results, plugin subprocesses, sandbox exits, store adapters, and internal sub-agent messages. The model and all retrieved content are treated as untrusted planners or data, not as authorization principals.

The threat model covers unauthorized agent access, tool calls that exceed policy, and plugins that trust model-supplied tenant identifiers. It also covers prompt injection from retrieved evidence and delegation cycles that exhaust concurrency. Execution risks include malformed streams that appear successful, incomplete histories that break tool-call ordering, and repeated work that exhausts cost or queue capacity. A compromised host, a malicious database administrator, and a provider that deliberately violates its API contract are outside the threat model.

The design follows fail-safe defaults, complete mediation, and least privilege as classical protection principles [12]. Every protected request must resolve to an identity. Authorization checks apply after the target agent is resolved, and policy removes denied tools before the model sees them. Trusted user scope travels outside model-controlled arguments. If sandbox startup fails, execution does not silently move to the host. OWASP guidance for agent systems similarly recommends per-tool authorization, untrusted-data separation, bounded tool chains, structured audit records, and human approval for high-impact actions [13]. The implementation's six-pattern prompt scanner is only an unvalidated heuristic layer. It cannot substitute for authorization, policy filtering, parameter validation, or human review.

Residual risks remain. Session reads currently fail open to an in-memory copy if the durable store returns an error, whereas required identity loading fails closed. These are different consistency policies and must not be described as one guarantee. API-key ACL checks are implemented for resolved OpenAI-compatible chat targets, but future endpoints still require complete-mediation regression tests. Native plugins and local MCP servers inherit subprocess and supply-chain risk; policy can reduce exposed tools but cannot prove that an allowed tool is benign. These limitations are revisited in Section IX.

# III. AGENT RUNTIME SYSTEM ARCHITECTURE

## A. Layered Architecture

The system is a Go-based, multi-user agent platform. The default executable starts the Gateway, database-backed store, workspace object store, plugin manager, task queue, channel manager, cron scheduler, setup/API server, and the embedded web interface. User spaces and agents are loaded lazily after authentication rather than preloading every tenant at startup.

Figure 1 locates the runtime controls between external ingress, model providers, extensible capabilities, and durable tenant state. The layers describe logical responsibilities. Built-in tools execute within the core runtime, while native plugins run in separate subprocesses on the same host and exchange JSON-RPC messages over standard input/output. MCP servers and sandbox commands have their own process, network, or container boundaries.

[[FIGURE_1]]

The architecture is divided into six logical layers.

1. **Ingress layer:** web chat, an OpenAI-compatible `/v1/chat/completions` API, WebSocket, Telegram, Discord, Slack, webhook, and scheduled messages.
2. **Identity and scope layer:** cookie sessions or Bearer API keys resolve a caller; an API key carries an explicit agent access list; the runtime stamps the effective user identity into the request context.
3. **Gateway orchestration layer:** the `MessageBus` normalizes inbound, outbound, and internal messages. The `TaskQueue` provides per-chat FIFO execution and process-wide concurrency control. A lazily loaded `UserSpace` groups each tenant’s configuration, agents, providers, skills, plugins, storage, and sandbox resources.
4. **Agent runtime layer:** a context builder assembles identity, policy, Skills, memory, and runtime metadata; the ReAct loop calls an LLM provider, executes tools, appends observations, and emits versioned events.
5. **Capability layer:** built-in tools, MCP tools, native JSON-RPC plugin tools, provider chains, Skills, and Docker or E2B sandbox executors.
6. **Persistence and telemetry layer:** SQLite by default or an unverified PostgreSQL deployment adapter; local, S3-compatible, or Aliyun-backed artifact storage; session history, agent files, scoped configuration, usage, traces, and evaluation reports.

## B. Ingress, Authentication, and Tenant Scope

All protected HTTP routes pass through the authentication resolver. The web UI uses a database-backed, HTTP-only session cookie. Programmatic callers use Bearer API keys stored as hashes; plaintext is shown only when a key is created or rotated. The resolved identity carries the user, role, authentication method, and API key’s authorized agents. The OpenAI-compatible endpoint first resolves the target agent, including any fallback, and then checks authorization. Omitting the agent header therefore cannot bypass the API key allowlist. An unknown explicit target is rejected rather than replaced by a fallback. A super administrator may inspect another user through read-only delegated scope, but mutation is rejected.

The Gateway does not invent a default tenant. Channel messages either carry a trusted owner from cron or webhook execution, or resolve ownership from a stored channel credential. If ownership cannot be established, the message is dropped. This fail-closed rule is important because a convenient “local user” fallback would convert an authentication failure into cross-tenant data exposure.

User configuration is layered by scope. System defaults, user-level settings, and agent-level overrides are merged when a `UserSpace` is loaded. The manager creates agents with a tenant-specific session store, memory adapter, workspace store, policy, provider, Skills configuration, and plugin tools.

## C. MessageBus and TaskQueue

External messages enter buffered channels in a normalized format. The TaskQueue creates a FIFO channel for each chat key and a goroutine that drains that queue serially. A counting semaphore limits independent root executions across the process. Each task records its state, timestamps, result, owner, agent, and observability metadata. After admission, each task receives an execution deadline derived from the shared timeout configuration. This deadline does not cover the preceding queue wait. Waiting for a root slot responds to request cancellation or queue shutdown; execution cancellation also requires downstream operations to honor the propagated context.

Internal sub-agent work inherits the root execution identifier. It does not acquire a second global semaphore slot, which prevents a coordinator from deadlocking when the configured maximum concurrency is one. Two limits apply independently. The TaskQueue has a 256-slot internal admission channel. The MessageBus allows up to 256 pending request correlations. They protect different resources and must be tuned together. The local completion callback is published at most once, but model calls, external side effects, and network delivery are not guaranteed to occur exactly once. Internal tasks retain request metadata while rebuilding cancellation links to both the request and queue shutdown. Using only the original cancellation chain could end nested telemetry too early. Detaching it without new links would instead leave internal work running after its parent stops.

Task-list requests return copies of task state rather than pointers to mutable records. The API authenticates the caller, filters tasks by accessible agent, and only then applies the response limit. This prevents unauthorized access to task metadata and avoids concurrent reads of mutable fields. A super administrator retains broader read access, including read-only `actAs` inspection.

A counting semaphore combines root admission directly with the existing per-chat goroutines and cancellation paths. It permits independent chat lanes to execute up to the configured bound while preserving FIFO order within each lane. A bounded worker pool is another viable design; at equal concurrency, long-running tasks can occupy capacity in either approach. The present tests do not establish a performance advantage over worker pools. Channels and mutexes synchronize access to task maps and the wait graph, as required by the Go memory model [14]. The code does not rely on the apparent order in which goroutines run.

## D. Provider Abstraction and Streaming

The provider interface supports both complete-response and streaming calls. OpenAI-compatible and Anthropic adapters convert runtime messages and tools into provider-specific wire formats. The adapters retain different raw data. The OpenAI-compatible adapter reconstructs an assistant payload from streamed fragments. The Anthropic adapter retains a thinking block when present, rather than a complete assistant message. These records support caching and replay, but do not preserve every provider message in a common format.

The streaming reader accumulates text, tool-call fragments, reasoning, signatures, and usage before publishing a terminal response. OpenAI-compatible requests ask for streaming usage and fall back when an endpoint rejects that option; Anthropic usage is assembled from streamed lifecycle events. The application distinguishes incremental content, convergent full snapshots, errors, incomplete terminal states, and stream closure. Deltas update the UI incrementally. If a client misses a delta, it can recover from the latest versioned snapshot. A required-identity failure reaches streaming clients as an error. Clients must interpret error and terminal events rather than treating stream closure alone as successful completion.

## E. Tools, Plugins, MCP, and Skills

The runtime uses one registry abstraction for tool definitions and executable functions. The built-in registry includes shell execution, file operations, messaging, memory search, and web fetching, with optional provider-backed web search, image generation, and text-to-speech. MCP servers can contribute tools to the same registry. Native plugins run as subprocesses that communicate through JSON-RPC 2.0 [3] over standard input/output and can provide tools, channels, providers, or hooks.

The plugin protocol carries trusted user, agent, and session identities. The runtime creates this scope after routing, outside model-controlled tool arguments. A stateful plugin can therefore reject calls without trusted context and query data by the authenticated tenant.

Skills are reusable instruction and workflow packages stored in layered directories. The loader reads five directory types: agent, team, user, managed, and extra. The bundled collection is currently empty. The loader checks operating-system support, required executables, and environment requirements. It also supplies configured environment variables. Only two fixed Skill roots are mounted into sandbox paths; team and extra paths can enter the prompt without equivalent filesystem mounts. The current implementation injects every enabled Skill in full. An on-demand loading helper exists, but it is not connected to the production registry. The runtime therefore cannot yet load Skill details only when needed. Skills describe methods, while tools perform atomic execution. The financial design in Section V uses typed tools or deterministic scripts invoked through a Skill-guided execution tool for data retrieval. Skills supply workflow instructions and script entry points; they do not confer execution authority outside the runtime's tool policy.

## F. Persistence and Workspace Storage

The database is mandatory. SQLite with write-ahead logging is the zero-configuration default. A PostgreSQL adapter is implemented but is not covered by the current automated tests. Its deployment behavior remains unverified. SQLite connections enable foreign keys, a five-second busy timeout, and immediate write transactions unless equivalent settings are already present. Session persistence may read before writing. Immediate transactions avoid the lock-upgrade problem in this pattern; a busy timeout alone is insufficient. WAL allows concurrent readers but only one writer. Deployments must monitor checkpoints and WAL growth [15]. Backups must use the SQLite online backup API or account for WAL sidecars rather than copying only the main database file [16]. The pinned driver and embedded engine versions are recorded in the repository for reproducibility. The unified store persists users, web sessions, API keys, agent ACLs, agents, conversation sessions, layered agent files, scoped configuration, channel credentials, and cron jobs.

Conversation sessions are keyed by channel and chat identifier and scoped by user and agent. In store-backed mode, the manager attempts to reload the session on every access. If a store read fails, the manager uses an in-memory copy when one exists. That copy may be stale. Reloading normally improves freshness across replicas, but does not guarantee that every request sees the latest stored history. This differs from required identity files, whose load failure stops the turn. Identity files are stored separately from user artifacts; workspace objects are namespaced by agent and optional session to prevent concurrent chats from overwriting one output name.

## G. Deployment and Failure Recovery Boundary

The implemented deployment unit is one Gateway process. It owns an in-memory MessageBus, TaskQueue, pending-correlation map, lazy user-space registry, channel manager, scheduler, plugin manager, and sandbox lifecycle pool. The SQL store and workspace object store retain durable state. Queue positions, pending request correlations, duplicate-suppression records, and cancellation links remain in memory within one process. Pointing two Gateway processes at PostgreSQL does not by itself create a distributed queue, a shared wait graph, or single-consumer channel semantics. Multi-instance active-active operation is therefore outside the demonstrated architecture.

Startup opens and optionally migrates the store, constructs the object store and usage meter, discovers enabled plugins, loads task-queue configuration, registers stored channel rows, and then starts background ingress and scheduling loops. Agents are loaded lazily only after an authenticated request resolves a real user. Configuration combines database-scoped settings with operations-managed environment overrides; credentials must remain in the environment or secret store rather than report artifacts.

On `SIGINT` or `SIGTERM`, the Gateway cancels its root context, waits for ingress, channel, scheduler, and cleanup loops, rejects and releases pending internal requests, stops the TaskQueue, stops plugins, and closes live sandboxes. Pending TaskQueue entries are marked cancelled, but the current shutdown path does not persist an externally replayable queue. A daemon wrapper can restart a crashed child with exponential backoff up to ten consecutive crashes, and launchd/systemd service templates can supervise the process. Supervision can restart the process, but cannot replay interrupted requests transparently. If an external tool may already have changed state, the client must treat the outcome as unknown.

Durable SQL and workspace state can be reloaded after restart, whereas pending queues, correlation waiters, and deduplication entries are process-local and are lost on a crash. An interrupted provider or external-tool request can therefore have an uncertain outcome and must not be retried as if exactly-once execution were guaranteed. SQLite deployments also require a coordinated checkpoint or online backup because the main database file alone may omit changes still present in WAL sidecars [15], [16].

For a single-host development or small deployment, SQLite and the local workspace provide the shortest operational path. Larger deployments require validation of the PostgreSQL adapter and remote object store, together with a separate distributed-admission and ownership design before multiple active Gateway replicas can safely share work.

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
ALGORITHM_STEP: 6. If no tool call exists and final-response validation passes, persist the assistant message, flush the session, emit `done`, and return; otherwise follow the bounded correction or incomplete-terminal path.
ALGORITHM_STEP: 7. Otherwise execute allowed tool calls concurrently; contain panics; append exactly one result for every call.
ALGORITHM_STEP: 8. Reject repeated exact calls, honor cancellation, and continue until a final answer or the iteration bound.
ALGORITHM_STEP: 9. Normalize and flush session state on every terminal path.

Before the first model call, the agent acquires a turn gate because the tool registry holds session-bound executor and workspace state. It then refreshes Skills, loads the session, repairs tool-call ordering, and binds the session sandbox. Required identity files are validated once and used to build the system prompt. Finally, the runtime appends the user message and compacts long history if needed.

Session-history compaction is a bounded-context safeguard, not a replacement for durable conversation storage. The current Go implementation estimates tokens from message text and tool-call arguments and checks an 80,000-token threshold at turn entry. When the estimate crosses that threshold, it first logs the full history and replaces long tool results older than the most recent 20 messages with a short marker. If pruning is insufficient, it asks the configured model to summarize the older messages while retaining those recent messages. A summarization failure falls back to the pruned history. This policy first removes lengthy tool output, then summarizes older conversation content. Token estimates are approximate, and a generated summary may omit earlier facts. The SEC experiment's retrieval stage serves a different purpose: it selects source records for an Evidence Bundle. Those experiments use isolated sessions and do not test history compaction.

The tool registry for the turn is then copied or overridden by request-scoped evaluation tools and filtered through the agent’s policy. The model never receives tools that the policy denies. This is stronger than allowing every tool and asking the prompt not to use some of them. The core state-machine invariant is that every persisted assistant tool-call block has one corresponding tool-result block before the next provider call. The history normalizer repairs interrupted calls at turn entry and runs again before terminal persistence.

For each iteration, the runtime makes one streaming model call, forwards content deltas, reads the terminal response, records usage, and decides between two transitions:

- **Final-answer transition:** append one complete assistant message, run post-turn hooks, flush the session, emit `done`, and return.
- **Tool transition:** append the assistant’s tool calls, emit trace events, execute the calls concurrently, append one matched tool result for each call identifier, and continue to the next model iteration.

An additional session-control mechanism supports task clarification in root conversations. When the model identifies missing information that materially affects the task, it can issue a structured clarification request. The runtime pauses the turn before running other tools in that response. It records that those calls were not executed and saves the question with an awaiting-clarification marker. The user's next reply supplies context for a new turn to continue the original task. This is a conversational pause, not a blocked worker, and it does not roll back actions completed in earlier iterations.

### Runtime Invariants and Repair Algorithms

Three invariants define the execution rules:

1. **Accepted-enqueue FIFO invariant:** for one `chatKey`, tasks are executed serially in the order in which they are successfully sent to that chat queue. Registration and queue insertion are separate operations. Concurrent callers may therefore enter the queue in a different order from their invocation times or task identifiers.
2. **Wait-graph invariant:** while the MessageBus lock is held, adding a source-to-target wait edge is permitted only when no target-to-source path already exists. Every accepted blocked internal call contributes one reference-counted edge, and completion, cancellation, publication failure, or shutdown removes it.
3. **History-shape invariant:** after normalization, each assistant tool-call position is followed by one matching result. The normalizer keeps the first unused matching result, marks a missing result as interrupted, and drops duplicate or orphan tool messages. This is structural provider validity, not proof that a tool executed exactly once or that its result is semantically correct.

Task admission, delegation, and history repair preserve these invariants. A chat lane accepts one task at a time; independent root tasks consume global capacity, while nested tasks inherit their root admission. An internal delegation adds a correlation waiter and a wait-graph edge only after checking ownership, capacity, and cycle freedom. The edge and waiter are released on reply, cancellation, backpressure, or shutdown. Before another provider call, history repair places each available tool result after its matching assistant call, inserts an interrupted-result marker when needed, and removes duplicate or orphan results.

The runtime detects three consecutive identical tool name/argument pairs and adds a loop warning. It also caps the number of tool iterations. Tool panics are recovered inside their execution goroutines and converted into explicit error results rather than terminating the Gateway process. Results are correlated by a consume-once call identifier; empty or duplicate identifiers produce explicit failures instead of silently copying another tool's result. Each tool records its own start time, duration, and hook context rather than inheriting a batch-level wall-clock duration.

## B. System Prompt and Identity Contract

The context builder combines runtime information, a user-message isolation policy, optional sandbox guidance, bootstrap files, Skills, long-term memory, group context, and reasoning-mode guidance. User text is wrapped in `<user_message>` tags only in the provider payload; the stored history remains clean for the UI.

Benchmark specialists can declare required identity files. Before a model call, the runtime loads those files once, rejects missing or empty content, and computes a short SHA-256-based revision identifier. The prompt uses this validated snapshot. This avoids a second database read and prevents the identity content from changing between validation and use. Store failures fail closed; only a confirmed not-found condition permits the legacy filesystem fallback. The revision proves that the expected identity material was loaded without exposing its contents in telemetry. Both streaming and non-streaming clients receive configuration errors.

## C. Tool Policy and Sandbox Binding

Policy presets include permissive, standard, restricted, `no-tools`, and `delegate-only`. The evaluation coordinator uses `delegate-only`, while fixed-evidence specialists use `no-tools`. When no file tools are allowed, related prompt guidance is also removed so the system prompt does not advertise capabilities the model cannot use.

If a sandbox pool is configured, the registry binds a session-specific executor at turn start. File and shell tools are re-registered against that executor. A `sandboxRequired` flag prevents silent fallback to host execution when the pool fails. Docker and E2B backends can therefore be exchanged behind one executor interface while retaining the same agent loop.

## D. Session Correctness and Streaming Semantics

Provider APIs require every assistant tool-call block to be followed by matching tool results. Client cancellation or a crash during tool execution can leave invalid history. The runtime repairs that history by matching available results to calls, marking interrupted calls, and removing duplicate or orphaned tool messages. Repair runs when a turn begins and before terminal persistence.

Web streaming uses versioned events carrying `turnId`, `messageId`, iteration `round`, and sequence number. `content_delta` events update the assistant message. Full `content` snapshots restore content after missed deltas. Matching `tool_call` and `tool_result` events share stable identifiers. On the normal success path, the final assistant message is persisted before `done` closes the stream. Error paths also emit `done`, and bounded but incomplete turns can emit a `terminal` code before closure. A successful turn must save a final response and have no error or incomplete terminal state. The `done` event alone does not establish success. Nested agents inherit cancellation and telemetry values, but cannot access the parent chat event channel. A specialist therefore cannot close the coordinator’s stream.

## E. Internal Multi-Agent Delegation

The `spawn_subagent` tool is not a direct in-process function call. It sends a trusted request through the MessageBus with owner, source agent, target agent, immutable call path, and correlation identifier. The Gateway verifies that the source and target exist and belong to the same tenant, rejects target reuse in the call path, submits an internal task, and resolves the correlated reply.

The bus stores a wait graph between tenant-agent lanes. Before accepting a request, it checks whether the target already waits—directly or transitively—on the source. Call-path validation alone cannot detect the following cross-root case: root R1 has lane A waiting for B, while root R2 independently asks B to wait for A. Neither immutable path contains a repeated target, yet the combined graph has A→B→A. A depth-first reachability check rejects the second edge before the circular wait is established.

The maintained invariant is that the directed lane wait graph is acyclic. If every blocked internal request corresponds to one graph edge, acyclicity rules out a circular wait among sub-agent lanes. DFS runs while the bus mutex is held. Its cost grows linearly with the number of lanes and edges. The pending-correlation cap bounds this work, although wider delegation still increases its cost. Alternatives include a static acyclic agent topology, a global lock order, or timeout-only recovery. Static topology reduces flexibility; timeout-only recovery detects a deadlock after consuming latency rather than preventing it. Pending internal calls are capped. A non-blocking publish reports backpressure when it cannot proceed. Shutdown rejects new work and releases all waiters.

Every production turn applies exact duplicate suppression keyed by `(target agent, task)`, so an identical retry reuses the first result while two distinct tasks for the same specialist still execute independently. Evaluation requests may additionally enable target-only suppression because the fixed benchmark contract expects at most one delegation to each specialist. This stronger evaluation policy is request-scoped and does not change production semantics.

Figure 2 shows the corresponding message path. In particular, delegation is mediated by both the MessageBus and TaskQueue rather than bypassing the scheduler through a direct coordinator-to-specialist function call.

[[FIGURE_2]]

## F. Telemetry and Cost Attribution

Each model call records agent, role, model, call path, prompt tokens, completion tokens, cache tokens, latency, error, and estimated cost. Sequence numbers are reserved when calls begin, so concurrent traces preserve invocation order rather than completion order. The collector identifies the root agent as coordinator and nested agents as specialists. Pricing is supplied by the evaluation suite instead of hard-coded in the runtime, preserving historical reproducibility when vendor prices change.

For one model call, the estimated cost is

`C = (Tin × Pin + Tout × Pout + Tcache-read × Pcache-read + Tcache-write × Pcache-write) / 10^6`,

where cached prompt tokens are removed from ordinary prompt tokens when the provider reports that they are already included. Reports aggregate coordinator and specialist cost, Team and Solo cost, full-harness cost, and cost per successful Team case.

All costs in this report are estimates based on the experiment’s fixed price table. They are not provider invoices and apply only to the recorded model allocation and pricing date.

## G. Operational Bounds and Claim Semantics

The runtime uses three different classes of controls. A **correctness invariant** must hold for every accepted state, such as wait-graph acyclicity or authorization after target resolution. A **safety bound** limits a specific resource or execution dimension: queue capacities bound buffered work, iteration limits bound loop rounds, and execution deadlines request cancellation. An iteration limit cannot bound a blocked call, and a deadline cannot force an uncooperative operation to terminate. An **operational default** is a provisional capacity choice, not a theorem or benchmark-derived optimum. A configured limit alone does not establish termination or scalability.

The current implementation applies configurable limits to root concurrency, admitted-task execution time, and tool iterations, together with bounded in-memory queues and correlation maps. These controls constrain the corresponding runtime resources and propagate cancellation; they do not establish a global wall-clock or cost bound for every downstream operation. The current values are defaults; load experiments have not established them as optimal.

These guarantees have specific limits. Local completion publication occurs at most once, and a live correlation accepts at most one reply. Neither implies exactly-once provider execution, external tool effects, durable message delivery, or transparent replay after process failure. The terminal state distinguishes a saved successful response from an error or incomplete turn, even though each may end with `done`. It does not coordinate a distributed commit across the browser, Gateway, provider, and external tools.

# V. FINANCIAL RESEARCH APPLICATION

## A. Product Position and Design

The financial application supports four research workflows: earnings-event review, candidate screening, read-only portfolio risk diagnosis, and review of conflicting or missing evidence. They share runtime sessions, tool execution, and traces, with workflow-specific inputs and state transitions. Research records and decision holds connect analysis to subsequent review. The application supports research rather than placing orders or treating a generated score as an investment recommendation.

Figure 3 shows how the components divide the work. Tools return structured evidence, and research Skills provide analytical procedures. The coordinator and optional challenger interpret the evidence. A human remains responsible for portfolio actions.

[[FIGURE_3]]

The design separates three concerns:

1. deterministic market data and calculations;
2. reusable research methods;
3. selective model reasoning and multi-agent challenge.

Deterministic tools handle data acquisition and calculation. The model interprets the resulting evidence and selects the next research action, while the runtime executes tool calls and retains the interaction history. A specialist is used when an independent interpretation, parallel deep dive, contradiction check, or risk challenge is useful. The same application can otherwise run in Solo mode.

## B. Native Finance Tools

The `finance-tools` native plugin wraps scripts from the external, unvendored Finskills directory and exposes eighteen typed tools. Plugin tests replace subprocess execution with controlled fixtures, so they verify argument handling, envelopes, caching, and ledger behavior without proving that a clean clone contains every external executable. The six-case multi-agent confirmation did not invoke these tools; its trace calls were exclusively coordinator-to-specialist delegation. The tools are grouped as follows.

TABLE_CAPTION: Finance capability groups exposed by the native plugin.

| Category | Tools | Purpose |
|---|---|---|
| Data and status | `toolkit_status`, `stock_snapshot`, `market_events`, `macro_snapshot` | Check capability availability and fetch timestamped market evidence. |
| Deterministic analysis | `screen_stocks`, `portfolio_risk`, `portfolio_policy_bound`, `serenity_scorecard` | Apply completeness gates, full-vector diagnostics, partial-information policy bounds, and reproducible research-priority scoring. |
| Thesis state | `thesis_save`, `thesis_get`, `thesis_list`, `thesis_match_event`, `thesis_record_review` | Persist hypotheses, catalysts, invalidations, evidence, and immutable reviews. |
| Monitoring state | `watchlist_save`, `watchlist_list`, `event_alert_ingest`, `alert_list`, `alert_update` | Configure monitoring, deduplicate events, and manage alert lifecycle. |

Every tool returns a `finance.tool.v1` envelope containing success state, request identifier, `as_of`, staleness boundary, data, sources, quality completeness, flags, structured errors, and cache metadata. External scripts are launched without a shell, with validated symbols, bounded arguments, captured output, and a timeout. Tools return structured errors so the agent can report a failure without inventing missing facts.

Stock screening includes a completeness gate. If a candidate appears to satisfy the numerical filters but a required metric is missing, it moves to the rejected set with `reason=insufficient_data`. This prevents missing data from being interpreted as zero or from silently improving a ranking.

For incomplete long-only holdings, `portfolio_policy_bound` checks whether a strict single-issuer limit can be established. It uses known weights, a residual expressed on the same denominator, and an explicit overlap condition. It does not infer exact concentration, HHI or factor exposure from missing holdings; `portfolio_risk` retains that refusal. The bound is a deterministic policy calculation, not an assessment of whether the investment thesis is sound.

## C. Research and Data Skills

The project uses a Serenity research Skill to map a value chain, identify difficult-to-expand bottlenecks, grade evidence, rank research priority, and define failure conditions. The Skill provides a reusable analytical procedure; it is not a market-data source, price predictor, valuation engine, or automatic buy/sell rule.

Serenity scorecard inputs are analyst judgments on bounded scales. The bundled script makes the arithmetic deterministic and repeatable, but cannot make subjective inputs objective. The output is therefore labelled a research-priority score. A valid experiment must hold the data, candidate universe, model, and prompt budget constant when comparing no Skill, Serenity, and Serenity plus an independent challenger.

A separate installed FinData Toolkit Skill packages market-data acquisition scripts and their usage instructions. In the tested path, the agent runs the stock-history script through the generic `exec` tool. It receives dated daily bars and a source URL, then saves a research record through the finance plugin. The Skill contains instructions and scripts. The `exec` tool runs the script, and the finance plugin manages the tenant-scoped thesis ledger. The trace can therefore verify data retrieval and ledger changes separately. A final answer alone cannot prove that either occurred. This integration is demonstrated in an isolated Gateway, not yet governed by a command-level Skill allowlist.

## D. Tenant-Isolated Thesis Ledger

The plugin maintains a separate SQLite database for research state. Every stateful call requires the trusted runtime context. Records are filtered by `userId`, allowing a coordinator and specialists owned by the same user to share a ledger while preventing cross-tenant reads.

A thesis records market, symbol, text, conviction, assumptions, catalysts, invalidation conditions, evidence snapshots, status, review schedule, creator agent/session, and an integer version. Review records are immutable and retain the reviewing agent and session. Updates require an `expected_version`; a stale write is rejected rather than overwriting a newer conclusion.

The finance plugin includes an opt-in evidence-completeness guard. A thesis can declare required event metrics, and the event-ingestion path stores the metric observations in the linked alert. At review-write time, the plugin compares the thesis requirements with the **stored alert**, not with fields supplied in the model's proposed review. If a required metric is absent, the plugin rejects a substantive decision. It accepts only `needs_review`, with status and conviction unchanged. A rejected call creates no review and does not increment the version. An accepted deferred review records the missing metrics and alert identifier. This rule checks declared metric requirements. It does not verify that ingestion extracted the source correctly. The bounded event-to-thesis panel below ran with this guard enabled.

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

Tools match and deduplicate events, and the ledger stores versioned reviews. The model focuses on interpreting the evidence.

## F. Evidence Governance and Analytical Boundaries

The application records the source and status of each observation before analysis. It represents an observation as

`e = (source, observed_at, as_of, payload, completeness, freshness, error_state)`.

The two timestamps serve different purposes. `observed_at` records when the runtime acquired the evidence, whereas `as_of` identifies the time to which the evidence applies. A later observation may describe an earlier accounting period, and a historical experiment must not expose information published after the simulated decision time. This requirement is consistent with established risk-data principles that emphasize lineage, timeliness, completeness, and traceability [11].

The runtime assigns different responsibilities to deterministic and probabilistic components.

TABLE_CAPTION: Allocation of responsibilities in the financial research workflow.

| Analytical operation | Primary mechanism | Reason |
|---|---|---|
| Data retrieval and normalization | Typed tool or deterministic script invoked through a Skill-guided tool call | Inputs, sources, and timestamps must be inspectable. |
| Ratios, thresholds, fingerprints, and concentration | Deterministic script | The same inputs should produce the same result. |
| Evidence completeness and duplicate suppression | Runtime policy and state | Missing values and duplicate events are data-quality problems, not language tasks. |
| Catalyst, contradiction, and invalidation interpretation | Coordinator or specialist model | The task requires contextual comparison and uncertainty handling. |
| Thesis and alert persistence | Versioned ledger operation | State transitions must be atomic, tenant-scoped, and auditable. |
| Portfolio action | Human decision | The application is decision support rather than autonomous execution. |

Separating these operations helps locate failures. If data retrieval, numerical calculation, and interpretation are merged into one free-form model response, a failed result cannot be attributed to a specific layer. With the decomposition above, the evaluator can distinguish missing evidence, incorrect deterministic state, routing failure, unsupported synthesis, and an explicitly deferred human decision.

## G. Representative Financial Scenarios

Two representative scenarios illustrate the boundary between deterministic control and model interpretation. In completeness-aware screening, a candidate has observed price-to-earnings and return-on-equity values but lacks free-cash-flow and leverage fields. The deterministic screen rejects the candidate as `insufficient_data`, and the coordinator must report the missing fields rather than fill them from model knowledge.

In the contradictory-evidence scenario, a filing states that capital-expenditure guidance fell from 8 billion to 5 billion yuan, while a later official transcript states that the original 8-billion-yuan plan remains unchanged. Because the supplied primary sources are not reconciled, the model must retain both claims, keep conviction unchanged, mark the thesis `needs_review`, and request clarification. This scenario tests uncertainty preservation rather than deterministic calculation.

## H. Scenario-to-Mechanism Mapping

TABLE_CAPTION: Financial scenarios and the safe outcomes their answers must describe in fixed-evidence calibration.

| Case | Mechanism represented in the scenario | Required outcome wording |
|---|---|---|
| Earnings catalyst | Dated evidence and thesis comparison | Versioned positive review; no trade authorization. |
| Thesis invalidation | Explicit failure-condition application | Status becomes invalidated; no unsupported price target. |
| Duplicate event | Fingerprint and optimistic state update | One alert, incremented occurrence count, one review. |
| Incomplete screening | Data completeness gate | Exclusion with `insufficient_data`; no imputation. |
| Portfolio concentration | Deterministic risk diagnostics | Reversible control and mandatory re-check. |
| Contradictory evidence | Uncertainty and governance | `needs_review`, unchanged conviction, clarification request. |

These calibration cases check expected answer content, not actual ledger writes. Later tool-backed studies inspect persisted state separately. Neither type of check establishes investment performance.

# VI. EVALUATION METHODOLOGY

## A. Research Design

The evaluation follows the report’s design-to-application structure. Engineering tests examine whether scheduling, isolation, cancellation, tool execution, and persistence behave as intended. Mode comparisons measure the completion and resource trade-offs of Solo and Team under fixed task conditions. Financial application studies examine whether these mechanisms connect supplied evidence or a Skill data fetch to analytical outputs and, where required, saved research state. Execution checks and assessments of analytical content use separate criteria so that completing a workflow does not automatically count as producing a sound financial conclusion.

Each experimental attempt uses a separate session for one case, repetition, and execution mode. In the retrieval study, runs derived from the same company and task form a cluster because they share source records. They are not independent financial cases. Fixed-evidence comparisons vary orchestration while holding evidence and model assignment constant. Retrieval comparisons vary execution structure and context allocation under a stated model assignment. Measures include task success, evidence retention, numeric grounding, collaboration quality, tokens, latency, and cost estimated from a fixed price table.

Infrastructure errors are reported separately from answer failures. A timeout, transport error, or unavailable provider is marked `errored`. It remains in the denominator for success over all assigned attempts, but is excluded when calculating success among completed outputs. The report lists assigned, evaluated, errored, and unavailable counts together.

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
| Finance retrieval | 24 SEC task configurations using fixed source documents with three repetitions of each primary mode; separate eight-configuration comparison using the same model | Retrieval recall and precision, evidence compression, specialist summary retention, synthesis grounding, latency, and cost under increasing corpus load. |
| SEC research case studies | 30 issuers with five sessions each; a separate three-issuer panel with two sessions each | Interpretation of checked comparisons, opposing evidence, research usefulness, and alignment with saved review state. |

The style subsets are regression tests for the project's evaluation harness. They are not official benchmark scores because they use fewer tasks, local fixtures, and project-specific graders.

The runtime includes an evaluation subsystem that executes tasks and records their outcomes. A YAML or JSON suite declares cases, expected behavior, repetitions, timeouts, and, where applicable, comparison modes. The evaluation CLI validates the suite. The selected runner creates a separate session for each case, repetition, and mode. The generic runner covers direct output, BFCL-derived function-call, and tool-trace tasks, while dedicated τ-style, SWE-style, multi-agent, and finance-retrieval runners apply their respective interaction and scoring rules. The HTTP executor submits an evaluation-scoped request to the real Gateway, which invokes the agent runtime and returns a final answer together with trace events, usage, and optional state. Deterministic tool responses and simulated specialist faults can be injected within a request; these controlled fixtures test particular decisions but do not by themselves establish behavior under an uncontrolled production outage. The report layer aggregates attempts and compares saved baseline and candidate results.

The evaluation uses three evidence channels. Final answers support outcome, milestone, and grounding checks. Tool traces record calls, results, and errors, linked by call identifiers. Model-call records provide roles, call paths, tokens, cache usage, estimated cost, latency, and errors. An answer alone does not prove that a tool or specialist was used. A valid trace does not prove that the answer is correct. The evaluators combine these records with saved state and, for repository tasks, hidden-test results.

The six-case fault-injection suite separately exercises specialist timeout, explicit error, malformed output, contradictory evidence, multiple partial failures, and noncritical dependency failure. The tests check whether the system detects the injected failure, identifies its source, and responds without unsupported claims. They do not measure service availability under real outages. This separation matters because a runtime or transport error, a model's unsupported assertion, a mismatched source fact, and an overly narrow grader are different failure classes requiring different remedies.

## C. Repetition and General Metrics

Each case runs in an isolated session with a configurable timeout and number of repetitions. This report presents assigned attempts, strict passes, separately identified infrastructure errors, descriptive mean latency, token usage, estimated cost, and selected evidence-retention outcomes. The harness retains additional per-attempt and aggregate diagnostics, but those are not all analyzed here. Queue-wait P50/P95 values in the scheduler test describe that controlled workload, not the latency distribution of the SEC model experiments.

When a suite includes state, communication, or policy checks, those checks must also pass. The financial confirmation populated text, milestone, contribution, and grounding checks; persistent state mutation was evaluated separately through deterministic plugin tests.

## D. Fair Team/Solo Baselines

A naive comparison between a Team and a closed-book Solo agent is unfair when specialists possess evidence unavailable to Solo. It measures both evidence access and orchestration. The financial suite therefore defines four evidence-matched or diagnostic modes:

- `solo_open_book`: one coordinator pass over the same evidence packet, anonymized and flattened, without delegation tools;
- `solo_two_pass`: two coordinator passes over the same anonymous evidence, controlling for the additional planning/synthesis opportunity;
- `team`: two coordinator calls plus three real specialist calls through the runtime;
- `oracle_team`: named specialist reports delivered directly, representing a routed-synthesis diagnostic candidate rather than a theoretical upper bound.

The fair collaboration gain is

`Gfair = S(team) − S(solo_open_book)`,

where `S` is outcome success under the same milestone and attribution graders. Planning-opportunity-matched gain is `S(team) − S(solo_two_pass)`. Two-Pass gives the coordinator an additional planning step. It does not match the compute used by Team’s three specialist calls. The older `team − solo_closed_book` value remains an evidence-access diagnostic in legacy suites but is not evidence that orchestration itself added value. Each mode receives an independent session and timeout. A baseline timeout, empty output, streamed turn error, or other infrastructure failure is marked `errored`. It counts toward assigned attempts but not success among completed outputs. Any paired effect that requires that output is unavailable. Infrastructure errors are not interpreted as model failures. Paired tables are constructed from case and repetition keys before computing statistics.

## E. Multi-Agent Metrics

For expected specialist set `E` and unique valid delegated set `D`,

`Precision = |D ∩ E| / |D|`, `Recall = |D ∩ E| / |E|`,

and delegation F1 is their harmonic mean. Contribution utilization is the fraction of expected healthy specialist evidence retained in the final answer. Coordination score is the mean of delegation F1 and contribution utilization. Milestone KPI is achieved deterministic output milestones divided by configured milestones.

## F. Preliminary Workflow Calibration

The financial suite contains six cases and three specialists—four runtime agents including the coordinator. The final confirmation used one repetition and four independently isolated modes, yielding 24 case–mode executions and 54 model calls after including the specialists and the two-pass baseline. Session keys are unique by case, repetition, and mode so that a prior answer cannot leak into another baseline. The same deterministic milestones and forbidden assertions are used for all four modes.

The evidence source is deliberately controlled. `FIN-01` through `FIN-06` are compiled into the benchmark tenant as a string lookup table, and each specialist is instructed to return the matching evidence. The calls traverse the real Gateway, TaskQueue, MessageBus, agent loop, provider, correlation, and telemetry paths, but they do not measure document retrieval or specialist evidence reasoning. The coordinator uses a delegate-only policy and specialists use a no-tools policy.

The preliminary harness retains five groups of measures; Section VII summarizes its completion results and diagnostic failures rather than reproducing every archived metric:

1. **Outcome validity:** strict case success and milestone completion;
2. **attribution wording:** required evidence-identifier recall, forbidden-assertion rate, and explicit uncertainty under contradiction;
3. **governance wording:** whether the answer states the expected thesis, watchlist, or alert action and optimistic-version requirement;
4. **orchestration validity:** delegation precision, recall, contribution utilization, fair collaboration gain, and oracle gap;
5. **efficiency:** Team-only tokens, Team P50/P95 latency, coordinator/specialist cost, and cost per successful Team case.

The six case oracles are specified before execution.

TABLE_CAPTION: Fixed evidence and expected answer content in the preliminary workflow calibration.

| Case | Core evidence | Expected answer content |
|---|---|---|
| Earnings catalyst | 18% services growth; 220-bp margin expansion; thesis version 4 | Positive review, conviction 3→4, active status, no trade. |
| Thesis invalidation | Customer loss equals 31% of revenue; invalidation threshold 25% | Invalidate version 2, request fresh review, no target price. |
| Duplicate alert | Same external event ID inside 24 hours; existing alert count 1 | Keep one alert, count becomes 2, update `last_seen_at`. |
| Incomplete screen | PE and ROE present; free cash flow and leverage absent | Reject as `insufficient_data`; request refresh; no imputation. |
| Portfolio concentration | 62% sector weight; 0.89 correlation; 17% stress loss versus 10% limit | Staged reduction below 45% and mandatory re-test. |
| Contradictory evidence | Filing says capex 8→5 billion; later transcript says 8 billion unchanged | `needs_review`, unchanged conviction, clarification required. |

Acceptance requires all configured wording and policy checks to pass across repetitions. Infrastructure errors must be reported separately. Cases with incomplete or conflicting evidence must contain no unsupported claims. Any Team advantage is measured against `solo_open_book`, which has access to the same evidence. Actual ledger mutation is tested separately by the Python plugin suite and is not inferred from generated prose. A positive return is not an acceptance criterion.

## G. Retrieval-Mediated SEC Experiment

The retrieval track introduces evidence acquisition as an explicit stage rather than assuming that a complete evidence packet is already available. The SEC study crosses four companies—NVIDIA, AMD, Intel, and NIKE—with two task families and three corpus loads. Point-in-time cases require one bounded observation and declared calculations. Longitudinal cases require chronology reconstruction, accounting-basis checks, cross-observation calculations, a contiguous research-state chain, and a bounded governance decision. Small, medium, and large loads add progressively more same-company, adjacent-period, peer, and irrelevant records. The 24 configurations are treatment combinations, not 24 independent issuers; each primary mode has three repetitions per configuration.

All records are extracted from archived SEC filing material and carry a source identifier, accession, filing date, locator, source hash, and record identifier. A provenance table records the concept, value, unit, accounting basis, reporting period, filing date, SEC acceptance timestamp, accession, source URL, and locator for each expected fact. Point-in-time cases exclude records accepted after the target observation time, while a separate derived-value table preserves formulas, input facts, units, rounding rules, and expected results. Reference answers come from the fixed source documents, not model output or agreement among graders. Expected calculation results are hidden from all non-Oracle modes.

The source and oracle packet underwent review before use, covering 44 SEC facts, 17 calculations, and 42 evidence groups. Fact checks compare values, units, periods, and accounting bases with filing passages. Calculation checks recompute the formulas. Evidence-group checks confirm that alternative passages support the same fact. All 103 items were reviewed, including technical checks of the 42 evidence groups. Generated answers undergo separate evaluation.

The five modes are:

1. `solo_monolithic`: one Pro call receives the raw corpus and performs retrieval, analysis, and synthesis in one context;
2. `solo_staged`: one Pro agent performs retrieval, three sequential analytical passes, and synthesis in isolated sessions;
3. `team_shared_retrieval`: one Flash retriever constructs a bounded packet, a Pro coordinator delegates the packet once to three parallel Flash specialists, and the coordinator synthesizes their summaries;
4. `team_raw_context`: the coordinator and parallel specialists receive the full raw corpus without the separate retrieval stage, comparing the overall raw-context strategy against shared retrieval rather than isolating compression alone;
5. `oracle_evidence`: one Pro synthesis call receives the gold evidence packet as an evidence-access diagnostic, not a theoretical quality ceiling or a deployable baseline.

The primary quality outcomes are strict pass, final evidence recall, milestone completion, and numeric grounding accuracy. Retrieval recall and precision, specialist-summary retention, synthesis retention, evidence-compression ratio, delegation precision and recall, infrastructure-error rate, tokens, estimated cost, and wall-clock latency are secondary mechanism and efficiency outcomes. Stage times are retained to explain execution costs. Specialist times are summed across parallel calls, so their total is not the end-to-end elapsed time.

The SEC main study assigns three repetitions of each primary mode—staged Solo, shared-retrieval Team, and raw-context Team—to all 24 configurations, for 216 assigned primary observations. One monolithic Solo and one Oracle diagnostic are also run per configuration, adding 48 observations. Mode order is seeded within case–repetition blocks, sessions are isolated, and each case report has a hash manifest. The main study uses the declared heterogeneous allocation above; the prespecified 24-observation comparison using Pro for every model call was not run and is not part of the results.

A supplementary comparison holds the model family and tier fixed across staged Solo and shared-retrieval Team. It selects eight prespecified configurations across four issuers, runs each mode three times, and contributes 24 paired blocks or 48 valid observations collected in two batches. Incomplete and invalid pilot observations are excluded. The supplement is analyzed separately from the main study because model allocation and collection batches differ.

Here, Pro and Flash refer to the archived DeepSeek model identifiers `deepseek/deepseek-v4-pro` and `deepseek/deepseek-v4-flash`, respectively. These identifiers describe the recorded service configuration, not immutable model-weight versions. The frozen suites and manifests specify the following settings for these two comparisons.

TABLE_CAPTION: Recorded configuration for the repeated SEC comparisons.

| Setting | Main study | Comparison using the same model |
|---|---|---|
| Recorded execution dates (UTC+8) | 10–11 October 2026 | 11 October 2026, two batches |
| Model allocation | Pro for Solo, coordinator, and Oracle synthesis; Flash for retrieval and specialists | Flash for all actual model calls |
| Repetitions | Three per primary mode and configuration; one per diagnostic | Three per mode and configuration |
| Suite timeout | 10 minutes per mode attempt | 10 minutes per mode attempt |
| Configured model limits | 8,192 output tokens per call; temperature 0.1; thinking off | Same |
| Scheduling | One case block at a time; Team specialists parallel within the block | Same |
| Mode-order seed | 20260802 | 20260802 |
| Frozen price-table date | 1 August 2026 | 1 August 2026 |

Both comparisons retain versioned prompts and grading rules, together with executable, source, suite, and result hashes for reproducibility. Each result refers to the implementation used for that experiment.

## H. Statistical Reporting and Reproducibility

The report presents raw outcome counts and descriptive mode-level means, with paired pass/fail counts for the main Team/Solo comparison. Per-attempt outcomes, timing, tokens, and errors remain in the machine-readable archive. Equal observed outcomes do not establish equivalence, and means can conceal long-running delegation paths. Completed-output latency comparisons exclude timeouts; pairs with a timeout are described separately as completion outcomes. Corpus loads and repeated calls derived from one company–task pair share source material and therefore cannot be counted as independent financial cases. No confidence interval or significance test is used to support the reported comparisons.

The six-case calibration has only one repetition, so equal observed pass counts cannot establish equivalence. The later SEC study adds repetition and load variation, but calls derived from one company–task cluster remain dependent. The report therefore emphasizes observed counts and paired trade-offs rather than a population reliability claim.

For the repeated SEC comparisons, the frozen suites, manifests, and result files record model allocation, repetitions, timeout, pricing date, execution modes, usage, latency, and errors. Evidence fixtures and graders remain unchanged within a comparison. The six-case confirmation and original retrieval Pilot contain one repetition; the SEC main study and comparison using the same models have three repetitions per selected configuration. Given only eight company–task clusters, one provider family, and two separate run batches for the supplementary comparison using the same model, the estimates describe these configurations rather than a wider population.

The finance-retrieval protocol additionally records the suite and source-lock hashes, a seeded mode order where configured, and a retained machine-readable report and manifest. These artifacts make the executed configuration inspectable; they do not remove provider variability, single-case dependence, possible grader error, or the need to freeze sources and oracles before confirmatory repetition.


## I. Financial Workflow and Case Study Methods

The application experiments use actual Gateway sessions and finance-tool calls. Each attempt starts from its own session and ledger state. For an event review, the agent reads a stored thesis and linked alert, examines the supplied evidence, chooses a research decision, writes a versioned review, and acknowledges the alert. Verification checks the returned tool records against the retained SQLite ledger, including the review's source links, thesis version, conviction, decision hold, and alert status. A tool call printed as text does not count as execution. Screening and portfolio cases instead check their configured candidate, rejection, risk, and state outcomes.

The four-workflow repetition panel contains 16 frozen cases, five attempts per case. Its SEC event cases use archived excerpts; source-conflict, screening, and portfolio cases use declared synthetic fixtures. An earlier event-to-thesis panel contains four SEC cases with two attempts each. These studies test distinct workflow requirements and are not combined into one pass rate. Two further cases use real sources. The historical screening case uses frozen company disclosures. The online Skill-to-ledger case retrieves dated market bars during the session.

The later research case studies use selected SEC earnings-exhibit rows with reporting periods, source URLs, locators, and hashes. The task asks the agent to compare two quarters and identify evidence for and against the existing view. It then asks for the implications, missing information, and a research decision. The agent must also verify the saved review and alert. This is a paraphrase of the archived task contract, not a quotation of a model answer. The prompt does not assign a target conclusion.

For these later cases, the host supplies a checked comparison catalog with row identifiers and sequential differences. The model selects comparisons, explains their implications and uncertainty, and reports state returned by the tools. The host renders the numerical reference card. The resulting report therefore combines deterministic source preparation and arithmetic with model-generated analysis. Correct displayed arithmetic alone does not demonstrate that the model independently calculated it, and a correct reference table does not guarantee that its interpretation is sound. The excerpts are selected evidence rather than complete filings, and Q2-to-Q3 comparisons are sequential rather than year-over-year.

One panel contains 30 issuers with five isolated Flash sessions each. The illustrative MQ and AIG examples were selected after inspecting outputs. A separate three-company study fixed three previously unrun issuers—MTB, RPAY, and CSGP—before generation and ran two sessions each. It enabled a check that validates calculations against the supplied source values. Failed or non-high answers remain in their respective panels. The two panels are presented separately because their selection, repetitions, and guard settings differ.

## J. Assessment of Analysis Quality

Execution checks ask whether the required calls, evidence links, and ledger transitions occurred. Content review asks whether the financial argument follows from the available evidence. Both the final answer and persisted research rationale are in scope. A material claim is checked for its value, unit, period, accounting basis, direction, derived arithmetic, and supporting source or tool record. Explanations of causes must be supported or explicitly framed as hypotheses; a statement that a decision is held must agree with the actual ledger.

The LLM-assisted assessment rubric has five dimensions: factual and numeric fidelity, inference discipline, risk and uncertainty, state alignment, and research utility. Each is scored from zero to two. To be rated high quality under the case-specific rubric, an answer requires two on every applicable dimension, no critical error, completed execution, and a supported research implication. An adequate answer has no critical error but falls below that threshold. A problematic answer has a material error or scores zero on an applicable dimension. A justified request for more evidence can be useful when it identifies what would resolve the question and actually suspends downstream use of the thesis.

The 80-attempt workflow panel received a retrospective first-pass review. Later SEC reviews use the frozen claim-level rubric, with masked scores completed for 100 of 150 answers; supplemental assessments are not pooled with those scores. The six answers from the three-company study received unblinded LLM-assisted review. These diagnostic assessments have no independent finance-expert validation. Illustrative examples demonstrate analysis and its connection to runtime state rather than investment performance or general financial reliability.

# VII. RESULTS

The results address runtime mechanisms, execution-mode trade-offs, and financial application workflows in that order. The repeated SEC main study and comparison using the same model provide the principal mode comparisons. Application results then connect tool execution to saved research state and examine selected financial arguments.

## A. Engineering Verification

The implementation was verified with focused package tests covering the evaluation harness, agent loop, sub-agent tools, store, plugins, tenant provisioning, API, and command layer, followed by the full Go test suite. Behavioral tests exercise assertion direction and negation, error-aware denominators, streamed turn errors, tool panic containment, duplicate call identifiers, production and evaluation deduplication semantics, per-tool duration, model-call ordering, and SQLite contention through the public Store API. Race-enabled tests for the agent, sub-agent tools, and store packages also passed and are reported separately because they detect synchronization faults rather than semantic failures.

The finance plugin passed 35 Python tests. These cover tool discovery, subprocess arguments, caching, data completeness, and trusted tenant context. They also check thesis isolation and versioning, saved event reviews, watchlist filtering, alert deduplication, user isolation, required-metric rules, and the partial-portfolio policy bound.

In the retained engineering-test snapshot, statement coverage measured with `go test ./... -coverprofile` was approximately 27.2% for runtime and production packages, or 28.4% when `project-report/analysis` is included. Coverage is strongly non-uniform: `policy`, `scope`, `session`, `plugin`, `mcp`, and `skills` are among the packages at 0.0%, while `agent/tools`, `gateway`, `sandbox`, `setup`, and `store` remain partial. These gaps affect mechanisms used in the design argument, especially policy-filtered registries, session normalization, and prompt-injection scanning. These coverage figures describe that snapshot rather than a cumulative measurement of subsequent patches. The tests verify selected execution paths. They do not establish full coverage, production capacity, security certification, or investment performance.

A small scheduler-only load test exercises the actual TaskQueue with 48 synthetic internal tasks distributed over 12 chat keys, four tasks per chat. Each handler waits 15 ms; no Gateway HTTP request, database, provider, or external tool is involved. Five local repetitions on Go 1.27.1 (Darwin/arm64) compared root-concurrency limits of one and four. All tasks completed, each chat retained submission order, and observed peak handler concurrency equaled but never exceeded the configured limit. A separate race-detector run passed. The timings below are ranges across the five ordinary repetitions, not service-capacity estimates.

TABLE_CAPTION: Queue-only synthetic load check, 48 tasks across 12 chats, five repetitions per limit.

| Root concurrency limit | Elapsed time | Queue-wait P50 | Queue-wait P95 | Observed peak handlers |
|---|---:|---:|---:|---:|
| 1 | 767–773 ms | 367–372 ms | 703–708 ms | 1 |
| 4 | 192–194 ms | 80–81 ms | 176–177 ms | 4 |

The test supports bounded root admission and per-chat serialization under this small controlled workload. Since the handler duration is artificial and dominates the run, these elapsed times do not quantify provider latency, production throughput, database contention, memory use, or behavior at queue saturation.

## B. Solo and Team Execution

### Repeated SEC Main Study

All 24 configuration reports and matching hash manifests were retained. The primary analysis assigns 72 attempts to each of staged Solo, shared-retrieval Team, and raw-context Team; the 24 monolithic and 24 Oracle observations are diagnostics rather than additional repetitions of those modes. The table reports assigned attempts, strict passes, separately identified infrastructure errors, mean wall-clock latency over completed outputs, provider-total tokens per assigned attempt, and total frozen-price estimated cost. The two Solo timeouts count toward assigned attempts but are excluded from mean completed-output latency. Their billed cost is unknown and is not added to the estimate.

TABLE_CAPTION: SEC main-study results across 24 configurations, with three repetitions per primary mode.

| Mode | Assigned | Strict pass | Infrastructure errors | Mean completed latency | Mean tokens per assigned attempt | Total estimated cost |
|---|---:|---:|---:|---:|---:|---:|
| Staged Solo | 72 | 55/72 | 2 | 70.17 s (70 completed) | 36,564 | USD 1.087207 |
| Shared-retrieval Team | 72 | 56/72 | 0 | 31.38 s | 43,158 | USD 0.625114 |
| Raw-context Team | 72 | 63/72 | 0 | 26.51 s | 76,663 | USD 0.872993 |
| Monolithic Solo diagnostic | 24 | 0/24 | 0 | 27.15 s | 15,760 | USD 0.191063 |
| Oracle-evidence diagnostic | 24 | 21/24 | 0 | 19.94 s | 6,195 | USD 0.082876 |

The main deployment uses Pro for staged Solo and the Team coordinator, with Flash for Team retrieval and specialists. Its latency and cost differences therefore reflect both execution structure and model allocation. They cannot isolate the architecture’s effect. Shared-retrieval Team finished faster in all 70 pairs where both modes completed. In the other two pairs, Team completed while Solo timed out; these are completion differences, not measured Solo completion times. Across all 72 assigned pairs, strict outcomes were mixed: 46 passed in both modes, ten only in Team, nine only in Solo, and seven in neither. Similar pass counts do not establish equivalent quality. Raw-context Team passed more attempts than shared-retrieval Team (63 versus 56) and was faster on this run, but consumed substantially more tokens and estimated cost. Shared retrieval used fewer resources, while raw context performed better on completion and latency in this configuration. Monolithic and Oracle diagnostics probe pipeline and evidence constraints; neither is a fair replacement for the complete staged workflow.

### Solo and Team Comparison Using the Same Model

The matched comparison uses Flash for every model call in both modes. Across eight configurations and three repetitions per configuration, all 48 observations in the 24 Team/Solo pairs completed without infrastructure errors.

TABLE_CAPTION: Team and Solo comparison using the same model over 24 paired repetitions.

| Mode | Strict pass | Mean end-to-end latency | Mean provider-total tokens | Total estimated cost | Mean final evidence recall |
|---|---:|---:|---:|---:|---:|
| Staged Solo | 24/24 | 33.62 s | 41,514 | USD 0.130359 | 1.000 |
| Shared-retrieval Team | 19/24 | 22.42 s | 47,029 | USD 0.133224 | 0.975 |

Team was faster in all 24 paired blocks, with an 11.20-second lower mean latency (33.3% relative to Solo's mean). It used approximately 13.3% more provider-total tokens and had 2.2% higher estimated cost under the fixed price table. It was cheaper in only eight of the 24 pairs. Two Team failures omitted declared calculations, and three occurred in the same AMD point-in-time large-corpus configuration with final evidence recall of 0.8. On these tasks, Team reduced latency but lost some completion accuracy and evidence. The result does not show a general quality advantage for multi-agent execution. The eight configurations share source material within four issuers and ran across two batches, so the 24 pairs are not independent draws from a broad task population. Estimated costs use the frozen experiment price table rather than the provider bill.


### Preliminary Calibration Findings

Earlier experiments checked the harness and task difficulty before the repeated study. In the six-case fixed-evidence confirmation, Open-Book Solo, Two-Pass Solo, and Team each passed 5/6 configured cases; a routed-synthesis diagnostic passed 4/6. All 24 attempts completed without an infrastructure error. Team called the expected specialists, but a lexical matcher rejected “estimated” where it required “estimate,” illustrating why a strict grader result must be interpreted alongside the retained answer.

A separate four-case SEC initial-observation suite produced 4/4 passes in each of the four modes. Its four-company longitudinal extension added chronology, cross-period calculations, and a research-state chain. Team and Open-Book Solo each passed 3/4 cases; Two-Pass Solo and the routed diagnostic each passed 1/4. An AMD Team answer followed an empty specialist response with excess delegation and omitted required evidence. A subsequent one-company retrieval pilot showed that a compact shared packet could reduce resource use relative to raw-context Team. These small studies informed the repeated design; their detailed metrics remain in the evaluation archive and are not pooled with the main results.

## C. Financial Workflow Execution

### Event Review and Persistent State

The initial tool-backed event panel covered four SEC cases with two isolated attempts each. Each attempt read an existing thesis and alert, compared the supplied period facts, selected an impact and research decision, wrote a review, and acknowledged the alert. The cases were designed to include recovery, mixed evidence, deterioration, and a missing required metric.

TABLE_CAPTION: Event review study using fixed source documents, two isolated model-backed attempts per case.

| Case | Evidence and research condition | Persisted decisions | Frozen decision rubric |
|---|---|---|---:|
| C01 | AMD Q3→Q4 2024: revenue +12.3%, gross margin +1 pp, Gaming +21.9%; sustained recovery needs more than one observation | Maintain; upgrade | 2/2 |
| C02 | AMD Q2→Q3 2024: revenue +16.9% and margin +1 pp, but Gaming −28.7% | Maintain; needs_review | 1/2 |
| C03 | Nike Q4 FY2024→Q4 FY2025: matching-quarter revenue −12.0%, margin −4.4 pp, digital YoY rate −16 pp | Invalidate; invalidate | 2/2 |
| C04 | NVIDIA Q1→Q2 FY2025: event packet includes revenue and Data Center growth but omits required gross margin | needs_review; needs_review | 2/2 |

All eight requests completed without a transport or provider error. Read-only checks found one thesis, one linked review, and one acknowledged alert per ledger, with a single thesis-version advance in each attempt. Both NVIDIA missing-margin cases preserved status and conviction while holding the decision. The frozen decision rubric passed 7/8: one AMD response selected a cautious review outside the permitted maintain/downgrade range. A separate content check found one unsupported claim that a single observed Gaming increase was a second consecutive improvement. These findings distinguish successful execution from decision calibration and interpretation.

### Four Workflow Families

The broader repetition panel ran 16 frozen cases five times each, using independent Gateway sessions and ledgers. The four families exercised event review, conflicting-source resolution, preliminary screening, and portfolio-risk diagnosis. The SEC event cases used archived excerpts; the other families used synthetic inputs.

TABLE_CAPTION: Application coverage and retrospective content judgments in the 80-attempt workflow panel.

| Workflow family | Task and source | High quality | Adequate | Problematic |
|---|---|---:|---:|---:|
| SEC event review | Assess a disclosed change and persist a thesis review; archived SEC excerpts | 16 | 4 | 0 |
| Source conflict or correction | Resolve or retain competing claims and update review state; synthetic fixtures | 13 | 2 | 5 |
| Candidate screening | Apply data-completeness and screening conditions before saving a candidate; synthetic fixtures | 12 | 5 | 3 |
| Portfolio risk | Interpret concentration or incomplete holdings against declared limits; synthetic fixtures | 13 | 2 | 5 |
| Total | 16 cases with five repetitions each | 54 | 13 | 13 |

All 80 attempts completed, with 77 passes on the workflow execution checks and three retained workflow failures. Two answers printed a tool call in prose without issuing it; another described a corrected capex amount in its final answer but omitted that value from the saved review rationale. There were no recorded request errors or unpriced calls. In all ten repetitions requiring evidence absent from the packet, the ledger recorded a review hold, kept status and conviction unchanged, and blocked the thesis from subsequent use.

The content judgments in the table are the retrospective first pass described in Section VI. Problematic answers included converting conflicting capex claims into a management range, inferring production capacity from capex without a supporting explanation, misnaming an earnings-growth metric, and overlooking a provable bound on incomplete holdings. The 77 passes on the workflow execution checks therefore cannot be read as 77 correct financial analyses. The panel demonstrates four executable workflow families and a functioning missing-evidence rule in the tested cases.

A subsequent ten-attempt retest supplied the deterministic partial-portfolio-bound tool. All ten used the source-linked tools and obtained the configured bound correctly, while local content review rated three high, six adequate, and one problematic. The remaining problem was an unsupported issuer-specific growth comparison. This supports the value of placing checkable arithmetic in tools while retaining separate review of the explanation.

## D. Selected SEC Research Analyses

The selected reports compare relevant financial measures, consider opposing evidence, and explain what can be concluded. They also save a research decision and identify the evidence needed next. They use the host-prepared comparison catalogs described in Section VI; the analytical contribution lies in how the model interprets and acts on those comparisons.

The 30-issuer panel retained all 150 Flash responses and ledger copies. Its automated execution checker marked 101 as candidates for qualitative review and 49 as held, with no recorded request error. These classifier labels are distinct from a thesis's research-review decision. The original masked review contains 100 completed scores. Supplemental reviews are recorded separately. MQ and AIG were selected for illustration after inspection. Their examples do not characterize the unreviewed answers or establish a population quality rate.

### Marqeta Revenue Growth and Earnings Quality

The MQ task compared the second and third quarters of 2025 using selected SEC earnings-exhibit rows [17], [18]. The question was whether stronger business activity supported a stronger research view when GAAP and company-adjusted profitability moved differently.

TABLE_CAPTION: Selected MQ comparison values used in the research case, Q2 and Q3 2025.

| Measure | Q2 2025 | Q3 2025 |
|---|---:|---:|
| Net revenue, USD million | 150.392 | 163.306 |
| Gross profit, USD million | 104.061 | 114.557 |
| Processing volume, USD billion | 91.386 | 97.962 |
| Company-defined Adjusted EBITDA, USD million | 28.509 | 30.312 |
| GAAP operating result, USD million | −9.228 | −10.370 |
| GAAP net result, USD million | −0.647 | −3.624 |

The useful interpretation was that revenue and activity growth did not yet demonstrate stronger GAAP profitability. Operating expenses rose by USD 11.638 million, exceeding the USD 10.496 million gross-profit increase. The displayed operating bridge is therefore +10.496 − 11.638 = −1.142 USD million, consistent with the wider operating loss. The selected high-rated answers kept the company-defined Adjusted EBITDA increase separate from the GAAP losses and identified expense drivers and the reconciliation between accounting bases as follow-up research questions.

All five MQ sessions saved source-linked reviews requiring further evidence, acknowledged their alerts, and left the thesis held and blocked. Local review rated four high and one adequate. The adequate answer overstated the absence of expense-line information in its saved rationale. This five-run case demonstrates repeated execution of the research workflow and several useful analyses within a fixed evidence packet.

### AIG Segment Improvement and Consolidated Earnings

The selected AIG answer compared second- and third-quarter 2025 disclosures [19], [20]. General Insurance adjusted pretax income increased by USD 241 million; underwriting and segment investment-income changes contributed USD 167 million and USD 74 million on the displayed measures. Consolidated GAAP net income attributable to common shareholders nevertheless fell by USD 625 million. The answer preserved the distinction between a segment's adjusted measure and consolidated GAAP income rather than treating one as a reconciliation of the other.

The answer also compared two measures of underwriting performance. The reported General Insurance combined ratio improved from 89.3% to 86.8%. The company-defined adjusted accident-year combined ratio changed only from 88.4% to 88.3%, while written premiums declined. The answer requested an earnings-basis reconciliation and more detail on underwriting drivers before changing conviction. The saved review required further evidence, the thesis was blocked, and the alert was acknowledged. The answer received a high-quality rating under the case-specific rubric.

Across AIG's five sessions, the original masked reviews contain three high ratings, one problematic rating, and one blank score. A later unblinded review rated the remaining answer high. The problematic answer left an unresolved earnings-basis conflict actionable. The selected answer handled the uncertainty carefully. Other answers to the same source packet were less reliable.

### Repay Holdings and the Impairment Base Effect

A separate prospective three-company study selected MTB, RPAY, and CSGP before generating outputs, with two Flash sessions each and a check that validates calculations against the supplied source values. The sources were the issuers' second- and third-quarter 2025 earnings exhibits [21]–[26]. All six sessions completed the configured tool workflow, each with one linked review and an acknowledged alert. Their complete local content outcomes were:

TABLE_CAPTION: Results of the six-session study, with execution and content reported separately.

| Issuer | Workflow completion | Local content judgments | Saved research state |
|---|---:|---|---|
| MTB | 2/2 | Two adequate | Maintain; both available |
| RPAY | 2/2 | One high, one problematic | Both held for review and blocked |
| CSGP | 2/2 | One adequate, one problematic | Both held for review and blocked |

RPAY's second answer identified the impairment base effect behind the improvement in GAAP earnings. Q2 included a USD 103.781 million impairment. The GAAP operating loss narrowed from USD 104.904 million in Q2 to USD 3.009 million in Q3. Company-defined adjusted EBITDA, however, fell from USD 31.811 million to USD 31.202 million [23], [24]. The displayed operating bridge, in USD thousands, was revenue +2,099 less an expense change of −99,796, giving an operating-result improvement of +101,895.

The answer stated that “the GAAP improvement is best read as a base-effect normalization rather than demonstrated operating leverage.” This quotation is from the retained final answer. It also identified the need for the full reconciliation, revenue drivers, and further period evidence. Its actual tool sequence read the thesis and alert, submitted a linked review, acknowledged the alert, and checked the stored thesis. The ledger retained conviction 3 with a review hold and blocked actionability. Local review rated this answer high within the selected-source case. The numerical comparison came from the checked host catalog; the model supplied the interpretation and research action.

The other RPAY answer incorrectly said both cost of services and selling, general and administrative expense increased more than revenue. Their changes were USD 1.531 million, USD 2.295 million, and USD 2.099 million respectively, so the first comparison was false. CSGP's first final answer incorrectly said the tax change did not offset a USD 23.9 million decline in operating result. The tax contribution improved by USD 30.3 million. A separate USD 37.0 million adverse change in other income/expense helped explain the lower net income [25], [26]. Both ledgers were held, but the explanations contained errors.

Replaying the saved review calls showed where the arithmetic guard missed errors. RPAY's wrong comparison was present in its persisted rationale and was not caught by the arithmetic guard. CSGP's wrong sentence appeared only in the final answer after the tool write. These cases identify different locations for further checking: the saved rationale and the post-tool explanation. A decision hold protects subsequent use of the thesis but does not itself certify every sentence.

### Interpretation of the Case Evidence

MQ, AIG, and RPAY illustrate three useful analytical tasks: distinguishing growth from earnings quality, reconciling segment and consolidated perspectives, and separating an impairment base effect from recurring improvement. In each selected successful answer, the model turned the supplied comparisons into a concrete evidence requirement and a persisted research decision. This supports the application claim that the runtime can produce and retain useful financial research outputs.

Other retained answers show the limits of these successes. Earlier fresh-issuer and screening panels mostly produced adequate rather than high-rated analysis, and the broader workflow panel exposed unsupported interpretation despite correct state handling. A separate response-blind sample of four previously unscored answers from the 150-run archive yielded one adequate and three problematic judgments, including signed tax-line errors and a false hold assurance. Those four observations are not a representative quality estimate, but they reinforce the need to present the positive cases as examples. The diagnostic scoring and the observed variability are the principal limits on a stronger quality claim.

## E. Real Source Screening and Live Data Integration

A historical AMD/Intel screening replay replaced synthetic inputs with frozen, hash-checked SEC disclosures. It applied two declared GAAP thresholds, saved a source-linked preliminary AMD thesis, and rejected Intel. A read-only review found that the source, arithmetic, and state checks passed. The case shows screening with real sources under two declared conditions. It does not test a broader investment-selection strategy.

An online AMD case exercised a longer path in one isolated Go Gateway session. The agent used the execution tool to run a FinData Toolkit Skill script and retrieve five dated Nasdaq daily bars. A second execution call performed the arithmetic. The agent then saved a preliminary thesis through the finance plugin. The first and latest closes were 570.82 on 14 October 2026 and 534.74 on 20 October 2026. Recalculation gives a first-to-latest change of −6.3207%. The saved evidence includes the source URL, dates, closing prices, bar interval, and rounded result of −6.32%. The payload did not specify currency or adjustment basis, so USD was explicitly an inference.

The retained ledger contains one preliminary thesis and no alert or review. All four model calls were priced, at an estimated USD 0.002679208. The original scorer misclassified the valid arithmetic call as a second market-data fetch and missed an equivalent percentage field name. A read-only review found that eleven execution, source, arithmetic, and state checks passed. The original score was retained. An earlier observation had an incorrect adjacent-day direction in its prose; the second corrected it.

The selected run demonstrates integration of a reusable data Skill, model-directed arithmetic, and persistent finance state. In that run, a price-only thesis appeared available despite missing fundamentals and valuation. A later serializer change labels preliminary research as research-only and an event decision hold as blocked; deterministic tests and replay checked that change. Correcting the displayed eligibility label does not establish that every downstream consumer enforces it. The original model result remains unchanged, and repeated live availability has not been established.

## F. Findings Against the Evaluation Questions

The engineering tests support selected isolation, cancellation, streaming, scheduling, and persistence paths (VP1). The queue-only load experiment demonstrates bounded admission and per-chat ordering under its synthetic workload.

The repeated SEC study and comparison using the same model answer RQ1 and RQ2 with configuration-dependent trade-offs. Shared-retrieval Team offers lower latency than staged Solo in the pairs using the same model, while Solo has higher strict completion and evidence retention. Shared retrieval reduces main-study resource use relative to raw-context Team, but raw context achieves more strict passes. These results support choosing execution modes according to task requirements.

The financial panels test VP2 through workflows that call the tools and save state. Their strongest evidence is the linkage among sources, model-selected actions, recorded reviews, alerts, and decision holds. Selected MQ, AIG, and RPAY answers also show useful analysis within their supplied evidence. Execution completion, analytical quality, and state policy remain separate properties: each needs its own checks.

# VIII. DISCUSSION

## A. What the Runtime Contributes to Financial Workflows

The runtime manages the work around model reasoning. Sessions preserve task context. The tool registry exposes permitted data and calculation functions, while the scheduler coordinates concurrent tasks. Saved records connect an analysis to later review. Financial workflows use these mechanisms together, allowing source retrieval, calculations, interpretation, and saved state to be checked separately.

The application results should therefore be read at two levels. Execution evidence shows whether the system carried out the requested workflow and preserved the expected state. Content review examines whether the interpretation was supported by the evidence and useful for the research question. The runtime supports this distinction through its traces and records, while the model and available sources still influence analytical quality.

Comparisons of runtime designs must account for the conditions of each run. Latency comparisons must disclose model allocation, provider conditions, output lengths, and call counts. Call count and parallelism may be mechanisms of a runtime design rather than quantities that must always be held equal. Their effects still need to be distinguished from changes in provider behavior and prompts. Completion comparisons likewise depend on evidence and grader consistency. Better attribution may result from a clearer specialist contract rather than a more capable specialist. Observability and replay make these distinctions inspectable; they do not by themselves establish causality.

## B. When Multi-Agent Execution Is Justified

The financial scenarios show that multi-agent execution should be selective. A specialist is justified when it provides independent evidence interpretation, a parallel deep dive, a formal challenge, or a distinct policy perspective. It is not justified merely because a tool has a financial label. Market-data retrieval, ratio calculation, threshold comparison, fingerprinting, and state persistence are deterministic operations and should remain tools.

The `solo_open_book`, `solo_two_pass`, and routed-diagnostic baselines help distinguish sources of performance differences. If Team does not exceed Open-Book, delegation adds overhead without detected outcome benefit. If Team does not exceed Two-Pass, additional synthesis compute rather than role specialization may explain the outcome. If the routed diagnostic exceeds Team, routing or specialist execution is a candidate bottleneck; if Team exceeds it, named roles, the diagnostic prompt, or direct evidence presentation may alter synthesis. The diagnostic is therefore a candidate comparison, not an oracle upper bound.

The contrast between the initial-observation and longitudinal SEC suites clarifies the role of task difficulty. The simple suite was saturated by all four modes and could not measure incremental accuracy. The longitudinal suite created mode-level failures, but the frozen Team and Open-Book rates remained equal. Harder tasks can reveal differences hidden by an easy test, but do not by themselves show that collaboration adds value. The AMD failure further shows that a correctly routed specialist can still return no usable evidence; a multi-agent treatment includes availability, response validation, and retry policy as well as nominal role decomposition.

The completed SEC study distinguishes role count from information flow more clearly than the earlier Pilot. In the main heterogeneous deployment, shared retrieval reduced Team token use and frozen-price estimated cost relative to raw-context Team, but raw context achieved more strict passes and lower mean latency. In the comparison using the same model, shared-retrieval Team was consistently faster than staged Solo, whereas Solo completed every selected task and retained all required final evidence. Evidence compression and parallelism are therefore engineering controls with measurable benefits and failure modes, not automatic improvements to every metric.

These results favor selective delegation. The same runtime can execute a staged Solo workflow when completeness and evidence retention are paramount, or admit parallel specialists when latency matters and their outputs can be checked for missing calculations and evidence groups. Deterministic data collection and state mutation remain tools. Team and Solo are modes of the same runtime. A future routing policy should choose between them according to task requirements.

## C. Financial Value Without Autonomous Trading

The application supports research by connecting evidence, analysis, and persistent review decisions. The system can reduce repeated data collection, expose missing fields, preserve thesis history, surface invalidation conditions, suppress duplicate alerts, and structure disagreement. These outputs are useful even when the final investment decision remains human.

Keeping research assistance separate from trading also simplifies evaluation. Return prediction requires controls for market conditions, benchmarks, turnover, transaction costs, and corporate actions. It must also account for survivorship bias and future information leaking into historical tests. Workflow correctness can be evaluated first with deterministic evidence and state oracles. Predictive evaluation may then be added as a separate layer after the data pipeline satisfies point-in-time requirements.

The fixed-evidence experiment checks whether the coordinator retains supplied evidence and states the required research decision. The retrieval track extends the boundary to archived SEC records fixed before evaluation, explicit evidence selection, specialist summaries, and final synthesis. The tool-backed panels add actual finance-tool calls and persistent ledger mutations, while the isolated live Skill case adds one external market-data fetch before thesis creation. The latter does not validate autonomous filing discovery, all financial tools, broad semantic accuracy, or subsequent portfolio outcomes. The eligibility-label error led to the serializer fix described in Section VII E. Downstream decision paths still need to enforce that label. These separate tests improve diagnosis without validating investment advice.

Return-based analysis should be added only after the data pipeline supports point-in-time constituent universes, dated `as_of` snapshots, corporate-action adjustment, delisting coverage, and explicit look-ahead prevention. It must remain separate from workflow correctness: a system can preserve evidence correctly without profitable forecasts, while a profitable backtest can still be invalid if it leaks future information.

## D. Quality and Resource Trade-offs

The useful deployment question is which execution mode satisfies the task's completion requirements within its latency and cost budget. In the study using the same model for both modes, Team reduced mean latency from 33.62 to 22.42 seconds, but passed 19/24 attempts against Solo's 24/24 and used slightly more estimated cost. The repeated heterogeneous study showed a different resource comparison: shared retrieval used fewer tokens and lower estimated cost than raw-context Team, while raw context passed more cases.

These results support offering both execution paths. Solo is appropriate when the observed completeness advantage matters more than latency; Team is a candidate when parallel specialist work is useful and its output can be checked before acceptance. A future routing policy would need to test that choice prospectively. Token totals must also retain their accounting definitions: provider totals include cache reads, while uncached-input-plus-output measures describe a different quantity.

## E. Generalizability

The architecture could support other tasks that combine stored state with interpretation, such as compliance review, incident response, customer operations, and scientific evidence synthesis. The financial scenarios are nevertheless domain specific. Thesis invalidation, portfolio concentration, and announcement deduplication encode assumptions that may not transfer directly to credit underwriting, high-frequency trading, or personal financial advice.

Generalization should therefore be tested at the mechanism level. Tenant isolation, bounded execution, tool-call pairing, correlated delegation, and evidence provenance are domain-independent mechanisms. The finance case oracles and research methodology are domain-specific configurations layered on top of them.

## F. Threats to Validity

The experiments support different claims at different levels. Synthetic tasks isolate state and policy behavior. Repeated SEC comparisons characterize execution modes. Selected real-source examples demonstrate attainable analysis. None of these sources alone describes the quality of an unrestricted financial assistant.

TABLE_CAPTION: Principal limits on interpreting the reported experiments.

| Issue | Effect on interpretation | Reporting treatment |
|---|---|---|
| Lexical and numeric grounding checks | A supported number may appear in a false explanation; a correct phrase may fail a lexical rule | Report automated check results separately from claim-level review and retain the raw answer |
| Deterministic comparison catalogs | Displayed arithmetic is prepared by the host | Attribute evidence selection and interpretation to the model, and calculation to the checked preparation pipeline |
| Repeated source packets | Repetitions and corpus loads are dependent | Keep issuer and task clusters visible; do not pool observations into a general reliability rate |
| Main-study model allocation | Pro/Flash role assignment differs across modes | Use the subset using the same model for the closer model-matched comparison |
| Multiple execution batches | Provider conditions can affect latency | Retain batch identity and restrict latency findings to the observed runs |
| Case and reviewer selection | Illustrated successes were selected after inspection; local model review is not independent expert validation | Disclose selection, report contrasting outcomes, and identify retrospective, masked, and unblinded reviews |
| Limited end-to-end scope | Most events are pre-ingested; one live data case does not establish continuous source availability | Describe the exact source and tool path exercised |
| Guard coverage | A state hold does not prevent every false comparison or a later erroneous final sentence | Check ledger state and prose separately; report the observed guard misses |

Traces and saved state provide direct evidence of execution. Assessing analytical usefulness also requires checking the claims against their sources. The report uses both kinds of evidence without treating successful execution as proof of sound financial interpretation.

# IX. SECURITY, ETHICS, LIMITATIONS, AND FUTURE WORK

## A. Security Controls

The system applies defense in depth and treats risk management as a lifecycle activity rather than a single filter [27]:

- authenticated cookie or API-key ingress with tenant scope;
- agent ownership and API-key ACL checks on management, observability, and resolved OpenAI-compatible chat targets;
- a six-pattern prompt-injection heuristic before the agent loop and user-message isolation inside the provider payload;
- policy-filtered tool definitions;
- session-scoped sandbox executors with no silent host fallback;
- validated internal source and target ownership for sub-agent calls;
- bounded queues, timeouts, wait-graph cycle detection, and shutdown release;
- trusted plugin execution context and user-filtered financial state;
- optimistic version checks for concurrent thesis and alert updates.

These controls reduce risk but do not prove complete security. The prompt-injection scanner has no dedicated test coverage and is described as an unvalidated heuristic, not a security control with measured detection performance. XML tags separate instructions but do not provide cryptographic isolation. A permissive policy also leaves powerful tools available. Production deployment should use least-privilege presets, network allowlists, secret management, audit retention, parameter validation, human approval for destructive actions, and adversarial testing [13].

The API-key ACL defect identified during review illustrates complete mediation in practice. The former chat path checked explicit agent headers in middleware but could resolve an omitted header to an inaccessible fallback. The handler now checks the resolved target and returns 403 for an inaccessible fallback. An unknown explicit identifier returns 404 rather than selecting a fallback. Behavioral tests cover omitted, inaccessible, unknown, and permitted targets. The correction improves the current endpoint but does not remove the need to audit each new route.

## B. Financial Ethics and Human Oversight

The financial research application is an assistant, not an investment adviser or execution engine. It may organize evidence, apply deterministic calculations, maintain a thesis record, and propose a reversible review action. It must not promise return, infer suitability, size a position for a client, or place an order. NIST AI RMF emphasizes explicit human roles and responsibilities for decisions and oversight [27]. In this application, a human remains accountable for accepting evidence, changing portfolio policy, and authorizing any irreversible external action.

An audit trail supports review but does not replace it. A trace can show which evidence identifier, policy preset, agent, model, and tool call contributed to an answer, but it does not certify that the evidence was licensed, complete, current, or fair. Real deployments must document data rights, retention, market-data terms, and whether generated commentary is shown to a client. Sensitive account or portfolio information must not be placed in model prompts or logs without an approved data-processing basis.

The preliminary fixed-evidence benchmark and synthetic workflow fixtures avoid personal or client data. Later SEC experiments use archived public disclosures, while the separate live Skill case retrieves online market data. Synthetic inputs reduce privacy risk but omit some real-source ambiguity; archived inputs preserve inspectable evidence without establishing live-source availability. Further data collection should preserve publication time and source licenses, redact personal information, and separate research evaluation from any live portfolio workflow. Human reviewers should see evidence and proposed state changes before acceptance, not only a fluent final narrative.

## C. Current Limitations

First, the agent-level turn gate serializes all sessions of one agent because the registry stores mutable session-bound state. The TaskQueue can run different agents concurrently, but true per-session concurrency for one agent requires immutable per-turn registries or a per-session gate.

The per-chat FIFO guarantee begins at successful channel enqueue. Concurrent callers obtain task identifiers under a mutex but send to the queue after releasing it. Their queue insertion order may therefore differ from their identifier order. This does not permit two tasks from one chat channel to execute simultaneously, but callers must not infer a total order from wall-clock invocation or task identifiers under concurrent submission.

Second, session appends are individually persisted rather than committed as one transaction. Normalization repairs interrupted histories, but transactional batch append would provide a stronger consistency model. Store-backed reads can fail open to a stale in-memory session on store error, so cross-replica freshness is best effort rather than guaranteed.

Third, Skills are currently injected in full. Installing a large financial Skill library can consume context and distract the model. On-demand loading is not connected to the production registry, and some Skill paths are prompt-visible without equivalent sandbox mounts. Progressive disclosure should initially expose only names and descriptions, then register and test on-demand loading for one to three selected methods.

Fourth, the fixed-evidence confirmation and original retrieval Pilot have one repetition and remain exploratory. The later SEC study executes 24 configurations with three repetitions per primary mode; the supplementary comparison using the same model covers eight selected configurations. These observations are not official benchmark scores or population estimates. Loads and repetitions derived from a company–task source set must not be counted as independent issuers, and the selected reports for the same-model comparison span two batches.

Fifth, the attribution and numeric-grounding graders rely on lexical matching and source-bound rules. Although they account for several forms of negation, quotation, and numeric variation, wording differences can still cause misclassification. Matching a number to a source record or declared calculation does not establish that the surrounding claim follows from the evidence. Broader factuality assessment requires claim-level semantic review.

Sixth, SQLite WAL supports concurrent access but requires care during backup. The main database file is incomplete while uncheckpointed changes remain in sidecar files. Operational documentation and deployment automation must account for this.

The MessageBus wait graph, TaskQueue, correlation map, and deduplication cache are process-local. The daemon can restart a failed Gateway, but it cannot replay volatile work or determine whether an interrupted external side effect occurred. PostgreSQL support does not make the scheduler distributed, and active-active Gateway replicas do not yet have lease, partition ownership, or durable-queue semantics.

Seventh, the financial layer lacks persistent portfolio holdings and policy limits, outbound alert delivery and retry state, and exchange-calendar-aware scheduling. It also lacks a point-in-time market data store suitable for unbiased backtesting, and Finskills remains an external, unvendored dependency.

Finally, the fixed-evidence confirmation uses compiled, verbatim-copy specialist evidence, while the SEC Pilot and repeated SEC study use archived records and model-based evidence selection. Those studies did not invoke finance tools or mutate the ledger. Later tool-backed panels persist reviews, alerts, screens, and preliminary theses, but their SEC events are pre-ingested or historical and other inputs include synthetic fixtures. The online Skill case verifies one live data fetch and ledger creation. It does not test autonomous filing discovery or repeatability during upstream outages. Its isolated agent used a broad tool preset rather than a command-level Skill allowlist. Preliminary theses now receive a research-only label, but universal enforcement of that restriction by downstream decision consumers has not been demonstrated. These gaps concern workflow execution and controls. They are separate from judgments about the value of an analysis.

## D. Future Work

Longer-term engineering and evaluation work includes:

1. extend the matched Solo/Team comparison beyond its four issuers and one provider family; the larger SEC application panel uses a different task and does not expand that comparison;
2. extend the existing local claim-to-evidence review with independent human labels and broader checks of saved rationales and final explanations;
3. optionally repeat the matched Team/Solo comparison with other model tiers to test transfer beyond the completed subset using the same model;
4. extend the finance-tool and live-Skill paths to autonomous event acquisition, repeated-event idempotency, adverse evidence, and paired Team/Solo execution; add a narrow Skill-command policy and a decision-eligibility guard for price-only preliminary theses;
5. add in-flight model-call, token, cost, and latency budgets together with per-session concurrency;
6. add transactional session append, progressive Skill loading, portfolio policy state, alert delivery, and exchange-calendar support;
7. design durable admission, lease ownership, idempotency, and replay semantics before active-active deployment;
8. construct point-in-time financial datasets before evaluating investment performance.

# X. CONCLUSION

This project designs and evaluates an agent runtime with financial research applications. Its architecture supports staged Solo execution and coordinator–specialist Team execution through shared mechanisms for authenticated requests, tenant-scoped sessions, bounded scheduling, policy-filtered tools, streaming responses, and persistent state. Cancellation, cycle prevention, session-history repair, and per-call telemetry make the execution path observable and constrain common failure modes. Financial workflows use these mechanisms to connect data collection, analytical interpretation, and research-state management.

Executable tests support selected control paths, and the small scheduler load test completed all configured tasks while preserving per-chat ordering and the concurrency limit. The checks verify these functions under the tested conditions. Coverage remains incomplete, and the single-Gateway design does not provide durable distributed scheduling or transparent replay after a process failure.

The execution-mode experiments show useful trade-offs. In the repeated SEC main study, shared-retrieval Team passed 56/72 assigned attempts and staged Solo passed 55/72, with two Solo provider timeouts retained. In the comparison using the same model, Solo passed 24/24 and Team passed 19/24, while Team was faster in every pair and reduced mean latency from 33.62 to 22.42 seconds. Shared retrieval also reduced main-study resource use relative to raw-context Team, although raw context achieved more strict passes. These findings support a runtime that offers both modes and exposes their costs and outcomes for task-specific selection.

The financial application demonstrates how the runtime supports work beyond generating a final answer. Across four workflow families, agents called finance tools, linked evidence to research records, acknowledged alerts, and applied decision holds. The 16-case repetition panel recorded 77/80 passes on the workflow execution checks, and all ten missing-critical-evidence repetitions blocked subsequent use while preserving the existing thesis. A separate live Skill case connected market-data retrieval and arithmetic to a saved preliminary research record.

Several analyses of real disclosures produced useful research observations. MQ answers distinguished business growth from deteriorating GAAP profitability. An AIG answer separated segment-adjusted improvement from weaker consolidated earnings. An RPAY answer identified the impairment base effect behind a narrower GAAP loss. The checked comparison catalogs supplied their arithmetic, while the model identified opposing evidence, explained implications, requested specific further information, and persisted a review decision. These examples demonstrate a working combination of deterministic tools and model interpretation.

Other archived answers contain incorrect comparisons, unsupported inferences, and mismatches between prose and saved state. The successful examples therefore do not establish consistent analytical quality. The contribution is a working runtime, financial research applications built on it, and an evaluation of their observed behavior. Together, the engineering tests, mode comparisons, and application cases show how execution controls and financial reasoning can be combined and inspected. Further work can strengthen semantic checks, state consistency, source acquisition, and deployment resilience.

# APPENDIX A. FINANCIAL CASE ACCEPTANCE CHECKLIST

The following checklist defines answer-level acceptance conditions for the six fixed-evidence calibration scenarios. State changes in this table are actions the answer must propose or describe; this experiment does not execute them. Actual ledger mutations are evaluated separately in the tool-backed studies.

TABLE_CAPTION: Case-level evidence, proposed-state, and policy wording checks.

| Case | Evidence checks | Governance wording checks | Policy checks |
|---|---|---|---|
| Earnings catalyst | Filing ID, date, 18% growth, and 220-bp margin expansion retained | Review references thesis version 4; conviction 3→4; active status | No trade authorization |
| Thesis invalidation | Customer C-17, 31% revenue share, and 25% threshold retained | Decision `invalidate`; expected version 2; invalidated status | No unsupported target price |
| Duplicate event | External event ID and 24-hour window retained | Proposes reusing the alert, incrementing count 1→2, and updating `last_seen_at` | Proposes only one thesis review |
| Incomplete screen | Observed PE/ROE separated from missing free-cash-flow and leverage fields | Candidate excluded with `insufficient_data` | No imputation from model knowledge |
| Portfolio concentration | 62% sector weight, 0.89 correlation, 17% stress loss, and 10% limit retained | Proposed exposure target below 45%; checks scheduled again | No return guarantee; no automatic execution |
| Contradictory evidence | Both dated primary-source claims retained | `needs_review`; conviction unchanged | No convenient-source selection; clarification requested |

Failure classification should identify the layer supported by the retained evidence. In this calibration, that means routing, specialist response, synthesis, policy wording, or infrastructure; a proposed state change is not evidence of persistence. Later tool-backed studies additionally inspect calculation results and actual state transitions. This distinction prevents all unsuccessful outputs from being grouped under a generic “model failure.”

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
2. report raw counts and descriptive rates with their denominators;
3. calculate only the track-specific predeclared paired effects;
4. report Team-only latency and tokens in addition to full-harness totals;
5. disclose simulated specialists, omitted cases, reruns, and pricing assumptions;
6. disclose shared company–task sources and avoid treating repeated calls as independent financial cases;
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

[14] The Go Authors, “The Go Memory Model,” version Jun. 6, 2022. [Online]. Available: https://go.dev/ref/mem. Accessed: Sep. 23, 2026.

[15] SQLite Consortium, “Write-Ahead Logging.” [Online]. Available: https://www.sqlite.org/wal.html. Accessed: Sep. 23, 2026.

[16] SQLite Consortium, “SQLite Backup API.” [Online]. Available: https://www.sqlite.org/backup.html. Accessed: Sep. 23, 2026.

[17] Marqeta, Inc., “Second Quarter 2025 Earnings Release,” exhibit to SEC filing accession 0001522540-25-000020, Aug. 6, 2025. [Online]. Available: https://www.sec.gov/Archives/edgar/data/1522540/000152254025000020/mqearningsrelease-q2x2025.htm

[18] Marqeta, Inc., “Third Quarter 2025 Earnings Release,” exhibit to SEC filing accession 0001522540-25-000033, Nov. 5, 2025. [Online]. Available: https://www.sec.gov/Archives/edgar/data/1522540/000152254025000033/mqearningsrelease-q3x2025.htm

[19] American International Group, Inc., “Second Quarter 2025 Earnings Release,” SEC exhibit, Aug. 6, 2025. [Online]. Available: https://www.sec.gov/Archives/edgar/data/5272/000000527225000077/q22025earningsrelease.htm

[20] American International Group, Inc., “Third Quarter 2025 Earnings Release,” SEC exhibit, Nov. 4, 2025. [Online]. Available: https://www.sec.gov/Archives/edgar/data/5272/000000527225000156/q32025earningsrelease.htm

[21] M&T Bank Corporation, “Second Quarter 2025 Earnings Release,” SEC exhibit. [Online]. Available: https://www.sec.gov/Archives/edgar/data/36270/000162828025034994/ex991release2q25.htm

[22] M&T Bank Corporation, “Third Quarter 2025 Earnings Release,” SEC exhibit. [Online]. Available: https://www.sec.gov/Archives/edgar/data/36270/000003627025000018/ex991release3q25.htm

[23] Repay Holdings Corporation, “Second Quarter 2025 Earnings Release,” SEC exhibit. [Online]. Available: https://www.sec.gov/Archives/edgar/data/1720592/000172059225000010/rpay-ex99_1.htm

[24] Repay Holdings Corporation, “Third Quarter 2025 Earnings Release,” SEC exhibit. [Online]. Available: https://www.sec.gov/Archives/edgar/data/1720592/000119312525274223/rpay-ex99_1.htm

[25] CoStar Group, Inc., “Second Quarter 2025 Earnings Release,” SEC exhibit. [Online]. Available: https://www.sec.gov/Archives/edgar/data/1057352/000105735225000095/q22025earningspressrelease.htm

[26] CoStar Group, Inc., “Third Quarter 2025 Earnings Release,” SEC exhibit. [Online]. Available: https://www.sec.gov/Archives/edgar/data/1057352/000105735225000116/q32025earningspressrelease.htm

[27] National Institute of Standards and Technology, “Artificial Intelligence Risk Management Framework (AI RMF 1.0),” NIST AI 100-1, Jan. 2023, doi: 10.6028/NIST.AI.100-1.
