# Guarded SEC inference diagnostic v2 — result and first-pass content audit

This is a post-v1 engineering diagnostic on **known** AFRM, SOFI and UPST
source packets, not an unseen holdout. The source facts and v1 failures were
known when the v2 check line and workflow gate were designed. The v1 results
remain in their own directory and are not pooled with v2 as independent cases.
Judgments below are a Codex first pass, not an independent finance-expert or
investment-outcome rating. Raw `result.json`, turn checkpoints, ledger DBs,
logs and their hash manifest have not been edited.

## Execution

- 15/15 fresh Gateway/session/ledger runs completed the original tool and
  ledger invariants without a terminal request error. Total estimated model
  cost was **USD 0.0560259112**, below the frozen USD 0.15 arm cap.
- The added workflow publication gate accepted **10/15** as *candidates for
  manual claim review* and held **5/15**. It requested a bounded second turn
  in **6** runs; only UPST-r2 moved from a wrong first check to a checker-
  accepted second answer. A checker-accepted answer is **not** a high-quality
  answer.
- All six first and repair turns are retained. No repair was silently
  substituted for an original observation. The Gateway API had already
  returned each first candidate to this local harness; the gate only withheld
  downstream workflow acceptance, not every user-facing Gateway response.

## Gate behavior and experimental defect

| Observation | Outcome | Concrete reason |
|---|---|---|
| AFRM-r3 | Held | First and second check lines say +39,304; correct is +39,294 USD thousand. |
| AFRM-r4 | Held | First check +39,300 was wrong. Repair check became +39,294 but used a tool during the answer-only repair; worse, its prose newly claimed RLTC fell 34,271 rather than 24,271. |
| AFRM-r5 | Held | First check +39,300 was wrong. Repair inverted the comparison and gave −39,300; it used a tool and remained wrong. |
| SOFI-r3 | Held | The answer treated signed −4,362/−3,323 adjustment values as operands to subtract again, yielding 704,815 instead of 689,445. The repair repeated the interpretation and called a nonexistent 15,370 discrepancy. |
| SOFI-r4 | Held | The first check used `−(−3,323)`, yielding 696,091. The repair's check line was internally inconsistent (`697121-4362+9-(-3323)=689445`) and used a tool. |
| UPST-r2 | Checker-accepted after repair | First check said YoY adjusted net loss was `NARROWER`; repair corrected it to `WIDER` and made no tool call. |

The SOFI instruction was **ambiguous**: the source packet stores adjustment
values with signs, while the requested bridge expressed the negative items as
subtractions of their magnitudes and also asked for “signed arithmetic
values.” This caused a double-negative interpretation in two observations.
The checked formula itself is valid (`697121-4362+9-3323=689445`), but the
prompt/check schema was insufficiently clear. A revised experiment must
define the sign convention explicitly before any run; these v2 failures are
retained and are not relabeled as successful runs.

## First-pass content review of the 10 checker-accepted final answers

The scores use F/I/R/S/U from `INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md`. They are
provisional until a full claim worksheet is completed. `F=1` means an
imprecision that is not judged decision-changing; `I=0` means an inference
or attribution capable of misleading interpretation.

| Observation | F/I/R/S/U | First-pass label | Evidence in final answer |
|---|---|---|---|
| AFRM-r1 | 1/1/2/2/2 | adequate_within_case | Correct revenue delta +39,294, but labels it +5.98%; +39,294/659,185 is **5.96%**. “Cost-and-credit dynamic rather than a demand problem” is stronger than this selected packet establishes. |
| AFRM-r2 | 1/2/2/2/2 | adequate_within_case | Same +5.98% rather than **5.96%** on correct delta. Other material directions and mixed-risk limits agree. |
| SOFI-r1 | 2/2/2/2/2 | high_within_case | Q3 bridge, sequential changes, basis distinctions, missing Q2 adjustment components and ledger state align. |
| SOFI-r2 | 2/2/2/2/2 | high_within_case | Q3 bridge closes; net-income growth remains unattributed; Q2 components are not invented. |
| SOFI-r5 | 2/2/2/2/2 | high_within_case | Correct bridge and same-basis growth; distinguishes reconciliation from causal attribution. |
| UPST-r1 | 2/1/2/2/2 | adequate_within_case | Correct two comparison windows and debt-gain magnitude; “GAAP net-loss improvement is not an operating result” is too categorical given concurrent sequential operating-loss narrowing. |
| UPST-r2 | 2/2/2/2/2 | high_within_case | Repair corrected YoY adjusted-loss direction and preserves the lack of a source-backed causal bridge. |
| UPST-r3 | 2/1/2/2/2 | adequate_within_case | Correct numeric directions; repeats an overcategorical statement that net-loss narrowing is not an operating result rather than saying it is **not wholly** operating. |
| UPST-r4 | 0/0/2/2/2 | problematic | Says −5.3 vs −15.282 million is a **wider** sequential adjusted net loss; it is **narrower** by about 9.982 million. Also assigns 33,361 of the Q2→Q3 net-loss change to the Q3 debt gain without a Q2 comparator/complete bridge. The checker missed both. |
| UPST-r5 | 2/0/2/2/2 | problematic | Claims the sequential net-loss improvement was “dominated by” the Q3 nonoperating gain; the packet establishes a Q3 gain but not its share of the Q2→Q3 change. The checker missed this causal overreach. |

Among the ten checker-accepted answers, the first pass finds **4 high, 4
adequate and 2 problematic**. Counting the five held answers as not meeting
the quality gate gives AFRM 0/5, SOFI 3/5, UPST 1/5 high — below the v1
diagnostic reference threshold of 4/5 for each issuer. The formal prospectively
generalizable quality claim remains **unproven**.

The narrow source-derived check is useful as a fail-closed workflow component,
but it did not guarantee correct percentages, all comparison directions or
bounded causal claims. The one-turn repair sometimes introduced new factual
errors. No further paid run should start until a revised sign convention,
coverage rules and repair audit are frozen; then a **new unseen source-diverse
case set** is needed to test the broader stable-quality objective.
