# Speaker notes

## Slide 1

Suggested time: 30 seconds

This project develops an agent runtime that supports both individual and coordinated agent execution. My focus is the engineering layer around the language model: how a request becomes tool calls, how execution proceeds, and how the system retains the resulting state and evidence. I will explain the design, show how it supports financial research workflows, and summarize the results and their limitations. I will also explain how the runtime handles clarification within a conversation.

Sources: /Users/m0yuw/Downloads/fastclaw-complete-device-migration-2026-08-11/fastclaw-finance-e2e/project-report/fastclaw_project_report.md

## Slide 2

Suggested time: 50 seconds

A model can generate a plausible answer without giving us a dependable application. A financial research task may require several data sources, calculations, tool calls and persistent updates. The runtime needs to control execution and preserve enough context for the next step. It must also let us inspect what actually happened. My objective is to implement these mechanisms and evaluate them through concrete workflows. Financial analysis provides a demanding application because source periods, accounting definitions and saved research decisions all matter. I do not assume that successful execution automatically implies a financially sound conclusion.

Sources: /Users/m0yuw/Downloads/fastclaw-complete-device-migration-2026-08-11/fastclaw-finance-e2e/project-report/fastclaw_project_report.md

## Slide 3

Suggested time: 70 seconds

Requests enter through the web interface, APIs or other channels. Authentication resolves the user and target agent before the runtime starts work. Inside one Gateway process, the message bus connects requests and responses, while the task queue controls admission and per-chat ordering. The agent loop assembles the prompt, invokes a model and executes permitted tools. External model providers, plugin processes and sandboxed execution support this loop. SQL storage and workspace storage retain sessions and application records. Telemetry connects individual calls to the execution. A key boundary is that the queue and pending correlations are process-local. Persistent storage does not by itself make this a distributed scheduler or provide transparent recovery of interrupted external actions.

Sources: /Users/m0yuw/Downloads/fastclaw-complete-device-migration-2026-08-11/fastclaw-finance-e2e/project-report/fastclaw_project_report.md, Sections III and IV. Architecture asset: project-report/diagram-candidates/01-runtime-architecture.png.

Diagram explanation: The diagram summarizes logical request flow. Identity and scope checks belong to Gateway ingress, not a separate deployed service. Session and trace adapters execute in process and persist records to storage. Tools include in-process adapters and separate plugin processes.
Visual: conceptual diagram generated with the built-in image generation tool from the project architecture, not a product screenshot.

## Slide 4

Suggested time: 70 seconds

The implementation concentrates on four concerns. First, the scheduler limits concurrent root work and serializes work within each chat. Cancellation and execution timeouts constrain a running request. Second, session handling repairs tool-call histories and compacts long conversations so later calls remain usable. Compaction is a context-management mechanism, and this report does not isolate its causal effect on answer quality. Third, the runtime filters tools and binds execution to a trusted user and agent scope. Native plugins run in separate processes. Finally, the runtime records calls and outcomes so that a failure can be examined at the provider, tool, delegation or application-state layer. The implementation still has incomplete test coverage and does not provide a comprehensive security guarantee.

Sources: /Users/m0yuw/Downloads/fastclaw-complete-device-migration-2026-08-11/fastclaw-finance-e2e/project-report/fastclaw_project_report.md

## Slide 5

Suggested time: 50 seconds

The runtime supports both modes rather than treating them as competing products. In staged Solo execution, one agent carries out the analysis stages. In Team execution, a coordinator delegates focused tasks and combines specialist outputs. Delegation uses the runtime's request correlation and scheduling mechanisms. Parallel specialists can reduce elapsed time, but each handoff creates another opportunity to omit evidence or lose a calculation during synthesis. The appropriate choice therefore depends on the task. My experiments examine these trade-offs instead of trying to prove that more agents are always more intelligent.

Sources: /Users/m0yuw/Downloads/fastclaw-complete-device-migration-2026-08-11/fastclaw-finance-e2e/project-report/fastclaw_project_report.md

Diagram explanation: The three specialists illustrate fork-and-join execution, not a fixed team size. Synthesis is the coordinator combining returned results. The diagram omits retrieval-stage details and scheduling internals.
Visual: conceptual diagram generated with the built-in image generation tool from the project architecture, not a product screenshot.

## Slide 6

Suggested time: 60 seconds

Following the suggestion to test more applications, I expanded evaluation across four workflow families. Earnings review connects disclosures to a research view. Screening checks companies against criteria and creates preliminary research records. Portfolio diagnosis examines supplied holdings and limits. Conflict handling preserves the existing thesis while blocking its downstream use until the uncertainty is resolved. These tasks exercise actual financial tools and ledger operations, including reviews and alerts. Most inputs are frozen disclosures or synthetic fixtures, which makes outcomes inspectable. A separate online Skill case retrieved market data and created a preliminary research record. That isolated live case does not establish continuous source availability.

Sources: /Users/m0yuw/Downloads/fastclaw-complete-device-migration-2026-08-11/fastclaw-finance-e2e/project-report/fastclaw_project_report.md, Sections VI-F, VI-G and VII-C through VII-E.

Diagram explanation: The diagram groups four alternative input families, not four mandatory inputs to every task. Saved reviews and decision holds can coexist. A hold preserves the thesis while blocking its downstream use. Most tests use frozen or synthetic inputs.
Visual: conceptual diagram generated with the built-in image generation tool from the project architecture, not a product screenshot.
Portfolio diagnosis is read-only and does not require a ledger update. The persistence branch illustrates the research-update workflows.

## Slide 7

Suggested time: 90 seconds

This case illustrates what a useful analysis looks like within the workflow. The task compares selected Marqeta SEC earnings-exhibit data for the second and third quarters of 2025. Revenue and company-defined adjusted EBITDA both increased, but the GAAP operating and net losses widened. The important insight is the distinction between growing activity and improving accounting profitability. Gross profit increased by 10.496 million dollars, while operating expenses increased by 11.638 million. The difference explains the 1.142 million deterioration in the operating result. A checked comparison catalog supplied the arithmetic. The model selected and interpreted the evidence, identified the opposing signals, and requested further information on expense drivers and accounting reconciliation. All five sessions saved linked reviews, acknowledged their alerts, and kept the thesis held and blocked. Local review rated four answers high and one adequate. This is a selected demonstration of useful analysis, not independent expert validation or an estimate of general analytical quality.

Sources: /Users/m0yuw/Downloads/fastclaw-complete-device-migration-2026-08-11/fastclaw-finance-e2e/project-report/fastclaw_project_report.md, Section VII-D, Marqeta case. SEC Q2: https://www.sec.gov/Archives/edgar/data/1522540/000152254025000020/mqearningsrelease-q2x2025.htm ; SEC Q3: https://www.sec.gov/Archives/edgar/data/1522540/000152254025000033/mqearningsrelease-q3x2025.htm

## Slide 8

Suggested time: 80 seconds

This slide separates three kinds of evidence. The charts show the comparison using the same model, where all model calls in both modes use the same model tier. Across eight configurations and three repetitions, Team completed faster in all 24 pairs. Its mean latency was 22.42 seconds versus 33.62 for Solo. However, Solo passed all 24 strict checks and Team passed 19. Team failures involved omitted calculations or missing final evidence, so speed came with a completeness trade-off. The configurations share source material from four issuers, and the study ran in two batches. Separately, the financial workflow panel recorded 77 passes on workflow checks in 80 attempts. Those checks concern the configured workflow requirements, not comprehensive insight quality. Finally, the queue-only load test ran 48 synthetic tasks across 12 chats, repeated five times for each concurrency setting. Tasks completed with ordering and concurrency limits intact. This excludes provider and database workload and does not measure production capacity.

Sources: /Users/m0yuw/Downloads/fastclaw-complete-device-migration-2026-08-11/fastclaw-finance-e2e/project-report/fastclaw_project_report.md, Sections VII-A, VII-B and VII-C.

## Slide 9

Suggested time: 55 seconds

This slide illustrates how task clarification fits into session management. A user asks to compare the latest results, but the company and periods are missing. The agent can ask a focused question. The runtime pauses the current turn before executing the other tools in that response and saves the question. The user replies in the same conversation, and the next turn uses the original request, question and reply to continue. This is a conversational pause and does not keep a worker blocked. It also does not undo actions from earlier turns. The dialogue is an explanatory example rather than a recorded experiment.

Source: project-report/fastclaw_project_report.md, Section IV-A.

## Slide 10

Suggested time: 30 seconds

The main contribution is an inspectable runtime that connects model reasoning to controlled execution and persistent application state. The financial workflows show how these mechanisms support research beyond a standalone answer. The experiments also make the trade-offs visible, including faster Team execution and imperfect evidence retention. The next focused steps are to evaluate the clarification behavior and improve checks that link conclusions to their evidence. I would welcome feedback on whether the application coverage and engineering evidence are sufficient for the project report.

Sources: /Users/m0yuw/Downloads/fastclaw-complete-device-migration-2026-08-11/fastclaw-finance-e2e/project-report/fastclaw_project_report.md