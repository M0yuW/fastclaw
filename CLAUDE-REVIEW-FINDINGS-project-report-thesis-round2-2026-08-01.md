# FastClaw Project Report — Thesis Round-2 Independent Review

Reviewer role: anonymous thesis examiner (CS/SE), with distributed-systems, LLM-agent-runtime, LLM-evaluation/statistics, multi-tenant-security and fintech-evidence-governance hats.
Date: 2026-08-01. Round: 2 (independent re-audit, not a continuation of Round 1).
Scope of action taken: **review only.** No source, paper, artifact, DOCX/PDF or Git state was modified. No Gateway started, no model called, no paid API used. `runtime-benchmark-tenant.json` was never read.

Artifacts under review (hashes recomputed by me this round):

| File | SHA-256 | mtime |
|---|---|---|
| `project-report/fastclaw_project_report.md` | `ee8629107d560d10b7aeeaf7a37f9be52ea7f900044adfd93b36bf62a821647d` | 18:04:13 |
| `project-report/FastClaw_Project_Report_Zheyu_Wang.docx` | `df43934e37ff390bc1ee7759ef40b25592235fba3501568a71f76b7a9ec326bf` | 18:05:13 |
| `project-report/FastClaw_Project_Report_Zheyu_Wang.pdf` | `6c5c819c1c8adb164128797a4b3227be66faf8e3ade53bad489b634c7fc90daa` | 18:05:21 |
| `project-report/page_map.json` | — | 18:05:12 |
| `project-report/finance_reanalysis.json` | `94711e99ea39ba018c770fa01c2b14f5fc1062c1e84d7dc48d0b95adf0b0cbda` | **20:00:41** |
| `finance-runtime-formal-r5.json` | `5366a91398ca575d303af56d62da179f2a3f1fb13a1d0f5aae5c1773debfbc00` | — |
| `evals/multiagent-finance-runtime.yaml` | `4fbf54eca61dc7363342ea1db364cb84426e1541937a99c1e1266dbfb3e5dc44` | — |

Report measured this round: 976 markdown lines, 17,519 words, 14 `#` chapters, 59 `##` sections, 18 tables, 4 figures, 12 abbreviations, 17 references, 42 PDF pages.

---

## 1. Overall Verdict

**Classification: a competent, defensible undergraduate thesis (本科论文合格并偏优), at the lower boundary of a taught-master's project thesis.** It is clearly above "普通项目报告" and above "优秀毕业设计" in argumentative discipline; it is not yet a taught-master's-level thesis because the empirical core resolves to one undetermined research question at n=6, and the strongest chapter (evaluation methodology) is stronger than the strongest evidence.

| Dimension | Score /10 | One-line basis |
|---|---:|---|
| Academic rigor | 8.0 | Claims are consistently bounded; the negative result is stated as a negative result. |
| Technical depth | 7.0 | Concurrency, bus and grader arguments are genuine; provider, persistence and plugin layers stay descriptive. |
| Methodology | 8.5 | Four evidence-matched modes, a power bound, and a zero-cost grader ablation are the report's real contribution. |
| Statistical validity | 8.0 | Every number I recomputed matched; the residual issue is interpretive framing, not arithmetic. |
| Reproducibility | 7.0 | Manifest, SHA pinning and a two-pass build gate are real; the dirty snapshot and untracked artifacts cap it. |
| Security reasoning | 6.5 | Threat model exists and the ACL fix is real and tested; several disclosed-in-code gaps are absent from the paper. |
| Writing | 7.5 | Disciplined and readable; some mechanism sentences overstate, and the introduction is thin. |
| Citation quality | 7.0 | 17 verifiable primary sources, but one live IEEE-ordering violation and two decorative uses. |
| Visual quality | 6.5 | Real TOC/LoF/LoT/abbreviations with every page number verified correct, plus a stability-gated build; but zero numbered table cross-references, four captions with no lead-in, a literal-backtick rendering defect on PDF p12, a chapter-only TOC, and a shipped PDF of 43 pages against a page map that says 42. |

**Core judgment (≤250 words).** This is a different document from the one Round 1 audited — 754→976 lines, ~11.9k→17.5k words, ~20→42 pages — and the Round-1 P0 set is genuinely closed, not merely claimed closed. I independently reproduced every headline r5 number from the raw artifact (5/5/5/4; 6,557/23,910/13,955/5,062 billable tokens; 9,885/30,822/41,219/8,902 provider totals; −41.6%/+33.7% sign reversal; 2.13×/4.17×; +51.3%/−53.2% cost; 94.4% milestone, 97.2% coordination, 44 grounding assertions, 0 violations, `faults_expected=0`), re-derived all pooled counts (18/15/16/18), all Wilson bounds, all three exact paired p-values (0.5078125, 0.7265625, 1.0), the full seven-row ablation table, the Serenity 24-ok/2-mismatch manifest result, and the 17 finance tools. All matched. The manifest's four SHA-256 values re-verify byte-exactly. **未发现新的 P0 in the thesis's numbers or scientific claims.** The two P0s I do raise are documentation-integrity defects, not measurement errors: `artifact.md` still specifies the superseded 20-page build with wrong margins, wrong usable width, wrong type sizes and stale artifact hashes; and hypotheses H1–H5 are declared and never resolved anywhere, with no "not tested" marker, which contradicts resolution item P1-10. Everything else is P1/P2: zero numbered table cross-references, four captions with no lead-in sentence, a literal-backtick rendering defect on PDF p12, undisclosed empty state/communication/policy/tool-trace grader families, and coverage inflated ≈1.2 pp by counting the thesis's own analysis program. The paper's honesty is its strongest feature; do not weaken it to look stronger.

---

## 2. Previous-Review Closure Audit

| Old ID | Author status | My re-verification | Evidence | Regression? | Residual risk |
|---|---|---|---|---|---|
| **P0-01** r5 failure misattributed to window distance | DONE | **CLOSED, and independently corroborated.** Report L660 now attributes the failure to inflectional morphology (`estimated` ↛ `estimate`), and the ablation row `without_bounded_clause_gap` is 20/21/23/22 — identical to `current` — proving the token-gap guard changed nothing on these artifacts. | `finance_reanalysis.json` ablation; report L660, L706 | No | None. This is the single best-evidenced fix in the batch. |
| **P0-03** n=6 framed as equality | DONE | **CLOSED.** Abstract, L544, L861 all state "undetected difference, not equivalence" and give the 2/2⁶=0.03125 bound. I re-derived it. `grep` finds no "equivalent"/"no advantage" claim about Team. | Report L7, L544, L861 | No | The word "equivalence" survives only in the negation. Acceptable. |
| **P0-05** r2–r5 information unused | DONE | **CLOSED.** Pooled table (L670), paired discordant text (L676), per-case 4-run matrix (L682), Wilson intervals — all recomputed and all match to the digit. | `finance_reanalysis.json`; report L668–690 | No | Pooling is post hoc and *is* labelled post hoc twice (L668, L538). Correctly bounded. |
| **P0-07** coverage claim exceeded evidence | DONE | **CLOSED with a residual defect.** 28.4% is reproducible; the zero-coverage package list is accurate (I confirmed `policy`, `scope`, `session`, `plugin`, `mcp`, `skills` have **zero `_test.go` files**). But the profile includes `project-report/analysis` (75.8%), i.e. the thesis's own measurement instrument, inflating the figure ≈1.2 pp (27.20% excluding it). Also the scanner-as-heuristic downgrade is present at L792. | `go test ./... -coverprofile`; `ls internal/*/ *_test.go` | No | See P1-05 below. |
| **P0-10** token accounting misleading | DONE | **CLOSED, exemplary.** Billable-like is presented first, provider total second, and the sign reversal is elevated to a methodological finding (L642, L764). Both series recompute exactly. | r5 usage records; report L640–642 | No | One live gap: `cache_creation` is identically 0 across all 112 usage records, so the published formula's `Tcache-write × Pcache-write` term is never exercised (P2-04). |
| **P0-14** OpenAI-compatible ACL bypass | DONE | **CLOSED, and I traced the real path, not a fixture.** `internal/api/server.go:71` wires `authMiddleware → rateLimitMiddleware → HandleChatCompletions`; the handler resolves the agent at `openai.go:104` and *then* enforces `ident.CanAccessAgent(ag.Name())` at `openai.go:118` → 403. Unknown explicit id returns 404 at `:106` without falling back. Four-case table test at `openai_integration_test.go:385` covers omitted/inaccessible/unknown/permitted. | `server.go:71`, `openai.go:104-122`, test `:385-441` | No | `auth.go:92` still returns `true` unconditionally for the **session** path ("check happens in the handler"). The chat handler is now safe; this remains a per-route obligation the paper acknowledges at L812. |
| **P0-16** dirty source snapshot | DISCLOSED | **CORRECTLY DISCLOSED, not papered over.** Manifest `source_snapshot.status = "dirty_working_tree"`, HEAD `351ee42…`, Go `go1.26.4 darwin/arm64`, two critical file hashes — I re-verified both (`multiagent.go` `0d0f4ccd…`, `tenant.go` `7db4341c…`) byte-exactly. Report L630 and Appendix C L940 both state outputs can be regraded but trajectories cannot be regenerated. | manifest; `shasum` | No | Correct and honest. No further action possible without a rerun. |
| **P1-04** cross-root cycle detection unargued | DONE | **CLOSED, and the code matches the argument.** L225 gives the exact two-root counterexample (R1: A→B, R2: B→A, neither call path repeats a target); `bus/internal.go:101` calls `waitPathExistsLocked(targetLane, sourceLane)` under `internalMu`, implemented as a seen-set DFS at `:195-213`. L227 states the acyclicity invariant, the under-mutex cost, and three alternatives. | `internal/bus/internal.go:78-108, 195-213`; report L225-227 | No | The DFS is genuinely under the lock as stated. Claim and code agree. |
| **P1-08** no grader ablation | DONE | **CLOSED, and this is the paper's most valuable addition.** Seven configurations × four modes recompute exactly. `with_extended_inflections` raises Team 23→27 and Open-Book 20→25 while dropping the routed diagnostic 22→21 — a genuine direction-changing sensitivity result, obtained with zero model calls. | `finance_reanalysis.json`; report L696-706 | No | `analysis/main.go` imports `internal/eval` only for **mode-name constants, `LoadMultiAgentSuite` and `Report` decoding**; the matcher (`containsRequiredAssertion`, `normalizeWord`, `wordsAppearInOrder`, …) is re-implemented locally. So it is a genuine second implementation, not a call into the graded code — but a *transcribed* one, so shared-misconception risk remains (P1-06). |
| **P2-04** missing TOC/LoF/LoT/abbreviations | DONE | **PARTIALLY CLOSED.** All four exist (PDF p2/p3/p3/p4) and every page number I sampled matches `page_map.json` and the real PDF. But the TOC lists only the 14 `#` chapters — `build_report.py:913` filters `startswith("# ")`, so all **59 `##` subsections are absent**. For a 42-page thesis this is a navigability defect. | PDF p2-p4; `build_report.py:913`; `page_map.json` | No | See P2-01. |
| **P2-09** build depended on local environment | DONE | **CLOSED, and better than required.** `build_artifacts.sh` is a genuine two-pass build ending in `cmp "$PAGE_MAP_PATH" "$FINAL_PAGE_MAP_PATH"` — a real page-map stability gate — with `CODEX_PRIMARY_RUNTIME`, `PYTHON_BIN`, `PYTHON_PACKAGES`, `DOCUMENT_SKILL_ROOT`/`DOCX_RENDERER` all overridable. | `build_artifacts.sh` (51 lines) | No | `extract_page_map.py` hard-codes `pages[4:]`, `range(1,5)` figures, `range(1,19)` tables — the gate silently mis-slices if counts change (P2-05). |

Additional Round-1 items spot-checked and confirmed closed: P0-02 (two failures from one rubric value, 2/3 milestones, 0.8333 coordination — all present at L660 and all recomputed), P0-06 (the single `may`-hedge exemption; I located the exact sentence in the r5 trace — `contradictory-primary-evidence`/`team`: "the filing **may** carry higher evidentiary weight"), P0-08/P0-09 (L867 and Appendix C both state zero finance-tool calls and verbatim-copy fixtures; manifest records `financial_tool_calls: 0`, `spawn_subagent_tool_calls: 18` — I found exactly one tool name in the entire artifact, `spawn_subagent`), P0-11 (`faults_expected: 0` disclosed at L656 and L718 as vacuous), P0-13 (L442 states the guard checks counts not identifiers, and that pairing is manual), P0-15/P0-17 (manifest complete; suite pinned in `multiagent_test.go`), P1-11 (no "upper bound" phrasing survives; "routed-synthesis diagnostic candidate" at L440), P1-12 (24-ok/2-mismatch reproduced under my own verifier).

**Regression count across the whole closure audit: zero.** No Round-1 fix introduced a new numerical, statistical or code-factual error that I could find.

---

## 3. New Findings by Severity

### P0 — Blocking

**P0-R2-01. `project-report/artifact.md` still specifies the superseded 20-page build.**
- Location: `project-report/artifact.md` (110 lines, mtime 05:52 — 12 hours *before* the report at 18:04). Named as a required fact source at review-prompt L52.
- Evidence, five contradictions against the shipped build:
  - "Margins: 0.60 in left/right, 0.75 in top/bottom" vs `build_report.py:531-534` → top 0.82, bottom 0.78, left 0.85, right 0.85.
  - "explicit widths within the 7.30-inch usable page width" vs `BODY_WIDTH_INCHES = 6.80` (`build_report.py:52`); 8.5 − 0.85 − 0.85 = 6.80.
  - "Title: centered, 24 pt" vs `size=22` (`build_report.py:559`, `:649`).
  - "Level-1 section headings: centered, 10 pt, bold" vs `("Heading 1", 13, True, False)` (`build_report.py:561`).
  - "DOCX … 20 rendered pages, SHA-256 `c42d1403…`; PDF … 20 US Letter pages, SHA-256 `98f8f5ad…`" vs actual **42 pages**, DOCX `df43934e…`, PDF `6c5c819c…`.
  - It also names `runtime-pilot.json` and `runtime-pilot-optimized-v2.json` as authoritative historical evidence; both are excluded by `.gitignore:76:/runtime-*.json`.
- Impact: an examiner following the prompt's own reading list is handed a specification that disagrees with the submitted PDF on page count, geometry, type size and file identity. Every hash in it is falsifiable in one command. This is the single most damaging integrity defect in the submission because it *invites* the accusation that the artifacts are not the ones described.
- Fix: regenerate `artifact.md` from the shipped build (or delete it and let the manifest + Appendix B be the only contract). If retained, it must be produced by the build script, not hand-maintained.
- Verification: `shasum -a 256` on both artifacts equals the values in `artifact.md`; `pdfinfo`/pypdf page count equals the stated count; the four typography values equal the `build_report.py` constants.
- Affects Abstract/Results/Conclusion: no. Affects submission integrity: yes.

**P0-R2-02. Hypotheses H1–H5 are declared and never resolved; no "not tested" marker exists anywhere.**
- Location: `fastclaw_project_report.md:406-410` (PDF p21). RQ mapping table L97-103 (PDF p8). RQ answers L712-720 (p31) and L859-867 (p37).
- Evidence: `grep` for `H1`–`H5` returns **only** the five defining lines. The RQ table has columns `RQ | Operational estimand | Primary evidence | Present status` — **no hypothesis column**. `grep "not tested"` over the whole document returns nothing. Resolution item P1-10 claims "增加映射表，未执行假设明确标 not tested"; the mapping table exists, the hypothesis linkage and the markers do not. Concretely: H1 (identity/policy/bounded delegation improves strict success) is never tested — no ablation was run, and L474's cumulative ablation table is explicitly labelled *proposed*; H3 (fault-aware coordination reduces unsupported claims) cannot be tested at `faults_expected=0`; H4 (deterministic finance controls achieve exact state invariants) is supported only by the ten Python tests, not by r5, which made zero finance-tool calls.
- Impact: a thesis that states hypotheses and never returns a verdict on them has a structural argument gap that a viva committee will find in under a minute ("你的 H1 结论是什么？"). Three of the five are *unfalsifiable with the present artifact*, which is a defensible position — but only if stated.
- Fix: add a `Hypothesis` column to Table I, or a short subsection in VII.G resolving each of H1–H5 as `supported / not supported / not tested`, with the reason for each `not tested` (no ablation executed; zero fault denominator; no r5 ledger mutation).
- Verification: every one of H1–H5 appears at least twice — once at definition, once at resolution; `grep -c "not tested"` ≥ 3.
- Affects Conclusion: yes — X currently answers RQ1–RQ5 but never H1–H5.

### P1 — Major

**P1-R2-01. Empty grader families (`state`, `communication`, `policy`, `tool_trace` = 0) are never disclosed, while three passages imply state-transition grading occurred.**
- Location: report L355 ("A fluent answer that … leaves the thesis active **fails the state-transition grader**"), L425 (τ-bench-style row credits "Multi-turn **state accuracy**, communication, and policy compliance"), L726 (minimum reporting table promises a per-case "**state-transition result**"), L432 (L434: "final success requires the configured state, communication, and policy components to pass").
- Evidence, from `finance-runtime-formal-r5.json` metrics: `state_graders = passed_state_graders = state_accuracy = 0`; `communication_graders = passed_communication_graders = communication_accuracy = 0`; `policy_graders = 0`; `tool_trace_graders = passed_tool_trace_graders = tool_trace_accuracy = 0`. The only graders that fired in r5 are the text/milestone/contribution/grounding families. Table XVI *does* contain the row "r5 'state' grader observes prose, not mutation" — so the author knows — but the count is never given, and L355's claim that an answer "fails the state-transition grader" is, for r5, false: no state grader existed to fail.
- Impact: the strongest-sounding governance claim in Chapter V rests on a grader family with denominator zero. This is the same defect class as the `faults_expected=0` disclosure, which the author handled correctly — so the inconsistency is one of coverage, not of understanding.
- Fix: in VII.E add one sentence: "r5 evaluated 44 grounding assertions and 18 milestones; `state_graders`, `communication_graders`, `policy_graders` and `tool_trace_graders` were all zero, so state, communication, policy and tool-trace accuracies are vacuous." Rewrite L355 to "fails the configured `decision` milestone assertion" and mark L425/L434 as describing harness capability, not r5 execution.
- Verification: `jq '.metrics | with_entries(select(.key|test("state|communication|policy|tool_trace")))' finance-runtime-formal-r5.json` values appear verbatim in the paper.

**P1-R2-02. `Table I`–`Table XVIII` have zero in-text cross-references.**
- Location: all 18 tables. Captions render as `Table {Roman}. {text}` (`build_report.py:792`) and appear in the List of Tables (`:928`), but `grep -oE "Table [IVX]+"` over the markdown returns **nothing**.
- Impact: on 42 pages with 18 tables, a reader cannot tell which paragraph a table supports. IEEE/thesis convention requires every float be referenced. Prose that says "the following table" breaks whenever pagination moves the table.
- Fix: insert explicit `Table N` references at the ~18 discussion points (Table I at L96, XI/XII in VII.E, XIII–XV in VII.F, XVI in VIII.F, XVII/XVIII in the appendices), and align style with the figure references.
- Verification: `grep -oE "Table [IVX]+" fastclaw_project_report.md | sort -u | wc -l` = 18.

**P1-R2-03. Four table captions with no introducing sentence (caption directly under a heading or a figure placeholder).**
- Location: L562 (under `## B. Historical Runtime Regression Sequence`), L696 (immediately after `[[FIGURE_4]]`), L776 (under `## F. Threats to Validity`), L919 (under `# APPENDIX C`).
- Scope, checked precisely: all 18 `TABLE_CAPTION:` lines **are** followed within two lines by their `|`-delimited table, so no caption is stranded from its table. The defect is that these four are *preceded* by a heading or a figure placeholder rather than by prose; the other 14 have a proper lead-in.
- Impact: Tables VIII, XV, XVI and XVIII appear before the reader is told what question they answer, and at L696 a table caption sits directly beneath a figure placeholder, where it reads as the figure's caption.
- Fix: one introducing sentence before each, containing the `Table N` reference required by P1-R2-02.
- Verification: no `TABLE_CAPTION:` line is preceded (ignoring blanks) by a `#`/`##` heading or a `[[FIGURE_` placeholder.

**P1-R2-04. Algorithm 1 step 6 renders literal backticks in the shipped PDF.**
- Location: source `fastclaw_project_report.md:187`; renderer `build_report.py:809-827` (`add_algorithm` ends with `run = paragraph.add_run(step)`); visible on **PDF p12**: `l exists, persist the assistant message, flush the session, emit \`done\`, and return.`
- Evidence: `add_algorithm` bypasses `add_inline_text` (`build_report.py:618`), the only function that consumes `INLINE_PATTERN` (`:615`). Step 6 is the only algorithm step containing inline code, so it is the only one affected.
- Impact: a raw markdown artefact on the page that presents the thesis's central state machine.
- Fix: route algorithm steps through `add_inline_text`.
- Verification: rebuild; `pypdf` text for p12 contains `emit done` with no backtick; `grep -c '`' ` on extracted p12 text = 0.

**P1-R2-05. The 28.4% coverage figure includes the thesis's own analysis program.**
- Location: report L558 (p26) and L859 (p37).
- Evidence: my profile gives all-packages 4292/15123 = 28.38%; excluding `project-report/analysis` (75.8% covered, 745 lines) gives 4013/14755 = **27.20%**. The measurement instrument is counted inside the measured system, inflating the headline ≈1.2 pp.
- Impact: small in magnitude, but it is a self-measurement error inside the one number the paper uses to bound its own correctness claim — precisely the kind of thing this thesis elsewhere catches.
- Fix: report "27.2% for the runtime packages (28.4% including the report's own analysis program)".
- Verification: `go test ./... -coverprofile` then recompute with and without the `project-report/analysis` rows.

**P1-R2-06. `analysis/main.go` is a transcription of the graded matcher, not an independent reimplementation.**
- Location: `project-report/analysis/main.go` (745 lines); tests `main_test.go` (61 lines, 2 tests).
- Evidence: it imports `internal/eval` only for the four mode constants, `LoadMultiAgentSuite` and `Report` decoding; the matcher is local (`containsRequiredAssertion:493`, `containsForbiddenAssertion:524`, `wordsAppearInOrder:588`, `normalizeWord:715`, `maxAssertionTokenGap = 8` at `:15`). So it *is* a second code path — but the same rules, thresholds and hedge set, evidently transcribed from the graded implementation. Its two tests assert agreement with the audited counts and quantify stored drift; neither is a differential test against `internal/eval`.
- Impact: the paper's replay argument is stronger than "the same code was run twice" but weaker than "two independent implementations agree". A shared misconception (e.g. the `-ed` morphology gap, which both share) would be invisible.
- Fix: state the relationship explicitly in VI.J — "a transcribed second implementation sharing the rule definitions, which detects transcription and plumbing errors but not shared rule misconceptions" — and add one differential test comparing per-assertion verdicts between `internal/eval` and `analysis` over the retained outputs.
- Verification: a new test in `analysis/main_test.go` that fails when the two implementations disagree on any of the 44 assertions.

**P1-R2-07. Provider-mechanism overstatements at L154 and L158.**
- L154: "the OpenAI-compatible path retains **the complete assistant payload** in `RawAssistant`". It does not — `openai.go:384-386` *reconstructs* it: `rawMsg := apiMessage{Role:"assistant", ToolCalls: result.ToolCalls}; rawMsg.Content, _ = json.Marshal(result.Content); result.RawAssistant, _ = json.Marshal(rawMsg)`. Fields outside `{role, content, tool_calls}` are dropped. The package doc comments (`provider.go:29-31`, `:123`) make the same overstatement ("exact assistant message JSON as returned by the API"), so the paper faithfully reproduces a source-comment error. Because `openai.go:69-72` substitutes `RawAssistant` for the entire wire message with no provider discriminator, an Anthropic-persisted session replayed through the OpenAI path is a real (undisclosed) hazard — the report's own L154 warning that "callers cannot assume one cross-provider raw-payload contract" is directionally right but understates it.
- L158: names four event types (`content_delta`, `content`, `error`, `done`). `grep -o 'emit("[a-z_]*"' internal/agent/events.go | sort -u` gives **six**: `content`, `content_delta`, `done`, `error`, `tool_call`, `tool_result`. Omitting the two tool events understates the observability the thesis claims as a contribution.
- Fix: "reconstructs a `{role, content, tool_calls}` assistant message" and "six event types, of which four are terminal-state relevant".
- Verification: `grep -o 'emit("[a-z_]*"' internal/agent/events.go | sort -u | wc -l` = 6; the L154 sentence quotes the three reconstructed fields.

**P1-R2-08. Only one of three unreachable tool registrations is disclosed.**
- Location: report L828 discloses `load_skill` only.
- Evidence: `RegisterCronTools` (`internal/agent/tools/cron.go:25`) and `RegisterSkillInstall` (`skill_install.go:23`) are likewise never called from a production path, exactly like `RegisterLoadSkill` (`load_skill.go:16`).
- Impact: the paper earns credit for one honest disclosure while two identical cases remain unstated. An examiner who greps for one will find the others.
- Fix: extend L828 to "three registration helpers exist without production call sites: `load_skill`, cron tools, and Skill installation".
- Verification: for each of the three symbols, `grep -rn --include='*.go'` shows definition + tests only.

**P1-R2-09. PostgreSQL is called "the production target" with 14 dialect branches and zero dialect tests.**
- Location: report L168; code `internal/store/factory.go:13` ("Postgres is the production target"), `database.go` branches at `:196, :346, :368, :391, :431, :586, :944, :1037, :1132, :1238, :1366, :1397, :1416`.
- Evidence: `grep -rn --include='*_test.go' -i postgres internal/store/` → **0 matches**. Every branch is exercised only on the SQLite side.
- Impact: the persistence chapter's portability claim has no executed evidence. The paper's own standard (Table XVI, VII.A) is that untested paths get bounded language.
- Fix: "PostgreSQL is the intended production target; its dialect branches are unexercised in the current test suite" and add it to Table XVI as a construct/external threat.
- Verification: either a `TestDialectPlaceholders`-style unit test over `ph()`/migration SQL, or the disclaimer sentence.

**P1-R2-10. A thin Introduction against an oversized application chapter.**
- Measured prose distribution (tables and captions excluded; prose total 14,582 words): I 491 (3.4%), II 1,448 (9.9%), III 1,492 (10.2%), **IV 1,215 (8.3%)**, **V 2,067 (14.2%)**, VI 2,028 (13.9%), VII 2,009 (13.8%), VIII 1,256 (8.6%), IX 1,007 (6.9%), X 706 (4.8%).
- Impact: two structural problems. (a) A 491-word Introduction cannot carry problem statement + gap + RQs + contributions + thesis outline for a 42-page thesis; the gap argument is effectively deferred to II. (b) Chapter IV is the declared core contribution (the runtime execution mechanism) yet is the *smallest* substantive chapter, 41% shorter than the application chapter — the opposite of the weight the abstract claims.
- Fix: move ~400 words of gap/contribution/outline material into I (source it from II, do not pad); move the six scenario narratives in V that restate Table IV into a tightened form, and reinvest in IV (see §6 for what is missing there). Net length should not grow.
- Verification: I ≥ 800 words with an explicit "Contributions" list and an outline paragraph; IV ≥ V in prose words.

**P1-R2-11. Reference [14] first appears at L798, after [15]–[17] at L542 — a live IEEE ordering violation.**
- Evidence, first-appearance order: [1]@27, [2]@45, [3]@45, [4]@47, [5]@53, [6]@53, [7]@53, [8]@61, [9]@61, [10]@70, [11]@70, [12]@111, [13]@111, **[15]@542, [16]@542, [17]@542, [14]@798**.
- Fix: renumber so NIST AI RMF becomes [17], or cite it earlier where risk-lifecycle framing is actually used.
- Verification: first-appearance line numbers are monotonically non-decreasing in reference number.

**P1-R2-12. Two decorative citations.**
- [14] NIST AI RMF at L798 introduces nine controls, none of which is derived from AI RMF functions (Govern/Map/Measure/Manage) — the citation adorns a list it did not generate. This was Round-1 D13 and is unresolved.
- [10] Rashkin et al. is bibliographically correct (I verified: ACL-IJCNLP 2021, pp. 704–718, DOI `10.18653/v1/2021.acl-long.58`) but is a *controllable-generation* paper used at L70 to ground the *definition* of "evidence attribution", and its DOI is omitted while sibling ACL entries [8]/[9] carry theirs.
- Fix: either map each control to an AI RMF function or drop [14] from that sentence; for attribution definitions cite an attribution/attributability paper (e.g. AIS-style work — **待核验**, I did not confirm a specific one this round) and add [10]'s DOI.
- Verification: every citation's cited claim is traceable to a specific section of the source.

### P2 — Minor

**P2-01. TOC omits all 59 `##` subsections** (`build_report.py:913` filters `startswith("# ")`). Fix: include level-2 headings with a second indent level; the two-pass page map already resolves their page numbers.

**P2-02. `Figure N` in prose vs `Fig. N` in captions.** Four in-text references (L121, L231, L251, L692) say "Figure"; the four captions (hard-coded at `build_report.py:992-995`) say "Fig.". Pick one — IEEE convention is `Fig.` in captions and `Fig.` in text.

**P2-03. Under-filled pages, and one blank page beyond the stated page count.** By non-empty-line count (`pdftotext -layout`, which I used for the second pass because `pypdf` is not importable in this machine's default interpreter): **p38 = 9 lines**, **p20 = 11**, p14 = 14, p4 = 16, p2 = 17, against 50 on the densest pages (p21, p23). p20 ends Chapter V's case table with three prose lines; p38 carries a single closing paragraph of Chapter X. Separately, the shipped PDF has **43 pages, of which p43 is completely empty**, while `page_map.json` records `"pages": 42` and the paper, Appendix C and the resolution document all say 42 — so the shipped page map was not extracted from the shipped PDF, or a trailing break was added afterwards. Fix: remove the stray trailing page break, adjust `keep_with_next`/table-split thresholds so p20's tail joins p19 and p38's paragraph joins p37, then rerun the two-pass build and assert `page_map["pages"] == len(reader.pages)`.

**P2-04. `cache_creation` is identically 0 across all 112 r5 usage records**, so the published cost formula's `Tcache-write × Pcache-write` term (L241, PDF p14) is never exercised; `cache_read` sums to 124,032. Fix: one clause noting the write term was unexercised in r5. Related: `CacheReadIncludedInPrompt` exists in exactly four places (`openai.go:326`, `provider.go:132`, `usage_trace.go:182`, `usage_trace_test.go:25`) and Anthropic never sets it (`anthropic.go:415-417`), so `estimateModelCallCost` would not subtract cache reads for Anthropic — worth one sentence since the paper presents cache-aware costing as a contribution.

**P2-05. `extract_page_map.py` hard-codes counts**: `pages[4:]`, `range(1,5)` figures, `range(1,19)` tables. The `cmp` gate in `build_artifacts.sh` compares two page maps produced by the *same* brittle extractor, so a count change mis-slices consistently and passes the gate. Fix: derive the ranges from the markdown.

**P2-06. Figure 4 label sizes are borderline for print.** `create_grader_ablation_figure` (`build_report.py:253-304`) draws with **PIL `ImageDraw`**, not matplotlib, at `_font(19)`/`_font(21)` on a 2400×1500 canvas inserted at 6.80 in — an effective ≈5.4 pt against 10 pt body text. Fix: raise to `_font(30)`+ or reduce the canvas. *(Correction to the Round-2 visual pass: the recommendation "increase matplotlib font sizes" is inapplicable — there is no matplotlib in this figure path.)*

**P2-07. Cost-formula typography** (L241 / PDF p14): rendered flat-monospace, `Tcache-read` reads as a subtraction and `10^6` as a literal caret. Fix: subscript the tokens/prices or switch to `T_cache_read` and `10⁶`.

**P2-08. Abbreviation table covers 12 of ~35 acronyms actually used.** Unlisted: AI, BCBS, CLI, DOI, DOCX, DSN, HTTP, ICLR, JSON, JSON-RPC, KPI, NIST, OWASP, PDF, PMLR, RMF, RPC, SHA, SQL, SSE(listed), SWE, TOC, USD, WAL(listed), XML, YAML. Fix: add the ones that appear ≥2 times outside references.

**P2-09. `finance_reanalysis.json` (20:00:41) postdates the DOCX/PDF build (18:05).** Figure 4 is drawn from this file at build time (`build_report.py:253-304`), so the shipped figure was rendered from an earlier copy. The prior idempotence check showed identical content, so this is not a correctness defect — but the artifacts are not *provably* downstream of the current inputs. Fix: rerun `build_artifacts.sh` once so mtimes and hashes order correctly, and record the reanalysis hash in Appendix C.

**P2-10. `HookRegistry` has no mutex** (`internal/agent/hooks.go:47-69`): `Register` and `Run` touch a bare `map[HookPoint][]HookFunc`. Registration is boot-time in current call paths, so it is latent, not live — but the paper's concurrency chapter should not claim uniform synchronization discipline.

**P2-11. Compaction summarization always fails** (`internal/agent/compaction.go:145`: `prov.Chat(nil, …)`). I verified empirically that `http.NewRequestWithContext(nil, …)` returns `net/http: nil Context`, and `openai.go:151` uses that constructor; `compaction.go:76-84` swallows the error (`slog.Warn("compression failed, using pruned messages")`) and silently degrades to pruning. `memory.go:281` and `skills_learner.go:144` pass real contexts, so this is compaction-only. Not a paper claim — L184 only says history is "optionally compacted" — but if the thesis wants to cite compaction as a runtime mechanism it currently describes an unreachable behavior. **Engineering finding, out of scope for the paper; listed so it is not lost.**

**P2-12. Untracked evidence base.** `evals/multiagent-finance-runtime.yaml`, `evals/finance-runtime-formal-r5.manifest.json`, `finance-runtime-formal-r5.json` and the whole of `project-report/` are untracked (`git status --porcelain`); `.gitignore:76:/runtime-*.json` excludes the historical `runtime-pilot*.json` files that Table VIII depends on; and the suite-pinning row in `internal/eval/multiagent_test.go` is an **uncommitted** edit. Accurate statement: committing that test without also committing the YAML would break a clean clone. Fix: commit suite, manifest, r5 artifact and `project-report/` together, and either commit the historical artifacts or mark Table VIII's inputs as unarchived.

**Corrections to the Round-2 visual pass, recorded so they are not propagated.**
1. The reported "missing space after the comma joining two inline display formulas" at source L457/L509 and PDF p22/p24 is a **false positive**. Extracted PDF text reads `Precision = |D ∩ E| / |D|, Recall = |D ∩ E| / |E|,` (p22) and `FaultObservation = |O| / |F|, FaultAttribution = |A| / |F|.` (p24) — the space is present in both the markdown and the PDF.
2. The Figure 4 remedy is PIL-side (`_font(19)`/`_font(21)`), not matplotlib — see P2-06.

---

## 4. Claim–Evidence Matrix

| # | Paper claim | Code evidence | Test evidence | Experiment artifact | Support level | Permitted wording | Forbidden wording |
|---|---|---|---|---|---|---|---|
| 1 | Runtime correctness: bounded turn state machine with terminal consistency, tool-call/result pairing, panic containment, cancellation | `agent/loop.go` (single `ChatStream` at `:696`, persistence `:747/:775`), `agent/context.go`, `agent/events.go` (6 events) | Package tests for cancellation, stream error, panic containment, duplicate call IDs; `go test ./... -count=1` passes; race tests for `agent`, `agent/tools`, `store` | — | **Functional feasibility of tested paths only.** 28.4% statement coverage (27.2% excl. the report's own analysis pkg); `policy`, `scope`, `session`, `plugin`, `mcp`, `skills` have **zero test files** | "focused tests execute these control paths"; "functional verification" | "verified correct"; "production-safe"; "proven"; "comprehensive coverage" |
| 2 | Orchestration benefit (RQ2) | `eval/multiagent.go` four-mode driver; `bus/internal.go` correlated delegation | Baseline-isolation and denominator tests in `internal/eval` | r5: Team 5/6, Open 5/6, Two-Pass 5/6, Routed 4/6; fair gain 0.0 pp; pooled r2–r5 18/15/16/18; p=0.5078/0.7266/1.0 | **Not determinable.** Two sensitivity axes move in opposite directions (pooling favours Team; extended inflections favours Team *and* Open more) | "not determinable at this suite resolution"; "undetected difference" | "Team equals Solo"; "orchestration improves financial analysis"; "no benefit"; "equivalent" |
| 3 | Efficiency (RQ3) | `agent/usage_trace.go:160-192` pricing + cache-aware cost | `usage_trace_test.go`; pricing coverage 54/54 = 1.0 in r5 | Billable 6,557/23,910/13,955/5,062; provider 9,885/30,822/41,219/8,902; cost 0.005510/0.017798/0.008335/0.004320; Team P50/P95 21.30/22.49 s | **Descriptive, one config, one repetition.** Sign reversal (−41.6% billable vs +33.7% provider) is real and correctly elevated to a finding | "descriptively, for one model pair and one pricing table"; "the direction depends on the token definition" | "Team is more efficient"; "cost-optimal"; any efficiency ranking without stating the token convention |
| 4 | Fault tolerance (RQ4) | Fault-injection instrumentation in `eval/multiagent.go`; simulated-only gate | Harness tests for fault observation/attribution and unsupported-claim rate | r5 `faults_expected = 0`, `faults_observed = 0`, all four fault rates 0, `graceful_degradation_rate = 0` | **Instrument contributed, not exercised.** Zero denominator | "the instrument exists and is untested by the primary run"; "vacuous zeros" | "robust under faults"; "graceful degradation demonstrated"; "zero fault rate" as a result |
| 5 | Financial workflow validity (RQ5) | `plugins/finance-tools/plugin.py` (17 tools verified at `tool_definitions():104`); `evaltenant/tenant.go` tenant-scoped ledger | 10 Python tests: typed discovery, arg validation, cache, completeness gate, trusted tenant ctx, thesis isolation + versioning, review persistence, watchlist filter, alert dedupe, user isolation | r5: **0 finance-tool calls**, only `spawn_subagent` (36 occurrences / 18 calls), 0 ledger mutations, evidence = compiled lookup with verbatim-copy instruction | **Split.** Deterministic state ⇒ Python tests only. Governance *wording* ⇒ r5 text graders only | "ten deterministic tests support ledger semantics; r5 supports governance wording under fixed evidence" | "validated end-to-end financial workflow"; "live retrieval"; "specialist research ability"; "ledger correctness demonstrated in r5" |
| 6 | Configured attribution accuracy 100% | `eval/multiagent.go` grounding checker; hedge set {may, might, could, possible, possibly} | Assertion-direction and negation tests | 44 assertions, 0 violations, **one hedge exemption** (`contradictory-primary-evidence`/team: "the filing **may** carry higher evidentiary weight") | **Lexical policy result only** | "configured attribution accuracy, including one disclosed hedge exemption" | "factual accuracy"; "grounding"; "entailment"; "no hallucination" |
| 7 | Security: tenant isolation, ACL, policy-filtered tools, sandbox without host fallback | `api/server.go:71` middleware chain; `api/openai.go:104-122`; `auth/auth.go:79-95`; `policy/defaults.go` five presets; `sandboxRequired` | 4-case ACL table test (`openai_integration_test.go:385`); auth integration test `:106` | — | **Implemented + tested for the chat ACL path.** `policy`, `scope`, sandbox and the injection scanner have **no dedicated tests**; session-path `CanAccessAgent` returns `true` and defers to handlers | "the corrected chat path is authorized after resolution and behaviourally tested"; "the injection scanner is an unvalidated heuristic" | "secure"; "least privilege enforced throughout"; "sandbox escape prevented" |
| 8 | Reproducibility | `build_artifacts.sh` two-pass + `cmp` page-map gate; `analysis/main.go` zero-model-call replay | `analysis/main_test.go` (2 tests: audited-count agreement, stored drift); suite pinning in `eval/multiagent_test.go:419` | Manifest 4/4 SHA-256 re-verify byte-exactly; suite `4fbf54ec…`, artifact `5366a913…`, `multiagent.go 0d0f4ccd…`, `tenant.go 7db4341c…` | **Analysis-level reproducible; execution-level not.** Dirty tree, unarchived patch, untracked artifacts | "outputs can be regraded and tables recomputed with zero model calls"; "provider trajectories cannot be regenerated from the recorded HEAD" | "fully reproducible"; "exact reproduction"; "clean commit" |
| 9 | Historical 0/8→4/8→8/8 improvement | — | — | `runtime-pilot*.json` (gitignored, unarchived) | **Descriptive association only**; runtime, evidence and grader changed together | "regression sequence consistent with…"; "does not identify a causal effect" | "the runtime caused"; "improved success by 100%"; any ablation-style attribution |

---

## 5. Independent Numerical Audit

All values below were recomputed by me this round from the raw artifacts (`finance-runtime-formal-r5.json`, `finance_reanalysis.json`), with no reliance on the paper's tables, the author's resolution document, or any background agent's report. Zero model calls were made.

| # | Quantity | Formula / input | My result | Paper value | Match |
|---:|---|---|---|---|---|
| 1a | r5 per-case outcomes | iterate `cases[*].attempts[*].baselines[]` (a **list** of `{mode, passed}`) | earnings-catalyst T/T/T/T; thesis-invalidation F/T/T/T; duplicate-event T/T/T/F; incomplete-screening T/T/**F**/T; portfolio-concentration T/**F**/T/F; contradictory-evidence T/T/T/T (order: open, two-pass, team, oracle) | — | — |
| 1b | r5 per-mode counts | column sums of 1a | Open 5/6, Two-Pass 5/6, **Team 5/6**, Routed 4/6 | 5/6, 5/6, 5/6, 4/6 | ✅ |
| 2 | r2–r5 pooled | `current_grader_pooled_r2_r5` | Team 18/24 (75.0%), Open 15/24 (62.5%), Two-Pass 16/24 (66.7%), Routed 18/24 (75.0%) | identical | ✅ |
| 3a | Team/Open discordant + exact p | b=6, c=3; two-sided = 2·Σ_{i≤3} C(9,i)/2⁹ | 9 discordant, +12.5 pp, **p = 0.5078125** | +12.5 pp, p=0.5078 | ✅ |
| 3b | Team/Two-Pass | b=5, c=3; n=8 | 8 discordant, +8.3333 pp, **p = 0.7265625** | +8.3 pp, p=0.7266 | ✅ |
| 3c | Team/Routed | b=3, c=3; n=6 | 6 discordant, 0.0 pp, **p = 1.0** | 0.0 pp, p=1.0000 | ✅ |
| 3d | Minimum attainable p at n=6 | 2/2⁶ | **0.03125** (attained only at 6–0) | 0.03125 | ✅ |
| 4 | Wilson 95% intervals | p̂=k/n, z=1.959964, (p̂ + z²/2n ± z√(p̂(1−p̂)/n + z²/4n²))/(1+z²/n) | 18/24 → [0.55101, 0.88001]; 15/24 → [0.42710, 0.78841]; 16/24 → [0.46706, 0.82028]; 5/6 → [0.43650, 0.96995]; 4/6 → [0.29999, 0.90323] | [55.1,88.0], [42.7,78.8], [46.7,82.0] | ✅ |
| 5a | Token totals per mode | sum `prompt`/`completion`/`cache_read` over usage records; billable = (prompt − cache_read) + completion | open 6 calls: p3803 c6082 cr3328 → **billable 6,557**, provider 9,885; two-pass 12 calls: p13874 c16948 cr6912 → **23,910** / 30,822; team 30 calls: p30222 c10997 cr27264 → **13,955** / 41,219; oracle 6 calls: p4064 c4838 cr3840 → **5,062** / 8,902 | 6,557 / 23,910 / 13,955 / 5,062 and 9,885 / 30,822 / 41,219 / 8,902 | ✅ |
| 5b | Team/Open ratios | 13955/6557; 41219/9885 | **2.128×** billable, **4.170×** provider | 2.13×, 4.17× | ✅ |
| 5c | Team/Two-Pass ratios | 13955/23910 − 1; 41219/30822 − 1 | **−41.635%** billable, **+33.732%** provider | −41.6%, +33.7% | ✅ |
| 5d | Cost deltas | 0.008335222 vs 0.005510029 vs 0.017798286 | Team vs Open **+51.27%**; Team vs Two-Pass **−53.17%** | +51.3%, −53.2% | ✅ |
| 6 | Why the token directions reverse | `total = prompt + completion` with `cache_read ⊆ prompt` by provider convention. Team has by far the largest `cache_read` (27,264 of 124,032 total) because 30 calls replay a shared coordinator prefix. Subtracting cache reads (billable-like) removes 27,264 from Team but only 6,912 from Two-Pass; leaving them in (provider total) credits Team with tokens it is not billed for at full rate. | **Confirmed mechanically.** Team billable 13,955 < Two-Pass 23,910, yet Team provider 41,219 > Two-Pass 30,822 | Report L642 gives exactly this explanation | ✅ |
| 7 | Grader ablation, 30 outputs/mode (order: Open, Two-Pass, Team, Routed) | `grader_ablation_r1_r5` | current 20/21/23/22; without_negation_scope 12/13/14/13; without_hedge_scope 20/21/22/22; without_conditional_scope 20/21/22/22; without_bounded_clause_gap 20/21/23/22; without_plural_morphology **19**/21/23/22; with_extended_inflections **25**/21/**27**/21 | identical, all 28 cells | ✅ |
| 8 | incomplete-screening aggregation | rubric value `not estimate \|\| instead of estimating` vs output "must not be imputed, inferred, or estimated"; `normalizeWord` folds plurals only, no `-ed` | 2/3 milestones, 2/3 contributions utilized, coordination = mean(F1=1.0, 2/3) = **0.8333**; global milestone KPI **17/18 = 94.4%**, contribution utilization **17/18 = 94.4%**, coordination **0.9722**, delegation P/R/F1 = 1.0, unexpected delegations 0, average delegations 3 | 2/3, 2/3, 0.8333, 94.4%, 94.4%, 97.2%, 100%/100% | ✅ |
| 9 | Forbidden-phrase hedge exemption | scan all baselines for `higher evidentiary weight` | **exactly one occurrence**, `contradictory-primary-evidence` / `team`: "…the filing **may** carry higher evidentiary weight — but this determination must be made by legal/compliance counsel…" Suppressed by the 5-token hedge lookback. Totals: 44 assertions, 0 violations, accuracy 1.0 for all four modes | one `may` exemption within 44/44 | ✅ |
| 10 | r5 fault denominator | `metrics.multi_agent_faults_expected` and siblings | `faults_expected 0`, `faults_observed 0`, `fault_injected_attempts 0`, `fault_injection_rate 0`, `fault_observation_rate 0`, `fault_attribution_rate 0`, `graceful_degradation_rate 0`, `unsupported_claims 0`, `unsupported_claim_rate 0` | "Faults expected 0 — vacuous" | ✅ |

Additional recomputations not required by the prompt but performed:

| Quantity | My result | Paper | Match |
|---|---|---|---|
| Coordinator vs specialist split | coordinator 22,236 provider tokens / USD 0.007059615; specialists 18,983 / USD 0.001275607 | 22,236 / 0.007060; 18,983 / 0.001276 | ✅ |
| Cost per successful Team outcome | 0.008335222 / 5 = **0.001667044** | USD 0.001667 | ✅ |
| Total r5 cost | **0.035963957** | — | — |
| Pricing coverage | 54/54 = **1.0** | "all 54 model calls were priced" | ✅ |
| Team P50/P95 | nearest-rank `index = int((n−1)q + 0.5)` (`runner.go:486-492`) → at n=6, P50 takes the 4th of 6 ordered values | **21.30 / 22.49 s**, and this is why P50 > the 19.45 s mean | L658 explains it as short cases pulling the mean down — correct in effect, but the *mechanism* is the nearest-rank index, which the paper does not state | ⚠ see P2 note |
| Gain validity flags | fair 0.0 (**valid True**), compute-matched 0.0 (**valid True**), legacy collaboration gain (**valid False**, `solo_evaluated = 0` — `solo_closed_book` absent from r5), oracle success rate 0.6667 | fair/compute-matched reported; legacy explicitly demoted at L442 | ✅ |
| `cache_creation` across 112 usage records | **sum = 0** (cache_read sum = 124,032) | not stated | ❌ see P2-04 |
| Empty grader families | `state_graders`, `passed_state_graders`, `state_accuracy`, `communication_graders`, `passed_communication_graders`, `communication_accuracy`, `policy_graders`, `tool_trace_graders`, `passed_tool_trace_graders`, `tool_trace_accuracy` = **all 0** | not stated | ❌ see P1-R2-01 |
| Serenity manifest | my own SHA-256 verifier over `skills/serenity-skill/SHA256.txt`: **ok 24, mismatch 2, missing 0**; mismatches `./README.md`, `./README.zh-CN.md` | L282: "24 successful checks and two failures for `README.md` and `README.zh-CN.md`" | ✅ |
| Finance tool count | `tool_definitions()` at `plugin.py:104` declares **17** | "seventeen typed tools" (abstract, L265) | ✅ |
| Statement coverage | all 4292/15123 = **28.38%**; excl. `project-report/analysis` 4013/14755 = **27.20%** | 28.4% | ⚠ see P1-R2-05 |

**Verdict on the numerical audit: every paper-reported number that I could recompute, recomputed exactly. No arithmetic or statistical error was found.** The three ⚠/❌ rows are omissions and framing, not miscalculations.

---

## 6. Technology Depth Audit

Scores are 0–5 for *thesis-level treatment* (mechanism + invariant + alternative + failure mode + test evidence), not for code quality.

**1. Agent turn state machine — 4/5.** Strengths: Algorithm 1 (L182-190) gives nine numbered steps; L192-198 explains why the turn gate exists (session-bound executor/workspace state in the registry) and that the identity snapshot is immutable for the turn; terminal-path normalization is stated. Missing principle: no formal state set/transition relation — the "state machine" is a numbered procedure, so no unreachable-state or terminal-completeness argument is possible; the iteration bound is mentioned but its interaction with duplicate-call rejection is not analysed. Alternatives not discussed: an explicit typed FSM, or an actor with an inbox. Trade-off unstated: the turn gate serializes an agent's turns, so per-agent throughput is 1 regardless of the root semaphore. Test gap: no test asserts "every terminal path flushes exactly once". Section: IV.A.

**2. MessageBus/TaskQueue scheduling — 4/5.** Strengths: per-chat FIFO with its own goroutine (`taskqueue/queue.go:78-92`), root counting semaphore (`:93`), and the semaphore-vs-worker-pool justification at L150 is a genuine design argument (head-of-line blocking between unrelated lanes). Missing: the **two independent 256 caps** (`bus/internal.go:16 maxInternalPending`, `taskqueue/queue.go:119 internalSlots`) are not related to each other in the text — a reader cannot tell which one a caller hits first, or what happens when they disagree. Alternatives: `errgroup.SetLimit`, `semaphore.Weighted`, work stealing — all named at L150. Failure mode unstated: chat-queue goroutine lifetime and what happens to queued items on shutdown. Test gap: no test drives both caps to saturation simultaneously. Section: III.C / IV.B.

**3. Cancellation and back-pressure — 4/5.** Strengths: `context.WithCancel(context.WithoutCancel(requestCtx))` plus two `context.AfterFunc` edges is a non-obvious pattern and the report explains why (detach the sub-agent from the HTTP request while keeping two explicit cancellation edges). Non-blocking publish returning `ErrInternalBackpressure` rather than blocking is stated (L227). Missing: the *observable consequence* of back-pressure for the caller — a coordinator receiving `ErrInternalBackpressure` mid-fan-out; and `emitEvent` is a blocking send, so a slow client back-pressures into the model loop, which the paper does not mention. Test gap: no test asserts that a stalled consumer cannot wedge a turn. Section: IV.B.

**4. Wait-graph cycle detection — 5/5.** The best-argued mechanism in the thesis. Claim (L225-227), counterexample (two roots, A→B and B→A, neither call path repeating a target), implementation (`waitPathExistsLocked`, `bus/internal.go:195-213`, seen-set DFS from source to target), invariant (the directed lane wait graph stays acyclic; one blocked internal request ⇒ one edge), cost (linear in the live graph, computed under `internalMu`), and three alternatives (static topology, global lock order, timeout-only recovery) with why each is worse. Code matches text exactly, including the under-lock claim. Only gap: edges are ref-counted (`internalWaits[source][target]++`, `removeInternal` decrements) — the multiplicity is not discussed, and cycle detection ignores counts, which is correct but worth one sentence. Section: IV.B (keep as is).

**5. Sub-agent dedup semantics — 3/5.** Strengths: the report distinguishes production from evaluation dedup and notes evaluation reuses duplicate results (L762). Missing: the actual key (which fields make two calls "the same"), and why reuse is sound in evaluation but not production — this is a *measurement-affecting* decision (it lowers Team's token count) and therefore deserves the same treatment the token-convention reversal received. Test gap: duplicate-identifier tests exist; a test pinning the eval-vs-production divergence is not cited. Section: VI.D, alongside the fairness argument.

**6. Provider streaming and tool-call protocol — 2/5.** Weakest substantive area relative to its importance. Strengths: the asymmetry between OpenAI and Anthropic raw payloads is acknowledged (L154), and the usage-option fallback is mentioned. Missing/incorrect: (a) `RawAssistant` is *reconstructed*, not retained (P1-R2-07) — and the reconstruction is substituted for the whole wire message at `openai.go:69-72` with no provider discriminator, a real cross-provider replay hazard the paper does not name; (b) six event types, not four (L158); (c) there is **no retry layer** anywhere in `internal/provider` — the only re-issue is the `stream_options.include_usage` fallback (`openai.go:246-263`, gated by `isUnsupportedStreamingUsageError` at `:265-291`: status 400/422 **and** a body mentioning `stream_options`/`include_usage` **and** an unsupported/unknown-field marker), executed inside `doChatRequest` before SSE parsing, so usage records stay 1:1 with iterations; (d) on a stream failure the usage record is written with **zero tokens**, because `loop.go:718-732` only assigns `modelUsage` when `resp != nil` and `:719-722` ignores `resp` when `resultErr != nil`, making the partial `result` from `openai.go:377-386` unreachable — i.e. failed streams are silently free in the cost ledger; (e) tool-call delta assembly drops non-contiguous indices and concatenates re-sent names. Test evidence: exactly one test file, `provider_stream_test.go` (261 lines), 38.4% package coverage. Section: IV.D needs the corrections and one paragraph on failure-mode accounting.

**7. Tenant authentication and authorization — 4/5.** Strengths: two credential types funnelling into one `Identity` (`auth/auth.go:11-51`), no anonymous fallback, `EffectiveUserID`/`ActAsUserID` read-only impersonation, and the ACL fix authorized **after** resolution with a four-case behavioural test. Missing: `CanAccessAgent` returns `true` unconditionally on the session path (`auth.go:92`) and defers to each handler — a design decision with a real failure mode (a handler that forgets), which the paper hints at (L812 "does not remove the need to audit each new route") but does not name as a structural property. Also unmentioned: `setup/handlers_skills.go:164-180` joins an unvalidated `r.PathValue("name")` into `filepath.Join(homePath,"skills",name)` before `os.RemoveAll` — no traversal validation. Section: IX.A.

**8. Policy-filtered tools and sandbox — 3/5.** Strengths: five presets with distinct tool counts (`policy/defaults.go`: permissive 6, restricted 20, standard 43, no-tools 67, delegate-only 81 — line anchors), registry copy-then-filter so the base registry is unmutated, and `sandboxRequired` with no silent host fallback. Missing: the **filtering algorithm and its default** (allow-list vs deny-list, and what an unknown tool resolves to) — the security argument depends on fail-closed behavior that is asserted rather than shown; and the two-fixed-mount limitation is stated (L164) without its consequence for team/extra Skill paths that enter the prompt without mounts. Test gap: `internal/policy` and `internal/sandbox` filtering have **no dedicated tests** (zero `_test.go` in `internal/policy`). Section: III.E + IX.A.

**9. Plugin/MCP/Skill architecture — 3/5.** Strengths: JSON-RPC 2.0 subprocess protocol with a correct primary citation [3]; the trusted `ToolCallContext` (`userId`/`agentId`/`sessionId` injected post-routing, not model-controlled) is exactly the right invariant to highlight and is genuinely enforced by the Python plugin's tests; full-Skill injection with `load_skill` unreachable is honestly disclosed. Missing: supply-chain reasoning for subprocess plugins (no signature, no pinned interpreter, `finskills` external and unvendored); the token cost of full-Skill injection is not quantified even though it directly affects the efficiency chapter; and two further unreachable registrations go unmentioned (P1-R2-08). Test gap: `internal/plugin`, `internal/mcp`, `internal/skills` all have **zero test files** — the Go side of the plugin protocol is untested; only the Python side is tested. Section: III.E + IX.

**10. SQLite WAL and transaction locking — 3/5.** Strengths: DSN normalization is described precisely and matches code (`database.go:67-85`: `journal_mode(WAL)`, `foreign_keys(1)`, `busy_timeout(5000)`, immediate transactions unless already present); the *reason* for immediate mode (read-then-write upgrade in session persistence, which a busy timeout alone cannot rescue) is a genuine database-systems argument; WAL sidecar backup semantics are correct. Missing: no transactional batch append for session messages and no cross-instance locking — mentioned as future work (L850 item 7) but their present consequence (a torn multi-message append under crash) is not analysed; PostgreSQL is called the production target with **zero dialect tests** (P1-R2-09). Test gap: `database_integration_test.go` exercises contention through the public Store API on SQLite only. Section: III.F.

**11. Session consistency and workspace isolation — 4/5.** Strengths: the store-backed **fail-open** behavior is stated with unusual precision (L170: on store error with an in-memory copy present, the read fails open to a potentially stale copy) and correctly contrasted with fail-closed identity loading; workspace namespacing by agent + optional session is justified by the concrete hazard (concurrent chats overwriting one output name). Missing: no bound on staleness, and no statement of what a client can observe (two consecutive requests seeing different histories). Test gap: `internal/session` has **zero test files**, so the normalization and fail-open paths named in the design argument are untested — the paper acknowledges the coverage gap generically but does not connect it to this specific mechanism. Section: III.F.

**12. Telemetry and cost attribution — 4/5.** Strengths: per-call role/call-path/token/latency/error retention, coordinator-vs-specialist split, the cache-aware `estimateModelCallCost` (`usage_trace.go:178-192`), and the billable-vs-provider convention elevated to a methodological finding. This is the mechanism most directly load-bearing for the paper's results and it is handled well. Missing: (a) unpriced calls contribute 0 indistinguishably from free calls, and `MAPricingCoverage` (`runner.go:361`) is reported but never thresholded — r5 happens to be 54/54, so the hazard is latent; (b) `CacheReadIncludedInPrompt` is set only on the OpenAI path (four occurrences repo-wide; `anthropic.go:415-417` sets tokens without the flag), so Anthropic costs would not subtract cache reads — an asymmetry in the very convention the paper elevates; (c) float64 cost summation is order-dependent; (d) the API trace drops `seq`/timestamps/agent ids. Section: IV.E + VI.C.

**13. Evaluation harness and grader design — 5/5.** The strongest chapter. Four evidence-matched modes with an explicit fairness argument (L436-442), `errored` excluded from the capability denominator but retained in the cost ledger, the guard's limitation disclosed (counts not pair identifiers) with manual pairing stated as the remedy, an explicit power bound, and a seven-configuration zero-model-call ablation that changes the direction of the conclusion. One genuine gap: **three distinct `Passed` definitions** coexist — baseline pass = all milestones ∧ zero grounding violations (`multiagent.go:615-616`); Team attempt pass additionally requires delegation/contribution/efficiency (`:538-547`); strict case success is a third — and they coincide at 5/6 in r5 *coincidentally*. The paper compares "5/6 vs 5/6" across modes whose pass predicates are not identical. This deserves one paragraph in VI.D, because a reader could reasonably think the comparison is like-for-like. Section: VI.D/VI.E.

**14. Fault injection and graceful degradation — 2/5.** Instrument described (timeout, explicit error, malformed output, contradictory evidence, multiple partial failure, non-critical failure; observation/attribution/degradation/unsupported-claim metrics; per-fault not per-phrase counting so the rate cannot exceed 100%) and correctly declared unexercised. But with `faults_expected = 0` the entire section is design documentation. The simulated-only gate is the right safety property and is stated. Score is low not because the treatment is poor but because there is **no evidence at all**. Section: VI.E — keep, and keep the "not exercised" label.

**15. Finance evidence governance and persistent state — 4/5.** Strengths: 17 typed tools (verified), the `finance.tool.v1` envelope's `as_of` vs `observed_at` distinction (the single most defensible domain idea in the thesis), integer-version optimistic concurrency with `expected_version`, immutable reviews, SHA-256 event fingerprints with a 24-hour dedupe window, and ten Python tests that genuinely cover isolation/versioning/dedupe. Missing: the envelope's completeness/staleness semantics are not tied to a decision rule (what the *coordinator* must do when `completeness = insufficient` is a governance rule stated in prose, not a typed contract); and the r5 disconnect (zero tool calls) means the entire deterministic layer is evidenced only by unit tests — correctly disclosed, but it means the "financial application" contribution is an *implemented and unit-tested* artifact rather than an *evaluated* one. Section: V + VIII.F.

**Aggregate depth: 3.6/5.** Concurrency and evaluation are thesis-grade. The provider layer and fault tolerance are the two areas where the paper's language currently exceeds its evidence, and the provider layer is the only one where I found factual errors.

---

## 7. Experimental Methodology Audit

### RQ → hypothesis → estimand → baseline → metric → artifact → conclusion

| RQ | Hypothesis | Estimand | Baseline / comparison | Metric | Artifact | Present conclusion | Gap |
|---|---|---|---|---|---|---|---|
| RQ1 runtime correctness | H1 (identity/policy/bounded delegation improve strict success) | Correct terminal state, scope, cancellation, bounded execution | none (no ablation executed) | test pass/fail; statement coverage | Go test suite; 28.4% profile | "partially supported; feasibility not proof" | **H1 is untested** — Table VII's cumulative ablation is labelled *proposed*. RQ1's estimand ("correct terminal state…") is not what the evidence measures ("tests of terminal state pass"). |
| RQ2 orchestration benefit | H2 (Team exceeds Open-Book only where routing adds value) | Paired Team − evidence-matched Solo success | `solo_open_book` (fair), `solo_two_pass` (compute-matched), `oracle_team` (diagnostic) | strict success; discordant pairs; exact two-sided p | r5 + pooled r2–r5 + 7-way ablation | "not determinable" | Correctly reasoned. H2 is *partially* addressed by the per-case matrix (Team 4/4 on invalidation, 3/4 on concentration, 0/4 on screening) but never stated as an H2 verdict. |
| RQ3 efficiency | H5 (unnecessary delegation raises cost without improving milestones) | Billable tokens, provider totals, latency, calls, cost | cross-mode | two token conventions; P50/P95; USD | r5 usage trace | "descriptively supported for one run" | H5 is *contradicted in direction* by r5 (Team costs 53.2% less than Two-Pass at equal pass count) yet never resolved. The oracle_team mode is the natural H5 test (fewest calls, lowest cost, **worst** outcome 4/6) and is not used for it. |
| RQ4 fault tolerance | H3 (fault-aware coordination reduces unsupported claims) | Safe output under observed/attributed faults | fault-injection suite vs none | observation, attribution, degradation, unsupported-claim rate | r5 with `faults_expected=0` | "instrument contributed; not exercised" | H3 **cannot** be tested by r5. Correctly disclosed at the RQ level; not marked at the hypothesis level. |
| RQ5 financial validity | H4 (deterministic controls achieve exact state invariants) | Evidence-attributed governance wording + deterministic ledger behavior | plugin tests vs r5 text graders | 10 Python tests; 44 grounding assertions; 18 milestones | plugin tests + r5 | "split; no r5 ledger mutation" | Best-handled split in the paper. H4's "exact state invariants" are evidenced by unit tests only; the r5 half evidences wording. Also: `state_graders = 0` undisclosed (P1-R2-01). |

### What the present experiments can and cannot answer

**Can answer.** (i) Whether the four-mode harness produces internally consistent, replayable, priced measurements under matched evidence visibility — yes, demonstrably. (ii) How sensitive a lexical-attribution conclusion is to grader design — quantitatively, with zero marginal cost: the `with_extended_inflections` switch alone moves Team 23→27 and Open 20→25 while moving Routed 22→21, i.e. it changes both level and ordering. (iii) The cost/latency profile of one coordinator+3-specialist configuration against two solo controls under two token conventions. (iv) That a morphology gap can systematically reverse a mode comparison (Team 0/4 on incomplete screening). These are real, publishable methodological results.

**Cannot answer.** (i) Whether orchestration improves financial analysis — n=6 with one repetition, and the two sensitivity axes point in opposite directions. (ii) Any causal share of individual runtime controls — no ablation was executed. (iii) Fault tolerance — zero denominator. (iv) Retrieval, specialist research ability, or ledger correctness under the real runtime — zero finance-tool calls, verbatim-copy fixtures. (v) Whether the lexical grader tracks human judgment — no human-labelled subset exists. (vi) Anything about investment performance — no point-in-time data, no returns, and the paper correctly refuses to speculate.

### Minimum defensible next experiment

The prompt asks for the *minimum* defensible next step, not the most impressive. In priority order:

1. **Human-adjudicated grader validation (cheapest, highest validity return, zero model calls).** Take the 44 grounding assertions and 18 milestones already in r5, have 2 annotators label each output-assertion pair for entailment, and report grader–human agreement (Cohen's κ) plus the confusion matrix. This directly attacks the paper's largest construct-validity threat and requires **no new model calls at all** — only retained outputs. If κ is low, every capability number in the thesis is reframed; if high, the lexical grader is defended empirically rather than rhetorically.
2. **Powered orchestration run.** Sample size should be derived, not asserted. For an exact paired (McNemar) test at two-sided α=0.05, power 0.80: if the true discordant-pair probability is p_d ≈ 0.30 with a 2:1 asymmetry (a large, optimistic effect), the required number of discordant pairs is ≈ 25, implying ≈ 84 paired observations. With 3 repetitions that is **28 cases** — which is why the paper's own "≥24 cases × 3 repetitions" (L724, L869) is the right order of magnitude and I endorse it, with the caveat that it is powered only for a *large* effect. For a modest effect (55:45 split among discordant pairs) the requirement exceeds 700 paired observations, which is out of reach — so the honest framing is "powered to detect a large orchestration effect; a modest effect remains undetectable", and the thesis should say so.
3. **Execute the fault suite** (`faults_expected > 0`) at 3 repetitions. This converts RQ4 from vacuous to answerable and is the only RQ that a single additional run can fully resolve.
4. **Retrieval-and-mutation integration track**: real finance-tool calls and real ledger mutations under the runtime, graded on post-state rather than prose. This is what would convert RQ5's "split" into a single answerable claim.
5. **Cumulative runtime ablation** (Table VII, currently proposed) — the only design that can isolate the runtime contribution the abstract foregrounds. Most expensive; do it last.

Not recommended next: more cases under the current grader. That increases n against an instrument whose validity is unmeasured — it would make the confidence intervals narrower and the construct question no less open.

---

## 8. Financial Application Audit

### What the system actually is

Judged by code and artifacts rather than by framing: FastClaw's financial layer is **a research-methodology copilot with a deterministic evidence-governance substrate, wrapped in an evaluation harness**. It is not a financial agent product (no market data, no execution, no valuation engine, no portfolio accounting), and the report does not claim otherwise. The paper's own characterization at V and VIII is accurate. The one place the framing gets ahead of the evidence is the *implicit* impression that r5 exercised this layer — dispelled explicitly at L656/L726, but the reader has to reach Chapter VII to learn it.

### Four-state classification

| Capability | Implemented | Unit-tested | Executed in r5 | Planned only | Evidence |
|---|---|---|---|---|---|
| 17 typed finance tools | ✅ | ✅ (10 tests) | ❌ **zero calls** | — | `plugin.py:104`; manifest `financial_tool_calls: 0` |
| `finance.tool.v1` envelope (`as_of`/`observed_at`, staleness, completeness, structured errors) | ✅ | ✅ | ❌ | — | `plugin.py`; `test_plugin.py` |
| Tenant-isolated Thesis Ledger | ✅ | ✅ | ❌ **zero mutations** | — | `evaltenant/tenant.go`; manifest evidence block |
| Optimistic integer versioning (`expected_version`) | ✅ | ✅ | ❌ | — | `test_plugin.py` conflict case |
| Immutable reviews | ✅ | ✅ | ❌ | — | `test_plugin.py` |
| Watchlist + SHA-256 event fingerprint, 24 h dedupe | ✅ | ✅ | ❌ | — | `test_plugin.py` |
| Serenity research Skill (pinned) | ✅ | executable content verified | injected into prompts | — | 24 ok / 2 mismatch (`README.md`, `README.zh-CN.md`) — reproduced independently |
| Six financial cases with compiled evidence | ✅ | — | ✅ | — | `evals/multiagent-finance-runtime.yaml` |
| Coordinator + 3 specialists delegation | ✅ | — | ✅ (36 `spawn_subagent` calls) | — | r5 trace; only tool name present |
| Governance-wording graders (milestones, grounding, forbidden phrases) | ✅ | ✅ (Go) | ✅ | — | 18 milestones, 44 assertions |
| Live retrieval / market data | ❌ | ❌ | ❌ | ✅ | fixtures are verbatim-copy specialist instructions |
| Ledger mutation under the runtime | ✅ (capability) | ✅ (plugin) | ❌ | ✅ (integration) | — |
| Fault injection in the financial suite | ✅ (instrument) | — | ❌ (`faults_expected=0`) | ✅ | manifest |
| Human-labelled entailment | ❌ | ❌ | ❌ | ✅ | — |
| Return backtest / alpha / Sharpe | ❌ | ❌ | ❌ | ✅ (and correctly deprecated) | — |

### Validity of the financial construct

**Defensible.** The `as_of` vs `observed_at` split is the single strongest domain idea: it makes the *temporal provenance* of a datum a typed property rather than prose, which is exactly the failure mode that makes naive financial LLM pipelines unsafe. Optimistic versioning on a thesis record is the right primitive for a human-in-the-loop analyst workflow (two reviewers cannot silently clobber a thesis). Immutable reviews plus fingerprinted event dedupe give an audit trail. The refusal-to-impute governance rule (the `incomplete-screening-data` case) is a genuine financial-research norm, not an invented benchmark artifact.

**Over-simplified.** Six fixed cases with compiled evidence do not represent financial research: they remove retrieval, source authority ranking, conflicting-source arbitration, and temporal drift — i.e. all four of the hardest parts. A specialist instructed to copy a fixture verbatim measures *the coordinator's synthesis and governance wording*, nothing more. This is a legitimate controlled design, and the paper says so, but it caps the external validity of RQ5 at "wording under ideal evidence".

**Correctly refused.** The paper does not claim investment performance, and its stated reasons (no point-in-time universe, no corporate actions, no delisting handling, no transaction costs) are the right four. Any backtest built on the present data would be survivorship- and look-ahead-biased. I endorse the refusal and would flag its removal as a P0 in a future round.

**Boundary that needs sharpening.** Serenity is described as a research methodology, which is correct — but a reader could infer it supplies data. One sentence stating "Serenity contributes analytical procedure and checklists; it contributes no market data and performs no valuation" would close this. Likewise "Thesis Ledger" invites a mental model of a general-ledger accounting system; it is a versioned research-thesis record store.

### Next-phase priority for the financial track

1. **Retrieval-and-mutation integration** — let specialists call the real tools and mutate the ledger, grade on post-state (ledger version, review immutability, dedupe outcome) rather than prose. This is the only change that converts RQ5 from split to answerable, and it also finally exercises the 17-tool layer that currently has no runtime evidence.
2. **Human-labelled entailment on the existing 44 assertions** — zero model cost, largest validity return (see §7).
3. **Larger holdout with conflicting sources** — introduce two sources that disagree on `as_of`, so evidence arbitration becomes measurable.
4. **Skill/challenger ablation** — with vs without the Serenity Skill, to test whether the injected methodology changes governance wording at all. Currently the Skill is injected but its contribution is unmeasured.
5. **Return backtest — do not do this.** It is the lowest-value and highest-risk option: it would require point-in-time data the project does not have, and a weak backtest would undermine the parts of the thesis that are sound.

### Claims requiring human oversight / compliance framing

The r5 outputs already show the right instinct — the one hedge exemption is the model deferring an evidentiary-weight judgment to legal/compliance counsel. The paper should keep (and does keep) three boundaries explicit: no suitability assessment for any individual; no recommendation framing; and mandatory human adjudication before any ledger state that would inform a real decision. These are stated in IX; they are adequate.

---

## 9. Security and Threat-Model Audit

Legend for **State**: `IMPL+TEST` implemented and covered by a test I located; `IMPL` implemented, no dedicated test found; `DOC` asserted in the report only; `FUTURE` future work.

| # | Control | Implementation evidence | Test evidence | State | Residual risk | Permitted paper wording |
|---|---|---|---|---|---|---|
| 1 | Two credential types → one `Identity`, no anonymous fallback | `auth/auth.go:11-51`; `api/server.go:144-153` | `openai_integration_test.go` | IMPL+TEST | Cookie lifetime/rotation not analysed | "authenticated identity is resolved before routing" |
| 2 | API-key agent ACL on the OpenAI-compatible path | `api/openai.go:103-118` (403 after `resolveAgent`) | `openai_integration_test.go:385`, 4 sub-cases (omitted → 403, inaccessible → 403, unknown → 404, allowed → 200) | IMPL+TEST | Per-route pattern must be repeated on every new route | "enforced on the resolved agent, with behavioural tests for allow/deny/unknown" |
| 3 | Session-path agent authorization | `auth.go:92` returns `true`; handler performs the check | handler tests only | IMPL | **Structural**: a future handler that omits the check has no backstop. The report hints at this (L812) but does not name it as a property of the design | "authorization for session callers is delegated to handlers; this is a deliberate but fail-open-by-default arrangement" |
| 4 | Superadmin scope separation | `internal/scope` | **zero `_test.go` in `internal/scope`** | IMPL | Untested privilege boundary | "implemented; not covered by automated tests" |
| 5 | Task visibility filtering | `internal/taskqueue` | queue tests | IMPL+TEST | Cross-tenant listing under store failure unexamined | as written |
| 6 | Workspace namespacing (agent + optional session) | `internal/workspace` | workspace tests | IMPL+TEST | No quota / no path-escape fuzzing | as written |
| 7 | Policy-filtered tool registry (copy-then-filter, 5 presets) | `internal/policy/defaults.go` (permissive/restricted/standard/no-tools/delegate-only) | **zero `_test.go` in `internal/policy`** | IMPL | Fail-closed default for unknown tools is asserted, not demonstrated | "five presets are implemented; the filtering behavior is not covered by tests" |
| 8 | Sandbox required, no silent host fallback | `internal/sandbox` | sandbox tests present | IMPL+TEST | Only two fixed mounts; Skill paths outside them enter the prompt without file access | as written (L164 is accurate) |
| 9 | Trusted `ToolCallContext` (ids injected post-routing, not model-controlled) | plugin bridge | Python `test_plugin.py` | IMPL+TEST | Go side of the JSON-RPC bridge has **zero tests** (`internal/plugin`) | "tenant identity is injected by the runtime, not supplied by the model" |
| 10 | Prompt-injection posture | policy filtering + typed tool args | — | DOC | No injection corpus, no test. Full-Skill injection enlarges the untrusted surface | "the architecture constrains the blast radius; no injection evaluation was performed" |
| 11 | Model-generated tool arguments | typed envelopes, structured errors | Python tests | IMPL+TEST | Go-side argument validation untested | as written |
| 12 | Tenant spoofing | tenant-scoped ledger keys | `evaltenant` integration test | IMPL+TEST | — | as written |
| 13 | Plugin subprocess / supply chain | JSON-RPC subprocess | Python tests | IMPL | **`finskills` external and unvendored**; no signature, no interpreter pin, no subprocess resource limits documented | "subprocess isolation is process-level only; supply-chain integrity is not addressed" |
| 14 | Stale session / store failure | `session` store-backed read **fails open** to an in-memory copy | **zero `_test.go` in `internal/session`** | IMPL | Unbounded staleness; a client can observe history regressions. The disclosure at L170 is honest but the security consequence (authorization decisions made against stale state) is not drawn | "reads fail open to a possibly stale copy; the staleness bound is unspecified" |
| 15 | Cost exhaustion / fan-out | root semaphore, two 256 caps, iteration bound, queue-wide timeout | queue tests | IMPL+TEST | No per-tenant budget; a permitted tenant can spend without limit | "concurrency and depth are bounded; monetary spend is not" |
| 16 | Auditability | per-call role/token/latency/error trace | `usage_trace_test.go` | IMPL+TEST | Trace drops `seq`/timestamps/agent ids; unpriced calls indistinguishable from free | "per-call telemetry supports cost attribution; it is not a tamper-evident audit log" |
| 17 | Human approval | immutable reviews, refusal-to-impute rule | Python tests | IMPL+TEST | Not enforced at the runtime layer — nothing prevents an agent writing a thesis state without review | "human review is modelled and recorded; it is not a runtime-enforced gate" |

### Additional findings from this round

**S-R2-01 (P1, not in the report).** `internal/setup/handlers_skills.go:48-55` and `:165-178` build `filepath.Join(homeDir, "skills", r.PathValue("name"))` and call `os.RemoveAll` with **no validation of `name`**. Mitigating facts I verified: the routes are `DELETE /api/skills/{name}` (admin-gated) and `DELETE /api/agents/{id}/skills/{name}` (auth-gated) — Go's `ServeMux` wildcard does not match `/`, and it path-cleans, so multi-segment traversal is blocked and a bare `..` segment is normalized away before matching. So this is **not a demonstrated escape**, but it is a delete-by-path with no allow-list check and no `filepath.Clean`-plus-prefix assertion in front of a recursive delete, i.e. one router change away from being one. Recommendation: validate `name` against the enumerated skill set (or assert the joined path is strictly under the skills dir) before `RemoveAll`. Paper impact: the threat-model table should not claim path-level validation for skill management, because none exists.

**S-R2-02 (P2).** `internal/agent/hooks.go:47-69` — `HookRegistry` is a bare `map[HookPoint][]HookFunc` with no mutex on `Register`/`Run`. Registration is startup-time in the shipped paths, so this is latent rather than live, but the report's concurrency chapter claims disciplined shared-state handling and this is a counterexample worth one line in the limitations table rather than in the architecture chapter.

**S-R2-03 (P2).** `CacheReadIncludedInPrompt` is set on the OpenAI path only (`provider/openai.go:326`); the Anthropic path (`anthropic.go:415-417`) records cache tokens without it, so `estimateModelCallCost` (`usage_trace.go:182`) would **not** subtract cache reads for Anthropic. r5 used a single provider so no reported number is affected, but the paper elevates the billable-token convention to a methodological contribution and should note that the convention is currently provider-asymmetric.

### Threat-model completeness verdict

Assets, trust boundaries, attacker capabilities, non-goals, and a control/residual-risk table are all present — Round 1's P1-02 is genuinely closed. Two structural weaknesses remain in the *reasoning*, not the table: (a) the report does not distinguish sharply enough between "control exists" and "control is tested", which matters because five of the security-relevant packages (`policy`, `scope`, `session`, `plugin`, `skills`) have **zero tests**; and (b) the largest realistic attack surface for an LLM runtime — prompt injection into a full-Skill-injected context with 43–81 tools available under `standard`/`no-tools` presets — is discussed architecturally and never evaluated. Neither is a P0, because the paper does not claim to have evaluated them.

---

## 10. Academic Writing Findings

The prose is, on the whole, unusually disciplined for a student thesis: hedging is calibrated, the negative result is stated without euphemism, and the Abstract does not oversell. The items below are the sentences where the language still outruns the evidence, plus a small number of structural defects. I have excluded sentences that are already accurate — per the prompt's instruction not to rewrite for the sake of volume.

**W-01 — L154 (PDF p11). Factual.**
- 原句: "the OpenAI-compatible path retains **the complete assistant payload** in `RawAssistant`"
- 建议改写: "the OpenAI-compatible path **reconstructs a synthetic assistant payload** from accumulated stream fragments and stores it in `RawAssistant`, so it is a re-serialization rather than the original wire message"
- 问题类型: factual overstatement of a replay guarantee
- 为什么更严谨: the field is assembled from deltas, not captured; the paper's own conclusion — that callers cannot assume one cross-provider raw-payload contract — is *strengthened*, not weakened, by the correction. As written, a reader could build a caching or signed-reasoning replay path on a guarantee that does not hold.

**W-02 — L156 (PDF p11). Factual/incomplete enumeration.**
- 原句: "The application-level event contract distinguishes incremental `content_delta`, convergent full `content` snapshots, `error`, and terminal `done`."
- 建议改写: "…distinguishes six event types: incremental `content_delta`, convergent full `content` snapshots, `tool_call` and `tool_result` trace events, `error`, and terminal `done`."
- 问题类型: enumeration presented as exhaustive but is a subset
- 为什么更严谨: `tool_call` and `tool_result` are emitted by the same emitter (verified: six distinct `emit(...)` literals in `internal/agent/events.go`), and L199 *relies* on them ("emit trace events"). Declaring a four-element contract contradicts the paper's own algorithm.

**W-03 — L656 (PDF p30). Statistical explanation.**
- 原句: "The P50 exceeds the 19.45-second mean because several short cases pull the arithmetic mean below the midpoint of the six ordered values."
- 建议改写: "The P50 exceeds the 19.45-second mean because the harness uses a nearest-rank percentile, `index = int((n−1)q + 0.5)`; at n=6 this selects the fourth of six ordered values rather than interpolating between the third and fourth."
- 问题类型: correct number, wrong mechanism
- 为什么更严谨: the stated reason is a property of the data; the actual reason is a property of the estimator (`runner.go:486-492`). A reader who reproduces the analysis with an interpolating percentile will get a different P50 and conclude the paper is wrong. Naming the estimator makes the number reproducible.

**W-04 — L406-410 (PDF p22). Methodological.**
- 原句: the five hypotheses "**H1:** …", "**H2:** …", … stated and never returned to.
- 建议改写: keep the definitions, then add an explicit resolution line to each RQ answer, e.g. "**H1: not tested** — the cumulative runtime ablation that would test it is proposed work (Table VII)"; "**H3: not testable from r5** (`faults_expected = 0`)"; "**H5: not supported in the observed direction** — Team used 41.6% fewer billable-like tokens than Two-Pass at equal pass count."
- 问题类型: dangling hypothesis; declared instrument never resolved
- 为什么更严谨: a thesis that names hypotheses and never adjudicates them invites the examiner's first question. H5 is the sharp case: r5's evidence points *against* it, which is an interesting result the paper currently discards.

**W-05 — L355 (PDF p18) and L434 (PDF p23). Factual — grader families.**
- 原句: "A fluent answer that describes the customer loss but leaves the thesis active **fails the state-transition grader**." / "final success requires the configured state, communication, and policy components to pass."
- 建议改写: "In the r5 configuration the state, communication, policy, and tool-trace grader families are empty (`state_graders = 0`); the corresponding behavior is checked only through milestone and grounding assertions over the final prose."
- 问题类型: describing an instrument as active when the artifact records it as unpopulated
- 为什么更严谨: r5 has `state_graders = passed_state_graders = communication_graders = policy_graders = tool_trace_graders = 0`. The present wording implies a state-transition oracle graded the run; the actual oracle was lexical assertion matching over prose. This is the single most consequential wording gap I found, because it goes to what RQ5 measured.

**W-06 — L168 (PDF p12). Evidence boundary.**
- 原句: "SQLite with write-ahead logging is the zero-configuration default; **PostgreSQL is the production target**."
- 建议改写: "SQLite with write-ahead logging is the zero-configuration default; a PostgreSQL dialect is implemented across the store layer but is not covered by automated tests, so portability is implemented rather than verified."
- 问题类型: readiness claim without test evidence
- 为什么更严谨: I found 14+ `dialect == "postgres"` branches and **zero** matches for `postgres` in any `internal/store/*_test.go`. "Production target" reads as a validated deployment posture; the honest claim is an untested dialect.

**W-07 — L798 (PDF p35). Citation use.**
- 原句: "FastClaw applies defense in depth and treats risk management as a lifecycle activity rather than a single filter [14]:"
- 建议改写: either tie the reference to a specific function ("mapping the controls below to the NIST AI RMF *Govern*, *Map*, *Measure*, and *Manage* functions [14]") or drop [14] and cite it where the lifecycle framing is actually used.
- 问题类型: decorative citation
- 为什么更严谨: as written, [14] endorses a sentence about FastClaw rather than supporting a claim about risk management. A named-function mapping makes the citation checkable — and would also fix the reference-ordering violation (see §11).

**W-08 — L282 (PDF p17). Precision, in the paper's favour.**
- 原句: "Verification of its supplied SHA-256 list produced 24 successful checks and two failures for `README.md` and `README.zh-CN.md`"
- 建议改写: "…24 of 26 hashes matched; the two mismatches are `README.md` and `README.zh-CN.md`, i.e. documentation rather than executable content or `SKILL.md`. The mismatch is consistent with local documentation edits, not with modified analysis logic."
- 问题类型: incomplete denominator + missing interpretation
- 为什么更严谨: "24 successes and two failures" leaves the reader to infer the denominator, and omits the material point — that the drift is confined to non-executable files. I reproduced this result independently; the paper is *entitled* to the stronger, better-scoped statement.

**W-09 — L558 (PDF p26). Measurement scope.**
- 原句: "Repository-wide statement coverage measured with `go test ./... -coverprofile` is 28.4%."
- 建议改写: "…is 28.4% including the thesis's own `project-report/analysis` package, or 27.2% for production packages only."
- 问题类型: measurement includes the instrument under discussion
- 为什么更严谨: `project-report/analysis` is analysis tooling written for this thesis and is heavily covered, inflating the figure by ≈1.2 pp. Reporting both numbers costs one clause and removes the objection.

**W-10 — L869 (PDF p37). Argument clarity.**
- 原句: "exposing how much of an apparent capability result belongs to the **oracle**."
- 建议改写: "…belongs to the **grader** rather than to the agent"
- 问题类型: overloaded term
- 为什么更严谨: the paper spends Chapter VI carefully renaming `oracle_team` to "routed-team diagnostic" precisely so that "oracle" does not connote an upper bound. Reusing "oracle" in the Conclusion to mean "the grading instrument" reintroduces the ambiguity in the one place a reader is most likely to quote.

**W-11 — L25 (PDF p5). Structural, not sentence-level.**
- 原句: the Introduction's opening paragraph ("Large language models (LLMs) can answer questions, generate code, and invoke external tools, but model capability alone does not produce a dependable software system…")
- 建议改写: the sentence itself is fine; the problem is that Chapter I is **491 words (3.4% of prose)** while Chapter V is 2,067 (14.2%) and Chapter IV — the core runtime contribution — is 1,215 (8.3%). Move ≈300 words of gap statement and contribution scoping into I, and move implementation enumeration from V into an appendix.
- 问题类型: chapter proportion inconsistent with contribution claim
- 为什么更严谨: an examiner reads the Introduction as the contract for the rest of the thesis. At 3.4% it cannot carry the gap statement, and the chapter that the Abstract foregrounds is currently the smallest substantive one.

**W-12 — L241 (PDF p14). Typography/precision.**
- 原句: `` `C = (Tin × Pin + Tout × Pout + Tcache-read × Pcache-read + Tcache-write × Pcache-write) / 10^6` ``
- 建议改写: render subscripts properly (T_in, P_in, …) and `10^6` as a superscript, state that prices are per million tokens, and extend L243's condition to name the asymmetry: the cache-read subtraction is applied only when the provider reports cache tokens as included in the prompt count, **which the OpenAI-compatible adapter does and the Anthropic adapter does not**.
- 问题类型: formula typography; a stated precondition that is provider-asymmetric in implementation
- 为什么更严谨: L243 already states the condition correctly — credit where due — but `CacheReadIncludedInPrompt` is set only at `provider/openai.go:326`, while `anthropic.go:415-417` records cache tokens without it, so the same formula yields a different cost on the Anthropic path. r5 used one provider, so no reported number is affected; but the billable-token convention is presented as a methodological contribution, and a contribution that behaves differently per adapter must say so. Separately, the inline-code rendering of a display formula produces `Tin`/`10^6` as literal text on p14, which for the paper's only equation is worth fixing.

**W-13 — L425 (PDF p22). Terminology.**
- 原句: table row "τ-bench-style | Three retail state-machine cases | Multi-turn state accuracy, communication, and policy compliance."
- 建议改写: "τ-bench-*inspired* | Three locally authored retail state-machine cases | Locally defined state, communication, and policy checks (not the τ-bench dataset, tasks, or metrics)"
- 问题类型: benchmark-adjacent naming
- 为什么更严谨: L429 already disclaims that these are regression tests rather than official scores, but the table's metric column reuses τ-bench's metric vocabulary, which is exactly what a skimming reader will extract. The disclaimer should be in the table, not only after it.

**W-14 — L170 (PDF p12). Consequence not drawn.**
- 原句: "If the store returns an error and an in-memory copy exists, the read fails open to that potentially stale copy"
- 建议改写: add: "The staleness is unbounded, and the paths that read session state are untested (`internal/session` has no test files), so a client can in principle observe a history regression between two consecutive requests."
- 问题类型: honest disclosure without its consequence
- 为什么更严谨: the disclosure is already good; naming the observable symptom and the test gap converts it from a design note into a limitation an examiner can evaluate.

**W-15 — L187 / PDF p12. Production defect, surfaces as writing.**
- 原句(as rendered): "…l exists, persist the assistant message, flush the session, emit \`done\`, and return."
- 建议改写: route `ALGORITHM_STEP` lines through `add_inline_text` in `build_report.py` (currently `add_algorithm` calls `paragraph.add_run(step)` at `:827`, bypassing `INLINE_PATTERN`).
- 问题类型: build defect producing literal backticks in the final PDF
- 为什么更严谨: Algorithm 1 is the paper's formalization of its core mechanism; literal backticks on the page are the most visible typographic defect in the document and appear in the chapter the Abstract advertises.

**Structural note (not a numbered finding).** Chapters are otherwise well separated: Background does not drift into Related Work, Methodology defines metrics before Results uses them, Results does not introduce new methods, Discussion is genuinely interpretive, and the Conclusion answers each RQ in order. I found **no** marketing language, no causal overclaim, no vague subject where a specific actor was needed, and no place where a passing test is called a correctness proof. On the specific traps the prompt lists, the paper is clean: lexical matching is never called grounding or factuality (L70 defines the narrower term and holds it); a style subset is never called an official score (L429); a dirty snapshot is never called exact reproducibility (Appendix C); the zero fault denominator is called vacuous in both RQ answers (L718, L865); and the routed diagnostic is never called an upper bound.

---

## 11. Citation and Related-Work Audit

### Per-reference verification

| Ref | Verified content | Status | Note |
|---|---|---|---|
| [1] ReAct, Yao et al., ICLR 2023 | authors, venue, year, OpenReview id `WE_vluYUL-X` | ✅ correct | Supports L27's claim precisely (pattern, not runtime) |
| [2] MCP spec, revision 2026-07-28 | revision-dated URL + access date | ✅ correct form | 待核验 — I did not fetch the URL (no network use in this review); the citation is well-formed and internally consistent with L45 |
| [3] JSON-RPC 2.0 | origin 2010, updated 2013 | ✅ correct | Correctly cited as the plugin transport at L160 |
| [4] BFCL, Patil et al., ICML 2025, PMLR v267, pp. 48371–48392 | ✅ plausible and correctly formed | 待核验 (page range) | L47's use is accurate: structural comparison of tool calls |
| [5] τ-bench, Yao et al., ICLR 2025 | ✅ correct | — | L53's use is accurate |
| [6] SWE-bench, Jimenez et al., ICLR 2024 | ✅ correct | — | L53's "executable oracle part of the benchmark" is exactly the paper's point |
| [7] MultiAgentBench, Zhu et al., ACL 2025, doi 10.18653/v1/2025.acl-long.421 | ✅ correct form | 待核验 (page range 8580–8622) | Correctly used for milestone/communication metrics |
| [8] FinQA, EMNLP 2021, doi …emnlp-main.300 | ✅ correct | — | — |
| [9] TAT-QA, ACL 2021, doi …acl-long.254 | ✅ correct | — | — |
| [10] Rashkin et al., ACL 2021, "Increasing faithfulness in knowledge-grounded dialogue with controllable features" | ✅ reference is real and correctly formatted | ⚠ **weak fit** | Used at L70 to license the fidelity-vs-fluency distinction. That paper's contribution is *controllable generation features for dialogue*, not a definition of attribution for evaluation. A closer primary source is Rashkin et al., "Measuring Attribution in Natural Language Generation Models" (*Computational Linguistics*, 2023) — the AIS framework — which is literally about attribution as an evaluation construct |
| [11] BCBS 239 | ✅ correct (BIS, 9 Jan 2013) | ⚠ **weak fit at L70** | Sound and apt for the *governance* argument (data aggregation, timeliness, completeness) and for the `as_of`/`observed_at` discussion at L316. But at L70 it is used to help define evidence attribution, which BCBS 239 does not address. Move it to L316 and the governance controls |
| [12] Saltzer & Schroeder 1975 | ✅ correct, canonical | — | Fail-safe defaults / complete mediation / least privilege at L111 is the correct use |
| [13] OWASP AI Agent Security Cheat Sheet | ✅ correctly labelled as guidance, not research | 待核验 (2026 edition) | Correctly distinguished from a peer-reviewed source |
| [14] NIST AI RMF 1.0, doi 10.6028/NIST.AI.100-1 | ✅ correct | ❌ **decorative + ordering violation** | See W-07. Also: first cited at **L798**, after [15]–[17] at L542, so IEEE first-appearance numbering is violated |
| [15] Wilson 1927, JASA 22(158):209–212 | ✅ correct | — | Correct use for the interval |
| [16] McNemar 1947, Psychometrika 12(2):153–157 | ✅ correct | ⚠ | The paper applies the **exact binomial** test on discordant pairs and cites McNemar for it. That is standard practice but worth one clause: "the exact conditional (binomial) form of the McNemar test [16]" — because McNemar's original statistic is the χ² approximation, not the exact test |
| [17] Efron 1979, Ann. Statist. 7(1):1–26 | ✅ correct, canonical | — | Correctly cited for a *reserved future* method, and correctly not used |

### Findings

**C-01 (P2).** Reference-order violation: first body appearances are [1]@27, [2][3]@45, [4]@47, [5][6][7]@53, [8][9]@61, [10][11]@70, [12][13]@111, **[15][16][17]@542, [14]@798**. IEEE requires numbering by first appearance. Two clean fixes: renumber so NIST becomes [17], or cite [14] earlier where the lifecycle framing is introduced (which W-07 recommends anyway).

**C-02 (P2).** [10] and [11] are both attached to L70's definition of *evidence attribution*, and neither is about attribution as an evaluation construct. This is the paper's most load-bearing definitional sentence — the one that keeps it from claiming factual entailment — so it deserves the strongest available support. Recommended additions (both verifiable primary sources): Rashkin et al., "Measuring Attribution in Natural Language Generation Models", *Computational Linguistics* 49(4), 2023 (AIS); and Honovich et al., "TRUE: Re-evaluating Factual Consistency Evaluation", NAACL 2022, for the gap between lexical overlap and entailment-based measurement. The second would let the paper cite evidence, not just assert, that lexical checks under-approximate entailment.

**C-03 (P1) — missing topics.** Four areas that the thesis *argues about* have no literature anchor:
1. **Multi-agent effect skepticism.** The thesis's headline is a null/undetermined orchestration result, yet no source is cited on when multi-agent systems fail to beat a single strong agent. Recommended: Cemri et al., "Why Do Multi-Agent LLM Systems Fail?" (2025) — a taxonomy of MAS failure modes — and Wang et al., "Unleashing the Emergent Cognitive Synergy in LLMs" (NAACL 2024) for the single-agent-with-personas control. Marked 待核验 for exact venue/pages. Without these, the negative result reads as a local measurement artifact rather than as a contribution to a live debate.
2. **Database concurrency.** The immediate-transaction argument (read-then-write upgrade under WAL) is a textbook concurrency-control problem cited to nothing. Recommended: Bernstein/Hadzilacos/Goodman, *Concurrency Control and Recovery in Database Systems* (1987), plus the SQLite WAL and `BEGIN IMMEDIATE` documentation as a primary specification.
3. **Deadlock/wait-for-graph detection.** The wait-graph cycle detection — the paper's best mechanism — has no reference. Recommended: Coffman, Elphick & Shoshani, "System Deadlocks", *ACM Computing Surveys* 3(2), 1971, for the four conditions and wait-for-graph formulation. One citation would let the paper say its invariant is the classical one applied to a new object (agent lanes), which strengthens the novelty claim rather than diluting it.
4. **Human-in-the-loop financial decision support.** Chapter IX's oversight boundary is argued from first principles. Any decision-support/appropriate-reliance source would anchor it; the paper should not rely on BCBS 239 alone to carry both data governance and human oversight.

**C-04 (P2).** The paper correctly separates specifications ([2],[3]), benchmark papers ([4]–[9]), security guidance ([13],[14]) and statistical methods ([15]–[17]) — Round-1 P2-08's intent is met. One residual asymmetry: §IX's nine security controls rest on [12] (1975), [13] (a cheat sheet) and [14] (a framework), with **no** peer-reviewed source on prompt injection or LLM-agent security specifically. Since the paper explicitly declines to evaluate injection, a survey citation is sufficient and is the cheapest way to close the gap.

**C-05 (no action).** No fabricated or unverifiable-looking reference was found. Every entry corresponds to a real, locatable work with a plausible venue, and no reference is cited for a claim it obviously cannot support (the two ⚠ fits above are imprecision, not invention). Items I could not confirm without network access are marked 待核验 above and are limited to page ranges and edition dates.

---

## 12. Visual and Build Audit

### Page count discrepancy (new, P2)

`pdftotext` reports **43 pages** in `FastClaw_Project_Report_Zheyu_Wang.pdf`, of which **page 43 is completely empty** (zero non-blank lines). `page_map.json` records `"pages": 42`, and `extract_page_map.py` computes `result["pages"] = len(pages)` — i.e. the extractor and the file disagree by one, which means the shipped `page_map.json` was **not** produced from the shipped PDF, or a trailing page was added after extraction. The paper, the resolution document, and Appendix C all say 42 pages. Impact is cosmetic (a blank trailing page after References), but it breaks the one invariant `build_artifacts.sh` exists to enforce: its final `cmp "$PAGE_MAP_PATH" "$FINAL_PAGE_MAP_PATH"` compares two extractions of the *same* PDF, so it cannot detect a page-count drift between the map and the artifact. Fix: strip the trailing empty page (a stray `add_page_break` after References), then re-run the two-pass build; and additionally assert `page_map["pages"] == len(PdfReader(pdf).pages)` on the final artifact.

### Front matter

| Item | Finding | Severity |
|---|---|---|
| Table of Contents (p2) | Lists **only the 14 `#` chapters**. All **59 `##` subsections are omitted** because `add_front_matter` filters on `if stripped.startswith("# ")` (`build_report.py:913`). For a 42-page thesis with ten substantive chapters, a chapter-only TOC is below thesis convention — a reader cannot navigate to "VI.D Baseline Modes" or "IX.A Threat Model". | P2 (P1 for a formal submission) |
| Page numbers in TOC | Verified against the PDF: I@5 II@6 III@9 IV@12 V@15 VI@21 VII@26 VIII@32 IX@35 X@37, Appendices 39/40/41, References 42 — **all correct**. | ✅ |
| List of Figures (p3) | 4 entries, pages 9/14/15/30 — **all verified correct**. | ✅ |
| List of Tables (p3) | 18 entries, Roman I–XVIII, pages 8,16,17,19,21,23,24,26,26,27,28,28,29,30,30,34,39,41 — **all verified correct**. | ✅ |
| List of Abbreviations (p4) | 12 entries. The body uses noticeably more initialisms than that (ACL, API, DSN, FIFO, DFS, JSON-RPC, MCP, P50/P95, RQ, SSE, WAL, LLM, …). Incomplete rather than wrong. | P2 |
| Running header / footer | Header "UNDERGRADUATE THESIS · AGENT RUNTIME AND FINANCIAL RESEARCH" and footer "FastClaw Undergraduate Thesis · Zheyu Wang \| N" present and consistent on every sampled page; date August 2026 consistent with `REPORT DATE` (L5). Round-1 P2-01 closed. | ✅ |

### Body pages

| Item | Finding | Severity |
|---|---|---|
| **Algorithm 1 (p12)** | Confirmed defect: step 6 renders as `…l exists, persist the assistant message, flush the session, emit \`done\`, and return.` — literal backticks in the PDF. Cause: `add_algorithm` calls `paragraph.add_run(step)` at `build_report.py:827`, bypassing `add_inline_text`/`INLINE_PATTERN` (`:615-618`). This is the most visible typographic defect in the document and it lands on the paper's central formalization. | **P1** |
| Cost formula (p14) | Rendered from inline code, so it appears as `C = (Tin × Pin + … ) / 10^6` with no subscripts and a literal `^6`. It is the paper's only equation. | P2 |
| Sparse pages | p20 = 11 non-blank lines, p38 = 9, p14 = 14, p4 = 16, p2 = 17. p38 (nine lines: the final Future Work paragraph, then the footer) and p20 (a table remnant plus two short paragraphs) read as underfilled. Dense pages reach 50 lines (p21, p23), so the variance is large. | P2 |
| Blank page | p43 empty (see above). | P2 |
| Table continuation | Sampled long tables (Table XVI threats-to-validity, 11 rows, p34; Table XVII, p39) hold together with headers on the same page as their captions. Round-1 P2-07's intent is met. | ✅ |
| Numeric column alignment | Markdown alignment markers are genuinely parsed (`|---:|` present at L524, 565, 574, 636, 646, 671, 682, 699) and right-aligned in the rendered tables. Round-1 P2-03 closed. | ✅ |
| **Table cross-references** | **Zero occurrences of "Table I"–"Table XVIII" anywhere in the body prose** (`grep -c "Table [IVX]"` = 0). All 18 tables are captioned and numbered but never referenced by number. Figures are the opposite: all four are referenced ("Figure 1 locates…" L121, "Figure 2 shows…" L231, "Figure 3 summarizes…" L251, "Figure 4 visualizes…" L692). Round-1 P2-05 is therefore **closed for figures and open for tables** — the resolution's "所有主图表有稳定编号并在正文显式引用" is accurate for numbering, not for reference. | **P1** |
| Orphaned captions | Clarification of P1-R2-03, which stands: every one of the 18 `TABLE_CAPTION:` lines **is** followed within two lines by a `|`-delimited table, so no caption is stranded without its table. The defect is narrower than that — four captions (L562, L696, L776, L919) are preceded, ignoring blanks, by a `##`/`#` heading or by `[[FIGURE_4]]` rather than by an introducing sentence, so the reader meets Tables VIII, XV, XVI and XVIII before being told what question they answer, and at L696 a table caption sits directly beneath a figure placeholder. The other 14 captions all have a proper lead-in sentence. | **P1-R2-03** |
| Figure 4 label size | Drawn with PIL `ImageDraw` at `_font(19)`/`_font(21)` on a 2400×1500 canvas placed at `BODY_WIDTH_INCHES = 6.80` in ⇒ effective ≈5.4 pt for the 19 px labels, against 10 pt body text. Legible under magnification, marginal in print. The fix is the PIL font size, **not** matplotlib parameters. | P2 |
| Figures 1–3 | Caption text matches the hard-coded strings at `build_report.py:992-995` and the body references at L121/L231/L251. Figure 2 does show Client→Gateway→TaskQueue→Coordinator→MessageBus→parallel specialists, closing Round-1 P2-06. | ✅ |
| References formatting (p42) | IEEE-style, hanging entries, DOIs and URLs present, no visible wrapping breakage. Ordering violation is content, not layout (§11 C-01). | ✅ layout |

### Build reproducibility

| Item | Finding | Severity |
|---|---|---|
| Markdown as single source | Confirmed: `parse_source()` reads `fastclaw_project_report.md`; Algorithm 1 content lives in the Markdown (L178-190) — Round-1 P2-02 closed. | ✅ |
| Hard-coded conclusions in the generator | I re-checked: `build_report.py` hard-codes **presentation** (figure captions `:992-995`, type sizes, margins) and **reads** `finance_reanalysis.json` at build time to draw Figure 4 (`create_grader_ablation_figure`, `:253-304`). It does **not** hard-code any experimental result into prose. Good. | ✅ |
| Two-pass page numbering | `build_artifacts.sh` genuinely renders, extracts, re-renders, re-extracts, and `cmp`s the two maps. Sound in principle. | ✅ |
| **Gate weakness** | `extract_page_map.py` hard-codes `body_pages = pages[4:]`, `range(1, 5)` for figures and `range(1, 19)` for tables. So the gate proves stability of *these* 4 figures and *these* 18 tables under *this* 4-page front matter. Add a 19th table or a 5th figure and the `cmp` still passes while the List of Tables silently loses an entry. Combined with the 42-vs-43 page mismatch above, the build gate currently does not detect the one class of drift it was added for. | **P1** |
| `finance_reanalysis.json` mtime | 20:00:41, i.e. **after** the 18:05 report build — so Figure 4 in the shipped PDF was drawn from an earlier version of that file. Content is idempotent (the resolution records identical SHA-256 across reruns, and I reproduced the file by running the repo's own analysis program), so this is a provenance-ordering defect rather than a data defect. Recommend regenerating the analysis JSON *before* the report in `build_artifacts.sh` and recording both hashes in the manifest. | P2 |
| Local-machine dependencies | `build_artifacts.sh` exposes `CODEX_PRIMARY_RUNTIME`, `PYTHON_BIN`, `PYTHON_PACKAGES`, `DOCUMENT_SKILL_ROOT`, `DOCX_RENDERER` as overrides, which is the right pattern and closes Round-1 P2-09's intent. Residual: the DOCX→PDF step still depends on a locally available renderer, and `pypdf` is not importable in the default interpreter on this machine (I had to use `pdftotext` for the page audit), so a fresh clone cannot run `extract_page_map.py` without the documented `PYTHON_PACKAGES` install. Document the exact package list in Appendix B. | P2 |
| **`artifact.md`** | Documents the superseded 20-page build: margins 0.60/0.75 vs `build_report.py:531-534` (0.82/0.78/0.85/0.85); "7.30-inch usable page width" vs `BODY_WIDTH_INCHES = 6.80` (`:52`); "Title 24 pt" vs `size=22` (`:559`,`:649`); "Level-1 headings 10 pt" vs `("Heading 1", 13, True, False)` (`:561`); "20 rendered pages, DOCX SHA-256 `c42d1403…`, PDF `98f8f5ad…`" vs the actual 42(+1) pages, `df43934e…`, `6c5c819c…`. It also names gitignored `runtime-pilot*.json` as authoritative inputs. This is P0-R2-01 in §3 and remains the single worst reproducibility defect in the submission package. | **P0-R2-01** |
| Secrets | No secret, and no absolute home path, appears in the report, the manifest, or the page map. `runtime-benchmark-tenant.json` was never read in this review. | ✅ |

### Thesis-format verdict

The document reads as a thesis, not a padded project report: chapter proportions are uneven (§10 W-11) but the structure, front matter, numbered tables/figures, algorithm environment, threats-to-validity table, three appendices and IEEE reference list are all present and correctly paginated. The two things a formal submission would still be marked down for are the chapter-only Table of Contents and the literal backticks in Algorithm 1 — both single-line fixes in `build_report.py` (`:913` and `:827`), neither requiring any change to the paper's text or to any experiment.

---

## 13. Prioritized Remediation Plan

Cost tiers: **A** = zero model calls, minutes of work; **B** = zero model calls, hours (analysis or re-derivation); **C** = paid model calls required. Everything at tier A or B can be completed without spending anything.

### P0 — must fix before submission

| # | Item | Files to change | What to change | New model calls? | Cost | Acceptance evidence |
|---|---|---|---|---|---|---|
| 1 | `artifact.md` documents a superseded build | `project-report/artifact.md` | Replace margins with 0.82/0.78/0.85/0.85, usable width with 6.80 in, title 22 pt, Heading 1 13 pt; replace "20 rendered pages / `c42d1403…` / `98f8f5ad…`" with the shipped page count and `df43934e…` / `6c5c819c…`; remove gitignored `runtime-pilot*.json` from the authoritative-input list and name `finance-runtime-formal-r5.json` + its manifest instead | No | **A** | `shasum -a 256 project-report/FastClaw_Project_Report_Zheyu_Wang.{docx,pdf}` matches the values in `artifact.md`; every typographic number in `artifact.md` matches a line in `build_report.py` |
| 2 | H1–H5 declared, never resolved | `fastclaw_project_report.md` (RQ answers at L712-720 and L859-867; optionally the RQ table at L94-103) | Add one resolution clause per hypothesis: H1 **not tested** (ablation is proposed, Table VII); H2 **partially addressed** via the per-case matrix, not resolved; H3 **not testable from r5** (`faults_expected = 0`); H4 **supported for the deterministic layer only** (plugin tests); H5 **not supported in the observed direction** — Team used 41.6% fewer billable-like tokens than Two-Pass at equal pass count. Add a `Hypothesis` column to the RQ mapping table | No | **A** | `grep -c "H[1-5]" ` shows each of H1–H5 appearing in both the definition block and an RQ answer; `grep "not tested"` returns a non-empty result |

### P1 — should fix; each materially changes what a reader concludes

| # | Item | Files | Change | Model calls? | Cost | Acceptance |
|---|---|---|---|---|---|---|
| 3 | Empty `state`/`communication`/`policy`/`tool_trace` grader families not disclosed (P1-R2-01) | report L355, L425, L434, L726, Table XVI | State plainly that in r5 these families are unpopulated (`state_graders = 0`) and that the effective oracle is milestone + grounding assertion matching over final prose. Rewrite L355 accordingly (§10 W-05) | No | **A** | `jq '[.. \| objects \| select(has("state_graders")) \| .state_graders] \| add' finance-runtime-formal-r5.json` = 0, and the report says so |
| 4 | Zero table cross-references (P1-R2-02) | report, ~18 sites | Insert `Table N` references at each table's discussion point, matching the existing figure-reference style | No | **A** | `grep -oE "Table [IVX]+" fastclaw_project_report.md \| sort -u \| wc -l` = 18 |
| 5 | Four captions with no lead-in (P1-R2-03) | report L562, L696, L776, L919 | One introducing sentence before each, carrying the `Table N` reference from item 4 | No | **A** | No `TABLE_CAPTION:` line is immediately preceded (ignoring blanks) by a heading or `[[FIGURE_` |
| 6 | Algorithm 1 literal backticks on PDF p12 (P1-R2-04) | `build_report.py:809-827` | Route `ALGORITHM_STEP` text through `add_inline_text` instead of `paragraph.add_run(step)` | No | **A** | Rebuild; extracted p12 text contains `emit done` and zero backtick characters |
| 7 | Chapter-only TOC | `build_report.py:913` | Also emit `##` subsections at one indent level, using `page_map` keys extended for subsection headings (`extract_page_map.py` `source_headings()` must match `## ` too) | No | **B** | TOC lists 14 chapters + 59 subsections; two-pass `cmp` still passes |
| 8 | Build gate cannot detect float/page drift | `extract_page_map.py`, `build_artifacts.sh` | Replace `range(1,5)`/`range(1,19)` with counts derived from the markdown (`[[FIGURE_` and `TABLE_CAPTION:` occurrences); assert `page_map["pages"] == len(reader.pages)`; fail the build if any expected float is unlocated | No | **B** | Adding a dummy 19th table makes the build fail rather than silently drop it |
| 9 | Trailing blank page; 42 vs 43 mismatch | `build_report.py` (stray break after References), `page_map.json` regenerated | Remove the trailing page break; rebuild both passes | No | **A** | `pdftotext` page count == `page_map["pages"]` == the number stated in Appendix B/C |
| 10 | Provider-layer factual errors (§10 W-01, W-02) | report L154, L156 | "reconstructs a synthetic assistant payload" instead of "retains the complete assistant payload"; six event types instead of four | No | **A** | `grep -o 'emit("[a-z_]*"' internal/agent/events.go \| sort -u \| wc -l` = 6 and the report agrees |
| 11 | Coverage figure includes the thesis's own analysis package (P1-R2-05) | report L558, L859 | Report 28.4% (all packages) **and** 27.2% (production packages only) | No | **A** | `go test ./... -coverprofile` rerun; both figures derivable from the same profile |
| 12 | PostgreSQL "production target" with no dialect test | report L168 | Downgrade to "implemented but not covered by automated tests" (§10 W-06); optionally add one Postgres-dialect test | No (paper) / No (test) | **A** / **B** | `grep -rn --include="*_test.go" -i postgres internal/store/` currently returns 0 — either the count becomes non-zero or the report matches it |
| 13 | Three `Passed` predicates compared as if identical (§6 item 13) | report VI.D | One paragraph: baseline pass = milestones ∧ zero grounding violations; Team pass additionally requires delegation/contribution/efficiency; the 5/6-vs-5/6 comparison is therefore across non-identical predicates that coincided in r5 | No | **A** | `multiagent.go:538-547` and `:615-616` cited in the text |
| 14 | Two unreachable registrations undisclosed (P1-R2-08) | report L828 | Extend the `load_skill` disclosure to all three unreachable registration paths | No | **A** | Each named path has a `grep` showing no production caller |
| 15 | Missing literature anchors (§11 C-03) | report II/IX + References | Add MAS-failure-mode and single-agent-persona sources, a database concurrency-control source, Coffman et al. 1971 for the wait-for graph, and one human-in-the-loop decision-support source; move [11] from L70 to L316; add an attribution-measurement source (AIS / TRUE) at L70 | No | **B** | Every new entry resolvable to a real venue; anything unconfirmed marked 待核验 |
| 16 | Skill-deletion path taken from a URL segment without validation (S-R2-01) | `internal/setup/handlers_skills.go:48-55`, `:165-178` | Validate `name` against the enumerated installed skills, or `filepath.Clean`-plus-prefix-assert under the skills directory, before `os.RemoveAll`; do not claim path validation in the threat-model table until then | No | **B** | A test asserting `DELETE /api/skills/..%2fx` and a non-existent name both fail closed |
| 17 | Reference [14] ordering + decorative use (§11 C-01, W-07) | report L798, References | Cite [14] against named AI RMF functions, or renumber so first-appearance order holds | No | **A** | First-appearance scan over the body returns a monotone 1…17 |

### P2 — polish

| # | Item | Files | Change | Cost |
|---|---|---|---|---|
| 18 | Cost formula typography + provider asymmetry (W-12) | report L241/L243 | Real subscripts and superscript; note that the cache-read subtraction is set on the OpenAI adapter only | **A** |
| 19 | Abbreviation table incomplete (12 entries) | report L10-21 | Add the initialisms actually used (ACL, API, DSN, FIFO, DFS, JSON-RPC, P50/P95, RQ, WAL, …) | **A** |
| 20 | Figure 4 effective label size ≈5.4 pt | `build_report.py:253-304` | Raise the PIL `_font(19)`/`_font(21)` sizes (**not** matplotlib — the figure is drawn with `ImageDraw`) | **A** |
| 21 | Chapter proportions (W-11) | report I, V | Move ≈300 words of gap/contribution scoping into Chapter I; move implementation enumeration from V to an appendix | **B** |
| 22 | `finance_reanalysis.json` postdates the build | `build_artifacts.sh` | Regenerate the analysis JSON before rendering; record both hashes in the manifest | **A** |
| 23 | P50 explanation names the wrong mechanism (W-03) | report L656 | Name the nearest-rank estimator `int((n−1)q + 0.5)` | **A** |
| 24 | Serenity / Thesis Ledger naming (§8) | report L282, V | One sentence each: Serenity supplies methodology and no data; the Thesis Ledger is a versioned research-thesis record store, not an accounting ledger | **A** |
| 25 | τ-bench row reuses benchmark metric vocabulary (W-13) | report L425 | "τ-bench-inspired", locally authored, locally defined checks — inside the table, not only after it | **A** |
| 26 | Session fail-open consequence (W-14) | report L170 | Add unbounded staleness + the `internal/session` test gap | **A** |
| 27 | "oracle" reused in the Conclusion (W-10) | report L869 | "belongs to the grader rather than to the agent" | **A** |
| 28 | `HookRegistry` has no mutex (S-R2-02) | limitations table | One row; startup-time registration makes it latent, not live | **A** |
| 29 | Serenity hash result under-stated (W-08) | report L282 | "24 of 26 hashes matched; both mismatches are documentation, not executable content or `SKILL.md`" | **A** |
| 30 | `cache_creation` identically zero | report VII | One clause: the cache-write term of the cost formula is unexercised in r5 | **A** |

### Experiments (tier C — the only items that cost money)

| # | Experiment | Prerequisite | Cost | Acceptance |
|---|---|---|---|---|
| E1 | **Human-adjudicated grader validation** | none — uses retained r5 outputs | **A/B (zero model calls)** | κ between the lexical grader and 2 human annotators on all 44 assertions + 18 milestones, with the confusion matrix; do this **first** |
| E2 | Execute the fault suite (`faults_expected > 0`, 3 repetitions) | suite config change only | **C**, low | RQ4 gains a non-zero denominator; observation/attribution/degradation rates reportable |
| E3 | Powered orchestration run: ≥24 untouched cases × 3 repetitions, frozen grader preregistered, pair identifiers retained in the gain guard | E1 (so the grader is validated before scaling) | **C**, medium | Powered for a *large* paired effect (≈25 discordant pairs needed at α=.05/power .80); state explicitly that a modest effect stays undetectable |
| E4 | Retrieval-and-mutation finance track: real finance-tool calls, real ledger mutations, graded on post-state | tenant fixtures + suite work | **C**, medium | `financial_tool_calls > 0`, ledger version increments observable, RQ5 no longer split |
| E5 | Cumulative runtime ablation (Table VII) | E3's harness | **C**, high | The only design that isolates the runtime contribution the Abstract foregrounds; do last |

**Sequencing.** Items 1–2 (P0) then 3–6 and 9–11 (all tier A, one afternoon) then a rebuild; that alone lifts the submission package's integrity. Items 7–8 next, because they protect every subsequent rebuild. E1 before any paid experiment.

---

## 14. Safe Abstract and Conclusion Boundary

### Assessment

**The current Abstract (L7) and Conclusion (L855-871) are already safe, and I do not recommend rewriting them to sound stronger.** This is the most disciplined part of the thesis. Verified against the ten forbidden framings in the review prompt, the Abstract:

- reports 5/6, 5/6, 5/6 vs a routed diagnostic 4/6, then states "the smallest attainable two-sided exact probability is 0.03125; the result is therefore an undetected difference rather than evidence of equivalence" — the correct treatment, and it forecloses the equivalence reading in the same sentence that gives the numbers;
- labels the pooled +12.5-point Team advantage "post hoc" and reports its non-significant p=0.5078 alongside it;
- says the historical 0/8→4/8→8/8 sequence "do[es] not identify a causal runtime effect" **because** evidence visibility and the grader changed with the runtime;
- calls the routed team a "routed-team diagnostic", never an oracle or an upper bound;
- closes with "not superior financial judgment, factual entailment, or investment performance" — three refusals in one clause;
- describes the contribution as "an auditable runtime and evaluation harness whose measurement assumptions can be replayed and challenged".

The Conclusion is equally careful: RQ1 "partially supported… not formal proof or production certification"; RQ2 "remains not determinable"; RQ3 "supported descriptively for one model configuration and pricing table"; RQ4 "unanswered by the primary artifact… empty values rather than evidence of robust coordinator behavior"; RQ5 "supported only after separating two constructs". L869's "transparent negative result" is the right self-characterization.

### What the present evidence permits in the Abstract and Conclusion

1. A multi-tenant Go agent runtime with a bounded streaming turn, per-chat FIFO scheduling, root-level admission, correlated internal request/reply, and transitive wait-graph cycle detection — **implemented, and the concurrency mechanisms have tests**.
2. A four-mode, evidence-matched evaluation harness with error-aware denominators, dual token conventions, and role-attributed cost — **implemented and exercised**.
3. r5's raw counts (5/5/5/4 of 6) with the 0.03125 power bound and the explicit "undetected, not equivalent" reading.
4. The post hoc r2–r5 pooled counts (18/15/16/18 of 24) with their exact paired p-values and the post hoc label.
5. The zero-model-call grader ablation as a *methodological* result: switching one lexical rule moves pass counts by up to 5 of 30 per mode and can reverse the mode ordering, so the orchestration question is not determinable at this suite resolution.
6. Seventeen deterministic finance tools, a typed evidence envelope with `as_of`/`observed_at`, optimistic version control, tenant isolation and event deduplication — **implemented and unit-tested**, not exercised by r5.
7. The corrected OpenAI-compatible ACL as a worked example of complete mediation, with allow/deny/unknown behavioural tests.
8. Reproducibility framed as *replayable analysis over retained artifacts*, with the dirty-snapshot boundary disclosed.

### What must not appear (and currently does not)

- Team ≡ Solo, "statistically equivalent", or "no difference".
- Any statement that multi-agent orchestration improved financial analysis.
- The routed team as an oracle, upper bound, or ceiling.
- Attribution checks described as factual accuracy, entailment, or grounding.
- Any claim that r5 exercised live retrieval, specialist research ability, finance-tool calls, or ledger mutation.
- 0/8→4/8→8/8 as a causal runtime effect.
- Zero fault metrics as evidence of fault tolerance.
- Any investment-performance, alpha, Sharpe, or predictive-accuracy language.
- Full test pass as production safety or completeness.
- The dirty snapshot as exact trajectory reproducibility.
- τ-bench/BFCL-style subsets as official benchmark scores.

### One permitted addition

If anything is added, add the sharpest true sentence the paper has not yet claimed: **the two sensitivity axes point in opposite directions** — pooling r2–r5 raises Team's estimate while the extended-inflection grader switch raises Open-Book's by more (20→25 vs Team 23→27, with the routed diagnostic falling 22→21) — which is a stronger and more interesting statement of undecidability than "not determinable" alone, and it is fully supported by `finance_reanalysis.json`. Beyond that, **no strengthening is warranted, and I would flag any attempt to strengthen these two sections as a regression.**

---

## 15. Defense Questions

Fifteen questions a committee should ask, with what an excellent answer must cover. These are ordered by how much damage a weak answer does.

**Q1. Why is this a runtime contribution and not a model benchmark? If I swapped your coordinator model, would any of your conclusions change?**
Must cover: the four modes hold the model assignment fixed and vary only runtime configuration (delegation on/off, evidence flattening, extra coordinator pass); the runtime supplies prompt assembly, policy-filtered registries, delegation routing, error-aware denominators and the grader, all of which are experimental variables in this design and constants in a model benchmark. Must also concede: RQ3's numbers are for one model pair and one pricing table, so the *magnitudes* would change; the *methodological* result (that a grader switch moves conclusions more than the mode does) is model-independent. The honest answer names the missing evidence: no cross-model replication was run.

**Q2. Team, Open-Book and Two-Pass all passed 5/6. Doesn't that mean orchestration is useless?**
Must cover: at n=6 with one repetition the smallest attainable two-sided exact p is 2/2⁶ = 0.03125, so a zero-point difference is an *undetected* difference, not an equivalence; the per-case matrix shows the modes are not interchangeable (Team 4/4 on thesis invalidation, 0/4 on incomplete screening); and the single Team failure is traceable to grader morphology (`estimated` not folding to `estimate`), not to coordination. Must not say "equivalent". Must state what would settle it: ≥24 cases × 3 repetitions with a preregistered frozen grader.

**Q3. How do you isolate the runtime's contribution from the model's?**
Must cover: honestly — *you currently cannot*. The cumulative ablation (Table VII) that would isolate it is **proposed work**. The historical 0/8→4/8→8/8 sequence cannot serve, because evidence visibility and the grader changed alongside the runtime. What *is* isolated: the grader's contribution, quantified by zero-model-call replay. An answer that claims isolation from the present data fails this question.

**Q4. Your specialists copy compiled evidence fixtures verbatim. What is the scientific value of that?**
Must cover: it makes evidence visibility an experimental control rather than a confound — Team and Open-Book see byte-identical evidence, so any difference is attributable to routing and synthesis, not retrieval luck. The cost is external validity: retrieval, source-authority ranking, conflict arbitration and temporal drift are all removed, so RQ5's scope is "governance wording under ideal evidence". Must name the next experiment (real tool calls, real ledger mutations, graded on post-state).

**Q5. Your grader is lexical. Why should I believe it measures anything?**
Must cover: the paper never claims entailment — L70 defines *evidence attribution* as a link between a claim and a supplied evidence identifier and holds that narrower meaning throughout. Its validity is *bounded* rather than asserted: the negation lookback, hedge suppression, conditional scope, clause-break and morphology rules are each ablated, and the ablation shows the negation rule is load-bearing (removing it drops Team 23→14) while the morphology rule reverses a mode comparison. The correct concession: grader–human agreement has **not** been measured, and doing so on the existing 44 assertions costs zero model calls. That should be the next experiment.

**Q6. 28.4% statement coverage. What can you actually conclude from your tests?**
Must cover: functional feasibility of selected principal paths — authentication, provider parsing, cancellation, tool panic containment, internal calls, task snapshots, store contention, and the corrected ACL — and nothing about completeness, load behavior or security certification. Must also volunteer the non-uniformity: `policy`, `scope`, `session`, `plugin`, `mcp`, `skills` are at 0.0%, and three of those (policy filtering, session normalization, the plugin bridge) are load-bearing in the *design argument*. A candidate who additionally notes that 28.4% includes the thesis's own analysis package (27.2% without it) demonstrates the right instinct.

**Q7. Your primary run came from a dirty working tree. In what sense is it reproducible?**
Must cover: the distinction between *artifact-replay* reproducibility and *execution* reproducibility. The former is achieved and demonstrated — the retained outputs, suite, manifest and four SHA-256 values let anyone recompute every reported number with zero model calls, idempotently. The latter is **not** available: the recorded HEAD `351ee42` plus `dirty_working_tree` does not identify the exact source, and even a clean commit would not fix stochastic model output. The manifest records HEAD, Go version and critical file hashes precisely so the gap is visible rather than hidden. Must not claim exact trajectory reproduction.

**Q8. Why no return backtest? Isn't that the obvious test for a financial system?**
Must cover: four specific missing controls — no point-in-time universe (survivorship bias), no corporate-action handling, no delisting treatment, no transaction-cost or turnover model — plus the absence of a stated investment objective. A backtest built on this data would be look-ahead- and survivorship-biased, and a weak one would undermine the parts of the thesis that hold. The system is positioned as a research copilot; portfolio action is deliberately outside its boundary.

**Q9. Are your security controls complete?**
Must cover: the four-way distinction — implemented **and tested** (auth identity, API-key ACL with allow/deny/unknown tests, tenant-scoped ledger, task filtering, workspace namespacing, trusted `ToolCallContext`, sandbox-required); implemented but **untested** (scope separation, policy filtering, session fail-open — the packages have zero test files); **documented only** (prompt-injection posture — the six-pattern scanner is explicitly an unvalidated heuristic); and **future work** (supply-chain integrity, per-tenant budgets, runtime-enforced human approval). Must also volunteer the two structural facts: `CanAccessAgent` returns `true` on the session path and delegates to handlers, so a new route that forgets the check has no backstop; and skill deletion joins a URL segment into a path before `os.RemoveAll` with no validation.

**Q10. Zero faults were injected in r5, yet you report fault-tolerance metrics. Isn't that misleading?**
Must cover: the report states in both RQ4 answers that the zero rates are *vacuous*, not favourable, and Chapter VI labels the instrument "contributed but not exercised". The contribution is the instrument (bounded simulated faults, error-aware denominators, per-fault rather than per-phrase counting so rates cannot exceed 100%, a simulated-only gate). The concession: RQ4 is the one research question a single additional run can fully resolve, which is why it is high in the remediation plan. A candidate who calls zero faults "good robustness" fails.

**Q11. You call the routed team a diagnostic. Why isn't it an upper bound?**
Must cover: it passed **4/6 — fewer than Team's 5/6** — so it empirically is not a ceiling; routing to a designated specialist removes the coordinator's option to seek additional evidence or to reconcile conflicting inputs, so perfect routing does not imply a better answer. It is a *candidate comparison* that isolates routing choice from routing execution. Must reject any "oracle" framing, including the residual reuse of the word in the Conclusion.

**Q12. Team used 41.6% fewer tokens than Two-Pass by one measure and 33.7% more by another. Which is true?**
Must cover: both, of different quantities. Billable-like = uncached prompt + completion; provider total counts cache-read tokens inside prompt totals. Team's 30 calls carry 27,264 cache-read tokens against Two-Pass's 6,912, so a metric that charges for cache reads reverses the ordering. The report presents the billable measure first because it approximates what is paid, and reports both because they answer different telemetry questions. Must be able to state the accounting identity (`total = prompt + completion`, `cache_read ⊆ prompt`) and that `estimateModelCallCost` subtracts cache reads only when the provider flags them as prompt-included.

**Q13. Why should a committee accept a null result as a contribution?**
Must cover: the contribution is not the null itself but the *demonstration that the instrument cannot decide the question, and why*. Two sensitivity axes are quantified and they point in opposite directions — pooling r2–r5 moves Team up (+12.5 points, p=0.5078), while the extended-inflection grader switch moves Open-Book up more (20→25 vs Team 23→27) and moves the routed diagnostic down (22→21). That is a measurable statement about *evaluation design*, replayable at zero marginal cost, and it generalizes beyond this suite. A candidate who defends the null as "we found no effect" has missed their own strongest result.

**Q14. Which of your fifteen mechanisms is genuinely novel, as opposed to competent engineering?**
Must cover: an honest ranking. Strongest candidate: transitive cross-root wait-graph cycle detection over agent lanes — with the two-root counterexample showing call-path checking is insufficient, an explicit acyclicity invariant, and DFS under the bus mutex. Second: the zero-model-call grader-ablation methodology. Third: the `as_of`/`observed_at` typed evidence envelope as a domain contract. Must also classify the rest as engineering: per-chat FIFO, counting semaphores, WAL pragma normalization, `WithoutCancel` plus two `AfterFunc` edges are all standard patterns correctly applied, and the thesis should not present them as research contributions.

**Q15. What is the single next experiment, and why that one before the others?**
Must cover: **human-adjudicated grader validation on the retained r5 outputs** — 44 grounding assertions and 18 milestones, two annotators, Cohen's κ plus a confusion matrix. Why first: it costs **zero model calls**, and it attacks the threat that presently caps every capability number in the thesis. If κ is low, scaling the suite would have multiplied a measurement error; if κ is high, the lexical grader is defended empirically instead of rhetorically, and only then is a powered run worth paying for. Must be able to justify the *subsequent* sample size from power rather than convention: ≈25 discordant pairs are needed for a large paired effect at α=0.05/power 0.80, implying ≈84 paired observations — hence ≥24 cases × 3 repetitions — while stating plainly that a modest effect would need several hundred and remains out of reach.

---

## Review Closing Statement

This second-round review examined the 976-line Markdown source, the shipped DOCX and PDF, the four build scripts, `finance-runtime-formal-r5.json` and its manifest, `finance_reanalysis.json`, the r1–r4 artifacts, the eval suite YAML, and the production code paths named in the paper's technical claims. Every reported number that could be recomputed from retained artifacts was recomputed, and all of them matched. No model was called, no gateway was started, no cost was incurred, no source file, paper, artifact, DOCX/PDF or git state was modified, and `runtime-benchmark-tenant.json` was never read.

**未发现新的 P0 in the thesis's numbers, statistics, or scientific claims.** The two P0 items raised (`artifact.md` describing a superseded build; five declared hypotheses never resolved) are submission-package integrity defects, both fixable with zero model calls. The single most valuable next action is not a fix to the paper but the human-adjudicated grader validation described in §7 and §13 — the one experiment that costs nothing and can change how every capability number in the thesis should be read.







