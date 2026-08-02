# SEC Retrieval-Mediated Orchestration Pilot

## Research question

This pilot evaluates a realistic financial-research topology in which source
acquisition consumes context before analysis begins. It asks whether retrieving
one bounded evidence packet and sharing it across parallel specialists preserves
financial conclusions more efficiently than either a monolithic agent, a
sequential single-agent pipeline, or a team that repeatedly receives the raw
corpus.

The pilot does **not** test investment returns, forecast skill, or autonomous
trading. It tests the runtime mechanisms that sit between primary-source
documents and an evidence-bounded research memorandum: retrieval, context
allocation, specialist delegation, synthesis, grounding, latency, and cost.

## Data integrity and controls

- Case: `nvda-longitudinal-medium`.
- Input: 30,518 characters assembled from locked SEC primary-source records.
- Suite SHA-256: `7b73f4b82a3f97cb1151b372dcf8172eb88c04d37e1e137ed80b2a87bfb44e20`.
- Source-lock SHA-256: `a4d4b4dc3be440238e3d428d60d04fb4a4a9d21d8c0b4eec4cb313e2e181fe22`.
- Common protocol: all modes received the same task, required sections,
  declared calculations, rounding rule, evidence identifiers, and grounding
  threshold. Expected calculation answers were withheld from non-oracle modes.
- Model assignment: coordinator and Solo used `deepseek-v4-pro`; retriever and
  specialists used `deepseek-v4-flash`. Thinking mode was disabled to keep
  visible-output and token accounting stable.
- Grounding pass threshold: at least 95% of extracted numeric assertions had to
  be supported by the locked corpus or declared calculations.
- Execution: one repetition. The results are descriptive pilot observations,
  not confidence-bounded estimates.

## Experimental modes

1. `solo_monolithic`: one Pro call receives the raw corpus and performs
   retrieval, multi-perspective analysis, and synthesis in one context.
2. `solo_staged`: one Pro agent performs retrieval, three sequential analytical
   passes, and final synthesis in isolated stages.
3. `team_shared_retrieval`: one Flash retriever produces a bounded evidence
   packet; a Pro coordinator sends the packet once through a batch delegation to
   three parallel Flash specialists and synthesizes their summaries.
4. `team_raw_context`: a Pro coordinator sends the full raw corpus once as
   shared batch context to the same three parallel Flash specialists.
5. `oracle_evidence`: one Pro synthesis call receives the perfect gold evidence
   packet. This is a diagnostic upper bound, not a deployable baseline.

## Pilot results

| Mode | Strict pass | Milestones | Final evidence recall | Grounding | Latency | Tokens | Cost (USD) | Compression |
|:---|:---:|---:|---:|---:|---:|---:|---:|---:|
| Solo monolithic | No | 2/3 | 100% | 98.29% | 55.96 s | 15,259 | 0.008263 | N/A |
| Solo staged | Yes | 3/3 | 100% | 95.45% | 141.04 s | 37,693 | 0.020690 | 6.12x |
| Team shared retrieval | Yes | 3/3 | 100% | 98.28% | 89.81 s | 42,829 | 0.011987 | 7.58x |
| Team raw context | No | 3/3 | 100% | 94.87% | 104.61 s | 69,553 | 0.022884 | N/A |
| Oracle evidence | Yes | 3/3 | 100% | 100% | 37.89 s | 7,095 | 0.002464 | N/A |

All five observations use the same suite and source-lock hashes. The final
records are split across three files because the modes were rerun selectively
after trace-integrity validation:

- `2026-08-02-retrieval-pilot-v8-nvda-medium-final.json`: shared-retrieval Team
  and Oracle.
- `2026-08-02-retrieval-pilot-v9-nvda-medium-baselines.json`: monolithic Solo
  and staged Solo. Its raw-context observation is superseded.
- `2026-08-02-retrieval-pilot-v10-nvda-medium-raw-trace.json`: final raw-context
  Team after structured batch-trace compaction.

## Interpretation

The strongest fair accuracy comparison is `team_shared_retrieval` versus
`solo_staged`. Both passed all three milestones and preserved every gold
evidence group, so this case does not show an incremental final-answer accuracy
gain from multiple agents. It does show a different efficiency frontier. Shared
retrieval reduced wall-clock latency by 36.32% and estimated cost by 42.06%,
while using 13.63% more provider-total tokens. The cost reduction despite the
token increase follows from heterogeneous allocation: specialist work used
Flash while every staged-Solo call used Pro. Shared retrieval also improved
retrieval precision from 66.67% to 100%, grounding by 2.82 percentage points,
and evidence compression from 6.12x to 7.58x.

The raw-context ablation isolates the value of context allocation within a
multi-agent topology. Relative to `team_raw_context`, shared retrieval reduced
latency by 14.15%, tokens by 38.42%, and cost by 47.62%, while improving
grounding by 3.40 percentage points. Raw-context Team generated eight unsupported
or unrequested numeric forms and missed the 95% threshold by 0.128 percentage
points; shared-retrieval Team generated two. Both used one parallel batch
delegation with perfect target precision and recall, so the principal treatment
difference was evidence compaction rather than the number of delegations.

The monolithic call was fastest among deployable modes, but it omitted the
required separation between sourced facts, derived calculations, and judgment.
This is a workflow-compliance failure rather than a retrieval-recall failure.
The Oracle result quantifies remaining system overhead but cannot be treated as
a production competitor because it assumes perfect retrieval.

For Team modes, `analysis_latency_ms` is the sum of specialist model-service
times; specialists execute concurrently, so it must not be added to wall-clock
latency. The mode-level `latency_ms` is the end-to-end wall-clock measure.

## Engineering calibration, excluded from inference

Earlier calibration exposed a runtime issue: copying the same evidence into
three separate tool arguments could exceed trace/request field budgets and made
delegation attribution unreliable. The runtime now supports one batch
`spawn_subagent` call containing one `sharedContext` plus three concise tasks,
and compacts batch traces while preserving valid JSON and agent identifiers.

An early Team calibration consumed approximately 225.9 seconds, 113,665 tokens,
and USD 0.0301; the final shared-retrieval Team consumed 89.8 seconds, 42,829
tokens, and USD 0.01199. These correspond to reductions of approximately 60.2%,
62.3%, and 60.2%. They are engineering calibration figures only: prompts,
coordinator configuration, thinking mode, grader behavior, and runtime batching
changed together, so the difference is not a controlled causal estimate.

## Validity limits and confirmatory design

- The sample contains one company, one corpus load, one task, and one
  repetition; no significance test is appropriate.
- The heterogeneous Team and all-Pro staged Solo are system-level alternatives,
  not model-capacity-matched treatments.
- Mode execution was not randomized, so provider load and cache state may
  confound latency.
- The numeric grounding grader verifies corpus membership and declared
  calculations; it is not a full semantic-entailment judge.
- Calibration runs `v1` through `v7` informed implementation and grader fixes
  and must not enter confirmatory statistics.

The confirmatory study should freeze the suite and grader, execute all four
companies at small, medium, and large corpus loads with at least three
repetitions, randomize mode order within each case-repetition block, preserve
paired identifiers, and report paired differences with bootstrap confidence
intervals. A model-capacity-matched ablation should additionally compare an
all-Pro Team, an all-Flash Team, and a staged Solo using the same per-stage model
allocation.
