# Typed insight candidate: seen-case Flash development probe

This is a development result, not a source-distinct confirmatory experiment or a quality-reliability estimate. The earlier v4 results remain sealed and are not pooled with this probe.

## Authorized run and custody

- Cases: FITB, RELY, TFC and VRSK, two fresh independent sessions each; deterministic order SHA256 `9da12b469a19365e7940a692cc6a5ad0654e15f6f00f771fa307ccceba3244cb`.
- Separate user authorization: incremental estimated cost stop at USD 0.25; no model-observation retries.
- An initial `results/2026-10-25-insight-candidate-development-flash-v1/` attempt stopped at Gateway startup in the local sandbox: zero model turns and zero estimated cost. This is retained as an execution-environment failure, not an insight observation. A subsequent free, local scripted Gateway replay in `results/2026-10-25-insight-candidate-gateway-replay-v3/` passed both branches with zero external provider calls.
- The eight paid observations are in `results/2026-10-25-insight-candidate-development-flash-v2/`. Its `RESULT-SHA256.txt` verifies every result, finance ledger database and manifest. Eight of eight sessions completed mechanically, with 47 priced model calls, no request errors and no cost-uncertain or unpriced sequences. Total estimated cost was USD 0.06392766, below the stop cap.

## Candidate-gate findings

All eight final responses were parseable JSON with the three requested top-level fields, and all eight independently saved a linked review, acknowledged the alert and reached a ledger-consistent thesis state. However, **all eight were originally held by the frozen candidate gate**; none received a quality pass.

Post-run inspection found one evaluator defect: it compared the order of `evidence_ids` as if it were part of evidence identity. All eight model assertions contained exactly the persisted evidence IDs, in the ledger's order, and matched the other asserted state fields; the old gate had sorted the canonical IDs. The corrected verifier compares the ID lists order-independently while preserving exact comparison for review ID, date, decision hold, actionability and alert status. An eight-test verifier suite passes. The sealed paid results and their original `held` judgments were not edited.

The latest separate read-only recheck is `results/2026-10-25-insight-candidate-development-flash-v2-offline-recheck-v4/`. It reports **one** FITB response as `candidate_for_qualitative_review` and **seven** still held. Across the seven, 17 typed assertions fail: nine contradict the selected source rows and eight are invalid or unassessable (four unlabeled cross-basis ratios, three comparisons of incompatible units and one unsupported relation literal). One response also has unstructured numeric interpretation text, and three contain numerical text in the saved free-form rationale. The arithmetic checker now validates any model-reported delta pair rather than silently ignoring it; this additional check did not change the one/seven split. A candidate is *only* eligible for further qualitative review, not an automatic high-quality insight. The recheck's own hash list verifies.

The retained claim records make the failure modes concrete: FITB's second response reverses a verified ratio direction; both RELY responses submit signed expense/EBITDA identities whose component signs do not reconcile to the claimed total; TFC includes comparisons across unlike units and unlabeled GAAP-versus-operating-basis ratios; both VRSK responses reverse a source-derived gap direction. These are distinct from the evidence-order evaluator defect and should not be relabeled as runtime transport failures.

## What this establishes and what it does not

The real model can autonomously follow the three-field JSON output shape and use the runtime to persist a traceable review and alert state across these seen cases. The proposed numerical/ledger gate can catch substantive assertion problems, but the original gate also produced an avoidable false hold due to evidence ordering. Correcting that bug does not cure the remaining numerical and unstructured-prose failures. This probe does not validate the economic usefulness, causal soundness, completeness or reproducible quality of the generated insight; it also reuses cases inspected during development.

Next: diagnose the seven numerical assertion failures by failure type, expand coverage checks to qualitative text and saved rationale, then freeze a genuinely source-distinct panel and a new protocol before any separately authorized confirmatory run. Do not describe the one rechecked candidate as a quality success.
