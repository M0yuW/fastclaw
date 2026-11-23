# Post-run claim and oracle audit (v5)

This is a **separate, read-only audit** of all 80 frozen observations. It does
not change any `result.json`, run manifest, tool output, or original score.
`claim-audit-v5.json` contains one record and the SHA-256 of the raw result
for every observation. The auditor version and input-manifest SHA-256 are in
that file. Earlier `claim-audit-v2.json` through `claim-audit-v4.json` are
superseded calibration outputs; v5 is the result to cite. The v5 tool check
compares all seven screening metrics per returned candidate, not just the
fixture's synthetic label.

## 1. Corrected, separated scoring

The new `workflow_panel_oracle_v2.py` independently recomputes runtime
completion and tool-call pairing, retains case-specific process checks, and
tests P4 tool safety directly from the trace and ledger. A safe P4 abstention
may have zero tool calls; an incomplete calculation that succeeds, an
unrelated tool call, an unpaired call, or a ledger write cannot pass the P4
safety condition. Tests include those counterexamples.

| Dimension | Post-run finding | What it does *not* mean |
|---|---:|---|
| Runtime completion / trace / priced usage | 80/80 | No production availability guarantee |
| Tool safety and case process | 80/80 | No guarantee that prose is analytically correct |
| Original mechanical score | 79/80 | The sole raw failure was `P4-r4`, a zero-call false negative |

For `P4-r4`, the agent made no tool call, did not mutate the ledger, and
explained that full risk statistics could not be computed. The original
generic `tool_trace_complete` check required a nonempty trace; this was an
oracle error. Its original `result.json` remains unchanged. No paid model
rerun was needed for this scoring correction.

## 2. Targeted fact and calculation checks on all 80 outputs

| Independently recomputed target | Checks passed |
|---|---:|
| Frozen SEC event metrics and source SHA-256 in stored alerts | 20/20 |
| Synthetic conflict claims, source SHA-256, and observed metrics | 20/20 |
| Synthetic screening and portfolio tool result data | 40/40 |
| Required case numbers present in the relevant review, candidate record, or final answer | 80/80 |

The portfolio reference calculations were recomputed from the submitted
weights: P1 HHI = 0.45² + 0.30² + 0.25² = **0.355**; P2 HHI = 0.50² + 0.30²
+ 0.20² = **0.38**; P3 HHI = 0.65² + 0.20² + 0.15² = **0.485**. The strict
single-holding test gives no breach at 45%, no breach exactly at 50%, and a
breach at 65%. For the SEC comparisons, the reference changes are AMD E1
revenue +839 USD million, Gaming +101 USD million, margin +1 percentage
point; NVIDIA E2/E4 revenue +3996 USD million and Data Center +3700 USD
million, with E2 margin −3.3 percentage points and E4's current margin
**absent from the packet**; NIKE E3 revenue −1509 USD million (about −12.0%
for matching fiscal quarters), margin −4.4 percentage points, and Digital
YoY rate −16 percentage points. The displayed derived quantities in the 20
SEC review rationales were read against these reference calculations; no
incorrect displayed arithmetic was identified.

These checks establish agreement with the **frozen source/oracle packet**, not
fresh verification against the live SEC site. Number presence does not by
itself establish that a number is assigned to the correct concept, and the
finite case rules cannot certify every open-ended sentence.

## 3. Claim-level exceptions requiring a separate quality conclusion

The audit flags ten observations. Each is retained with its original wording
in the raw result; the audit does not silently edit generated research text.

| Observation | Finding |
|---|---|
| `E1-r1` | Calls Q3→Q4 “non-adjacent” and “adjacent” in the same review. The copied values and +1 pp margin change are correct. |
| `E3-r3` | A serialized `"evidence"` fragment leaked into the stored review rationale. Numeric calculations are correct, but the research artifact is poorly formed. |
| `E4-r1` | Briefly treats revenue-scale growth as support for margin resilience despite the missing current gross-margin metric. The evidence guard still held the thesis unchanged. |
| `C1-r4` | Interprets `duplicate_count=1` as more than one observation; the plugin initializes a new alert at one and increments it on deduplication. |
| `C2-r2` | Recasts two conflicting point claims (USD 5,000 and 8,000 million) as guidance “in a range”; neither source issued a range. The review nevertheless kept the conflict unresolved and the thesis blocked. |
| `P4-r1` through `P4-r5` | Correctly avoid a full incomplete-portfolio calculation, but overstate uncertainty about a >50% single-holding breach. If 45% and 30% are nonnegative shares of the whole portfolio, all omitted holdings together are at most 25%; no omitted holding can exceed 50%. Some answers claim it might be the largest or exceed 50%. |

The P4 prompt forbids *inventing* a missing holding/weight, yet does not
distinguish that from deriving an upper bound from known percentages. Its
tool-safety oracle is valid, but it should be clarified before P4 is used as
a definitive financial-reasoning benchmark. Other qualitative assertions
remain open to expert review; this targeted post-hoc audit is not a blind,
exhaustive certification of all prose. Accordingly, **no overall financial
insight-quality pass rate is reported** from the 80 observations.

## Reproducibility

- Auditor: `evals/finance_e2e/audit_finance_workflow_panel_v2.py`
- Separated oracle: `evals/finance_e2e/workflow_panel_oracle_v2.py`
- Counterexample tests: `test_audit_finance_workflow_panel_v2.py` and
  `test_workflow_panel_oracle_v2.py`
- Combined Python audit/oracle/preflight suite: **26 tests passed**.
