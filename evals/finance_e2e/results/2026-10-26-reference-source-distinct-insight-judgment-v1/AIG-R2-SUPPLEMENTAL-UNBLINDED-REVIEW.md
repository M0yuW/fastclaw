# AIG r2 supplemental, unblinded claim review

This is a later **unblinded** diagnostic check of observation
`RS-AIG-CY2025Q2Q3-r2` (`J-bedc3e5de52812d6`). The reviewer already knew the
issuer and had inspected other AIG runs. It does **not** fill the original blank
masked score, change the sealed result, or qualify as a prospectively blinded
judgment for the 30-issuer aggregate.

The raw result SHA-256 is
`7c26e00ca1bd719b3fee510085636d33c73ac0965af5c120955ed01257b6e2a9`;
the masked packet SHA-256 is
`2d51d4cbaa52d2944a5abc5dcd2768770fe6388a0a8b67787ab79de1cd278520`.
Both match the retained mapping/hash list. The result passed its mechanical
workflow checks; the qualitative check below is separate. The offline source
freeze/fixture preflight was rerun and verified the 30-issuer, 523-comparison
catalog including AIG without making a provider request.

| Material final-answer and saved-review claim | Frozen selected-row check | Judgment |
| --- | --- | --- |
| Adjusted pretax and after-tax income improved while common-shareholder GAAP income fell. | Total adjusted pretax 1391→1622, adjusted after-tax 1044→1226, GAAP net income attributable to common 1144→519, all USD million. | Supported; explicitly different accounting bases. |
| General Insurance improvement included underwriting and segment investment income. | GI adjusted pretax 1497→1738; GI underwriting 626→793 and GI investment 871→945. The displayed changes satisfy 167+74=241. | Supported arithmetic contribution, not a proven economic cause. |
| Reported combined-ratio improvement did not establish a better current accident-year loss trend. | Reported GI ratio 89.3→86.8%; adjusted accident-year loss ratio 57.4→57.4%; adjusted accident-year combined ratio 88.4→88.3%. | Supported bounded inference. |
| GAAP and APTI-basis investment-income lines diverged. | Consolidated reported 1466→772 versus company-defined APTI basis 955→1024, USD million. | Supported; answer does not equate the bases or invent a reconciliation. |
| Gross and net written premiums declined; their drivers cannot be identified here. | GI gross 10056→8686 and net 6880→6230, USD million. | Supported. The answer explicitly avoids attributing the movement to rate, volume, mix, or cession. |
| The proper research action is to await basis and driver reconciliations without changing conviction. | Saved review `needs_review`; active conviction 3 preserved; `decision_hold=true`, `actionability=blocked`; linked alert acknowledged. | Supported by retained ledger and trace. |

The answer correctly confines itself to selected SEC exhibit rows, not complete
filings or a year-over-year comparison. Its suggested future evidence—GAAP to
adjusted reconciliation, investment-income basis, premium drivers, and prior-year
development/catastrophe detail—is relevant to the unresolved question. No
material contradiction, invented tool state, or decision-changing unsupported
claim was found. Under the existing F/I/R/S/U definitions, this supplemental
diagnosis would be **2/2/2/2/2, high within this selected-source case**, with
zero identified critical errors. This is a Codex diagnostic judgment, not
independent finance-expert validation or a prospective pass-rate observation.

Selection matters: the same AIG issuer has three previously scored high
answers, one scored problematic answer, and this originally unreviewed answer.
The problematic saved result remains part of the record. A selected high answer
can illustrate *capability*, not reliable high-quality output for AIG or the
broader issuer population.
