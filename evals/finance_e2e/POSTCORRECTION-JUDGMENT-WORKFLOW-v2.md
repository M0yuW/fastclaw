# Post-correction answer adjudication workflow v2

This workflow applies to the prospective SEC event→thesis panel in
`POSTCORRECTION-HOLDOUT-PROTOCOL-v2.md`. It must not relabel the frozen v1 batch.
No raw answer, ledger, result, or source packet is edited during judgment.

1. After the paid run finishes or stops, verify its `RESULT-SHA256.txt`, count all
   retained observations, and record errors as outcomes. Do not retry a low-quality
   answer or exclude a failed session.
2. Run `prepare_postcorrection_judgment_v2.py` on the frozen result directory
   into a **new** output directory. Give the judge only `masked_packets/` and
   `scores/`, never `PRIVATE-MAPPING.json`. The packet contains the final answer,
   persisted review/ledger and alert state, tool evidence, model-visible prompt,
   and source-selected facts. It omits private interpretation checks, runner
   pass/fail, cost, repetition number, and runtime chronology/session markers.
   Source issuer identity remains visible because it is necessary for SEC review;
   this is partial masking, not a blinded finance-professional study.
3. For each material numeric, comparative, explanatory, risk, and state claim
   in **both** the final answer and persisted review, fill one
   `claim_adjudications` entry in the matching `scores/J-*.json`: exact `span`,
   `location` (`final_answer` or `persisted_review`), `verdict`
   (`supported`, `bounded_hypothesis`, `unsupported`, `contradicted`, or
   `unassessable`), and `evidence_refs` pointing to frozen SEC fact IDs, source
   rows, arithmetic, or actual tool/ledger state. Record a `critical_errors`
   entry with `claim_index`, `code`, and `evidence_refs` for each critical error.
   Assess F/I/R/S/U according to `INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md` and mark
   whether each answer surface was covered. Do not copy a host-computed table
   into the score as proof that the agent's conclusion is correct.
4. Freeze completed score files before viewing `PRIVATE-MAPPING.json` or the
   mechanical labels. `aggregate_postcorrection_judgments_v2.py` checks the
   reviews, rejoins them to raw results using recorded hashes, and applies the
   five-session case gate. A case passes only with all five mechanical passes,
   no critical error, and at least four `high` plus at most one `adequate`.
   Failed, absent, or unassessable observations remain in the denominator.
5. Report the 20 case outcomes, exact one-sided Bonferroni-adjusted lower bound,
   failure categories, and examples of supported and unsupported claims. The
   all-20 route is the predeclared threshold for a lower bound above 80% in
   this event-case universe. A partially completed panel or a single failed
   cluster cannot satisfy that strict claim. A passing event arm does not prove
   screening or portfolio-workflow reliability, investment return, or economic
   value. With only Codex/LLM judges, describe ratings as diagnostic rather than
   independent finance-professional validation.

Example commands, after a newly authorized paid run has produced results:

```bash
python3 evals/finance_e2e/prepare_postcorrection_judgment_v2.py \
  --results-dir <frozen-results-dir> --output-dir <new-judgment-dir>
python3 evals/finance_e2e/aggregate_postcorrection_judgments_v2.py \
  --results-dir <frozen-results-dir> --judgment-dir <judgment-dir> \
  --output <new-summary-json>
```

These commands are local transformations. They do not call an external judge;
sending answers to a provider would require separate authorization.
