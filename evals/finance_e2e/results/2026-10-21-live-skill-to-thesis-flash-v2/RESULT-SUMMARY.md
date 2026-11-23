# Live Skill → preliminary thesis: one isolated end-to-end observation

This is one exploratory AMD observation, not a reliability or investment-quality estimate. The experiment used a temporary Go Gateway on port 18955, an isolated session and finance ledger, DeepSeek v4 Flash, the installed FinData Toolkit US Skill, and the native finance-tools plugin. It did not modify the user's standing Gateway or ledger. The first v1 observation remains separate; its final prose incorrectly called the 2026-10-14→15 close change an up-day. The v2 prompt asks the agent to check adjacent closes before making such claims.

## Actual path and source

1. The agent called `exec` once to run the installed Skill's `stock_data.py` with `AMD --history --period 5d --source nasdaq`. The result contained five dated 1-day bars, a Nasdaq URL, and closes of 570.82 on 2026-10-14 and 534.74 on 2026-10-20. The tool output did **not** declare currency or adjusted-close basis; USD is only a labelled inference.
2. In the same session, the agent made a second `exec` call for local arithmetic (not another market-data retrieval), then called `finance-tools__thesis_save` once. The plugin created one AMD `researching`, conviction-1 preliminary thesis with the source URL, dates, closes, interval, computed change, and explicit missing-evidence notes. The ledger has no alert, portfolio change, or trade.
3. An independent calculation gives `(534.74 - 570.82) / 570.82 × 100 = -6.3207%`; the saved evidence reports `-6.32%`. The v2 final answer's four adjacent close directions also match the returned bars.

All three tool-call IDs have matching results, both turns completed, and all four model calls were priced. Estimated model cost was **USD 0.002679208**, below the isolated USD 0.02 stop. The raw result and a copy of the SQLite ledger are retained, with SHA-256 values in `RESULT-SHA256.txt`.

## Original score versus read-only adjudication

The original `result.json` is intentionally **not modified**: it says `needs_review` because two scorer assertions were too narrow. `skill_exec_once` counted *all* `exec` calls and therefore rejected the legitimate arithmetic-only call; the intended assertion is one **Skill fetch**, which the trace satisfies. `return_arithmetic` looked only for `close_change_percent`, while the saved evidence used `computed_change_percent`; both denote the same percentage. Recomputing from the raw source values verifies the saved number within 0.02 percentage points. The runner has been corrected for future observations; the v2 raw score remains historical. This adjudication supports successful source→analysis→ledger execution, not blanket correctness of every sentence.

## Boundary requiring a separate product decision

The saved thesis explicitly says that earnings, valuation, SEC filings, and forward catalysts were not verified. Nevertheless, the current `thesis_save` API records a new `researching` thesis with `decision_hold=false` and `actionability=available`; it does not automatically block downstream decisions for price-only evidence. This test therefore **does not** establish that missing fundamentals trigger the earlier event-review `needs_review`/decision-hold safeguard. Until such a guard is defined for preliminary thesis creation, this record should be treated as a research stub, not an actionable view. The observed price move is descriptive and has no demonstrated predictive or investment value.
