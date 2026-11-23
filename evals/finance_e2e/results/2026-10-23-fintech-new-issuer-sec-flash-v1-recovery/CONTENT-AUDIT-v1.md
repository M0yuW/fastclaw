# New-issuer SEC panel: content audit (first pass)

This is a post-run Codex review of the 15 retained answers, not an independent
finance-expert review or a measure of investment outcomes. The eight pre-run
checks per observation are in `FINTECH-INFERENCE-CLAIM-GATE-v1.json`; the
0–2 dimension definitions are in `INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md`.
The source packet is limited to selected SEC facts; an omitted packet metric
does not mean it is absent from the full filing. The unscored, hash-checked
120-row claim worksheet is `CLAIM-REVIEW-WORKSHEET-unscored.csv`. Raw run
results, ledger databases, and `RESULT-SHA256.txt` were not changed.

## Execution and source controls

- Six original SEC Exhibit 99.1 documents were frozen by URL and SHA-256.
  The independent local source audit checked 38 selected facts and column
  placements. This establishes the selected packet's transcription, not every
  statement in a complete filing.
- First local gateway startup attempt in the sibling `...-v1/` directory had
  a sandbox bind failure before any model call. It is excluded from these 15
  observations and had zero estimated model cost.
- In this recovery directory, 15/15 observations reached `mechanical_pass`,
  15/15 stored one linked review and acknowledged the alert, and none has a
  terminal request error. Sixteen tool-input rejections were repaired within
  their runs; a successful terminal state does not imply every intermediate
  input was valid.
- Total estimated model cost: USD 0.0427739088, under the USD 0.10 cap.
  The sum of per-run elapsed times is 393.748 seconds; this is not an
  end-to-end wall-clock benchmark. The result hash manifest verifies.

## Per-observation first-pass labels

`F/I/R/S/U` means factual-numerical fidelity / inference discipline / risk
and uncertainty / state alignment / research utility. A score of 0 or a
critical error yields `problematic`. The pointers below refer to each
observation's `result.json`, `turns[0].response.choices[0].message.content`,
unless the ledger is explicitly named.

| Observation | F/I/R/S/U | Label | Critical issue or reason for less than high |
|---|---|---|---|
| AFRM-FISCAL-COST-r1 | 0/2/2/2/2 | problematic | `MATH`: reports revenue change +39,304; 698,479 − 659,185 = **39,294** USD thousand. |
| AFRM-FISCAL-COST-r2 | 0/2/2/2/2 | problematic | `MATH`: reports +39,394 instead of **39,294**. |
| AFRM-FISCAL-COST-r3 | 0/2/2/2/2 | problematic | `MATH`: reports +39,394 (+5.98%); correct is **39,294** (about **5.96%**). |
| AFRM-FISCAL-COST-r4 | 0/2/2/2/2 | problematic | `MATH`: reports +39,304 instead of **39,294**. |
| AFRM-FISCAL-COST-r5 | 2/2/2/2/2 | high_within_case | Material source values, basis, arithmetic, mixed-risk interpretation and ledger state agree. |
| SOFI-REVENUE-BRIDGE-r1 | 1/2/2/2/2 | adequate_within_case | Calls a gap increase from 1,653 to 7,676 “slight”; direction and values are correct but characterization is imprecise. |
| SOFI-REVENUE-BRIDGE-r2 | 2/2/2/2/2 | high_within_case | Separates GAAP and adjusted revenue and computes Q3 adjustment sum −7,676. |
| SOFI-REVENUE-BRIDGE-r3 | 0/1/2/2/2 | problematic | `MATH`/`GAAP_ADJUSTED`: claims the GAAP/non-GAAP gap “narrowed in relative terms”; 1,653/598,618 ≈ 0.28% versus 7,676/697,121 ≈ 1.10%, so it widened. |
| SOFI-REVENUE-BRIDGE-r4 | 2/2/2/2/2 | high_within_case | Correctly reconciles 697,121 − 4,362 + 9 − 3,323 = 689,445, without attributing net-income growth to one segment. |
| SOFI-REVENUE-BRIDGE-r5 | 0/1/2/2/2 | problematic | `MATH`/`GAAP_ADJUSTED`: says adjusted-revenue growth overstates GAAP-basis growth; it is about **15.5% vs 16.5%**, so it understates it. |
| UPST-MIXED-BASIS-r1 | 1/2/2/2/2 | adequate_within_case | Contains an abandoned “209?” intermediate before the correct 10,334 loss-narrowing calculation; final direction and comparison bases are correct. |
| UPST-MIXED-BASIS-r2 | 2/0/2/2/2 | problematic | `CAUSAL`/`NONOPERATING_GAIN`: says the sequential net-loss narrowing was “heavily shaped” by the Q3 debt gain, although the packet lacks a Q2 gain comparator or complete change bridge. The Q3 gain's existence is established; its share of the Q2→Q3 change is not. |
| UPST-MIXED-BASIS-r3 | 2/2/2/2/2 | high_within_case | Preserves sequential improvement, year-over-year deterioration, non-GAAP basis and the debt-gain limitation. |
| UPST-MIXED-BASIS-r4 | 2/1/2/2/2 | adequate_within_case | Correct numbers and an explicit magnitude-not-attribution caveat, but “net-loss narrowing is not an operating result” is too categorical given a simultaneous sequential narrowing of the operating loss. |
| UPST-MIXED-BASIS-r5 | 0/0/2/2/2 | problematic | `SEQUENTIAL_VS_YOY`: says adjusted net loss narrowed year over year; **−5.3 vs −3.9 USD million** is a wider loss. The same wrong direction recurs in its support and counterpoint. |

The ledger `S=2` scores only mean the final text agrees with retained thesis,
review and alert state. Some runs chose `needs_review` while thesis
`actionability` remained `available`; none of their final answers falsely
claims a `decision_hold`. The experiment did not precommit that every
`needs_review` decision must set a hold, so this is a policy-design question,
not silently counted as a ledger pass for decision safety.

## Gate result and interpretation

| Issuer cluster | Mechanical pass | High | Adequate | Problematic | Pre-run requirement |
|---|---:|---:|---:|---:|---|
| AFRM | 5/5 | 1 | 0 | 4 | At least 4/5 high, zero critical failures |
| SOFI | 5/5 | 2 | 1 | 2 | At least 4/5 high, zero critical failures |
| UPST | 5/5 | 1 | 2 | 2 | At least 4/5 high, zero critical failures |
| **Total** | **15/15** | **4** | **3** | **8** | **Not met** |

The pre-run content-quality gate **fails**, even though the execution gate
passes. These five repeats per issuer reuse one source packet and are
correlated; they are not 15 independent financial situations. The result
supports a narrower engineering claim: the runtime completed source-linked,
ledger-persisted workflows reliably in this panel, including recovery from
rejected tool inputs. It does **not** support stable high-quality financial
insight, analyst-level judgment, financial predictions, or economic value.

The most direct next change is a deterministic pre-publication verifier for
source-linked arithmetic, sign/direction and comparison bases, followed by a
new sealed panel. Repairing these historical answers in place or silently
discarding the errors would invalidate this audit.

## Free offline checker replay (subsequent diagnostic)

`verify_fintech_inference_answer_v1.py` recomputes explicitly recognizable
equations, the AFRM sequential revenue delta, SOFI relative-gap and growth-
basis directions, and UPST year-over-year adjusted-loss direction from the
frozen source packet. It also routes an explicit unsupported-change-bridge
phrase to review. On the **unchanged** 15 answers it detected all seven
first-pass numeric/direction critical errors, and routed the eighth critical
causal-attribution answer to review. Five answers had no contradiction in
the claims recognized by this narrow parser, and two had no recognized claim
and were marked `unassessed`. This replay is diagnostic and partly
case-specific; it is **not** a prospective quality result, a general financial
claim parser, or a repair of the published answers. Zero detected contradiction
never yields a quality pass (`quality_pass: null`). A new frozen arm and full
claim-level adjudication are still required after any runtime integration.
