# Agent Runtime Financial Application Progress

Zheyu Wang | Update for Professor Fong | 28 October 2026

## Application scope

Following your suggestion to test more business and FinTech scenarios, I extended the project to financial research workflows. The runtime now has tested paths for reviewing earnings events, handling conflicting evidence, screening candidates, and diagnosing portfolio risk. These applications connect model analysis to actual tool calls and persistent research records. The results demonstrate working workflows and selected useful analyses, while also identifying limitations in analytical consistency.

The project remains an agent runtime supporting both single-agent and coordinated multi-agent execution. The financial application tests whether it can carry a task from evidence to a recorded research decision. The research ledger stores the investment thesis, supporting sources, review history, and whether the thesis can be used in subsequent decisions; it does not execute trades.

## Workflows tested

- Earnings event review: compare disclosed results with an existing thesis, identify supporting and opposing evidence, save a review, and acknowledge the associated alert.
- Conflicting evidence: examine competing claims or corrections and record whether further review is needed. An unresolved material issue can preserve the existing conclusion while suspending its use in downstream decisions.
- Candidate screening: apply declared financial criteria and data-completeness requirements before saving a preliminary candidate or rejecting it.
- Portfolio risk diagnosis: evaluate concentration and incomplete holdings against declared limits, including cases where missing data requires a bounded conclusion rather than a precise estimate.

## Execution evidence

A repeated panel covered 16 fixed cases, with five independent sessions per case. It recorded 77 passes out of 80 attempts on the configured execution and state checks. In all ten attempts with required evidence missing, the stored thesis was held for review and blocked from subsequent use. This is evidence of workflow execution, not an assertion that 77 answers were analytically correct.

The panel used archived SEC excerpts for earnings events and synthetic inputs for the other three families. A separate screening case used frozen AMD and Intel disclosures: the agent saved a preliminary AMD thesis and rejected Intel under two specified GAAP criteria. Source, arithmetic, and stored-state checks passed for that task.

A separate online AMD case connected a market-data Skill to calculation and a saved preliminary research record. This demonstrates a live data-to-ledger path in one selected session; repeated live-service reliability has not yet been established.

<!-- PAGE BREAK -->

## Examples of useful financial analysis

The following examples compare selected second- and third-quarter 2025 SEC disclosures. A checked comparison catalog supplied the numerical values and differences. The model selected relevant evidence, interpreted it, identified uncertainty, and chose a research action. Correct arithmetic is therefore attributed to the combined system, not to independent model calculation.

### Marqeta growth and earnings quality

Revenue rose from USD 150.392 million to USD 163.306 million, but the GAAP operating loss widened from USD 9.228 million to USD 10.370 million. The selected answers distinguished stronger business activity from improved earnings quality and requested clarification of expense drivers and accounting-basis differences. All five sessions saved reviews and held the thesis pending further evidence; local LLM-assisted review rated four high within the case and one adequate.

### AIG segment and consolidated performance

A selected answer distinguished a USD 241 million increase in General Insurance adjusted pretax income from a USD 625 million decline in consolidated GAAP net income attributable to common shareholders. It avoided treating different accounting measures as equivalent and requested reconciliation before strengthening the research view. The saved thesis was blocked pending review. Other attempts on the same case varied in quality, so this is an illustrative success rather than a consistency claim.

### Repay Holdings and the impairment base effect

A selected answer recognized that the operating loss narrowing from USD 104.904 million to USD 3.009 million followed a quarter containing a USD 103.781 million impairment. Adjusted EBITDA nevertheless fell from USD 31.811 million to USD 31.202 million. It interpreted the GAAP improvement as a base effect rather than demonstrated operating leverage, requested further evidence, and saved a review hold. This example came from a separate six-session panel: all six completed the tool workflow, while local review rated one high, three adequate, and two problematic.

## Interpretation and proposed report emphasis

The application contribution is a traceable connection between evidence, analysis, and persistent research state. The examples show useful distinctions about earnings quality and concrete follow-up questions, rather than merely summarizing reported numbers. Execution checks and content review are assessed separately. Some answers still contain unsupported interpretations or incorrect comparisons, and the quality ratings are local LLM-assisted judgments rather than independent finance-expert validation.

I propose to present the project as an engineering study with financial application case studies. The report will explain the workflows and evaluation methods, summarize repeated execution results, and examine selected successful analyses alongside their limitations. I would appreciate your guidance on whether this application coverage is sufficient for the project report, or whether one particular business workflow needs deeper treatment.

Evidence reference: Project Report, Sections VI I–J and VII C–E. The underlying session outputs, tool records, ledger snapshots, and review records are retained in the project evaluation archive. The panels above are separate studies and are not combined into one quality rate.
