# Pre-frozen SEC event-to-thesis holdout: first result

## Scope and integrity

The case set, source IDs, numeric oracle, evaluation gates and USD 0.12 estimated-spend stop were written in `../../INSIGHT-QUALITY-PROSPECTIVE-PROTOCOL-v1.md` before the first call. This is a historical SEC-packet replay, not live market analysis. Four event transitions each ran five times in fresh sessions and ledgers: 20/20 planned observations completed. The eight SEC HTML cache files matched their `source-lock.json` SHA-256 entries at preflight. `manifest.json` records the runner, protocol, rubric, evidence, source lock, model, pricing, gateway binary and template DB hashes. `RESULT-SHA256.txt` verifies the 20 unchanged raw `result.json` files.

The model was `deepseek/deepseek-v4-flash`. Cumulative estimated charge was **USD 0.0307392176** against the USD 0.12 stop; it is a token-based estimate, not a provider invoice. There were no HTTP/request errors, unpriced usage or uncertain-cost sequences in the retained records. The experiment process exited normally. The isolated gateway was not left running.

## Execution and first quality judgment

| Case | Mechanical execution | High within case | Adequate within case | Problematic conclusion | No assessable conclusion |
| --- | ---: | ---: | ---: | ---: | ---: |
| H-AMD | 5/5 | 5 | 0 | 0 | 0 |
| H-INTC | 4/5 | 0 | 2 | 2 | 1 |
| H-NVDA | 4/5 | 3 | 1 | 0 | 1 |
| H-NKE | 4/5 | 1 | 3 | 0 | 1 |
| **Total** | **17/20** | **9** | **6** | **2** | **3** |

`INSIGHT-JUDGE-v1.csv` records one rubric row and a reason for every observation. A `not_assessable` quality label is assigned to the three observations without a completed review; they remain **execution failures** and are not silently excluded from the case-level result. All 17 completed responses had the core source numbers, units and period directions correct in this targeted first pass. This does not certify every sentence or validate predictive investment value.

The pre-frozen **within-case stability gate** required five of five execution and fact passes, then at least four of five inference/risk and utility passes without critical error. Only **H-AMD** satisfies it. H-INTC has an execution failure and two material inference failures; H-NVDA and H-NKE each have one execution failure. Therefore the panel fails its cross-case stability target. Do not relabel 17/20 as a general system reliability rate or 9/20 as an investment-insight success rate: repeats within a case are correlated, the set has only four companies, and this arm covers one workflow family.

## What failed

- `H-INTC-r4`, `H-NVDA-r3`, and `H-NKE-r2` returned DSML-like pseudo tool calls as ordinary assistant text (`finish_reason=stop`); each had one priced model call, zero actual tool calls, no linked review and no alert acknowledgement. There was no service timeout or billing error. This is an observed model/runtime interface failure; the records alone do not isolate whether prompt/tool formatting, provider output, or gateway interpretation caused it.
- The current Go loop has a pseudo-tool-markup correction path, but it is conditional on nonempty `toolDefs`. It did not activate in these three records (only one model call, no terminal code). A plausible explanation is that no tool definitions reached this turn, but that has **not** been verified; preserve gateway tool-definition counts and startup logs in the next diagnostic run before attributing root cause.
- The existing isolated test `TestPseudoToolCallTextGetsBoundedNativeCorrection` passed on this checkout when run with loopback access. Thus the narrow unit behavior works; it does not explain or erase the three end-to-end failures.

### Post-run startup diagnosis (not part of the frozen arm)

The experiment helper originally treated an open TCP port as Gateway readiness. The main process starts its HTTP server concurrently with `Gateway.Run`, while `Gateway.Run` starts plugins and only then logs `gateway started`. Five **model-free** isolated startup probes using the old helper found that `/v1/agents` could answer before that marker; in one of five probes there were zero finance-tool registrations at that moment. This is a concrete race that can explain an empty tool set and the pseudo-call text, but the three failed experiment homes did not retain startup logs, so it is **not definitive causal attribution for those specific observations**.

The helper was subsequently changed to wait for the post-plugin `gateway started` marker as well as the TCP port. Five further model-free probes all saw the marker and finance-tool registrations before `/v1/agents` was queried. This change does not alter, replace, or re-score the original 20 observations; a separate new arm is needed to test whether it eliminates the execution failures.
- `H-INTC-r1/r2` over-associated the USD 15.9 billion impairment/accelerated-depreciation bundle and USD 2.8 billion restructuring charges with the gross-margin collapse. The supplied event packet did **not** decompose these charges by income-statement line. The [underlying SEC exhibit](https://www.sec.gov/Archives/edgar/data/50863/000005086324000147/q324_earningsrelease.htm) says USD 3.1 billion of manufacturing-asset charges were substantially recognized in cost of sales, while the USD 15.9 billion bundle also included goodwill/intangible impairment and a USD 9.9 billion deferred-tax-asset valuation allowance. Treating the full bundle as a gross-margin cause is unsupported. The large 20.4-point observed margin decline and a cautious research downgrade can still be valid; the causal explanation is the problem. `H-INTC-r5` explicitly said attribution was not established, but its rationale contained weaker speculative wording, so it was marked adequate.
- `H-INTC-r3` and `H-NKE-r1` recorded `needs_review` because optional context was missing, while final ledger `actionability` remained `available`. Neither final answer falsely claimed a decision hold, so this is flagged as a **semantics/policy question**, not quietly counted as a blocked-state success. It differs from the required-evidence rule tested in the earlier panel.
- H-NVDA respected the nonadjacent-quarter boundary in four completed reviews. H-NKE generally distinguished a change in a YoY digital growth rate from a direct digital-revenue change, although some wording about “sustained” weakness or comparable revenue levels was weak.

## Methodological limits and next action

The cases and rubric were pre-frozen, but the Codex first-pass judge was **not blinded** to mechanical status, contrary to the protocol's planned masked-judge procedure. Treat the 9/6/2 quality split as transparent exploratory adjudication, not a fully protocol-compliant independent score. The original raw outputs are preserved so a future masked reviewer can rescore them. No external finance expert reviewed the answers. These source facts were previously audited for other tasks and the model may have prior knowledge of public filings; this is a holdout of the four case pairings from the 80-run workflow panel, not of the filings themselves.

The next prospective arm should be separate and should not overwrite this result: diagnose and test the pseudo-tool-call terminal behavior, tighten the distinction between packet facts and causal attribution without supplying the desired case answer, and then run an independently frozen real-source screening/candidate-thesis panel plus varied incomplete/conflicting-input controls. Any changed runtime or prompt must be labeled a new configuration, not treated as a retry of these failed observations.
