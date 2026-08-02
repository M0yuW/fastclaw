# Longitudinal SEC Multi-Agent Study (R3, Frozen Primary Run)

## 1. Research Motivation

The preceding four-company R7 pilot used one initial observation per company. Team, `solo_open_book`, `solo_two_pass`, and the routed-team diagnostic all achieved 4/4 strict success. This ceiling effect established runtime feasibility but made an incremental-accuracy comparison impossible: when a strong single coordinator already solves every case with the same evidence, the experiment has no remaining outcome variance from which to identify a collaboration benefit.

The longitudinal extension therefore increases task difficulty without changing the source corpus or introducing return prediction. Each case combines three locked SEC observations and requires chronology reconstruction, cross-observation calculation control, a contiguous versioned state transition, a final research-state decision, and explicit rejection of a stale control candidate. The objective is to test whether role specialization adds value after evidence visibility is equalized.

## 2. Experimental Design

- Companies: NVIDIA, AMD, Intel, and NIKE.
- Cases: `FHARD-NVDA-01`, `FHARD-AMD-01`, `FHARD-INTC-01`, and `FHARD-NKE-01`.
- Observations per case: three locked Form 8-K Exhibit 99.1 filing artifacts.
- Coordinator: `deepseek/deepseek-v4-pro`.
- Specialists: `deepseek/deepseek-v4-flash` for source chronology, methodology control, and governance-state validation.
- Modes: `solo_open_book`, `solo_two_pass`, `team`, and `oracle_team`.
- Evidence fairness: all modes receive the same substantive SEC, calculation, and governance evidence. Only Team may invoke runtime specialists.
- Repetitions: one per case in the frozen primary run.
- Timeout: eight minutes per mode.
- Numeric policy: only source values, version values, period labels, and predeclared calculation results are authorized.
- Governance policy: the accepted state chain must be `0→1→2→3`; the named stale candidate must be rejected; no trade may be recommended or authorized.

The `oracle_team` label denotes perfect evidence routing, not a theoretical performance upper bound. The coordinator must still synthesize the supplied reports and may omit a required assertion.

## 3. Instrument Calibration and Exclusion Rule

Calibration runs diagnosed output truncation, natural-language false positives in stale-candidate matching, percentage-point parsing, negative accounting context, conjunction splitting, ordered-list numbering, and coordinated decline phrases. These defects were corrected with regression tests before R3.

The NVIDIA pilot and full-suite R1/R2 artifacts are retained for benchmark development and failure analysis. They are excluded from the primary comparison because their outputs informed grader calibration. R3 is the first four-company run after the task suite and all identified scoring rules were frozen together. No R3 output was used to alter the reported R3 grader.

## 4. Frozen Primary Results

| Mode | Strict success | Rate | Total tokens | Estimated cost | Mean latency |
|---|---:|---:|---:|---:|---:|
| Solo Open-Book | 3/4 | 75% | 27,847 | USD 0.018099 | 57.32 s |
| Solo Two-Pass | 1/4 | 25% | 51,556 | USD 0.029369 | 94.31 s |
| Team | 3/4 | 75% | 78,800 | USD 0.022718 | 65.31 s |
| Routed-Team Diagnostic | 1/4 | 25% | 24,021 | USD 0.014562 | 48.69 s |

| Team metric | Result |
|---|---:|
| Fair collaboration gain, Team minus Solo Open-Book | 0 percentage points |
| Compute-matched gain, Team minus Solo Two-Pass | +50 percentage points |
| Delegation F1 | 100% |
| Specialist contribution utilization | 91.7% |
| Contribution-item coverage | 95.6% |
| Grounding accuracy | 100% |
| Evidence-ID retention | 100% |
| Unauthorized numeric values | 0 |
| Team latency P50 / P95 | 65.20 s / 86.56 s |
| Total four-mode experiment cost | USD 0.084748 |

Team and Solo Open-Book each passed three cases. Their paired outcomes contain one Team-only success (NIKE), one Solo-only success (AMD), and two ties. The fair collaboration gain is therefore exactly zero; the two discordant pairs are balanced, so an exact paired sign/McNemar test provides no evidence of a directional difference. Team exceeded Solo Two-Pass by two cases, but only two pairs were discordant; this pilot is too small for an inferential claim.

Relative to Solo Open-Book, Team used 183.0% more tokens, cost 25.5% more, and had 13.9% higher mean latency without improving strict success. Relative to Solo Two-Pass, Team used 52.8% more tokens but cost 22.6% less and reduced mean latency by 30.8%, reflecting parallel Flash specialists versus two sequential Pro coordinator passes. These are descriptive results under the recorded prices and model assignment.

## 5. Case-Level Outcomes

| Case | Open-Book | Two-Pass | Team | Routed diagnostic | Team interpretation |
|---|---:|---:|---:|---:|---|
| NVIDIA | Pass | Pass | Pass | Fail | Team preserved chronology, calculations, state chain, and stale-candidate rejection. |
| AMD | Pass | Fail | Fail | Fail | The governance specialist returned an empty result; the coordinator retried three times, reached five delegations, and still lacked auditable STATE/STALE evidence. |
| Intel | Pass | Fail | Pass | Fail | Team retained restructuring, impairment, workforce, dividend, period, and version-control evidence without undeclared arithmetic. |
| NIKE | Fail | Fail | Pass | Pass | Team preserved the change from initial margin improvement to later channel-and-margin deterioration and rejected the stale resolution state. |

The AMD failure is operationally important. Routing precision and recall alone were insufficient: the coordinator selected the correct specialist, but the specialist produced no usable evidence. Retrying changed neither the result nor the evidence state and violated the three-delegation budget. This exposes a runtime reliability problem—empty sub-agent responses require an explicit failure contract and a bounded retry policy—rather than a missing SEC fact.

## 6. Thesis Interpretation

The simple R7 tasks and the longitudinal R3 tasks support different claims. R7 demonstrates a ceiling effect: all evidence-matched modes solved every initial-observation case, so the experiment cannot identify incremental multi-agent accuracy. R3 removes that ceiling, but the final Team and Open-Book rates remain equal at 75%. Consequently, the current evidence supports neither a positive collaboration-accuracy claim nor an equivalence claim.

The defensible thesis conclusion is narrower:

1. increasing longitudinal, calculation, and state-conflict requirements creates measurable mode-level failures that the simple suite concealed;
2. FastClaw Team execution can preserve provenance and numeric boundaries on three of four hard cases;
3. role separation improves outcomes relative to the evaluated two-pass prompt but not relative to the strongest evidence-matched one-pass Solo baseline;
4. specialist availability and retry control are part of the measured treatment and can erase any theoretical coordination advantage;
5. a claim of incremental accuracy requires a preregistered, frozen, repeated holdout rather than one four-case run.

The result should therefore be reported as a measurement and systems finding: task difficulty is necessary to avoid baseline saturation, but difficulty alone does not guarantee a multi-agent advantage.

## 7. Required Confirmatory Study

1. Freeze the current suite and grader before generating an untouched holdout.
2. Expand to at least 24 longitudinal cases across additional issuers, sectors, and mechanism classes.
3. Run at least three repetitions per case and mode with paired case–repetition identifiers.
4. Report raw paired outcomes, Wilson intervals, exact paired tests, and between-repetition instability.
5. Add explicit sub-agent statuses for success, empty output, timeout, malformed output, and provider error.
6. Bound retries by both specialist and total delegation budget; report recovery success separately from first-attempt success.
7. Keep workflow correctness separate from point-in-time return prediction and portfolio performance.

## 8. Reproduction Artifacts

- Frozen suite: `../../multiagent-finance-sec-hard.json`
- Frozen suite SHA-256: `6b1933347fcead04b68732f99bc892b8e6b2d4a6bb8a8ae555e71dc2441b970e`
- Runtime evidence pack: `../runtime-agent-evidence-hard.json`
- Runtime evidence-pack SHA-256: `c3d8dbb511f74101e5bdbd2f661693babc5a05d5ae4e9ca5f37d9153a4890690`
- Raw R3 report: `2026-08-02-hard-r3-final.json`
- Raw report SHA-256: `61fab590cea3884ad37e4cc97e31adffc0e0fea3fd470cd81bd74128c7365209`
- Post-run analysis: `2026-08-02-hard-r3-final-analysis.json`
- Analysis SHA-256: `5702b3642d77fbfcc82af25017ccf7a903cfac4dbdeb344a1ae8385552a67f16`
