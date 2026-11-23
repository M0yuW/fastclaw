# Evidence-bundle v3 engineering pilot — first-pass review

This is a **three-known-case engineering pilot**, not a new-issuer holdout or
statistical evidence of stable financial-insight quality. It reused source-
audited AFRM, SOFI and UPST disclosures. Raw model answers, tool traces,
ledger snapshots and host-assembled notes are retained in the result files;
the raw result hash manifest is unchanged. Codex is a non-independent first-
pass reviewer, not a finance-expert gold standard.

## Execution and assembly

| Case | Original tool/ledger workflow | Envelope/host assembly | Why |
|---|---|---|---|
| SOFI | Complete; review `maintain`, alert acknowledged | Held | Model put period digits (`CY2024 Q3`, `CY2024 Q2`) in a qualitative field; the predeclared no-digit boundary rejected it. This is a schema failure, not a discovered arithmetic error. |
| AFRM | Complete; review `needs_review`, alert acknowledged | Assembled | JSON schema, comparison references and host-rendered table passed. |
| UPST | Complete; review `maintain`, alert acknowledged | Assembled | JSON schema, comparison references and host-rendered table passed. |

All three runs had no terminal request error and the original source/ledger
checks passed. Estimated total model cost was **USD 0.0090044752**, below the
USD 0.05 cap. No repair turn or replacement observation was used. A successful
assembly means only schema and numerical-boundary acceptance, not content
quality approval. The Gateway had returned each raw answer to the harness;
only the assembled note would be eligible for this workflow's downstream use.

## What the deterministic component established

- The host-derived AFRM revenue difference is **39,294 USD thousand** and
  **5.96%** of the baseline, avoiding v1/v2's model-written 5.98% figure.
- SOFI's signed adjustments are applied once:
  `697,121 + (−4,362) + 9 + (−3,323) = 689,445` USD thousand. The model did
  not need to choose between subtracting a magnitude and subtracting a
  negative signed value. SOFI's note was still held by the output schema.
- UPST's adjusted net loss is marked **narrower sequentially** and **wider
  year over year**, avoiding the v2 free-prose direction reversal. The
  rounded-million source precision is tagged `approximate_rounded_input`.

The numeric table is derived from the selected, previously source-audited
facts. It does **not** verify omitted filing content, economic significance or
the agent's causal interpretation. Rounded-million deltas are currently
printed with decimal thousand-unit digits despite an approximation flag;
future rendering should make the uncertainty visually explicit.

## Content review: schema success is not insight quality

- AFRM's assembled implication calls the pattern a “cost-and-credit
  absorption problem rather than a demand problem.” The selected quarter
  shows revenue up and cost/credit lines worsening, but it cannot establish
  that demand is not a problem or identify a causal absorption mechanism.
  The counterpoint later acknowledges the missing bridge. This is a useful
  research question, yet the headline is stronger than the evidence.
- UPST's assembled implication says “core lending economics improved” from
  revenue, operating loss, contribution profit and adjusted EBITDA. These
  support a favorable **sequential reported-metric** pattern, not a verified
  unit-economics or repeatability conclusion. Its counterpoint correctly
  notes adverse YoY comparisons and the nonoperating debt gain, but “the
  favorable net-loss move cannot be read as operating improvement” is too
  categorical because the GAAP operating loss also narrowed sequentially.
- SOFI's rejected raw interpretation was arithmetically coherent and
  appropriately distinguished accounting reconciliation from a profit
  driver. It was not assembled because it violated the frozen no-digit rule;
  it must remain a held observation in this pilot.

Therefore the pilot shows a **working numerical provenance/assembly path** in
two cases and fail-closed behavior in one, while also showing that bounded
qualitative inference still needs substantive adjudication. It does **not**
meet the user's full goal of proving stable, high-quality financial insights.
The next iteration should preserve the immutable numeric table, make rounded
precision explicit, use structured source references for period names rather
than relying on digits in narrative, and test inference bounds on unseen,
source-diverse cases across workflows. The three development cases must not be
reused as the final holdout.
