# Model-free failure replay for W01F-r1

This is a deterministic local regression, not a new finance-model observation. No paid provider, SEC request, or live market tool was called. The retained W01F-r1 result was read without modification.

The offline audit applies the finance tool's declared required fields to the retained tool-call trace. It detects four review calls missing `thesis_id`, four corresponding `invalid_input` results, one subsequent `alert_required` result, a later successful review write, and a terminal maximum-tool-iteration message. The request itself has no HTTP/provider error, but the workflow is incomplete because the Q4 alert remains unacknowledged. Tool calls and results remain paired.

A fresh, temporary finance ledger then replays the malformed review arguments directly against the actual finance plugin: each is rejected with no review or thesis-version mutation. A corrected call linked to the stored alert succeeds, followed by successful acknowledgement. This establishes that the tool can recover when correct arguments are supplied; it does not explain why the model repeatedly omitted them in the original run.

A separate Go agent-loop test uses a deterministic local fake provider and a fixture review tool. It confirms both error → corrected call → completion and repeated error → iteration-budget exhaustion. Under current Go behavior, budget exhaustion emits a normal-looking `done` plus fixed terminal text, not an `error` event. This is a diagnosability limitation, not a finance-ledger data-integrity failure.

An isolated HTTP Gateway replay then exercises the actual finance plugin and Gateway endpoint with a local scripted provider, not DeepSeek. Its [recovery result](../2026-10-18-finance-gateway-fault-replay-v1/recovery.json) shows one rejected malformed review followed by a successful corrected review and alert acknowledgement. Its [budget result](../2026-10-18-finance-gateway-fault-replay-v1/budget.json) shows eight rejected malformed reviews, no ledger mutation, an unacknowledged alert, and the maximum-iteration fallback text. Both have paired tool calls/results. This is full local Gateway-path fault injection, but not a Go/Python differential deployment or a fresh model observation.

Verification: `python3 -m unittest evals.finance_e2e.test_workflow_failure_audit evals.finance_e2e.test_missing_evidence_guard -q` passed (3 tests); `go test ./internal/agent -count=1` passed. The original W01F-r1 remains failed and was not retried or rescored.
