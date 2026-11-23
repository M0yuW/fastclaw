# New-issuer arithmetic-guard coverage probe

Offline, no model or Gateway/provider request. The catalog was constructed from each of the three verified mini-panel fixtures and passed to `ReviewArithmeticGuard.check` with an unheld `maintain` decision. These are adversarial probe sentences, **not saved model answers** and not a measured false-positive or recall rate.

| Explicit probe | MTB | RPAY | CSGP |
| --- | --- | --- | --- |
| False “research hold is preserved” | flagged | flagged | flagged |
| False “operating profit rose by more than revenue” | no comparable GAAP total rows | not flagged: Q2 impairment makes the displayed increment numerically true | flagged |
| False “tax expense created a larger tax drag” | no selected signed tax row | flagged | flagged |
| Correctly negated tax-drag sentence | not flagged | not flagged | not flagged |
| “GAAP loss improvement proves recurring operating recovery” | not applicable | **not flagged** | not applicable |

This probe exposed missing aliases for `gaap_operating_income_loss` and `gaap_income_tax_benefit`, and the need to interpret a signed tax-expense decrease as an improvement. The guard now handles those typed cases and recognizes a nearby negation; `test_review_arithmetic_guard.py` and `test_plugin.py` passed 40 tests after the change. No old result or answer was rewritten. The RPAY recurring-recovery inference remains outside this lexical arithmetic guard and requires claim-level review or a separately designed evidence rule. It must not be counted as prevented by the runtime.

The current guarded mini-run, if authorized later, will hash its actual guard code in the manifest. The earlier local scripted Gateway preflight only establishes that the legal `needs_review` path works; this offline probe does not establish that the Gateway catches every wrong narrative.
