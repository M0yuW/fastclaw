# Independent-source conflict guard: Flash regression

Two isolated repetitions reused the same frozen synthetic two-source capex case and seven checks from the earlier Pro guard regression. The only intended model change was the coordinator configuration and pricing table: every recorded inner model call was `deepseek/deepseek-v4-flash`. Each repetition had its own Gateway home, model session, and finance ledger. The local Gateway on port 18955 was stopped after the run.

| Attempt | Mechanical checks | Persisted review | Thesis conclusion | Actionability | Estimated model cost |
|---|---|---|---|---|---:|
| W02GF-r1 | 7/7 | `needs_review`, both source hashes linked | `active`, conviction 3 | `blocked` | USD 0.0016619288 |
| W02GF-r2 | 7/7 | `needs_review`, both source hashes linked | `active`, conviction 3 | `blocked` | USD 0.0016105936 |

Both completed without request/provider error or model mismatch. Combined estimated cost was USD 0.0032725224, below the isolated USD 0.03 stop. This result supports the narrow claim that the same runtime/finance-tool workflow can execute with Flash and preserve the decision-hold invariant. It does not establish general model independence, production reliability, source-extraction correctness, or financial-analysis quality. The source documents are explicitly synthetic; the plugin receives source-linked claims from trusted ingestion and does not independently parse document bytes.

The comparable Pro regression is in `../2026-10-17-finance-conflict-guard-v4/`. Neither small, non-random sample should be interpreted as a statistically meaningful Flash-versus-Pro comparison.
