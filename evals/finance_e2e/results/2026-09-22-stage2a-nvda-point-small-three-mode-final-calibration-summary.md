# Stage 2A corrected three-mode calibration — 2026-09-22

## Scope and status

This is an engineering calibration, not a confirmatory result. It contains one `FRET-NVDA-POINT-SMALL` case, one repetition, and three randomized modes. The corrected 103-item oracle has not yet completed two independent human reviews, and grader changes were informed by earlier calibration outputs.

- suite SHA-256: `fe13826db9d95327ce363e74b59112d71d737867af8cc6c12fda2118885f59c2`
- source-lock SHA-256: `a4d4b4dc3be440238e3d428d60d04fb4a4a9d21d8c0b4eec4cb313e2e181fe22`
- realized order: `team_raw_context`, `solo_staged`, `team_shared_retrieval`
- machine report: `2026-09-22-stage2a-nvda-point-small-three-mode-final-calibration.json`

## Result

| Mode | Strict pass | Milestones | Retrieval recall | Retrieval precision | Final recall | Grounding | Latency | Tokens | Estimated cost |
|:---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Raw-context Team | Yes | 3/3 | N/A | N/A | 100% | 95.89% | 81.27 s | 47,811 | USD 0.008922 |
| Staged Solo | No | 2/3 | 100% | 44.44% | 100% | 100% | 83.41 s | 24,966 | USD 0.011159 |
| Shared-retrieval Team | Yes | 3/3 | 100% | 66.67% | 100% | 100% | 47.93 s | 29,200 | USD 0.006892 |

Staged Solo failed `declared-calculations`: it reported `73.0 - 75.1` as `-2.0 percentage points` rather than the declared `-2.1`. This is a model-output arithmetic error, not a retrieval miss or scorer morphology error. Both Team modes passed all milestones. Shared-retrieval Team retained every gold record with a smaller evidence packet than Solo and incurred no unsupported numeric value.

## Descriptive contrasts

Relative to staged Solo, shared-retrieval Team was 42.54% faster and 38.24% cheaper, while using 16.96% more provider-total tokens. Relative to raw-context Team, shared retrieval was 41.02% faster, used 38.93% fewer tokens, and was 22.76% cheaper.

These contrasts support the report's efficiency-oriented hypothesis as a feasible measurement target. They do not establish a causal or general multi-agent advantage: this is one company, one small point-in-time case, one repetition, a heterogeneous model allocation, and a run performed after grader development.

## Python service compatibility

The local Python FastClaw 0.1.0 service listens on port 18954. It has an OpenAI-compatible chat route but rejects the runner's `fastclaw` request extension with HTTP 422. Without that extension it cannot receive the controlled mode configuration or return the required orchestration trace and per-role usage. It is therefore not a drop-in execution target for this experiment. Port 19854 had no listener during the check.

## What remains before formal execution

1. Complete and adjudicate two independent reviews of all 103 oracle tasks.
2. Independently confirm the SEC acceptance timestamps.
3. Freeze the suite, protocol, grader, price table, runtime revision, and stopping limits.
4. Use a current persistent Go gateway or implement an equivalent extension/telemetry contract in Python.
5. Run randomized paired repetitions across all declared company-task-load configurations, then report cluster-aware uncertainty rather than extrapolating this calibration.
