# Frozen multi-issuer SEC screening-to-research panel

Write and hash this protocol, case file, adapter and runner before the first model call. This is a historical four-issuer **single-company** workflow panel, not a contemporaneous cross-company investment ranking or a test of realized returns. Each observation uses a fresh Gateway session and finance ledger. Five repeats each of AMD, NVDA, INTC and NKE: **20 planned**. The sources were previously acquired and independently used in other tests, so this is a new workflow/case configuration, not a blind unseen-filing holdout.

## Input and deterministic screen oracle

`sec_disclosure_screen_singleton_panel_v1.json` freezes one SEC 8-K exhibit per issuer, URL, SHA-256, filing date, fiscal period, values, units and a material counterpoint. The offline adapter verifies all four raw cached HTML hashes at each invocation. It is a test-specific bridge from these historical disclosures into the existing `finance-tools__screen_stocks` tool; it is **not** live market data. Each model request screens exactly one issuer, so differing filing dates cannot be misconstrued as a same-day relative ranking.

The only deterministic screen rules are reported GAAP gross margin >=40% and reported revenue YoY >=0%. AMD Q3 2024 and NVDA Q2 FY2025 are retained. INTC Q3 2024 fails both; NKE Q2 FY2025 fails revenue YoY. These thresholds are workflow fixtures, not an SEC investment recommendation or an economic-value criterion. Do not infer P/E, valuation, forward return or real-time suitability.

The agent is instructed to inspect both retained and rejected outputs. For a retained company it must save one **historical preliminary** research thesis with the full source URL and hash, the material metric values, a countervailing risk and the absence of valuation/price evidence. For a rejected company it must not save a thesis and must explain the exact failed criteria. The instruction prescribes workflow state, not whether the company is an attractive investment.

## Independent gates and report

1. Source/number: cached SEC byte hash and each claimed value, period, reported-vs-currency-neutral basis, and percentage versus percentage-point distinction must match the frozen record. A material wrong figure or metric label fails.
2. Execution/state: genuine paired screen tool call; one source-linked preliminary thesis for retained issuers or zero for rejected issuers; no extras, trades, live-market call, stale next-review date, pseudo-tool text, request/terminal/cost error. The retained/rejected tool result must match the deterministic oracle.
3. Inference/risk: no assertion that passing the narrow screen means attractive valuation; risks must include AMD Gaming weakness, NVDA margin compression, or rejection-specific adverse metrics, as applicable. Do not attribute Intel's whole impairment bundle to gross margin. Missing valuation/price should block investment conclusions, not preliminary research bookkeeping.
4. Insight quality: apply `INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md` to anonymized final answers and persisted records, separate from mechanical labels; record F/I/R/S/U and a source pointer for each non-high score. If the judge is not genuinely blinded or independent, disclose that deviation and do not call the score independent ground truth.

Within a company, stability requires all five execution and material-fact gates, and at least four of five inference/risk and research-utility gates without a critical error. Report each of the four clusters; do not convert correlated repeats into a population reliability rate. This panel covers a second real-source workflow, but together with the event panel it still cannot prove unrestricted financial-insight value across all possible cases.

Freeze the configured Flash model, gateway binary, template DB, plugin, runner, adapter, source/case and rubric hashes in the manifest. Stop before a new call if priced cumulative estimated cost reaches **USD 0.08**, and stop on a request error, unpriced usage or uncertain cost. Keep failed attempts; no overwrite or selective retries.
