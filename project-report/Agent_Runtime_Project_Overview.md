# Design and Evaluation of an Auditable Agent Runtime

Zheyu Wang  |  Project Overview  |  October 2026

## Project focus

This project designs and evaluates a Go-based runtime for large language model agents. The central question is how one runtime can support both staged single-agent (Solo) execution and optional coordinator–specialist (Team) execution while keeping identity, tool access, state, concurrency, cancellation, and resource use observable and controlled. The project does not assume that Team is inherently more accurate. It studies the engineering properties and trade-offs of both modes within the same system.

## Implemented system

The runtime accepts authenticated requests through web, API, and channel interfaces and keeps user and agent state separate. It schedules work in per-chat order, limits independent root tasks, and correlates internal requests and replies during delegation. Policy filtering restricts available tools; cancellation, timeouts, and cycle detection bound execution. A provider abstraction supports streaming responses, while persistent sessions, plugin and MCP integrations, sandboxed execution, and role-level telemetry make behavior inspectable. The engineering work also addresses partial failures, including interrupted streams, incomplete tool-call histories, and uncertain outcomes after a process restart.

## Evaluation and current findings

Financial research serves as an application testbed because it combines source-based evidence, deterministic calculations, and model-assisted interpretation. The evaluation uses executable control-path tests, fixed-evidence tasks, and repeated tasks built from a locked set of SEC source materials. It records execution errors separately from scored output failures and preserves results for offline review.

In the main repeated study, staged Solo passed 55 of 72 assigned attempts, with two other attempts ending in provider timeouts; shared-retrieval Team passed 56 of 72 without infrastructure errors. This study used different model tiers across roles, so it does not isolate the effect of execution mode. A separate all-Flash comparison matched model tier across modes in 24 paired repetitions. Team was faster in every pair and reduced mean end-to-end latency from 33.62 to 22.42 seconds, while Solo had higher strict completion (24/24 versus 19/24). Team also used more tokens and slightly higher estimated cost. These findings support a selective choice between Solo and Team according to completion and latency requirements, rather than a claim that either mode is universally superior.

## Scope and next steps

The project demonstrates selected runtime control paths and a reproducible way to compare execution modes. It does not establish production-level reliability, complete factual correctness of generated analyses, or investment performance. The next steps are to review scored failures more closely, extend the task and provider panel, and test a complete workflow that invokes financial tools and writes versioned research state.
