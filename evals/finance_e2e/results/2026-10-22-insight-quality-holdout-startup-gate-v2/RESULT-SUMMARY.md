# Separate startup-gated SEC event-to-thesis retest

## Protocol and provenance

This is a new 20-observation arm, pre-described in `../../INSIGHT-QUALITY-STARTUP-GATE-RETEST-v1.md`. It does not overwrite or replace `../2026-10-22-insight-quality-holdout-flash-v1/`. The four case pairings and five repeats, source lock, frozen facts, model (`deepseek/deepseek-v4-flash`), gateway binary, template DB, plugin and agent prompt-generating code were retained. Manifest comparison found changes only in the runner's addition of this addendum to the manifest and in `run_thesis_event_panel.py`'s startup barrier. The barrier now waits for the post-plugin `gateway started` log marker as well as an open TCP port. Eight SEC cache files were hash-verified at preflight. The original 20 `result.json` files in this arm match `RESULT-SHA256.txt`.

The process completed all 20/20 planned observations and exited normally. Estimated token-based cost: **USD 0.0367651088**, below the USD 0.12 stopping limit. No HTTP/request error, unpriced usage or uncertain-cost sequence was retained. This is historical SEC-packet research, not live market analysis or investment advice.

## Separate execution and conclusion outcomes

| Case | Executed review and alert acknowledgement | High within case | Adequate within case | Problematic conclusion |
| --- | ---: | ---: | ---: | ---: |
| H-AMD | 5/5 | 3 | 2 | 0 |
| H-INTC | 5/5 | 0 | 2 | 3 |
| H-NVDA | 5/5 | 4 | 1 | 0 |
| H-NKE | 5/5 | 1 | 4 | 0 |
| **Total** | **20/20** | **8** | **9** | **3** |

The old arm had 17/20 execution completions and three pseudo-tool-call prose endings; this new arm had 20/20 actual finance-tool workflows. The five model-free startup probes with the old helper observed one agent request before finance-tool registration; five probes with the new barrier observed registered finance tools in all five. Together these support the startup-readiness race as a plausible contributor and show an operational improvement in this configuration. They do **not** prove a sole causal explanation for the old three failures or a population reliability rate. Neither arm had independently randomized startup timing, and 20 observations are a small correlated panel.

The first-pass Codex judge record is `INSIGHT-JUDGE-v1.csv`. It was not blinded to runtime status and has no independent finance-expert adjudication; its labels are exploratory. Core figures and directions in the 20 completed reviews matched the locked packet values in this targeted pass, but three Intel reviews had material inference problems:

- `H-INTC-r1` and `H-INTC-r3` associated the full USD 15.9 billion impairment/accelerated-depreciation bundle with gross-margin compression. The [SEC earnings exhibit](https://www.sec.gov/Archives/edgar/data/50863/000005086324000147/q324_earningsrelease.htm) separates about USD 3.1 billion substantially recognized in cost of sales from other goodwill/intangible and deferred-tax-asset items. The four-field event packet did not provide a line-item bridge. Attributing the full bundle to gross-margin causation is unsupported.
- `H-INTC-r4` correctly observed gross margin falling 20.4 percentage points, but then treated the thesis's **material margin deterioration** invalidation as though it also required sustained deterioration. The stored thesis has separate invalidations for `sustained segment weakness` and `material margin deterioration`. Maintaining conviction on that mistaken condition is a decision-relevant inference error.
- `H-INTC-r1` also persisted a malformed rationale ending with JSON-like evidence text while its structured review `evidence` array was empty. The review remained linked to the alert and event source, so the mechanical checker passed, but structured evidence fidelity was weaker than intended.

The protocol's within-case stability gate required 5/5 execution and factual fidelity, plus at least 4/5 sound inference/risk and research utility with no critical error. H-AMD, H-NVDA and H-NKE meet that **small-panel within-case** gate; H-INTC does not. Therefore this arm **fails the planned cross-case financial-insight-quality target despite 20/20 workflow execution**. It strengthens the runtime execution evidence but cannot justify “stable high-quality financial insights” as a system-wide claim. The experiment covers one workflow family and curated historical source packets, not complete filings, real portfolio data, future return outcomes, or an independently blinded expert score.

## Next engineering and evaluation boundary

Preserve both arms. Do not retrofit the Intel answer or silently change its label. A new configuration should expose the relevant primary-source charge composition or require the agent to explicitly leave causal attribution unresolved; the latter rule must be general and tested on unrelated filings, not phrased as the Intel answer. Separately test the production gateway's readiness semantics, since the CLI web listener can accept requests before plugin initialization completes. Then extend to real-source screening and other financial workflows with the same source/fact/state separation and a masked or external quality judge where available.
