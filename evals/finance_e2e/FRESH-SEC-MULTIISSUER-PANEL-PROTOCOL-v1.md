# Forward-looking real-source finance insight panel (v1)

## Purpose and status

This is a pre-output protocol for a three-issuer SEC event-to-thesis panel. It extends the prior four-issuer development set with AAPL, MSFT, and SBUX. The source facts and six raw-document hashes are frozen in `fresh_sec_panel_v1.json` (SHA-256 `a8f959d7bc7726d402a445069bc2b36fef041563a2e7aef51424a2b9b6c9950e`). The already-used five-dimension judge rubric is `INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md` (SHA-256 `d8d3f69c5acce9f29406195cc2cc6981bcb38247194f47e4c33df481a3503032`). **No model outputs exist for these cases at protocol freeze.** The panel is a forward-looking test of the current runtime, not a blinded company holdout from the investigator.

Source audit: the selected facts, units, fiscal periods and comparison bases were checked against the exact SEC exhibit URLs and recorded in `FRESH-SEC-SOURCE-AUDIT-v1.md`. The six original exhibit HTML files were then cached under `.cache/sources/`; their individual byte hashes are in the case corpus and must pass preflight. If a discrepancy is found, issue a numbered corpus revision before any paid run. Do not silently alter v1 after observations exist. SEC excerpts are input evidence; the system is not claimed to have parsed a complete filing.

## Run design

- Three case clusters, five independent repeats per case, **15 observations total**. Fresh session, database and initial thesis/alert per repeat; fixed agent policy, tool versions, model, prompt template, timeout, maximum iterations, and cost pricing. Randomize case order with a recorded seed. No adaptive retry, selective replacement or prompt editing within the panel.
- All 15 must use the real finance-tool event ingestion, thesis review and alert acknowledgement path. The review-only agent may not save a thesis or trade. The trusted harness classifies accounting line and source-explicit links; the model must state causal claims through the accounting-lineage guard. Freeze code, source, rubric and prompt hashes before the first call.
- Cap estimated model spend at **USD 0.10** for this panel, and stop before the next observation if that cap would be exceeded based on the current cumulative estimate and conservative next-call bound. Preserve any failure, timeout, or budget stop in the denominator with its cause. Actual provider billing may differ from estimates. Do not treat account-balance interruptions as runtime quality failures; report them separately.
- Do not send retained internal model outputs to an external service without separate authorization. New prompts may contain only the newly selected SEC facts, source links, initialized thesis/alert identifiers and task instructions.

## Distinctive challenges fixed before model execution

| Case | Decision-relevant trap | Required distinction |
| --- | --- | --- |
| AAPL | Revenue rises while GAAP EPS falls and a tax-adjusted EPS figure is higher | GAAP vs non-GAAP; income-tax event vs operating performance; different year-over-year and adjacent-quarter comparisons |
| MSFT | Cloud dollars rise while disclosed year-over-year growth percentages decelerate | Absolute revenue vs growth rate; Microsoft Cloud vs Azure; no invented Azure-dollar series |
| SBUX | Comparable sales, traffic and margin weaken despite a turnaround plan | Rate deterioration vs actual sequential dollars; management intention vs measured outcome; GAAP margin level vs year-over-year basis-point commentary |

## Scoring and decision rules

First, report deterministic execution separately: actual required tool calls, source packet equality, one linked review, guard acceptance or a correctly surfaced rejection, alert/state version, no prohibited mutation, usage/error trace. Never convert execution success into insight success.

Next, score each raw final answer together with the persisted review and ledger using F/I/R/S/U from the frozen rubric. Record every material claim and exact packet/result pointer. Count `high_within_case`, `adequate_within_case`, `problematic`, and `not_assessable` for each case and all 15 observations. Codex is the first-pass judge; it is not blind, not a finance expert, and not an independent gold standard. A second judge or expert is desirable but currently unavailable. Preserve raw JSON, database snapshots, adjudication CSV and SHA-256 list. Do not tune against results before reporting them.

An internal *panel-consistency gate* is met only if every cluster has at least 4/5 `high_within_case`, zero critical errors across all 15, 15/15 mechanically complete, and all 15 factual/numerical scores F=2. This is intentionally strict and descriptive; passing it would justify only “consistent in this pre-specified real-source panel,” not general stable high-quality production, investment value or predictive returns. Failure must be reported without post-hoc exclusions. Cross-workflow transfer and a larger issuer/industry sample remain separate requirements for a stronger broad claim.
