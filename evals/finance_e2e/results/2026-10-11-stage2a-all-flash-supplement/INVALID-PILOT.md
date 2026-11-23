# Nonconforming all-Flash pilot — excluded

The first six observations for `FRET-NVDA-POINT-LARGE` were generated with
the older isolated Gateway on port 18955. Although the suite declared Flash
for every role, actual `model_calls` show Pro for `finance-solo` (15 calls)
and `finance-coordinator` (six calls). The manifest model-allocation check
failed and no case manifest was produced. Preserve the raw JSON but do not
include its observations in the all-Flash comparison. Its recorded estimated
cost, USD 0.0544675852, remains in cumulative spending accounting.

The corrected experiment uses a distinct study ID, suite, result directory,
and isolated 18956 Gateway whose six finance Agent configurations were
verified as Flash before execution.
