# Financial insight quality: Codex first-pass review and cross-panel adjudication

## Status and method

This is an LLM-as-judge assessment by Codex, not a finance-expert assessment or an independent blinded replication. The F/I/R/S/U rubric in `INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md` separates factual/numerical fidelity, inference, risk/uncertainty, ledger alignment and research utility. Its `high_within_case` label means a useful, source-grounded implication *within the supplied case*; it does not mean profitable advice, predictive value or general reliability.

The panel-level labels below come from the retained observation-level judge CSVs. For this consolidated review, I verified the raw result SHA-256 lists (80, 20, 20 and 15 observations respectively) and directly re-read representative raw answers and state, including E4-r1, C2-r1, C3-r4, S3-r1, P4-r1/r4, H-INTC-r1/r4, H-NKE-r1 and FRESH-AAPL-TAX-r2. This is a targeted adjudication of prior first-pass judgments, **not** a new blind re-grade of every sentence in 135 responses. No raw observation or prior label was changed.

## Results must remain separated by panel

| Retained panel | Workflow evidence | Mechanical execution | High | Adequate | Problematic | Interpretation |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 80-run Flash reliability panel | Four workflows, 16 case clusters x 5; mostly synthetic outside SEC event cases | 77/80 | 54 | 13 | 13 | Good orchestration evidence, but repeated decision-relevant interpretation errors. |
| SEC event-to-thesis startup-gated retest | Four historical SEC case clusters x 5 | 20/20 | 8 | 9 | 3 | Execution improved; all three problematic conclusions are Intel-case inferences. |
| Historical SEC screening panel | Four issuer clusters x 5; deterministic offline screen | 10/20 raw; 20/20 after Unicode-minus sensitivity check | 0 | 20 | 0 | Correct filter/state behavior, but little independent insight beyond supplied tool fields. |
| Fresh SEC multi-issuer forward panel | AAPL, MSFT, SBUX x 5; new issuer sources | 14/15 | 0 | 13 | 2 | The predeclared quality gate failed; this is the clearest adverse generalization test. |

The first panel's repetitions are correlated within 16 cases. The later panels differ in source novelty, fixture content, tool guard and protocol, and some issuers overlap with earlier work. These counts must not be pooled into one “quality pass rate.” The six-run same-case recovery diagnostic is also separate: 6/6 mechanical, 3 high and 3 adequate. It demonstrates recovery on already-seen cases after repairs, not unseen-case reliability.

## Directly checked judgment examples

- **Conflict interpretation (C2-r1):** The answer correctly kept a ledger hold but described mutually incompatible USD 5,000 million and USD 8,000 million plan statements as a management “range.” Distinct point claims are not a range. The prior `problematic` inference label stands.
- **Unjustified causal inference (C3-r4):** A formal capex-plan correction was correctly recognized, yet the answer inferred fewer capacity additions from lower capex without disclosed scope, timing or efficiency. The prior `problematic` label stands.
- **Metric-name fidelity (S3-r1):** The fixture field was `earnings_growth_yoy`; the answer called it “EPS growth YoY” although no per-share basis was supplied. The correct no-thesis decision does not cure the factual-label error.
- **Partial-portfolio bound (P4-r1/r4):** With 45% and 30% of the same nonnegative total portfolio already accounted for, all unreported holdings together have at most 25%. Exact HHI needs the full vector, but the top-one weight is exactly 45% under these assumptions, and no unreported holding can exceed 50%. The answers alternately called top-one uncomputable or claimed undisclosed positions could defeat the bound. The prior `problematic` labels stand.
- **Missing evidence and state (E4-r1; H-NKE-r1):** E4-r1 accurately described a required margin metric as missing from its packet and matched an actual blocked ledger state. H-NKE-r1 was more cautious in prose (`needs_review`) while the ledger remained actionable; that is an important state-language limitation, though its prior label was `adequate`, not a material false claim of an enforced hold.
- **Intel inference (H-INTC-r1/r4):** One answer associated the whole charge bundle with gross-margin pressure despite lacking a line-item bridge and embedded malformed JSON-like text in its rationale. Another treated “material margin deterioration” as if it required sustained deterioration, although these are separate invalidation terms. Both decision-relevant `problematic` labels stand even though both tool workflows completed.
- **Period reasoning (FRESH-AAPL-TAX-r2):** The answer said adjacent fiscal Q3/Q4 values permit no sequential comparison merely because disclosed growth rates are year-over-year. Same-basis adjacent-quarter levels can be compared, while YoY rates must stay on their own basis. The `problematic` label stands.

The screening panel's ten raw `needs_review` results for rejected Intel/Nike cases are a separate **scorer parsing defect**: the answer used Unicode `−` rather than ASCII `-` for negative values. The original 10/20 raw mechanical number must remain visible beside the post-hoc 20/20 normalized sensitivity result; it is not evidence of ten model execution failures.

## Overall judgment and report wording

The evidence supports: **the tested runtime can execute several financial workflows, call tools, persist source-linked research state, recover or reject some invalid operations, and expose auditable failure traces.** It does not support an unqualified statement that the system *stably produces high-quality financial insights*. The strongest forward panel had no `high_within_case` answers and two problematic observations, while historical screening outputs mostly recapped deterministic fields. The failures cluster in source-conflict semantics, metric basis, causal attribution, bound reasoning and incomplete-workflow recovery—issues not reducible to transport reliability.

Suggested report wording: “The system demonstrated auditable end-to-end execution across financial research workflows. A first-pass LLM-as-judge assessment found useful source-grounded conclusions in selected cases, but also identified decision-relevant inference errors and limited incremental insight in screening. Consequently, the experiments establish workflow feasibility and measurable safeguards rather than stable, expert-validated financial insight quality.”

The judge is not independent of the project iteration, and most rubric applications were not blinded. The SEC event packets are historical and selected; other workflows often use synthetic inputs. No expert agreement, live decision value or future returns were measured. These limitations should remain explicit even if a later experiment improves the scores.
