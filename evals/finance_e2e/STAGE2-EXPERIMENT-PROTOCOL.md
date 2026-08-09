# Stage 2 Protocol: Retrieval-Mediated Financial Research

## 1. Protocol status

This document is the execution specification for the second-stage FastClaw
financial experiment. It is a **pre-execution protocol draft** until every item
in the freeze checklist is complete. Once the first Stage 2 provider request is
sent, the suite, source lock, graders, treatment definitions, model allocation,
randomization seed, stopping rules, and primary analysis must not be changed.

The experiment evaluates an agent runtime and its information-flow policy. It
does not evaluate investment returns, price forecasts, trade execution, or
client suitability. No result may be described as evidence that FastClaw is an
autonomous adviser or that a multi-agent system has superior investment skill.

## 2. Research objective

The practical financial workflow is:

1. retrieve relevant records from a dated primary-source corpus;
2. allocate the retrieved evidence to analytical perspectives;
3. produce specialist summaries without losing source identity;
4. synthesize a bounded research-state decision; and
5. retain enough telemetry to attribute quality, latency, tokens, and cost to
   retrieval, coordination, specialist analysis, and synthesis.

Stage 2 asks whether retrieving one bounded evidence packet before parallel
specialist analysis improves the quality–cost–latency frontier relative to a
sequential single-agent pipeline and a Team that repeatedly analyzes raw
context.

## 3. Claims and non-claims

### 3.1 Claims the design can support

- paired differences among declared runtime modes on the frozen SEC cases;
- evidence-retention and numeric-grounding behavior under increasing corpus
  load;
- the measured deployment trade-off of Pro coordinator/Solo and Flash
  retriever/specialists under the recorded pricing table;
- the effect of retrieved versus raw shared context inside the same Team
  topology;
- observed failure mechanisms and their stage attribution.

### 3.2 Claims the design cannot support

- general multi-agent superiority across financial tasks or model providers;
- latent model-capability improvement caused by the runtime;
- profitable forecasting, security selection, or portfolio performance;
- live-web retrieval reliability or source completeness beyond the archive;
- full semantic entailment from the numeric grounding grader;
- independent observations from every load and repetition of one company–task
  source set.

## 4. Preregistered questions and hypotheses

### RQ2-S2: orchestration outcome

Does `team_shared_retrieval` preserve strict success, milestone completion, and
final evidence recall relative to `solo_staged` on paired SEC cases?

### RQ3-S2: context allocation and efficiency

Does `team_shared_retrieval` reduce raw-context replication, unsupported numeric
assertions, latency, tokens, or estimated cost relative to
`team_raw_context`, and does the effect change with corpus load?

### Hypotheses

- **H2a—quality preservation:** shared-retrieval Team will not reduce final
  evidence recall or milestone accuracy relative to staged Solo.
- **H2b—parallel latency:** shared-retrieval Team will have lower paired
  wall-clock latency than staged Solo.
- **H3a—context compaction:** shared-retrieval Team will use fewer paired
  provider-total tokens and lower estimated cost than raw-context Team.
- **H3b—grounding:** shared-retrieval Team will have equal or higher numeric
  grounding accuracy and fewer violation values than raw-context Team.
- **H3c—load interaction:** the token and grounding differences between shared
  retrieval and raw context will be larger at medium and large loads than at
  small load.

These are directional mechanism hypotheses. The initial four-company matrix is
not powered for a population-level superiority or non-inferiority claim.

## 5. Experimental stages

### 5.1 Stage 2A: frozen four-company confirmation

Use the existing source-locked matrix:

- companies: NVIDIA, AMD, Intel, and NIKE;
- task families: point-in-time and longitudinal;
- corpus loads: small, medium, and large;
- configurations: `4 × 2 × 3 = 24`;
- independent company–task clusters: `4 × 2 = 8`.

The load levels are repeated treatments over related source material. They must
not be reported as 24 independent issuers or 24 independent financial events.

Primary modes run for three repetitions:

1. `solo_staged`;
2. `team_shared_retrieval`;
3. `team_raw_context`.

This produces `24 × 3 × 3 = 216` primary mode observations.

Diagnostic modes run once per configuration:

1. `solo_monolithic`;
2. `oracle_evidence`.

This adds `24 × 2 = 48` diagnostic observations. The complete Stage 2A target
is therefore 264 mode observations. Diagnostic modes are excluded from the
primary repeated-treatment confidence intervals.

### 5.2 Stage 2A capacity-matched ablation

The deployment comparison intentionally uses Pro for the coordinator and staged
Solo, and Flash for retrieval and specialists. Cost differences therefore mix
architecture and model allocation. Before making an architectural efficiency
claim, run a focused all-Pro Team ablation on eight prespecified configurations:

- one medium longitudinal case per company; and
- one large point-in-time case per company.

Each selected configuration runs three repetitions. The comparison is all-Pro
shared-retrieval Team versus the existing Pro staged Solo. This ablation is
reported separately from the heterogeneous deployment result and requires a
distinct mode label and pricing bucket.

### 5.3 Stage 2B: issuer-panel expansion

Stage 2B begins only after Stage 2A passes all data and grader audit gates. Add
four issuers to increase business-model diversity:

- JPMorgan Chase: banking income, credit quality, capital, and period-basis
  reconciliation;
- Visa: payment volume, cross-border volume, processed transactions, and
  revenue reconciliation;
- PayPal: total payment volume, transactions, active-account measures, and
  transaction-margin context;
- Microsoft: cloud segment growth, consolidated revenue, capital expenditure,
  and period-alignment checks.

These are candidate fact families, not predeclared numeric facts. No value may
enter the suite until it is extracted from an accepted source and independently
audited.

For each new company, construct the same two task families and three load levels,
adding 24 configurations and eight company–task clusters. The combined panel
will contain 48 configurations and 16 clusters. Cross-company comparison tasks
may be added later, but they require a separate period-alignment oracle and must
not be mixed into the within-company estimand.

## 6. Source-data contract

Only archived primary-source material accepted by the source audit may enter the
corpus. Each source must record:

- issuer and ticker;
- SEC accession or equivalent primary-source identifier;
- filing date and reporting period end;
- document type and exact locator;
- retrieval timestamp;
- source URL or archive path;
- SHA-256 of the retained document;
- accounting basis, unit, scope, and period for every gold numeric fact.

Every generated record must retain a stable record ID and source ID. A source
lock is immutable within a formal run. A hash mismatch, unavailable source, or
manual correction stops the run and creates a new protocol version rather than
silently replacing evidence.

### 6.1 Human audit

Two passes are required before freeze:

1. a source audit verifies that each excerpt exists in the locked document and
   that filing date, period, unit, and accounting basis are correct;
2. an oracle audit independently recomputes every declared calculation and
   checks every gold evidence-equivalence group.

The second pass must not use model-generated answers as a source of truth. Audit
disagreements are resolved before execution and recorded without model scores.

## 7. Treatment definitions

### 7.1 Solo staged

One Pro agent performs retrieval, three isolated analytical perspectives, and
final synthesis sequentially. It receives the same source corpus, analysis
protocol, formulas, and output contract as Team but has no delegation tool.

### 7.2 Team shared retrieval

One Flash retriever creates one bounded evidence packet. A Pro coordinator sends
that packet once through batch `spawn_subagent` to three parallel Flash
specialists—trend, accounting, and risk—and synthesizes their outputs.

### 7.3 Team raw context

The coordinator and specialist assignments are identical to shared-retrieval
Team, but the full raw corpus is supplied as batch shared context. The difference
between these Team modes estimates the system effect of retrieval compaction and
context allocation within the tested topology.

### 7.4 Diagnostics

`solo_monolithic` measures the minimum-call direct path but combines retrieval,
analysis, and synthesis in one context. `oracle_evidence` receives perfect gold
retrieval and estimates the remaining synthesis overhead. Neither is the primary
fair Team/Solo comparison.

## 8. Randomization and isolation

Before formal execution, the runner must support and report a fixed
randomization seed. For each case–repetition block:

1. derive a deterministic block seed from the frozen study seed, case ID, and
   repetition number;
2. randomly permute the three primary modes;
3. use a unique session for every mode;
4. prevent conversation history from crossing mode or repetition boundaries;
5. record the realized order in the result artifact.

The global Stage 2A seed is fixed to `20260802` unless the run has not started
and this protocol is versioned before freeze. Provider concurrency is limited to
one case block at a time for the primary analysis. Parallel specialist calls
inside one Team attempt remain part of the treatment.

## 9. Model and decoding controls

Record exact provider-facing model names for every call. The deployment
allocation is:

- coordinator: `deepseek-v4-pro`;
- staged Solo: `deepseek-v4-pro`;
- retriever and specialists: `deepseek-v4-flash`;
- thinking mode: disabled;
- maximum output tokens: fixed by agent role and unchanged during Stage 2.

Temperature and every provider-supported decoding parameter must be recorded.
If the provider does not expose or honor a parameter, the manifest states that
fact. A provider model-name change, silent alias migration, or pricing change
during one formal run stops the run.

## 10. Outcomes

### 10.1 Primary quality outcomes

- strict pass under the frozen mode-independent acceptance rule;
- final evidence-group recall;
- milestone accuracy;
- numeric grounding accuracy;
- evaluated and errored attempt counts.

### 10.2 Primary efficiency outcomes

- end-to-end wall-clock latency;
- provider-total tokens;
- prompt, cache-read, and completion tokens;
- estimated cost under the frozen price table.

### 10.3 Mechanism outcomes

- retrieval recall and precision;
- evidence-compression ratio;
- specialist-summary retention;
- synthesis retention;
- delegation precision and recall;
- number and values of grounding violations;
- coordinator and specialist model-service times;
- batch trace validity and contribution attribution.

Specialist model-service times are additive telemetry across parallel calls and
are not interpreted as wall-clock duration.

### 10.4 Human semantic audit

Numeric corpus membership is not semantic entailment. Before execution, select
the medium point-in-time and large longitudinal configuration for each company.
For repetition 1 of `solo_staged` and `team_shared_retrieval`, two human reviewers
independently label up to ten material numeric claims per output as supported,
derived under a declared formula, unsupported, or not assessable. Report raw
agreement and Cohen's kappa together with disagreements. This secondary audit
does not replace the frozen deterministic grader and is not used to alter model
pass/fail outcomes after inspection.

## 11. Acceptance rules

The following are engineering acceptance thresholds, not statistical
equivalence margins:

- minimum numeric grounding accuracy: 95%;
- minimum retrieval recall where retrieval is evaluated: 75%;
- minimum final evidence recall: 90%, with the observed distribution also
  reported rather than reduced to pass/fail;
- minimum specialist-summary retention: 75% where summaries are evaluated;
- zero unreported baseline infrastructure errors;
- valid delegation precision and recall of 100% for cases whose contract
  requires all three specialists;
- no source-hash mismatch or grader-version mismatch.

For the system-level Stage 2 conclusion, shared-retrieval Team is considered a
practically useful alternative only if:

1. its configuration-level strict-success difference versus staged Solo is not
   negative by more than one configuration in the 24-configuration matrix;
2. median paired final evidence recall is no lower than staged Solo;
3. median paired wall-clock latency is at least 20% lower than staged Solo; and
4. median paired tokens or cost are at least 20% lower than raw-context Team.

Failure to meet these engineering thresholds is reported directly; thresholds
must not be changed after execution to rescue a preferred conclusion.

A configuration-level strict outcome is defined before analysis as passing at
least two of three evaluated repetitions. A configuration is unavailable for
this rule if fewer than three repetitions are evaluated because of
infrastructure errors. Attempt-level counts remain visible and are not replaced
by the majority outcome.

## 12. Statistical analysis

### 12.1 Pairing

The canonical pair key is:

`company | task_family | corpus_load | repetition | mode`.

All mode differences are computed within the same company, task, load, and
repetition. Errored attempts are not converted into model failures. A dependent
effect is unavailable when either paired mode is unevaluated.

### 12.2 Dependence

The primary resampling cluster is `company | task_family`. Loads and repetitions
remain nested within that cluster. Report:

- raw paired configuration tables;
- median paired differences and percentile distribution;
- company–task cluster-bootstrap 95% intervals;
- load-stratified paired differences;
- Team-only and Solo-only strict outcomes.

With eight Stage 2A clusters, intervals are descriptive and no claim of general
superiority or non-inferiority is made. Stage 2B increases the cluster count to
16 but remains an issuer-panel study rather than a market-wide estimate.

### 12.3 Multiple outcomes

Strict pass, final evidence recall, grounding, latency, tokens, and cost are all
reported. No single post hoc composite score is constructed. Quality is treated
as a constraint and efficiency as a conditional comparison. A cheaper mode is
not preferred when it fails the prespecified quality floor.

## 13. Failure taxonomy

Every unsuccessful or errored attempt receives one primary classification:

1. source or suite integrity;
2. retrieval omission or contamination;
3. deterministic calculation;
4. specialist empty, malformed, timeout, or provider error;
5. delegation or trace attribution;
6. coordinator synthesis or evidence loss;
7. policy or bounded-decision violation;
8. grader disagreement;
9. authentication, transport, rate limit, or other infrastructure error.

Secondary contributing causes may be recorded, but the primary layer prevents
all failures from being collapsed into “model error.”

## 14. Stopping and invalidation rules

Pause the run immediately when any of the following occurs:

- suite, source-lock, grader, prompt, agent identity, or pricing hash changes;
- a source audit fails or a gold calculation is corrected;
- baseline infrastructure errors exceed 5% of attempted observations;
- HTTP 429 or provider-unavailable responses exceed 10% in any rolling twenty
  mode attempts;
- trace JSON cannot preserve batch target and contribution identity;
- cumulative estimated cost exceeds USD 10 without explicit reauthorization;
- elapsed serial runtime exceeds twelve hours without a checkpoint review.

After a pause, provider instability may be resumed under the same frozen
protocol and with new repetition identifiers. A source, grader, prompt, or
treatment change creates a new study version and invalidates pooling with the
previous version.

## 15. Pilot-based resource estimate

The final medium-context NVDA Pilot consumed approximately USD 0.066 across all
five modes and about 7.15 minutes of serial end-to-end mode time. A direct
medium-case extrapolation for 24 cases and three full repetitions would be about
USD 4.77 and 8.6 serial hours. Stage 2A repeats only the three primary modes and
runs diagnostics once, giving a lower nominal estimate, but large corpora and
issuer-specific output lengths can increase both quantities. The formal budget
is therefore capped at USD 10 and twelve serial hours before review. This is a
planning estimate, not a guaranteed provider bill.

## 16. Required implementation gates

No formal Stage 2 request may be sent until all gates pass:

1. add seeded within-block mode randomization and record realized order;
2. derive a Stage 2 suite version with 90% minimum final evidence recall, a new
   suite hash, and unchanged locked source records; retain the Pilot suite as an
   immutable historical artifact;
3. add a distinct all-Pro Team mode or role override for the capacity-matched
   ablation;
4. emit stable company–task cluster and pair identifiers in JSON reports;
5. emit a consolidated primary-mode table with errored denominators;
6. preserve source, suite, grader, prompt/agent, model, pricing, and executable
   environment hashes in a secret-free manifest;
7. add an analysis command that consumes only retained JSON and performs paired
   cluster-aware summaries without new model calls;
8. test that calibration files and superseded observations cannot enter the
   confirmatory input set by filename pattern or manifest status.

## 17. Artifact contract

The formal run directory must contain:

- frozen suite and source-lock files or their content-addressed references;
- secret-free execution manifest;
- raw JSON report for every batch;
- merged pair table in CSV or JSON;
- aggregate mode and load tables;
- cluster-bootstrap output and analysis configuration;
- failure-classification table;
- source and oracle audit records;
- human-readable result summary;
- explicit list of exclusions, pauses, reruns, and protocol deviations.

Recommended naming:

`YYYY-MM-DD-stage2a-<batch>-<seed>-<status>.<ext>`.

Calibration, pilot, invalidated, and formal artifacts must use different status
labels and must never be pooled automatically.

## 18. Freeze checklist

- [x] All 24 Stage 2A configurations regenerate without diff.
- [x] Every local source hash matches the source lock.
- [ ] Two-pass source and oracle audits are complete.
- [x] Stage 2 suite uses the preregistered 90% final evidence-recall threshold.
- [ ] Primary and diagnostic modes are final.
- [x] Model names, thinking mode, output limits, and pricing are recorded.
- [x] Seeded mode randomization is implemented and tested.
- [x] Pair and cluster identifiers are emitted and tested.
- [x] Grader and trace tests pass.
- [x] Full Go and finance Python test suites pass.
- [ ] Budget and stopping rules are accepted.
- [ ] Output directory is empty of calibration artifacts.
- [ ] Protocol status is changed from draft to frozen before the first request.

## 19. Thesis reporting rule

The thesis must report Stage 2 even if the Team effect is zero, negative, or
cost-inefficient. The primary conclusion is selected from the frozen outcomes:

- quality improvement;
- quality preservation with efficiency improvement;
- efficiency improvement with unacceptable quality loss;
- no material difference;
- or indeterminate because of infrastructure or measurement failure.

The wording “multi-agent improves accuracy” is permitted only if the frozen,
paired quality analysis supports it. Otherwise the result is reported as a
context-allocation, reliability, or efficiency finding with its model-allocation
and sample limitations.
