# Prospective financial-insight evaluation protocol v1

Frozen before generating any observations for this protocol. This document is not an assertion that the experiment has run or that financial value has been demonstrated.

## Question and inference boundary

Can the existing runtime repeatedly execute a source-grounded event-to-thesis workflow and produce a decision-useful, numerically faithful, uncertainty-aware research explanation? “Decision-useful” here means a clear supported implication or a justified deferral. It does **not** mean a profitable recommendation or future-return prediction.

The previous 80-observation panel was used for diagnosis and rubric calibration. It is not counted as holdout evidence. This first prospective stage uses four event transitions that were **not** E cases in that panel. Their SEC documents and human-audited fact records already exist in `source-lock.json` and `evidence.json`; therefore this is a holdout of workflow *case pairings and outputs*, not a claim that the underlying filings were unknown to the research team or model pretraining. All prompts, facts, source hashes, oracle rules, and costs must be frozen in a run manifest before the first model call.

## Case set and independent numeric oracle

Each case starts with a fresh thesis and ledger seeded from the baseline filing, ingests the current filing as an event, and lets the agent write a linked review and acknowledge the alert. The prompt must not dictate the review decision or conviction. Five fresh independent sessions and ledgers per case: **20 observations planned**. Do not drop a failure and replace it with a retry.

| Case | Baseline → event, source IDs | Required common metrics | Correct bounded interpretation |
| --- | --- | --- | --- |
| H-AMD | Q2 2024 → Q3 2024, `FSEC-AMD-01` → `FSEC-AMD-02` | revenue, GAAP gross margin, gaming revenue | Revenue 5,835 → 6,819 USD m (+984; +16.86% period-to-period), margin 49% → 50% (+1 percentage point), gaming 648 → 462 USD m (−186; −28.70%). Growth and segment weakness coexist. |
| H-INTC | Q2 2024 → Q3 2024, `FSEC-INTC-02` → `FSEC-INTC-03` | revenue, GAAP gross margin | Revenue 12,800 → 13,300 USD m (+500; +3.91%); margin 35.4% → 15.0% (−20.4 percentage points). Current filing separately reports restructuring and impairment-related amounts; do not sum them without checking overlap and period/basis. |
| H-NVDA | Q2 FY2025 → Q4 FY2025, `FSEC-NVDA-02` → `FSEC-NVDA-03` | revenue, GAAP gross margin, data-center revenue | Revenue 30,040 → 39,331 USD m (+9,291; +30.93%); margin 75.1% → 73.0% (−2.1 points); data center 26,300 → 35,600 USD m (+9,300; +35.36%). These are **nonadjacent** fiscal quarters, so do not call this Q/Q growth. |
| H-NKE | Q4 FY2024 → Q2 FY2025, `FSEC-NKE-01` → `FSEC-NKE-02` | revenue, GAAP gross margin, Nike Brand Digital YoY rate | Revenue 12,606 → 12,354 USD m (−252; −2.00% across nonadjacent quarters); margin 44.7% → 43.6% (−1.1 points); reported Digital YoY rate −10% → −21% (11 points worse). A change in a YoY rate is **not** a digital-revenue change. Nonadjacent and seasonally different quarters preclude a clean trend claim. |

Figures above are extracted from the locked `evidence.json`; the experimental source of truth is the SEC HTML byte cache named in `source-lock.json`, not this table. Before running, verify every cached file's SHA-256 and re-check the table against source locators. Tolerate only explicitly documented rounding in any output comparison.

## Gates, judged separately

1. **Execution/state gate:** actual paired model/tool calls; one linked review; alert acknowledgement; source IDs/hashes and observed metrics retained; version change and `needs_review`/hold/actionability state consistent with the workflow; no trade or unexpected ledger mutation; no terminal/request/cost uncertainty. A prose imitation of a tool call is a failure.
2. **Fact/calculation gate:** all material claimed numbers, units, reporting periods, GAAP/segment basis, directions, and derived differences match the locked source and deterministic arithmetic. A missing comparison may reduce utility, but a fabricated or mislabelled one fails this gate. Do not treat exact reproduction of the example prose as necessary.
3. **Inference/risk gate:** no unsupported causal explanation, false claim of source independence, period conflation, omitted material counterevidence, or actionable recommendation requiring missing valuation/price inputs. A supported hold or deferral can pass. Explicitly check H-NVDA and H-NKE nonadjacent-quarter language, and H-INTC charge overlap.
4. **Research-utility gate:** the answer states a supported thesis implication and what evidence would change it, rather than merely copying metrics. Score using `INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md`; retain a quote/pointer for each 0 or 1. The judge receives frozen source/ledger results and an anonymized answer, not the generating run's mechanical-pass label.

For a **case** to count as stable under this small panel, all five repeats must pass execution and fact gates; at least four of five must pass inference/risk and research utility with no critical error. This is an intentionally stringent *within-case* descriptive gate, not a population reliability estimate. Report each case and each repeat, all failures, and uncertainty intervals where proportions are shown. Aggregate “high” counts alone are insufficient; correlated repetitions and four-company coverage limit generalization. Do not alter this threshold after seeing outputs.

## Controls, provenance, and spending

- Keep model, temperature/sampling parameters, system instruction, tools, runtime binary, template DB, plugin, source packet, prompt text, and judge rubric fixed and hashed. Use fresh sessions and isolated ledgers. Record every request, response, usage/cost estimate, error, tool trace, and terminal code.
- Use Flash as the first model because this tests the runtime workflow rather than a particular premium model; identify the exact provider/model in the manifest. Model comparisons or prompt changes require separate arms and directories, never overwriting this arm.
- Stop **before** a new call if the cumulative priced estimate reaches USD 0.12; stop on request error, unpriced usage, or uncertain cost. This is a new local experimental cap, not permission to raise the prior experiment's cap. If no authorized provider/healthy gateway is available, run only offline preflight and report the absence of live observations.
- Preserve all original outputs and SHA-256 hashes. Judge calibration findings may motivate later fixes, but do not silently apply those fixes to this frozen arm.

This stage alone cannot prove stable high-quality insights across all financial workflows. After it, add a separately frozen real-source screening/candidate-thesis panel and realistic (possibly privacy-safe) portfolio cases, including incomplete and conflicting inputs. An independent human finance review would strengthen construct validity when available; its current absence must remain explicit.
