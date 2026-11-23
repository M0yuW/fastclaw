# Source-locked event-to-thesis workflow, v2

This is a bounded application-level validation of the Gateway and finance ledger, not a test of investment performance or autonomous SEC retrieval. Four prespecified, neutral-ID cases were each run twice against an isolated Gateway home, fresh session, and empty tenant-scoped SQLite ledger. Source-locked SEC facts, required metrics, case order, decision ranges, pricing, and a USD 0.10 estimated-spend stop were fixed in `thesis_event_panel_v2.json` before model calls. The model used `deepseek/deepseek-v4-pro`; the finance review agent could read the thesis/alert and write a review/acknowledgement but could not ingest events or trade.

| Case | Scenario | Runs | Persisted decisions | Strict decision rubric |
|---|---|---:|---|---:|
| C01 | AMD Q3–Q4 2024 growth with Gaming recovery caveat | 2 | maintain; upgrade | 2/2 |
| C02 | AMD Q2–Q3 2024 company growth with Gaming decline | 2 | maintain; needs_review | 1/2 |
| C03 | Nike matching Q4 FY2024–FY2025 deterioration | 2 | invalidate; invalidate | 2/2 |
| C04 | NVIDIA Q1–Q2 FY2025 event packet omitting required gross margin | 2 | needs_review; needs_review | 2/2 |

All 8/8 requests completed without transport or provider error. Each saved ledger independently contains exactly one thesis, one immutable review, and one alert. In all 8/8, the review linked the stored alert and source hash, the thesis advanced exactly one version, the alert was acknowledged, required-metric state was recorded, and no trade or portfolio tool was called. The deterministic missing-evidence guard preserved `active` status and conviction 3 for both C04 runs. These are workflow/state checks, not endorsements of the written analysis.

The frozen decision/status rubric passed 7/8. C02-r2 chose a cautious `needs_review` although the rubric permitted `maintain` or `downgrade`; this is a decision-calibration difference, not a failed write. Independent post-run reading also found that C01-r2 described the single visible Q3-to-Q4 Gaming improvement as a “second consecutive improvement” and treated a sustained-recovery condition as met without a second observed improvement. All eight reviews used the correct period pairing and the stated calculations rounded consistently with the source-locked values; C01-r2's unsupported inference limits analytical reliability. These semantic observations were not a pre-registered model-quality score.

The 8 attempts used 35 priced model calls, 124.061 seconds of summed Gateway wall time (mean 15.508 seconds), and USD 0.029961 of frozen-price estimated model cost, not a provider invoice. The cap did not trigger. `manifest.json` records suite, runner, evidence, source-lock, plugin, policy, Gateway binary, and template-DB hashes; each run retains its request/response trace and an independently inspectable ledger copy. Earlier exploratory artifacts remain untouched but are excluded from this v2 result.

Scope: source packets and thesis seeds were prepared and ingested before each model request; the run did not test autonomous acquisition, source-hash verification inside the plugin, repeated-event idempotency, Team-mode ledger mutation, broad financial judgment, or downstream investment outcomes. The runtime claim is narrower: a real model can traverse the Gateway, policy-filtered finance tools, deterministic evidence gate, and durable research-state workflow under isolated conditions. The observed unsupported inference is a model/application-analysis limitation that the state-transition checks alone do not prevent.
