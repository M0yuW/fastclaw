# Startup-readiness retest: pre-run addendum

Freeze this addendum before the first new model call. The original 20 observations and their failure labels in `results/2026-10-22-insight-quality-holdout-flash-v1/` remain unchanged.

## Change under test

The only intended operational change is that the isolated experiment helper now waits until the gateway logs its post-plugin `gateway started` marker **and** accepts TCP connections. The old helper waited only for the port. The four SEC case pairings, five repeats per case, frozen source records, agent/model, prompt-generating code, plugin, template DB and gateway binary should remain the same. The new manifest must record hashes so any incidental difference is visible. Use a separate output directory and fresh ledgers/sessions. Do not merge observations with the old arm as if interchangeable.

## Primary outcome and interpretation

Primary outcome: the 20 new observations' actual finance-tool calls, linked review and alert acknowledgement, plus any pseudo-tool terminal text. Record all 20 attempts; no replacing failures. If 20/20 pass, describe this as evidence that the startup barrier improved *this configuration's* execution, not proof that the race was the sole cause of all old failures or that future runs never fail. Retain the original 17/20 outcome for comparison. Any HTTP error, unpriced usage, uncertain price or estimated cumulative spend reaching USD 0.12 stops further calls.

Financial conclusion quality is a separate outcome. Apply the previously frozen insight rubric and original numeric oracle. The startup barrier does **not** cure Intel charge-attribution overreach, thin Nike inference, or the need for broader real-source workflows. A complete execution score does not by itself satisfy the project goal of stable high-quality insight.
