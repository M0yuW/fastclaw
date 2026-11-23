# Insight-quality remediation and next-arm plan (development, not preregistration)

**Execution update (2026-10-25):** The separately authorized v4 arm has now
finished 100/100 observations, with 99 mechanical passes and one retained TFC
review-write failure; estimated cost USD 1.136470428. The predeclared all-20
strong case gate is already unmet. See
`POSTCORRECTION-V4-RUN-SUMMARY-2026-10-25.md` for verified execution evidence
and the still-open blinded answer-quality review. Earlier planning statements
below describe their historical pre-run state, not the current run status.

The stopped v2 arm is 76/100. Its focused review found a reversed PNC growth
comparison and three ALLY answers falsely saying a source-defined pre-tax
bridge does not reconcile. The completed, separate v3 arm raised only the
output limit: it ran 100/100 at an estimated USD 0.924521796, with 99
mechanical passes and one retained MSCI tool-iteration failure. The former
CBOE output-limit case completed in v3, but a focused audit of the new ALLY
answers still found at least two false claims that the source-defined pre-tax
bridge could not be decomposed. See
`POSTCORRECTION-V3-PRELIMINARY-QUALITY-AUDIT-2026-10-24.md`. Neither v2 nor v3
raw data, prompts, or case gates may be retroactively changed or pooled with
a later intervention. The v3 run is not a quality correction.

## Development correction on already-seen material

The failure mode is a confusion between **accounting identity** and
**economic causation**. The system should present an exact signed bridge only
when a source auditor has verified the relevant formula, rows, units, periods,
and both period-level reconciliations. It must explicitly state that a zero
residual settles the arithmetic but does not establish what economically
caused any component to move. A model answer that says a listed bridge cannot
reconcile when its source-checked residual is zero fails the fact/calculation
gate even if its final action remains cautious.

`selected_fact_signed_bridge_v4.py` and
`build_postcorrection_signed_bridge_fixture_v4.py` are **free development
prototypes** over the already-inspected v2 issuer frame. They reproduce 22
source-defined signed bridges in 11 issuer cases, after re-running the source
auditors, with zero model calls. Their local scripted Gateway wiring is checked
below, but that success is not evidence of improved model output. Do not use the same
20 seen cases as a new confirmatory quality panel.

The free ALLY scripted-Gateway replay is now retained in
`results/2026-10-24-postcorrection-signed-bridge-local-replay-v4-loopback/`.
All nine checks pass: the signed +86−31+22=+77 bridge reached the local
model interface, four real finance-tool calls paired with four results, the
source-linked review persisted, the alert was acknowledged, and
`needs_review` left actionability blocked. The result/manifest hash list
verifies, port 18955 was closed, and external model calls/cost were zero. A
preceding sandbox-denied attempt has only a manifest and is not an
observation. This scripted replay verifies wiring only, **not** model
reasoning or a quality improvement.

## Genuinely fresh quality test

Select a new, source-distinct SEC issuer/period frame that has not supplied
development answers. Freeze every source byte hash, period, metric definition,
source row, GAAP/non-GAAP basis, formula and missing-data condition **before**
the first model call. Audit source facts independently of model answers.
The offline discovery roster `postcorrection_unseen_source_candidates_v4.json`
now ranks 23 unused issuers from the earlier sector pools; its first five per
sector form 20 **candidates**, not yet an eligible or frozen model panel.
`verify_postcorrection_unseen_candidates_v4.py` confirms none of the 20 was
observed in v1 or v2. The first public-source discovery batch (HBAN, PAYO,
VRSK, NTRS) located four Item 2.02 filings and four single EX-99.1 links per
issuer. Eight selected Q2/Q3 earnings exhibits were downloaded and hash-locked
in `results/2026-10-24-postcorrection-v4-first4-exhibits-complete/`; all eight
raw bytes and the manifest match `RESULT-SHA256.txt`. A separate October 20
HBAN merger announcement was excluded as **not** a quarterly earnings pair.
PAYO has now received a first richer source audit in
`payo_v4_rich_fact_packet.json` and `audit_payo_v4_rich_facts.py`: 30
selected historical facts, seven Q2 values repeated in the Q3 headline
table, and six guidance fields match the frozen exhibits. GAAP revenues,
operating expenses/income, signed financial expense, pre-tax income, tax
expense and net income reconcile in both quarters. Adjusted EBITDA is marked
non-GAAP, operating metrics retain their separate units, management
explanations are attributed rather than adopted as proved causes, and
guidance is labelled forward-looking. Four targeted tamper/pass tests pass.
`build_payo_v4_rich_fixture.py` produces a 15-metric event fixture and a
typed model-facing numeric context from that audited packet. It omits the
private interpretation checks and does not prescribe a thesis decision.
The free scripted-Gateway replay in
`results/2026-10-24-payo-v4-rich-local-replay/` passed all nine checks:
the GAAP signed change bridge, non-GAAP boundary, forward-looking guidance,
attributed management claims and source hash reached the local model
interface; four real finance-tool calls/results paired, a source-bound review
persisted, and the `needs_review` scripted decision blocked actionability.
Its result/manifest hash list verifies, port 18955 was closed, and external
model calls/cost were zero. This proves input/tool wiring only; the scripted
decision is **not** a generated financial insight or quality observation.
HBAN, VRSK and NTRS still require comparable row/period/basis audits; no v4
model output exists. This first packet is source preparation, not a quality
result.

Because PAYO was used to develop the richer prompt and inspect its evidence
mix, **exclude PAYO from the later confirmatory panel** even though the local
scripted provider produced no model answer. The 20-name discovery roster
therefore supplies at most 19 names for a 20-case panel;
its three listed reserves are all in the banking stratum. A replacement
payments candidate must be specified, source-checked and frozen under a
predeclared replacement rule before final panel selection. Do not silently
reuse PAYO or shrink the panel after seeing results.
WEX is the **provisional** same-stratum replacement candidate: the SEC lists
its [Q2 2025 earnings EX-99.1](https://www.sec.gov/Archives/edgar/data/1309108/000130910825000171/wexq22025earningsrelease.htm)
and [Q3 2025 earnings EX-99.1](https://www.sec.gov/Archives/edgar/data/1309108/000130910825000187/wexq32025earningsrelease.htm),
and WEX has no v1/v2 observation in the frozen roster. The two source bytes
are now retained in `results/2026-10-24-postcorrection-v4-wex-exhibits/`:
the Q2 and Q3 EX-99.1 files, manifest and hash list all verify. The source
lead text confirms the three-month periods ended June 30 and September 30,
2025, respectively. `audit_wex_v4_source_facts.py` has now checked 40
selected current-quarter values against their original SEC rows, the
GAAP/non-GAAP distinction, operating-volume units, both forward-looking
guidance ranges and prior-panel issuer exclusion. Four pass/tamper tests
pass. The displayed GAAP bridges have residuals of 0.0 or ±0.1 USD million
because the filing rounds to one decimal; no exact-zero bridge is asserted.
WEX is a source-audited replacement **candidate**, not a completed 20-case
panel: the other candidates, common prompt/rubric, and final frame still
need independent audit/freeze. Selection here uses no v4 model outcome.

The other 16 first-ranked issuers have now been processed in one free SEC
discovery batch, retained in
`results/2026-10-24-postcorrection-v4-remaining16-discovery/`.
`verify_postcorrection_v4_remaining_discovery.py` recomputes 85 raw-file
hashes covering 16 submission roots, five shards and 64 filing indexes;
62 indexes list a single EX-99.1, while two SPGI indexes list no EX-99.1.
For the latest Q3 SPGI filing, the single substantive earnings release is
labelled **EX-99**, not EX-99.1. The pre-output provisional selector now
records that explicit attachment-type exception and selects 16 adjacent
filing pairs. The 32 selected exhibit bytes and hash list are retained in
`results/2026-10-24-postcorrection-v4-remaining16-exhibits/`.
These are source-discovery and byte-integrity milestones, not row or
financial-quality audits.

NAVI is another important source-boundary exception: its Q2/Q3 EX-99.1
documents are short notices directing readers to the results, and contain
almost no financial values. The same 8-K filings include substantive
**EX-99.2** financial releases. Those two detailed attachments are now
hash-frozen in
`results/2026-10-24-postcorrection-v4-navi-detailed-exhibits/`,
with separate manifest and hash verification; their lead text identifies
second- and third-quarter 2025 financial results. The later NAVI packet must
cite both the announcement and detailed exhibit, drawing numeric facts from
EX-99.2. Treating the pointer EX-99.1 alone as full evidence would be a
case-design error, not a model-quality failure. All remaining candidate
periods, GAAP/non-GAAP bases, selected rows and material omissions still
require an independent per-case audit before a paid panel is frozen.

`audit_postcorrection_v4_source_identity.py` now runs a uniform read-only
identity/title precheck over the proposed PAYO-excluded/WEX-replaced 20-case
frame: 40 primary attachments plus NAVI's two detailed attachments. It
verifies local bytes and hash-list coverage, SEC CIK/accession URL identity,
the appropriate quarterly headline, and the SPGI/NAVI/FDS special source
rules. Three coverage/tamper tests pass. This establishes a plausible
source/period frame only. **All 20** candidates (WEX, HBAN, VRSK, NTRS,
SEIC, MKTX, FDS, RELY, CPAY, TFC, FITB, USB, C, FLYW, EVTC, SPGI, TRU,
NAVI, RKT and LPLA) now have selected-numeric-row audits; zero model
observations have been collected in v4, and the final panel/rubric is not
frozen. HBAN's packet and auditor
(`hban_v4_source_fact_packet.json`, `audit_hban_v4_source_facts.py`) verify 32
selected Q2/Q3 cells, all 16 Q2 values repeated in the Q3 exhibit, the FTE
revenue identities, and the distinct GAAP/non-GAAP notable-item arithmetic:
reported noninterest income rose USD 157 million, including a disclosed USD
24 million gain on sale, while adjusted noninterest income rose USD 133
million against the Q2 comparator. Four source/tamper tests pass. None of
these source checks is an answer-quality score; do not infer answer quality
from the 40/40 source-identity result. VRSK's packet and auditor
(`vrsk_v4_source_fact_packet.json`, `audit_vrsk_v4_source_facts.py`) separately
check 22 current-quarter SEC cells, six forward-looking guidance ranges, and
the displayed GAAP operating-income and tax/net-income identities in both
periods. Its Q3 release repeats the July revenue guidance range of USD
3,090–3,130 million before presenting an October update of USD 3,050–3,080
million. Although each release's headline also presents year-over-year
growth, the selected Q2→Q3 GAAP revenues and net income *decline* by USD 4.3
million and USD 27.8 million respectively. This is a useful future test of
period and GAAP/non-GAAP discipline, not a model result. Four VRSK tamper/pass
tests pass. NTRS's packet and auditor (`ntrs_v4_source_fact_packet.json`,
`audit_ntrs_v4_source_facts.py`) check 34 selected values, all 17 repeated
Q2 comparator values in the Q3 source, GAAP/FTE separation, trust-fee
subtotals, and a signed income-statement bridge. The Q3 credit-loss
provision is **negative** USD 17.0 million versus positive USD 16.5 million
in Q2, a signed change of −33.5 million; GAAP revenue rose USD 27.5 million
even while GAAP net interest income fell USD 19.7 million. Four NTRS
pass/tamper tests pass. SEIC's `seic_v4_declared_source_packet.json` is checked by the
reusable `audit_v4_declared_sec_rows.py`: 35 exact SEC table cells and nine
signed identities, including fee composition, operating income, pretax
income, tax and noncontrolling interest, reconcile. The Q2 one-time business
sale gain is USD 94.412 million and the Q3 row displays a dash/zero. Thus
SEIC's sequential operating income improved from USD 148.635 million to USD
159.961 million while net income fell from USD 227.083 million to USD
164.586 million; a model should not erase the one-time item or call the
operating line a decline. Four generic auditor pass/tamper tests pass.
MKTX's `mktx_v4_declared_source_packet.json` is also checked by that generic
auditor: 32 exact SEC cells and ten signed identities cover commission-based
revenue, operating/pretax/net income, and GAAP-to-adjusted net income. In Q2,
reported net income is USD 71.180 million while net income excluding notable
items is USD 74.489 million; Q3 reports USD 68.273 million on both bases.
The generic parser explicitly verifies the split closing cell for negative
amounts instead of silently dropping its sign. FDS's
`fds_v4_declared_source_packet.json` adds a fiscal-boundary case: FY2025 Q4
ended August 31, 2025 to adjacent FY2026 Q1 ended November 30, 2025. The
generic auditor checks 38 SEC cells and ten GAAP statement identities,
keeping reported results distinct from organic revenue and adjusted earnings.
GAAP net income changes from USD 153.616 million to USD 152.580 million while
non-GAAP adjusted net income changes from USD 154.590 million to USD 169.571
million; the periods must not be mislabeled CY Q2→Q3. Its fiscal-quarter
anchor tamper test passes. RELY's `rely_v4_declared_source_packet.json` adds
a cross-basis payments case: the generic auditor checks 46 exact SEC cells
and ten GAAP/adjusted-EBITDA identities. Sequential revenue and GAAP net
income rose, while operating income and adjusted EBITDA fell. The source
rows identify transaction expense, marketing, stock compensation and other
adjustments separately, so an answer cannot treat the adjusted EBITDA
movement as a GAAP net-income movement or infer a causal driver merely from
the arithmetic. Its signed-addback tamper test passes. CPAY's
`cpay_v4_declared_source_packet.json` checks 41 SEC cells and 12 GAAP-to-
adjusted-net-income identities. Sequential revenue and operating income
increase, while GAAP net income attributable to Corpay falls from USD
284.168 million to USD 277.941 million; adjusted attributable net income
rises from USD 366.421 million to USD 405.222 million. The source audit
retains disposition, integration, stock-compensation and tax adjustments,
including signed tax effects, so the two bases cannot be conflated. Its
signed-tax tamper test passes. The 20-case identity checker now actually runs
all eighteen available numeric row
auditors rather than reporting a stale hardcoded count. These remain source
facts, not agent quality observations.

TFC's `tfc_v4_declared_source_packet.json` checks 26 selected Q2/Q3 SEC cells,
13 Q2 comparators repeated in the Q3 exhibit, and both quarters' fully
taxable-equivalent (FTE) net-interest-income identities: interest income plus
the taxable-equivalent adjustment less interest expense. FTE net interest
income rises from USD 3,635 million to USD 3,680 million, whereas FTE net
interest margin slips from 3.02% to 3.01%; noninterest income rises and the
credit-loss provision falls. Net income available to common shareholders is
reported in rounded USD billions in the headline, so it is not used in an
exact USD-million reconciliation. The cross-source comparator tamper test
checks that an event-period table cannot silently misstate the baseline.

FITB's `fitb_v4_declared_source_packet.json` checks 30 Q2/Q3 SEC cells, 15
repeated Q2 comparators in the Q3 release, and ten exact GAAP identities
through net income available to common shareholders. Q3 GAAP net interest
income rises by USD 25 million and noninterest income by USD 31 million;
credit-loss provision rises by USD 24 million and noninterest expense by USD
3 million, yielding a USD 29 million pre-tax increase before a USD 8 million
tax increase and USD 4 million higher preferred dividends. The packet also
retains FTE NII and margin as separately typed non-GAAP measures; it does not
conflate them with the GAAP income bridge. Comparator and tax-sign tamper
tests protect those distinctions.

USB's `usb_v4_declared_source_packet.json` checks 34 selected SEC cells, 15
Q2 comparators repeated in the Q3 release, and 16 source-defined accounting
identities. Importantly, the earnings-highlight table uses a
taxable-equivalent presentation: its Q3 pre-tax income of USD 2,561 million
is USD 29 million above GAAP statement pre-tax income of USD 2,532 million,
and its income-tax-plus-adjustment line of USD 553 million is likewise USD
29 million above the GAAP tax line of USD 524 million. Both routes yield
GAAP net income of USD 2,008 million. The packet types those measures
separately so a later answer can be checked for a GAAP/FTE conflation.

Citigroup's `c_v4_declared_source_packet.json` checks 35 Q2/Q3 SEC cells,
14 repeated Q2 comparators, and 13 source-defined identities spanning
credit-cost components, pre-tax and attributable earnings, common earnings,
and the Q3 goodwill-impairment adjustment. Q3 reported net income
attributable to Citigroup falls from USD 4,019 million to USD 3,752 million
despite higher revenue, while the source separately reports USD 726 million
pre-tax/ USD 714 million after-tax goodwill impairment and adjusted Q3 net
income of USD 4,466 million. Reported diluted EPS is USD 1.86 versus
USD 2.24 excluding that charge. The packet preserves both the GAAP decline
and the non-GAAP addback; it does not infer that the adjusted figure is the
actual reported profit.

FLYW's `flyw_v4_declared_source_packet.json` checks 44 selected SEC cells,
ten GAAP/adjusted-EBITDA identities, and two unit conversions from exact
USD thousands to rounded USD millions. Q2 GAAP net loss of USD 12.007
million becomes Q3 GAAP net income of USD 29.631 million; separately,
adjusted EBITDA rises from USD 16.6 million to USD 57.1 million. The EBITDA
bridges preserve stock compensation, FX remeasurement and other addbacks,
with a USD 0.2 million tolerance only for the sum of individually rounded
one-decimal non-GAAP rows. Its Q3 source compares Q3 against the prior-year
quarter, not Q2, so no same-table Q2 comparator is claimed; sequential
change is computed only across the two independently frozen filings.

EVTC's `evtc_v4_declared_source_packet.json` checks 48 selected Q2/Q3 SEC
cells and 16 exact source-defined identities, including GAAP operating,
pre-tax, net and common earnings, EBITDA, adjusted EBITDA, and adjusted net
income. Q3 GAAP revenue falls from USD 229.607 million to USD 228.587
million, GAAP net income from USD 40.973 million to USD 33.460 million, and
operating income from USD 56.134 million to USD 37.732 million; yet adjusted
net income rises from USD 57.665 million to USD 59.784 million. Both
definitions remain distinct, with the Q3 tax benefit and transaction-fee
adjustment signs checked. The event table does not reprint Q2 as a comparator,
so the sequential comparison comes from the two individually frozen sources.

SPGI's `spgi_v4_declared_source_packet.json` checks 44 selected cells and 14
GAAP/non-GAAP identities across Q2 and Q3. It reads the Q3 filing's EX-99
earnings release rather than assuming an EX-99.1, and keeps GAAP versus
adjusted EPS, operating profit, interest, and tax distinct. GAAP revenue
increases from USD 3,755 million to USD 3,888 million; GAAP operating
profit from USD 1,551 million to USD 1,675 million; adjusted operating
profit from USD 1,931 million to USD 2,026 million. The Q2 adjusted
operating-profit component rows differ from the displayed rounded total by
USD 1 million, so that one identity has an explicit USD 1 million tolerance;
the Q3 version is exact. No Q2 comparator cell exists in the Q3 table.

TRU's `tru_v4_declared_source_packet.json` checks 44 SEC cells and 12
GAAP/adjusted identities. It additionally types five Q2-published Q3
guidance ranges as **forward guidance**, not realized results, and checks
that Q3 actual revenue, attributable net income, adjusted EBITDA, GAAP
diluted EPS and adjusted diluted EPS each exceed their preannounced upper
bounds. Q3 revenue is USD 1,169.5 million versus the earlier USD
1,115-1,135 million range; adjusted EBITDA is USD 425.1 million versus
USD 397-411 million. Those comparisons are source-verifiable, but a
"guidance beat" alone is not proof that an agent independently generated
a valuable investment conclusion. The Q3 GAAP net-income and adjusted-
EBITDA displays each have a USD 0.1 million rounded bridge difference,
explicitly bounded rather than silently forced to equality.

NAVI's `navi_v4_declared_source_packet.json` selects 36 rows from the
same-filing EX-99.2 detailed exhibits, not the short EX-99.1 announcement
pages. It verifies both SEC accession relationships, 18 Q2 comparator cells
reprinted in the Q3 detail, and 14 identities covering FFELP plus consumer
loan-loss provisions, interest income/expense, post-provision NII, GAAP
earnings and the source-defined Core Earnings bridge. Total provision jumps
from USD 37 million to USD 168 million (consumer lending: USD 29 million to
USD 155 million); post-provision NII turns from USD 91 million to negative
USD 26 million. Q3 GAAP net loss of USD 86 million becomes Core Earnings
net loss of USD 83 million after signed derivative, intangible and tax
adjustments. A source-identity tamper test prevents substituting the
announcement pointer for the detailed financial exhibit.

RKT's `rkt_v4_declared_source_packet.json` checks 64 selected Q2/Q3 SEC
cells, six exact-source-to-rounded-headline unit conversions, and 18
declared identities. Q3 GAAP revenue rises from USD 1,360.251 million to
USD 1,605.284 million, yet GAAP net income of USD 34.089 million turns to
a USD 123.854 million loss; the Q3 MSR fair-value line is negative USD
479.602 million versus negative USD 198.885 million in Q2, and total
expenses rise from USD 1,335.989 million to USD 1,789.480 million. The
release simultaneously reports adjusted net income of USD 158 million and
adjusted EBITDA of USD 349 million. The current packet verifies those
adjusted amounts as displayed rows but does **not yet** independently
recompute their full non-GAAP add-back bridges. Its adjusted-revenue
reconciliation permits only USD 1 million of published-million rounding;
the GAAP statement identities are exact in USD thousands. An answer must
not describe the positive adjusted result as GAAP profitability or present
the accounting decomposition as a causal explanation.

LPLA's `lpla_v4_declared_source_packet.json` checks 66 Q2/Q3 rows, 12
Q2 values reprinted in the Q3 exhibit, and 20 accounting/non-GAAP
identities. Q3 revenue rises from USD 3,835.025 million to USD 4,551.977
million, while total expense rises from USD 3,466.221 million to USD
4,586.088 million, taking GAAP net income from USD 273.249 million to a
USD 29.517 million loss. The source's acquisition costs excluding interest
rise from USD 71.562 million to USD 538.177 million. Its operating bridge
reconciles Q3 EBITDA of USD 236.612 million plus that disclosed acquisition
amount to adjusted EBITDA of USD 774.789 million, versus USD 688.336
million in Q2. This is a disclosed non-GAAP adjustment, not proof that the
cost is immaterial or nonrecurring. The packet does not yet recompute the
full adjusted EPS or adjusted pre-tax-income reconciliations.

`build_postcorrection_v4_event_preflight.py` now converts the 20 audited
source packets into **20 model-free event-workflow fixtures**. The builder
reruns the source/selected-row audits, binds each fixture to the frozen SEC
URL and hash, labels period/unit/basis, computes same-basis
event-minus-baseline changes, and renders 94 source-audited signed bridge
comparisons where both period formulas match. It keeps FDS's fiscal Q4-to-Q1
transition explicit, points NAVI at the same-filing detailed exhibit,
labels guidance as forward-looking, and does not prewrite an impact or
research-state decision. Fifty-two source/preflight tests pass, including
negative tests for altered values, signs, units, comparators and source
identity. These fixtures have **zero model observations**; creating them is
not a paid experiment or a quality score. A free scripted Gateway seam
replay using the final fixture was completed for LPLA in
`results/2026-10-25-postcorrection-v4-lpla-scripted-gateway-replay-v3/`:
all seven chain/state checks passed, with four paired finance-tool calls,
one persisted source-linked review, a blocked thesis and an acknowledged
alert; the result hash list verifies. The scripted provider made five local
requests and **zero external model requests**. This tests delivery and
execution, not autonomous analysis or insight quality. A fixed answer-level
rubric and fresh-run script are now written in
`POSTCORRECTION-V4-INSIGHT-QUALITY-PROTOCOL.md` and
`run_postcorrection_event_holdout_v4.py`. The source-audited preflight
declares 20 cases, five fresh sessions each, 94 rendered bridges, an 8,192-
token output limit, 16 tool iterations and fixed run-order digest
`c421216d9332475c37af20b01fce83deae4714da3c397e4422a9ba1f4b85b20c`.
`prepare_postcorrection_v4_judgment.py` also prepares order/outcome-masked
answer packets and blank F/I/R/S/U score forms without changing raw outputs.
Fifty-eight source, fixture, runner and masking tests pass. The official
DeepSeek Flash peak input/output/cache-read prices and the
DeepSeek-V4.1-Flash-1017 routing were checked on 2026-10-25. This is still **0/100 v4
model observations**. Verify current provider routing/prices and obtain a
new explicit spend authorization before running the paid arm; the v2/v3
authorization does not carry over.

The richer packet should explicitly distinguish what the **selected packet**
contains from what the **full SEC exhibit** contains. Where source-audited,
include GAAP statement rows, non-GAAP definitions/reconciliations, operating
metrics, guidance and management explanations as differently typed evidence.
Management's explanation is an attributed claim, not independent proof of
causation; guidance is forward-looking, not a realized result. This prevents
an agent from incorrectly asserting that a disclosure does not exist merely
because an earlier selected-fact extract omitted it.
Freeze the new prompt, bridge catalog, model, Gateway binary, output limit,
randomized run order, spending cap, error/timeout handling, and F/I/R/S/U
rubric before paid execution. New paid authorization is required; old caps do
not transfer.

Run fresh isolated sessions with five repetitions per case. Treat any
truncation, missing tool write, wrong fact/bridge, unsupported inference,
false ledger state, or unassessable output as an observation failure. Do not
retry or remove failures from the denominator. Review **all** material claims
in both final prose and persisted records against frozen SEC rows and actual
tool/ledger state, using masked order/outcome packets. Judge the importance of
counterevidence, uncertainty and research utility separately from literal
fact echoes. A Codex/LLM judge is diagnostic; without an independent finance
professional, do not claim expert-validated investment value.

For a new event-workflow panel, the existing stringent case rule (five
mechanically complete, no critical error, at least four `high` and at most
one `adequate`) remains a useful target. If the predeclared claim is a
Bonferroni-adjusted one-sided 95% lower bound above 80% across three
workflows, an **all-pass 20-case** event panel just clears it (lower bound
about 0.815); a **30-case** panel would tolerate one failed case (29/30 lower
bound about 0.815). These are design calculations, not observed results.
Choose and freeze the case count before collecting a new answer; do not
select a sample size after inspecting outcomes.

Finally, event→thesis evidence alone is not cross-workflow reliability. A
separate source-distinct screening→candidate and portfolio-risk panel is
needed for each additional workflow claim, with its own case frame and
quality/state rubric. No panel should be silently narrowed because another
workflow is harder.
