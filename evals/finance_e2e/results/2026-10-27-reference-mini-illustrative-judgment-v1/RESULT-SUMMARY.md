# Three new-issuer SEC research cases: six-session result

Date: 2026-10-27. This is a small, preselected *illustrative* event→research-review panel, not a population reliability estimate. MTB, RPAY and CSGP were frozen before these model outputs. Each used two isolated DeepSeek Flash sessions with the same prompt contract and an enabled source-hash-bound arithmetic guard. All six raw results and copied ledgers are in `../2026-10-27-reference-mini-illustrative-flash-v1/`; its `RESULT-SHA256.txt` verifies all six `result.json`, all six SQLite ledgers and the run manifest. The original outputs were not edited.

## Execution versus content

| Case | Mechanical completion | Local claim-level judgments | Stored research decision |
| --- | --- | --- | --- |
| MTB | 2/2 | 0 high, 2 adequate | Both `maintain`, conviction 3, available; credit/funding caveats in prose. |
| RPAY | 2/2 | 1 high, 1 problematic | Both `needs_review`, conviction 3, blocked. |
| CSGP | 2/2 | 0 high, 1 adequate, 1 problematic | Both `needs_review`, conviction 3, blocked. |
| **Total** | **6/6** | **1 high, 3 adequate, 2 problematic** | Four blocked; two available. |

Every session used the requested Flash model, had priced usage with no recorded request error or uncertain/unpriced model call, and saved exactly one linked review and one acknowledged alert. All six independent read-only SQLite checks agreed with the result JSON about thesis, review, alert, decision and rationale. Thirty-four priced model calls across the six sessions cost an estimated **USD 0.046767852**, below the authorized USD 0.25 incremental stop cap; this is a frozen-price estimate, not an invoice.

The detailed unblinded first-pass review is `ADJUDICATION.json`. Each listed claim span was checked against the raw final answer or persisted rationale; all six raw-result hashes and referenced selected source-row IDs were checked. The scores use the frozen F/I/R/S/U rubric and are diagnostic Codex judgments, not independent finance-expert ratings. Repetitions share issuer sources; none of these counts is a statistical claim that the runtime generally produces high-quality financial insight.

## Illustrative positive case: RPAY repetition 2

The agent recognized that Q2 2025 carried a USD **103.781 million impairment** and that the Q3 GAAP operating loss narrowed from USD **104.904 million** to **3.009 million**. It did not treat that improvement as proof of recurring recovery: company-defined adjusted EBITDA moved from USD **31.811 million** to **31.202 million**, while selected cost of services and SG&A increased. The displayed operating bridge is exact (USD thousands): revenue **+2,099**, total operating expenses **−99,796**, operating result **+101,895**. The model distinguished the impairment base effect from operating leverage, described the GAAP/non-GAAP tension, requested fuller reconciliation and driver evidence, and saved a source-linked `needs_review` decision. The ledger actually retained `decision_hold=true`, `actionability=blocked`, and conviction 3; the alert was acknowledged. This was rated **high within the selected-source case**. It is evidence that the runtime *can* carry a useful, bounded analysis through tools to a durable research state, not a validated investment thesis.

## Two retained failures

- **RPAY repetition 1:** The final answer *and saved review* said cost of services and SG&A each increased by more than revenue. In fact, revenue rose USD **2.099 million**, cost of services only **1.531 million**, and SG&A **2.295 million**. The overall caution/hold was right, but a material component comparison was wrong. The optional arithmetic guard did not detect this pattern.
- **CSGP repetition 1:** The final answer said the income-tax change did not offset deterioration in the operating result. Tax expense went from USD **15.4 million** to a USD **14.9 million benefit**, improving its net-income contribution by **30.3 million**—more than the **23.9 million** operating-result decline. A separate **37.0 million** unfavorable other-income/expense swing explains why net income still fell. The saved review and ledger held the thesis, but the *post-tool final explanation* introduced the wrong offset relation. A pre-commit review guard cannot veto an error that appears only after the tool write.

The two errors are model-generated interpretation/comparison errors, but their persistence boundaries differ. A free, controlled direct-plugin replay of the *actual saved review calls* on fresh isolated ledgers showed guard-off and guard-on both saved the same `needs_review` rationale for RPAY repetition 1; the current guard missed its false comparison. For CSGP repetition 1, the offending offset sentence was absent from the saved tool call and appeared in final prose. Both A/B arms retained a blocked review; the runtime state was correct but could not certify the later final narrative. This replay makes no new model call and is a mechanism diagnosis, not a second quality observation.

## Claim boundary for the project report

Use RPAY repetition 2 as an annotated capability example only alongside the full six-outcome table and the two failures. The evidence supports *end-to-end execution, source linkage, correct holds on the mixed RPAY/CSGP cases, and at least one high-quality selected answer*. It does **not** support stable quality, full semantic error prevention, autonomous SEC retrieval, or investment performance. It also reveals a design gap: `needs_review` prevents the stored thesis from downstream use but does not automatically remove a misleading sentence from either the persisted review or final response. MTB's two `maintain` outcomes remained available despite stated credit/funding uncertainties, which merits policy discussion but is not a demonstrated source conflict under the frozen task.
