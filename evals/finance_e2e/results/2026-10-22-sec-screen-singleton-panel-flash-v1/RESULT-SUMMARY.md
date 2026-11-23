# Historical SEC screening → preliminary research: 20-run Flash panel

## Scope and integrity

The four issuer cases, two deterministic screening thresholds, five repetitions, runner, source locks, quality rubric and USD 0.08 estimated-spend stop were specified in `../../SEC-SCREEN-SINGLETON-PANEL-PROTOCOL-v1.md` before the first model call. Each observation used a fresh Gateway/session/finance ledger and called the actual `finance-tools__screen_stocks` tool. The tool's historical offline adapter reads four SHA-locked SEC exhibits; it is **not** a live market-data or same-date cross-company ranking. The issuer filings were already present in the project, so this is a new workflow/case configuration, **not** an unseen-filing holdout.

All 20 planned observations completed. The 20 raw `result.json` hashes verify against `RESULT-SHA256.txt`. No request error, unpriced usage or uncertain-cost sequence was retained. Cumulative token-based estimated cost was **USD 0.0202644568** (not a provider invoice), below the USD 0.08 stop. The isolated process exited normally.

## Execution and judge results

| Issuer | Tool and state correct after review | Raw mechanical pass | Adequate within case | High within case | Problematic |
| --- | ---: | ---: | ---: | ---: | ---: |
| AMD | 5/5 | 5/5 | 5 | 0 | 0 |
| NVDA | 5/5 | 5/5 | 5 | 0 | 0 |
| INTC | 5/5 | 0/5 | 5 | 0 | 0 |
| NKE | 5/5 | 0/5 | 5 | 0 | 0 |
| **Total** | **20/20** | **10/20** | **20** | **0** | **0** |

All five AMD and NVIDIA observations made genuine screen calls, received retained results, and saved exactly one source-linked historical preliminary thesis. All five Intel and Nike observations made genuine screen calls, received rejection results and saved no thesis. No alert/trade or live market-data call was observed. All 20 traces had clean completion and priced usage. This is an observed small-panel result, not a population reliability rate.

The ten raw `needs_review` labels are **scorer false negatives**, not model execution failures. The frozen `core_values_reported` check searched for ASCII `-6`/`-8`; all ten rejected-case answers used the typographic minus `−6`/`−8` while correctly stating the GAAP margin, rejection criteria, source URL and full hash. A post-run read-only normalization of Unicode minus to ASCII minus verified the expected signed YoY and margin values in all ten. The original labels and raw files remain unchanged; this correction is an explicitly post-hoc sensitivity review and must not be silently represented as the original mechanical result.

`INSIGHT-JUDGE-v1.csv` records a first-pass Codex review of each final answer and persisted record on factual fidelity, inference, risk, state alignment and research utility. The judge was **not blinded** to raw mechanical status and has no independent finance-expert adjudication. It gives 20 `adequate_within_case` and zero `high_within_case`: all actions and threshold conclusions were appropriate, but the candidate records mostly restated the deterministic tool fields rather than developing an independently useful research insight. Much of the countervailing-risk text was supplied directly by the test adapter and copied into structured evidence; that is evidence preservation, not proof of original risk discovery. AMD `r1/r2` also mislabeled the SEC earnings-release exhibit as a Form 10-Q, a non-decision-changing provenance error. Intel `r4` loosely grouped USD 2.8 billion of restructuring with impairment wording; `r5` overstated the role of absent valuation in whether *any* preliminary thesis could exist. Neither changed the correct reject/no-thesis action.

## What this contributes and what it does not

Together with the separate event→thesis SEC panel, this establishes that the tested runtime configuration can complete **two** distinct historical, real-source finance workflow families with traceable tools and ledger state. This panel's complete within-case execution/fact gates and cautious no-valuation boundary are positive engineering evidence. It is **not** evidence that the system independently discovers high-quality investment insights: the screen is only a two-threshold fixture; input risk notes are supplied; source dates differ; there is no price, valuation, forward return, real portfolio outcome or expert utility score. The broader objective of demonstrating stable high-quality financial insight is **not met** by this panel alone, particularly because the separate event panel still has Intel inference failures.

For the project report, report the raw 10/20 mechanical label and the documented Unicode-minus sensitivity result side by side, rather than replacing one with the other. State the unit of generalization as four issuer clusters with five correlated repeats. A stronger next test should require agents to derive a source-grounded research implication from complete, differently structured disclosures without feeding them the counterargument as a ready-made risk note, and separately judge factual accuracy, causal discipline, state and utility.
