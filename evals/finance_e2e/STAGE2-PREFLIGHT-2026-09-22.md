# Stage 2 preflight — 2026-09-22

## Outcome

The retrieval gold-label and numeric-grounding defects are fixed. Formal model execution has not started; one corrected three-mode engineering calibration has completed.

The corrected design contains:

- 24 Stage 2A configurations;
- 44 locked SEC source facts;
- 17 deterministic calculations;
- 42 explicit fact-to-record mappings;
- 103 source/oracle review tasks in total.

The former count of 37 evidence groups was not a stable semantic count. It resulted from deduplicating raw record-ID lists, some of which had collapsed because the old generator matched common numeric substrings across different metrics and periods.

## Changes verified locally

- Numeric matching now uses complete numeric boundaries, so `10` does not match `110` and `2.8` does not match `12.8`.
- Generated records retain internal fact identity.
- Retrieval gold labels are bound to explicit fact IDs; overlapping alternatives are limited to the same locked filing and declared locator.
- Audit tasks identify the target `fact_id` and require checking metric, period, unit, basis, and sign.
- The historical Pilot suite was restored unchanged at SHA-256 `7b73f4b82a3f97cb1151b372dcf8172eb88c04d37e1e137ed80b2a87bfb44e20`.
- The corrected Stage 2 suite regenerates without diff.
- All 12 local SEC artifact hashes match the source lock.
- All 44 declared facts pass the automated source-presence check.
- All 53 generator, audit, artifact, manifest, and human-grader Python tests pass when `PyYAML 6.0.2` is supplied from an isolated temporary dependency directory.
- The complete Go test suite passes after adding `gold_fact_groups` to the strict suite schema.
- Numeric grounding no longer assigns the sign of a following table change column to the preceding level (for example, `70.1 % Down 3.3 pts`). A regression test preserves ordinary negative phrases such as `10 percent decline`.
- The thesis evidence manifest and retained Pilot hash chain verify after updating the Stage 2 draft hash.

## Model-run calibration

The host's port 18953 is active, but the running binary predates the OpenAI-compatible `/v1/chat/completions` route required by the current evaluation runner. The corrected source was therefore built separately and started on port 18963 against a temporary SQLite snapshot. The existing 18953 process was not stopped or modified.

The Python FastClaw 0.1.0 service is running on port 18954 (not 19854). It exposes `/v1/chat/completions`, but its `OpenAIChatInput` schema rejects the evaluation runner's `fastclaw` extension as an extra field. That extension carries the controlled orchestration request and the trace/usage contract needed to distinguish modes. A direct compatibility attempt therefore ended with HTTP 422 before any model result. The Python service cannot produce a formally comparable report without implementing that request and telemetry contract; removing the field would test a different system.

An early `FRET-NVDA-POINT-SMALL` × `solo_staged` run passed and was useful for plumbing validation. It is superseded for comparison by the clean three-mode calibration below because interim outputs exposed and informed grader fixes.

The corrected one-case, one-repetition calibration used suite SHA-256 `fe13826db9d95327ce363e74b59112d71d737867af8cc6c12fda2118885f59c2`, source-lock SHA-256 `a4d4b4dc3be440238e3d428d60d04fb4a4a9d21d8c0b4eec4cb313e2e181fe22`, and randomized order `team_raw_context`, `solo_staged`, `team_shared_retrieval`:

| Mode | Pass | Milestones | Final recall | Grounding | Latency | Tokens | Estimated cost |
|:---|:---:|---:|---:|---:|---:|---:|---:|
| `team_raw_context` | Yes | 3/3 | 100% | 95.89% | 81.27 s | 47,811 | USD 0.008922 |
| `solo_staged` | No | 2/3 | 100% | 100% | 83.41 s | 24,966 | USD 0.011159 |
| `team_shared_retrieval` | Yes | 3/3 | 100% | 100% | 47.93 s | 29,200 | USD 0.006892 |

The Solo failure is substantive rather than a grader false negative: its output states `73.0 - 75.1 = -2.0 percentage points`; the declared result is `-2.1`. Shared-retrieval Team reproduced the calculation and all three milestones correctly. Relative to this Solo observation, shared-retrieval Team was 42.54% faster and 38.24% cheaper while using 16.96% more tokens. Relative to raw-context Team, it was 41.02% faster, used 38.93% fewer tokens, and was 22.76% cheaper. These are descriptive single-run observations, not estimates of a general multi-agent advantage.

The machine-readable result is `results/2026-09-22-stage2a-nvda-point-small-three-mode-final-calibration.json`; its companion interpretation is `results/2026-09-22-stage2a-nvda-point-small-three-mode-final-calibration-summary.md`.

The earlier successful Solo plumbing run recorded:

- overall result: PASS;
- retrieval recall: 100%;
- final evidence recall: 100%;
- summary retention: 100%;
- milestone accuracy: 100%;
- numeric grounding: 96.10% against a 95% floor;
- retrieval precision: 50% (reported diagnostically; no frozen minimum precision threshold);
- wall-clock latency: 50.23 seconds;
- provider-total tokens: 26,569;
- frozen-price estimated cost: USD 0.012372;
- model calls: five.

The first interim calibration used singleton-only gold records and scored 50% recall despite selecting semantically valid overlapping windows. That result is retained with `interim-singleton` in its filename and is superseded by the fact-aware calibrations above. Other pre-fix files are explicitly named `pre-morphology-fix` or `pre-plus-fix` and must not be pooled with the corrected result.

## Remaining engineering prerequisites

1. Upgrade or restart the persistent Go gateway with a binary built from the current tree, or add the current Go evaluation extension and telemetry contract to the Python service. The running 18953 binary serves the UI but not `/v1/chat/completions`; Python 18954 rejects the extension.
2. Declare `PyYAML` as a reproducible evaluation dependency rather than relying on the temporary test directory used for this preflight.
3. Repair the migrated finance-tools plugin path, which still points to `/Users/wangzheyu/...`; the SEC retrieval calibration does not invoke this plugin, but a finance-tool experiment would fail initialization.
4. Preserve API-key handling through the existing benchmark credential file or an environment variable without recording the secret in manifests or results.

## Additional formal-run prerequisites

Calibration success is not sufficient for a confirmatory run. Before formal execution:

1. Complete two independent reviews of the corrected 103-item audit set and adjudicate every non-PASS item.
2. Independently confirm all point-in-time SEC acceptance timestamps.
3. Accept the USD 10 and twelve-hour stopping limits.
4. Confirm the primary and diagnostic mode definitions.
5. Repair the migrated Git worktree metadata so the executable source revision and dirty state can be recorded reliably.
6. Freeze the suite and protocol, remove `formal_freeze_blockers`, and change suite status from `draft` to `frozen`.
7. Create an empty confirmatory output directory and a secret-free pre-run manifest.

Until those formal gates pass, any successful provider call must be labelled `calibration` or `pilot` and excluded from confirmatory analysis.
