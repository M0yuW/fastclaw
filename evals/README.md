# Evaluation Suites

- `smoke.yaml` is a project-specific instruction-following smoke suite.
- `bfcl-v4-simple-subset.yaml` contains three BFCL V4 `simple_python` records
  adapted to FastClaw's request-scoped tool runner.
- `tau-retail-subset.yaml` contains three deterministic retail tasks with
  scripted users, stateful tools, communication requirements, and policy
  constraints.
- `swebench-local-subset.yaml` contains three offline Go repository issues with
  editable source files and hidden tests under `swebench/fixtures/`.
- `multiagent-collaboration-subset.yaml` contains three shared-goal tasks with
  private simulated specialist reports and automatic solo/team comparison.
- `multiagent-runtime-tenant.yaml` contains eight fixed-evidence tasks for the
  provisioned five-agent benchmark tenant and uses the real Gateway
  `spawn_subagent` route.

The BFCL-derived prompts, schemas, and ground truths originate from the
[UC Berkeley Gorilla repository](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard),
whose leaderboard data is released under
[Apache License 2.0](https://github.com/ShishirPatil/gorilla/blob/main/LICENSE).
The bundled file is a small regression subset and does not produce an official
BFCL leaderboard score.

The τ retail file is inspired by the final-state and communication grading
model in [τ³-bench](https://github.com/sierra-research/tau2-bench). It is a
hand-authored regression subset and does not produce an official τ³-bench
leaderboard score.

The SWE file follows the patch-and-test evaluation shape documented by
[SWE-bench](https://www.swebench.com/SWE-bench/guides/evaluation/), but uses
hand-authored local fixtures instead of official repository instances. Its
resolution rate is not an official SWE-bench Lite or Verified score.

The collaboration file is inspired by
[MultiAgentBench](https://aclanthology.org/2025.acl-long.421/) milestone and
coordination evaluation. It uses deterministic simulated specialists by
default and does not produce an official MultiAgentBench score.
