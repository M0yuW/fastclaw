# Claude Review Findings: FastClaw Project Report — Thesis-Level Review

审查对象：`project-report/fastclaw_project_report.md`（754 行，11,869 words）
审查依据：`CLAUDE-REVIEW-PROMPT-project-report-thesis.md`
审查日期：2026-08-01
审查轮次：第一轮（只审查、核验、规划；未修改任何文件、未生成 DOCX/PDF、未 commit）
`runtime-benchmark-tenant.json` 全程未读取。

本文件是第一轮审查的完整合并稿。所有分数与结论取终值；过程中我自己两处表述错误已在正文中更正并标注。原 §12（Questions Requiring Author Decision）按作者指示取消，改为 §12「已采用的默认决定」。

---

## 目录

1. Overall Verdict
2. Evidence and Claim Audit（A/B/C/D/E/F 六组，50 条）
3. Thesis Gap Matrix
4. Technology Depth Audit（14 项）
5. Experimental Methodology Audit
6. Academic Style Findings（24 组）
7. Related Work Plan
8. Recommended Thesis Outline
9. Figures, Tables, and Algorithms Plan
10. Exact Expansion Blueprint（P0 18 项 / P1 / P2）
11. Safe Abstract and Conclusion Boundary
12. 已采用的默认决定

---

# 1. Overall Verdict

**档位判定：合格的高质量 Project Report、优秀本科毕业设计的证据基础；尚未达到本科毕业论文，距授课型硕士项目论文有两级差距。**

差距的性质需要说清：不是篇幅，也不是写作水平，而是**测量效度与可复现性**。这份报告的语言克制程度和数字准确程度都高于它的实验所能支撑的结论强度。

| 维度 | 初评 | 终评 | 变动理由 |
|---|---:|---:|---|
| Academic rigor | 5.5 | **5.0** | RQ5 声称测状态转移，实际测散文措辞（A10）；construct validity 比初判更弱 |
| Technical depth | 6.5 | **6.5** | 不变。代码描述准确率约 85%，问题在深度而非正确性 |
| Methodology | 4.0 | **3.0** | r5 零工具调用；证据为编译进的抄写表（A11）；容错指标空真值（A14）；可比性守卫非配对；历史实验有未披露中间运行（A13） |
| Reproducibility | 3.5 | **2.0** | 被审计的套件文件未入版本控制（E1）；全部 artifact 未入库或被 gitignore（E2/E3）；无运行配置（E4）；无回归钉定（E5）；外部未 vendored 依赖（E6） |
| Writing | 6.5 | **6.5** | 不变。语言克制、术语一致；但存在无比较对象的主语、单次观测泛化、implementation 冒充 contribution |
| Citation | 3.5 | **3.0** | IEEE 编号顺序违规（D11）；4 条字段错误（D12）；2 处引用不支撑论点（D13）；最强方法学主张无引用（D14） |
| Visual quality | 4.5 | **4.5** | 不变。3 图不足（论文级需 10–12）；Markdown 中零编号交叉引用；无 TOC/图目录/表目录；Figure 2 缺 MessageBus |

**必须记入的正面事实。** 报告中每一个数字都经独立重算核对为准确：:561–:568 全部四模式的 pass/token/cost/latency、两个 SHA-256、24/54 的执行与定价计数、:493-506 整张历史表、:514 的成本拆分、:202 的 17 工具、:485 的 10 测试、:357-365 九个套件的 case 数——全部 MATCH，无一处算术或抄录错误。24 个 grader 判定被独立重实现的 matcher 逐一复核，**24/24 与 artifact 完全一致**。

报告的诚实度也显著高于同类项目文档：它主动否证了自己的编排优势、主动区分 style subset 与官方 benchmark、主动标注 `r5` 非 holdout。Abstract 的收尾限定、:388 的 validity 规则、§VI-I 明确标注为 proposed 的消融、§VII-D 的 evidence-status 表、§VII-G 的 required-validation 设计、§IX-B 限制 4–6、§X 的 "not superior financial judgment" 均已达到学术诚实标准。§VIII-A 应当被提升进 Introduction 的 research-gap 框架。

问题不在动机，不在细致度。问题是**正确的数字被赋予了实验设计不支持的含义**。

---

# 2. Evidence and Claim Audit

PDF 页码为按章节比例估算（已核验共 20 页），标 ≈。

## 2.1 A 组：事实错误（P0，15 条）

**A1｜`r5` 唯一失败的成因写错。** MD:570（≈p.17）："The bounded assertion grader nevertheless required `source refresh` and the anti-estimation clause to occur within one local assertion window; the answer placed them in separate sections."

代码探针（`package eval` 内直接调用 `containsRequiredAssertion`，探针文件已删除）逐值复核该 case 的 Team 输出：`insufficient_data` → TRUE，`exclude` → TRUE，`source refresh` → **TRUE**。唯一失败值是 `evals/multiagent-finance-runtime.yaml` 中 `'not estimate || instead of estimating'`。模型实际写的是 "must not be imputed, inferred, or estimated"。对同一 matcher："not estimated" → TRUE，"must not be estimated" → TRUE，"no estimation" → TRUE，"not estimate" → **FALSE**。

失败机制是**形态学缺口（estimate / estimated）**，而非距离或窗口问题。`maxAssertionTokenGap = 8`（`internal/eval/multiagent.go:125`）在此 case 上根本没有被触发。MD:654（≈p.19）的第五条 limitation 复制了同一错误诊断。`CLAUDE-REVIEW-RESOLUTION` §3 H8 声称新报告 "quotes its actual grader cause"——该声称不成立。

后果不只是一句话错：报告用这个错误诊断支撑了一条方法学结论（"bounded lexical graders reduce cross-clause false positives but can reject semantically complete answers whose evidence is distributed across sections"）。真实成因指向完全不同的结论——**轻量形态归一化的覆盖面不足**，而这恰好是 `CLAUDE-REVIEW-RESOLUTION` §5 L1/L2 主动收窄过的地方（去掉第二次复数裁剪、豁免 -ss/-is/-us）。L1/L2 的保守修复与 C1/C2 的严格化在这个 case 上互相碰撞了。这是一个真实、可写、有价值的 trade-off 发现，比现在写的假发现好得多。

**A2｜`r5` 记录了两个 grader failure，报告只写了一个。** MD:570 说 "The only Team failure was `incomplete-screening-data`"。`finance-runtime-formal-r5.json` 在该 case 下记录两条：`ma_milestone`（`milestone "decision" was not achieved`）与 `ma_contribution`（`utilized 2/3 specialist contributions`）。对应聚合指标 contribution_utilization = 0.6667、coordination_score = 0.8333。两者根因是同一条 rubric 字符串（该值同时出现在 `decision` milestone 与 finance-governance 的 `contribution_values`）。报告完全省略了 contribution 失败，也没有解释为什么全局 metrics 是 0.9444 / 0.9722（= 5 个 case 满分 + 1 个 case 双扣）。

**A3｜运行配置未记录，且与 suite 声明矛盾。** `evals/multiagent-finance-runtime.yaml` suite defaults 写 `repetitions: 3`（:6）；`internal/eval/multiagent.go:1544-1552` 的解析优先级是 CLI override → case → suite default；`r1`–`r5` 每个 case 实际只有 1 次 attempt，说明使用了未记录的 CLI override。而 `finance-runtime-formal-r5.json` 顶层键只有 `cases, description, duration_ms, finished_at, metrics, source, source_sha256, started_at, suite, version`——**没有任何运行配置**。这直接违反本报告自己的 Appendix B（MD:707-709，≈p.19）与正文 MD:475。**报告的 reproducibility checklist 未被自己的主实验满足**，这在评审眼里是最刺眼的一类矛盾。

**A4｜主结果由未提交代码产生。** `git diff --quiet HEAD -- internal/eval/multiagent.go` → 非零（该文件 +496 行；工作区共 891 insertions / 146 deletions across 11 files）。报告记录 suite SHA-256（MD:551）与 artifact SHA-256（MD:553），但全文无 commit hash、无代码版本、无 Go 版本。给定 grader 是 `r5` 结果的一部分（C1/C2 的修复就发生在这个文件里），`r5` 从任何**已记录**的代码状态都不可复现。这不与"论文正文不写 commit history"的约束冲突——约束禁止的是开发流水账，reproducibility appendix 里的单个 commit hash 是学术规范要求的。

**A5｜历史 0/8 → 8/8 从未在最终 rubric 下重评。** MD:495（≈p.15）表格首行 "Strict task success | 0/8 | 8/8 | +100 pp"，无任何限定。报告在 MD:510 与 MD:520 承认 "string graders rejected equivalent numeric forms" 是 before 失败原因之一，但表格与 Abstract（MD:6）都把 +100pp 当成 runtime 效应呈现。

这一点可以量化。我对金融套件做了对应操作作为方法示范：用当前 grader 重评 `r1`–`r5`，改判 cell 数为 r1: **4**、r2: 1、r3: 2、r4: 1、**r5: 0**。rubric drift 在早期 run 上足以翻转 4 个 cell。历史 8-case before artifact 从未做同样处理，因此 0/8 中有多少是 runtime、多少是 grader，**当前没有答案**。这是全文最醒目数字的最大未验证假设。

**A6｜合并四次冻结套件运行后，pass 计数方向反转。** `r2`–`r5` 具有相同 suite hash（`4fbf54…dc44`）、相同模型配置（Pro coordinator + Flash specialists）、相同 9 calls/case。在**当前唯一 grader** 下合并重评（n=24 per mode）：

| Mode | Passes | Rate | Wilson 95% |
|---|---:|---:|---|
| Solo Open-Book | 15/24 | 62.5% | [42.7, 78.8] |
| Solo Two-Pass | 16/24 | 66.7% | [46.7, 82.0] |
| Team | 18/24 | 75.0% | [55.1, 88.0] |
| Oracle Team | 18/24 | 75.0% | [55.1, 88.0] |

配对精确检验：Team vs Open +6/−3（9 discordant），p = 0.5078，Δ = +12.5pp；Team vs Two-Pass +5/−3，p = 0.7266，Δ = +8.3pp；Team vs Oracle +3/−3，p = 1.0000，Δ = 0.0pp。并入 r1 后（30 cells）：open 66.7%、two_pass 70.0%、team 76.7%、oracle 73.3%。

MD:566 / MD:578 / MD:684 的 "0.0 pp / no measured advantage / tied" headline 与此方向相反。但见 §5.2：这条轴必须与 rubric 词法轴并列呈现，不可单独作为"方向为正"的证据。

**A7｜按 case 的合并模式暴露了单次运行掩盖的结构。** `r2`–`r5`，每格 passes/4：

| Case | Team | Open | Two-Pass | Oracle |
|---|---:|---:|---:|---:|
| thesis-invalidation | 4/4 | 2/4 | — | — |
| portfolio-concentration | 3/4 | 1/4 | — | — |
| earnings-catalyst | 4/4 | 3/4 | — | — |
| duplicate-event | 3/4 | — | — | 2/4 |
| contradictory-primary-evidence | 4/4 | — | — | — |
| incomplete-screening | **0/4** | 3/4 | — | — |

这是全部实验数据中信息量最高的一张表，而它不在报告里。它同时给出三件事：Team 在 thesis-invalidation 与 portfolio-concentration 上稳定优于 Open（正好符合 MD:344 的 H2 预测，是 H2 的第一份真实证据）；Team 在 incomplete-screening 上 **0/4** 的系统性失败即 A1 的形态学缺口，是测量缺陷而非能力缺陷；聚合后的差异由具体机制而非随机波动构成。

**A8｜"44/44 grounding, 0 violations" 弱于表述。** MD:568（≈p.17）："Across each baseline, 44 configured forbidden assertions were evaluated and no violation was recorded."

在 `contradictory-primary-evidence` 上，Team 输出**字面包含**被禁短语 "higher evidentiary weight"（原句 "the filing may carry higher evidentiary weight"），未计违规的原因是 hedge 规则：`hasNegationScope`（`multiagent.go:1292-1341`）中 hedge 集合 {may, might, could, possible, possibly} 在候选断言**之前**出现时抑制违规（`CLAUDE-REVIEW-RESOLUTION` §5 L3 有意设计的行为）。所以 100% 反映的是 hedge 豁免规则的存在，不是该短语的缺席。MD:568 尾句的限定方向对，但需披露**具体有 1 次豁免命中**。

**A9｜Coverage 声称过强。** MD:359（≈p.13）在 "Unit and integration" 层声称覆盖 "Auth, storage, queueing, provider parsing, tool routing, cancellation, tenant isolation, ledger, alerts"。实测总覆盖率 **28.0%**；16 个包 0.0%：`channels, config, cron, daemon, mcp, plugin, policy, privacy, scope, session, skills, toolproviders(+imagegen/tts/websearch), usage, users`。`agent/tools` 6.0%、`gateway` 8.0%、`sandbox` 12.9%、`setup` 14.9%、`store` 31.1%。29 个测试文件 vs 146 个非测试 `.go`。

其中 `policy` 与 `scope` 是 0.0%，而 MD:137 明确把 policy-filtered registry 当成一项设计论证；`session` 是 0.0%，而 MD:160 把 `NormalizeToolResults` 当成正确性机制。论证依赖的模块恰好无测试，这是 P0 而非排版问题。

**A10｜r5 中零次金融工具调用；"state validity" 实际是对散文措辞的检查。** artifact 内全部 18 个 trace event 都是 `spawn_subagent`（18 = 6×3），**没有任何 `finance-tools.*` 调用**。原因在配置：bench coordinator 的 policy preset 是 `delegate-only`（`internal/policy/defaults.go:79-88`，只允许 `spawn_subagent`），specialists 是 `no-tools`（`internal/evaltenant/tenant.go:108-113`）。因此 :417-418、:429-434 与 Appendix A 中 "State validity: exact thesis, watchlist, or alert transition and optimistic-version requirement" 被评的是 **coordinator 最终答案里的状态转移措辞**，而非任何 ledger mutation。SQLite ledger 在本实验中**从未被执行**——它只被 10 个 Python 单元测试触及。

这比"不能外推到 retrieval"更严重：连 **state transition 也未被执行**。RQ5 目前测的是"模型是否写出了正确的状态转移句子"，不是"系统是否正确地转移了状态"。这两件事必须在论文中显式分开。

**A11｜Specialist 证据是编译进二进制的字符串查找表 + 抄写指令。** `internal/evaltenant/tenant.go:340-377` 把 FIN-01…FIN-06 硬编码为每个 specialist 的逐字字符串，经生成的 `SOUL.md`（`specialistSoul`，`:381-411`）注入，指令原文为："You are a controlled benchmark specialist. You have no tools. Do not use outside knowledge… **Copy the matching evidence line below verbatim into evidence.**"

:381 的 team 行说 "three real specialist calls through the runtime"——**调用是真的**，但 §V–VII 全文没有一句说明**证据是 fixture**。`evals/finance-runtime-formal-r5.md:129` 说了（"fixed specialist evidence rather than archived-source retrieval"），项目报告必须搬过来。措辞要准确到"抄写指令"这一层：这不是"固定证据包"，是"指示 specialist 逐字复制预置字符串"，因此 specialist 的语言能力也未被测量。

**A12｜缓存调整后，Team 的效率对比反向。** :566 领头写 "4.17 times as many tokens" 与 "+33.7% more tokens"，只在句尾轻描淡写 "prompt totals include separately reported cache-read tokens"。按计费口径（uncached prompt + completion，即 `usage_trace.go:179-192` 的扣减逻辑）：

| 对比 | 报告口径（total） | 计费口径 | 变化 |
|---|---:|---:|---|
| Team vs Open-Book | 4.17× | 13,955/6,557 = **2.13×** | headline 腰斩 |
| Team vs Two-Pass | **+33.7%** | 13,955/23,910 = **−41.6%** | **符号反转** |

这处修正对报告是**有利**的（Team 的计费 token 比 Two-Pass 少 41.6%），却因口径不当被写成 +33.7% 更贵。同伴文件 `evals/finance-runtime-formal-r5.md:98` 处理得比正文好。正确写法：两个口径并列，计费口径在前。算术根源是 `total = prompt + completion` 且 `cache_read ⊆ prompt`，故 `total_tokens` 对 cache read 双计。

**A13｜历史实验存在一次未披露的中间运行。** `runtime-pilot-optimized.json`（7 月 28 日 12:14，比 v2 早 6 分钟）记录 **4/8** strict success、KPI 0.833、coordination 0.931、contribution 0.862。"optimized" 配置本身经过了迭代，而报告 :493-506 把它呈现为**单一的 before/after 对**。这是选择性报告，必须披露：0/8 → 4/8 → 8/8。

**A14｜r5 的 `faults_expected = 0`，所有容错指标为空真值。** 每个 fault metric 都是 0，不是"表现良好"，是"分母为零"。主 artifact 中的容错指标全部 vacuous，却在 :446-450 与 RQ4 语境下被列出。

**A15｜:416-421 承诺的指标在 :559-570 一个都没报。** §VI-G 列了 state validity、delegation precision/recall、contribution utilization、oracle gap；§VII-E 全部缺失。而 artifact 里都有：`milestone_kpi = 0.9444`（17/18）、`contribution_utilization = 0.9444`、`delegation_precision = 1`、`recall = 1`、`coordination_score = 0.9722`、**oracle gap = 66.7 − 83.3 = −16.7 pp**。最后这个负值是全文最该被解释、却完全缺席的数字。

## 2.2 B 组：证据不足 / 过度声称（P0–P1，12 条）

| # | 位置 | 声称 | 核验结果 |
|---|---|---|---|
| B1 | MD:119（≈p.5） | "A `load_skill` tool also exists" | `internal/agent/tools/load_skill.go:15-17` 声明 `RegisterLoadSkill`，**全仓无任何调用点**；唯一其他引用是 `sdkbridge.go:28` readOnlyTools map 里的 `"load_skill": true`。不可达死代码。 |
| B2 | MD:119 | 从 "agent, team, user, managed, bundled, and extra paths" 发现 SKILL.md（六类） | 实际五类生效；bundled 集合为空。 |
| B3 | MD:119 | "mounts selected directories into a sandbox" | 只挂载两个固定 sandbox 路径；team/extra 目录仅进入 prompt，不挂载。 |
| B4 | MD:109（≈p.4） | "preserving a `RawAssistant` JSON representation"（暗示两 provider 对称） | Anthropic 适配器仅在 thinking block 非空时存储该 block，不是完整 assistant payload。OpenAI 路径才是完整的。 |
| B5 | MD:125（≈p.5） | "a session is reloaded on every access so a request handled by another replica observes the latest persisted history" | `internal/session/manager.go:117-126` 在 store 出错时 **fail-open**：静默返回陈旧内存副本。与 MD:150 "Store failures fail closed"（identity 路径，确为 fail-closed）形成未披露的不一致。多副本一致性声称不成立。 |
| B6 | MD:101（≈p.4） | "Each task has a deadline" | `internal/taskqueue/queue.go:294` 只有一个 queue-wide `q.taskTimeout`；Task 结构无 per-task deadline 字段。 |
| B7 | MD:103 | 把 internal-task 256-slot 与 bus pending cap 表述为同一个界 | 是两个独立的 256：`queue.go:119` `internalSlots` 与 `internal/bus/internal.go:16` `maxInternalPending`。 |
| B8 | MD:105 | "prevents both concurrent-read races and task metadata leakage" | 未限定 super-admin `actAs` 路径。 |
| B9 | MD:634（≈p.19） | "prompt-injection scanning" | 六条正则，**零测试覆盖**（`privacy` 包 0.0%）。列在 "defense in depth" 清单里会被读作已验证控制。 |
| B10 | MD:6 / MD:684 | "A historical eight-case, two-mode experiment **shows** that runtime controls can materially change realized cost and reliability" | 见 A5：未与 grader 效应分离。"shows" 应降为 "is consistent with"。 |
| B11 | MD:26 | "The experimental results in Section VII directly address this question" | §VII 的两个实验都不能回答"同一模型配置下 runtime 是否更可靠"这个因果问题：历史实验混杂 grader，金融实验的自变量是 orchestration mode 而非 runtime 配置。 |
| B12 | MD:382 / MD:606 | `oracle_team` = "perfect-routing synthesis diagnostic" | Oracle 在 r5 为 4/6，低于 Team；pooled 后与 Team 相等。MD:606 已正确指出不能当上界，但 MD:382 的定义句仍暗示它是。两处需一致。 |

## 2.3 C 组：安全（P0，1 条）

**C1｜`/v1/chat/completions` 缺少 agent ACL 检查。** `internal/api/openai.go:348-363` 解析目标 agent 时，未调用 `CanAccessAgent`。后果：一个仅授权 agent A 的 API key，只要**省略** agent 头，即可驱动该 space 的默认 agent B。这与 MD:85（"an API key carries an explicit agent access list"）和 MD:660 直接冲突——MD:660 把它写成了前瞻性建议，实际是一个现存缺口。

论文处理方式：不要藏，也不要写成"已修复"。写进 §Security 的 "identified gaps" 小节，附最小复现步骤，并在 Future Work 列为 P0 修复项。评审对"发现并披露自己系统的授权缺口"的评价，远高于对"清单里少一条"的评价。

## 2.4 D 组：构建、产物与引文（P1–P2，14 条）

| # | 证据 | 问题 |
|---|---|---|
| D1 | `build_report.py:587` `f"{metadata['EMAIL']}  ·  July 2026"` vs MD:549 "1 August 2026" | PDF 页脚日期与正文实验日期矛盾。 |
| D2 | `build_report.py:703` caption + `:716-726` 11 个 step 字符串 | **Algorithm 1 的标题与全部 11 步只存在于生成器**，Markdown 只有 `[[ALGORITHM_1]]` 占位符（MD:133）。违反"Markdown 是唯一正文事实源"：一个正文算法在源文件中不可见、不可 review、不可 diff。 |
| D3 | `build_report.py:613` `WD_ALIGN_PARAGRAPH.LEFT` 对所有 cell | Markdown 的 `---:` 右对齐被静默丢弃；所有数值表左对齐。 |
| D4 | grep TOC / PAGEREF / `w:sdt` → 0 hits；仅 PAGE field | **无目录设施**；无图目录、表目录、缩略语表。35–50 页论文不可接受。 |
| D5 | 图表编号由运行期计数器 + `figure_captions` dict（`:797-801`）分配 | **Markdown 中零编号交叉引用**（无 "Figure 1"/"Table 3" 字样）。任何章节重排都会静默错位；正文无法引用具体图表。 |
| D6 | `build_report.py:633-637` | table widths 仅支持 1/2/3 列。§VI-I ablation 表 6 列、finance 表 4 列均落在未定义分支。 |
| D7 | PDF 视觉 | p7→p8、p12→p13 两处静默表格中断；p15 约 1/3 页空白。`CLAUDE-REVIEW-RESOLUTION:112` 的"无缺陷"声称在论文排版标准下需限定（需 header 重复或 `keep_with_next`）。 |
| D8 | Figure 2（`build_report.py:151-277`） | MessageBus **完全不在图中**，而 MD:166-168 的整段论证围绕 bus 的 wait-graph 展开；"three parallel specialists" 是一个箭头 + 文字标签；箭头不对称。 |
| D9 | 环境 | `build_report.py` 当前跑不起来：python-docx 与 Pillow 缺失，无 PDF 步骤，soffice 不可用。 |
| D10 | 已确认无误 | 三张 PNG 均 2400px 宽（6.95in 下 ≈345 effective DPI，充足）；DOCX `c42d1403…bdad5`、PDF `98f8f5ad…3edba`、20 个 `/Type/Page`、1,063,966 bytes 全部复核一致；`build_report.py` 确实**不再**硬编码结果数字（grep 结果数字 → 0 hits），`CLAUDE-REVIEW-RESOLUTION:74` 成立。 |
| D11 | 首次出现顺序 `[1]@14, [2]@32, [3]@32, [4]@38, [5]@38, [6]@38, [7]@42, [8]@42, [10]@115, [11]@253, [12]@473, [9]@630` | **IEEE 编号顺序违规**。除 `[9]` 外全部升序，说明 NIST 条目是在安全章节起草后被插入列表中段。最小修复：JSON-RPC `[10]→[9]`、BCBS 239 `[11]→[10]`、Wilson `[12]→[11]`、NIST AI RMF `[9]→[12]`，同步改四个正文引用点。 |
| D12 | 逐字段核验 | **四条参考文献字段错误**：[2] MCP 无出版日期的活文档标注裸 "2026"，须加访问日期并钉住规范修订 `2026-07-28`；[3] BFCL 仅引 leaderboard URL，应升级为 ICML 2025 PMLR **267:48371–48392**，且印出的主机 `gorilla.cs.berkeley.edu` **未能验证**，可达官方主机是 `gorilla.eecs.berkeley.edu`；[4] τ-bench 存在归档版本却引 preprint，应为 ICLR 2025 Poster（OpenReview `roNSXZpUDN`）；[10] JSON-RPC 年份应为 2013（规范自报 origin 2010-03-26、updated 2013-01-04）。其余 8 条字段全部准确，含页码与 DOI。 |
| D13 | 引用与论点的匹配 | **两处引用不支撑其所附论点**（比字段错误更重）。(a) :630 的 `[9]` NIST AI RMF 是装饰性的：原文"treats risk management as a lifecycle activity rather than a single filter [9]:"后接九条 FastClaw 控制，冒号暗示该框架背书这九条，但九条中无一条源自 AI RMF；实际对应 Saltzer–Schroeder 的最小权限与 OWASP LLM Top 10 2025 的 LLM01/LLM06/LLM10。(b) :253 的 `[11]` BCBS 239 是类比而非依据：它治理银行内部风险数据聚合与监管报送，且 `observed_at`/`as_of` 的双时间区分**不是 BCBS 239 的概念**，不能让它承担 :251 的双时间形式化。 |
| D14 | :473 | 该段最强的方法学主张（配对 case 级比较、"effect sizes and paired outcome tables are more informative than significance claims"）**完全无引用**，仅有一条 1927 年 Wilson。这是全文最廉价的可信度提升点——见 §7 的 T12 引文簇。 |

## 2.5 E 组：可复现性（P0，6 条）

| # | 发现 | 后果 |
|---|---|---|
| E1 | **被审计的套件文件本身未入版本控制。** `evals/multiagent-finance-runtime.yaml` 在 git status 中是 `??`；只有 `multiagent-finance-workflow.yaml` 已提交 | :551 的哈希锚定的是**任何 commit 中都不存在的文件** |
| E2 | r1–r5 全部 artifact 与 `evals/finance-runtime-formal-r5.md` 均未入库（未被 gitignore，只是从未 add） | 主结果不在仓库历史中 |
| E3 | **两个历史 artifact 被 gitignore**：`git check-ignore -v` → `.gitignore:76:/runtime-*.json` | :493-506 整张表**从干净 clone 无法验证** |
| E4 | artifact 不含 :475 自己要求的运行配置（缺 repetitions、mode list、timeout、execution mode、case filter、endpoint class、pricing date）；套件声明 `repetitions: 3`，实跑 1，override 不可见 | A3 确认 |
| E5 | `multiagent-finance-runtime.yaml` **不在回归钉定中**。`TestLoadBundledMultiAgentSuite`（`internal/eval/multiagent_test.go:409-435`）只钉了 collaboration、runtime-tenant、fault-injection、finance-**workflow** | 全结果的溯源锚点可被静默编辑 |
| E6 | `~/finskills` 是**未 vendored 的外部依赖**（`FINSKILLS_HOME`，默认 `~/finskills`，`plugin.py:1605-1606`）；`test_plugin.py` stub 掉 subprocess | 无任何已提交 fixture 走通真实数据路径 |

harness 自身是可复现的（`go test ./internal/eval/...` 与 10 个 Python 测试均通过）；**实验不是**。这个区分必须写进论文。

## 2.6 F 组：本轮新核实的两条限定

- :219 的 "locally verified and version-pinned" 需限定——Serenity skill 的 `shasum -c SHA256.txt` 为 **24 OK / 2 FAILED**（`./README.md`、`./README.zh-CN.md`），可执行文件与 `SKILL.md` 均通过。应改为 "executable content verified"。
- :402 的 "four specialists" 与 `evals/README.md:13-15` 的 "five-agent" 计数口径不一致（不矛盾，但需统一并说明是否含 coordinator）。

## 2.7 应当删除或移入附录

| 位置 | 处置 |
|---|---|
| MD:551, :553 两个 SHA-256 | 移入 Reproducibility Appendix；正文只留"套件与产物哈希见附录 C"。 |
| MD:483 整段测试命令与包名列表 | 命令进附录；正文保留"覆盖哪些控制路径 + 覆盖率现状"。 |
| MD:572 "The preceding `r1`–`r4` artifacts…" | 内容必须保留（这是诚实性的核心），但改写为 Methodology 的 "calibration / confirmation / holdout 三段划分" 小节，而不是 Results 里的辩解段。 |
| MD:407 "The historical before/after reports were produced on 28 July 2026" | 日期进附录；正文保留"两模式、evidence 不匹配、因此仅作 regression study"。 |
| MD:664-676 Future Work 11 条平铺列表 | 压成 3 组（measurement validity / runtime hardening / financial data foundation），每组 2–3 句论证为何是该优先级。平铺列表读起来像 backlog。 |

## 2.8 依赖关系（决定修复顺序）

- A5 依赖 A4 与 E1–E3（无代码与套件版本无法重评）
- A6/A7 依赖 P0-12 的六开关消融（否则单轴结论仍不完整）
- A10/A11 使 RQ5 的 estimand 必须重新定义，因此 Ch.6/Ch.7/Ch.9 三章的相关段落必须**同批改**，不可分开
- A12 是纯口径修正，无依赖，应最先做（且对报告有利）

---

# 3. Thesis Gap Matrix

| # | 论文要素 | 当前状态 | 严重度 | 缺失内容 | 建议章节 | 所需证据 |
|---|---|---|---|---|---|---|
| 1 | Problem statement | MD:12-16 有，但混入 motivation | 中 | 一段独立、可否证的问题陈述：agent 系统的可靠性瓶颈在 runtime 而非模型，且当前缺少将 runtime 作为实验因子的评测方法 | 1.2 | 无需新证据 |
| 2 | Research gap | 隐含，未成段 | **高** | 明确 gap：现有 benchmark（BFCL/τ-bench/SWE-bench/MultiAgentBench）测模型在给定 harness 下的能力，**不测 harness 本身**；且多 Agent 收益研究普遍缺少 compute-matched baseline | 1.3 + 2.5 | 文献对比表（见 §7） |
| 3 | Related work | 628 words，9/12 引用各 1 次 | **高** | 独立章节 2,200–2,800 words，12 条主线 | Ch.2 | 见 §7 |
| 4 | RQ / hypotheses / operational definitions | RQ1-5 (MD:66-70) 与 H1-5 (MD:343-347) 均在，但 **H1/H3/H5 无对应执行实验**；RQ 与 H 无显式映射 | **高** | RQ×H×metric×artifact 四列映射表；对无实验支撑的假设明确标 "not tested in this work" | 3.4 + 附录 | 见 §5 映射表 |
| 5 | Requirements / threat model | MD:53-60 有 6 条工程需求；**无 threat model** | **高** | 显式威胁模型：攻击面（ingress / model-controlled tool args / plugin subprocess / cross-tenant / sub-agent cycle）、假设、非目标；含 C1 缺口 | 3.2 | `internal/auth`, `internal/scope`, `internal/policy`, `internal/plugin/protocol.go:86-93`, `api/openai.go:348-363` |
| 6 | Architecture | MD:74-125，1,101 words，准确率高 | 中 | 每个组件补 "invariant + 替代方案 + trade-off"；补 layered component 图与 tenant boundary 图 | Ch.4 | 已有代码 |
| 7 | Implementation / algorithms / concurrency | MD:127-182，1,012 words | **高** | Algorithm 1 必须移入 Markdown；补 Algorithm 2（一次 multi-agent attempt）；补 wait-graph cycle detection 的 DFS 伪码与正确性论证 | Ch.5 | `taskqueue/queue.go:71,93,119,286-294`, `bus/internal.go:16,77-84,100-103,195-214` |
| 8 | Financial application design | 2,305 words，本报告最强章节 | 低 | 六个 scenario 各压缩约 20%，腾出的预算给 evidence contract 的形式化（`e` 元组已在 MD:251，可扩成完整 provenance 模型） | Ch.6 | `plugins/finance-tools/plugin.py` |
| 9 | Evaluation methodology | 2,001 words，结构完整 | 中 | 补 rubric versioning 与 calibration/confirmation/holdout 三段划分的**方法论论证**；补 grader 形态学局限的形式化（A1） | Ch.7 | `multiagent.go:125,1153-1174,1292-1341` |
| 10 | Results / error analysis | 1,860 words | **高** | 必须补：双轴敏感性分析（A5/A6）、per-case 矩阵（A7）、双 failure 披露（A2）、hedge 豁免披露（A8）、零工具调用披露（A10）、承诺指标补报（A15） | Ch.8 | 五个 JSON + 当前 grader |
| 11 | Discussion / trade-off | 639 words | **高** | 扩到 1,800–2,200：RQ 逐条回答、orchestration 价值边界（含 A7 的 case 级异质性）、quality–cost Pareto、measurement 与 capability 的可分离性 | Ch.9 | 上述结果 |
| 12 | Security / ethics / limitations | 626 words | 中 | 加 ethics（金融决策支持的责任边界、非投顾声明、数据许可）；加 C1 缺口；限制条目从 8 条重组为按 validity 类型分组 | Ch.10 | — |
| 13 | Reproducibility | Appendix B 是**规范性 checklist**，不是本次运行的**记录** | **高** | 新增 "Reproduction record"：commit、Go 版本、suite SHA、artifact SHA、实际 repetitions、CLI 命令、pricing date、模型端点类别；并解决 E1–E6 | 附录 C | 需重跑或补记录 |
| 14 | Conclusion | 200 words，与 Abstract 高度重叠 | **高** | 扩到 700–900：逐 RQ 给出"证据支持到什么程度"，并明确"本工作证明了 measurement infrastructure，未证明 orchestration 价值" | Ch.12 | — |

---

# 4. Technology Depth Audit

评分标尺：0–3 提及，4–5 描述了行为，6–7 解释了机制，8–10 有替代方案 + invariant + 测试论证。

**T1 Go concurrency（goroutine/channel/mutex/context/sync.Once/semaphore/backpressure）— 当前 6/10**
代码证据：`queue.go:93` `sem chan struct{}`；`:71` `completeOnce sync.Once`；`:119` `internalSlots` 256；`:206` per-chat `make(chan *Task, 100)`；`:286-288` `context.WithCancel(context.WithoutCancel(requestCtx))` + 两个 `context.AfterFunc`。
应补原理：为什么用 counting semaphore 而不是 worker pool（root 执行时长方差大，pool 会 head-of-line block）；`WithoutCancel` + 双 `AfterFunc` 的组合为何必要（要保留 telemetry value 但重建取消边，单用 `WithValue` 会丢取消，单用原 ctx 会让 sub-agent 被父流终止）。
替代方案：`errgroup` with limit / 显式 worker pool / `semaphore.Weighted`。
Trade-off：per-chat channel 容量 100 是静默丢弃阈值还是阻塞点，需说明；`:411` `pruneOldTasks` 从持锁读路径裸 `go` 启动，是可写的一处已知粗糙点。
测试证据缺口：`taskqueue` 无 race 测试记录在报告中（MD:483 只列了 agent / agent-tools / store 三个包）。

**T2 MessageBus 与 TaskQueue — 当前 6.5/10**
代码证据：`bus/internal.go:16` cap；`:77-84` self-call + call-path 拒绝；`:100-103` pending cap；`:117-123` 非阻塞 publish → `ErrInternalBackpressure`；`:195-214` `waitPathExistsLocked` DFS；lane = `owner + ":" + agentID`。
应补原理：**为什么传递闭包检测强于 call-path 检测**——MD:168 说对了结论但没给反例。给一个具体反例：root R1 中 A→B 等待，root R2 中 B→A，两条 call path 各自合法，只有跨 root wait graph 能发现死锁。这是一个可以画图、可以写正确性论证的真实设计点，目前只有一句话。
替代方案：全局锁顺序 / 超时兜底 / 无环性由静态 agent 拓扑保证。
Trade-off：DFS 在持锁下执行，lane 数量上界即代价；256 pending cap 与 SDK 单次 fan-out 宽度无耦合（`CLAUDE-REVIEW-RESOLUTION` §5 L8 的残留风险）。
Invariant：lane 图在任意时刻无环 ⇒ 无 sub-agent 死锁。这条 invariant 应当被显式陈述并配一个测试。

**T3 Agent turn state machine — 当前 7/10（描述最扎实的一项）**
代码证据：`internal/agent/loop.go`、`context.go`、`sdkbridge.go`。
应补：把 MD:135-144 的散文升级为**形式化状态机**（状态集、转移条件、每个转移的持久化副作用），并明确 ReAct 与本 runtime 的差别不是"加了工程"，而是**转移必须可观测且可测试**——这正是 §2 gap 的落点。
Invariant：每个 assistant tool-call block 必有配对 tool result（`NormalizeToolResults` 在 turn 开始与终态持久化前各跑一次）。
测试缺口：`session` 包 0.0% 覆盖，而 normalizer 是这条 invariant 的唯一执行者。

**T4 Provider streaming 与 tool-call protocol — 当前 5.5/10**
应补：content delta / snapshot / error / done 的**语义契约**（谁是权威、丢 delta 如何靠 snapshot 收敛、失败流为何不能产生 false terminal chunk）；两 provider 的 usage 装配差异（OpenAI streaming usage option + fallback vs Anthropic message-start/message-delta 累加）。
必须修正：B4（RawAssistant 非对称）。
Trade-off：请求 streaming usage 会被部分端点拒绝，fallback 路径意味着 usage 可能整体缺失——这对成本核算的影响需要说明（`r5` pricing coverage 100% 是在这条路径成功的前提下）。

**T5 Sub-agent orchestration / dedup / cycle detection / correlation — 当前 7/10**
代码证据：`internal/agent/tools/subagent.go`；production exact `(agentID, task)` dedup vs eval target-only dedup。
应补：两种 dedup 的**estimand 差异**——eval 的 target-only 是为 "at most one delegation per specialist" 的固定契约服务的测量装置，它会掩盖真实 coordinator 的重复委派倾向。MD:170 说了"request-scoped, does not change production semantics"，但没说这对**测量效度**的影响：历史实验的 delegation precision 从 42%→100% 中，有多少来自 dedup 这个测量装置本身？这是 A5 的姊妹问题。

**T6 Multi-tenant auth/authz — 当前 6/10，但含 P0 缺口**
必须补 C1。必须补 threat model。`scope` 包 0.0% 覆盖需披露。
应补：`actAs` 只读放行 + 变更拒绝的实现位置与测试；为什么 fail-closed drop（MD:95）优于 default-tenant fallback——报告这一段写得好（"a convenient 'local user' fallback would convert an authentication failure into cross-tenant data exposure"），可直接进论文，建议扩成完整的 threat-model 条目。

**T7 Policy-filtered tool registry 与 sandbox — 当前 6/10**
代码证据：五 preset（permissive/standard/restricted/no-tools/delegate-only）；`sandboxRequired` 无静默 host fallback；`no-tools` 时同步移除 prompt guidance（MD:154，这是一个好细节，值得升级为设计原则："capability surface 与 prompt advertisement 必须一致，否则模型会尝试不存在的能力并进入恢复回合"）。
Trade-off：registry 过滤发生在 turn 开始，意味着 turn 内策略变更不生效。
测试缺口：`policy` 0.0%、`sandbox` 12.9%。论证依赖的两个模块都近乎无测试——必须在论文里如实写出，并作为 Future Work。

**T8 MCP / JSON-RPC plugin / Skill 架构 — 当前 5/10**
代码证据：`plugin/protocol.go:86-93` `Context ToolCallContext` 作为 `args` 的**兄弟字段**（`:83-87`），由 `tool_adapter.go:38` 从 ctx 而非 args 填充。
应补：这是全报告最值得深挖的安全机制之一。为什么"trusted context 作为 wire sibling"能防止模型伪造 scope——因为模型只能控制 `args` 的内容，而 `context` 由 runtime 在路由**之后**写入，且 plugin 可以拒绝无 context 的调用。给出攻击者视角：模型在 args 里塞 `userId` 也无法影响 plugin 的租户过滤。这段论证目前只有 MD:117 两句。
必须修正：B1/B2/B3。
应补：Skill 全量注入 vs progressive disclosure 的**量化**——一个大 Skill 库注入多少 token、对 context budget 的挤占。可用 `finance-tools` + Serenity 实测，低成本高说服力。
测试缺口：`skills` 0.0%、`mcp` 0.0%、`plugin` 0.0%。

**T9 SQLite WAL / transaction locking / PostgreSQL portability — 当前 7.5/10（最接近论文水准的一项）**
代码证据：`store/database.go:50-52` `url.ParseQuery` 归一化；`:103-109` pragma 名提取；`:79/:82/:85/:88` 四项默认。
应补：`SQLITE_BUSY_SNAPSHOT` 的**机制层解释**——deferred transaction 先取 read snapshot，升级为 write 时若快照已过期，SQLite 返回 BUSY_SNAPSHOT 而**不是**可等待的 BUSY，因此 busy_timeout 无法重试成功；`_txlock=immediate` 让 writer 在事务开始即取写锁，消除升级窗口。MD:123 一句话说对了结论，但这是全项目最好的一个"控制/处理组"实验（`database_integration_test.go` 里有 control/treatment 复现 + 12-worker 写测试），值得一整节 + 一张时序图。
Trade-off：immediate 降低并发写吞吐（所有写事务串行化），换取无 BUSY_SNAPSHOT。这个 trade-off 报告没写。
**新发现**：SQLite WAL 官方文档明确 WAL 要求所有连接位于**同一主机**（不支持网络文件系统）。这对部署叙事是承重的，且当前完全未引用。应进 Ch.5.5，与 `-wal`/`-shm` 备份语义（MD:656 已有，写得对）、缺跨实例锁并列。该主题**无实质学术文献**，不要制造；ARIES/Mohan TODS 1992 是唯一可能的学术锚点，**待核验**。

**T10 Session consistency / workspace isolation — 当前 5/10**
必须修正：B5（fail-open）。这不是小瑕疵：它使 MD:125 的多副本一致性声称失效，也与 identity 路径的 fail-closed 设计（MD:150）不一致。论文里应当把这个**不一致本身**写成一个发现——两条同样重要的持久化读路径采用了相反的失败策略，说明缺少统一的失败策略原则。
应补：workspace 按 agent + 可选 session 命名空间如何防止两个并发 chat 覆盖同名输出（MD:125 有结论无机制）。

**T11 Telemetry / token / cache / cost accounting — 当前 7/10**
代码证据：`usage_trace.go:85-95` `BeginModelCall` 在 mutex 下预留 sequence；`:144-159` Snapshot 按 Sequence 排序；`:179-192` 仅当 `CacheReadIncludedInPrompt` 时从 prompt 扣减 CacheReadTokens。
应补：`total = prompt + completion`、`cache_read ⊆ prompt` ⇒ `total_tokens` 对 cache read **双计**。这是 MD:566 那句"prompt totals include separately reported cache-read tokens"背后的完整算术，应写成显式恒等式，并据此修正 A12。
应补：为什么"reserve sequence at call start"是必要的——完成序 ≠ 调用序，而 coordinator/specialist 归因依赖调用序。
应补：errored call 不进能力成功率分母但进成本账本的**双账本论证**（`CLAUDE-REVIEW-RESOLUTION` §4 M11），MD:349 只写了前半。

**T12 Evaluation harness / grader / baseline design — 当前 6/10，含 P0**
代码证据：`multiagent.go:1115-1121` `multiAgentOutcomePass`（全 milestone 通过 **且** grounding violations == 0）；`:1153-1174` `containsRequiredAssertion`；`:1292-1341` negation/hedge；`:1345` conditional；`:1356` `expectedContainsNegation`；`:1369` clause split；`:1383+` `normalizeMatchText`（`"instead of"→"not"`、`"rather than"→"not"`、`"%"→" percent "`）；`:259` `execution_mode == "runtime"` 时拒绝 fault 注入。
必须修正：A1 的真实成因，并把它升级为一节 "Lexical grader design space and its failure modes"：严格化（C1/C2，防跨句假阳）与宽松化（L1/L2 形态归一，防假阴）是同一个轴上的对立压力，本项目在 `estimate/estimated` 上恰好落在错误一侧。这是本报告能贡献的、最具方法学价值的一个真实发现。
应补三处 grader 行为（均未被记录）：(a) `maxAssertionTokenGap = 8` 是**逐步 gap 而非窗口**（`wordsAppearInOrder:1194` 的 `limit := min(len(actual), actualIndex+maxGap+2)`），N-token 断言可合法横跨约 9(N−1) 个 token；(b) ` and ` 是**硬分句边界**（`forbiddenMatchClauses:1241`），用 "and" 连接的两个词**不可能落在同一 clause 内**；(c) `hasNegationScope` 的 5-token **lookback** 会让同一 clause 内在前的 "exclude"/"reject" 抑制在后的正向词（实测 `req("exclude from ranking, source refresh", "source refresh")` = **False**），是活跃的假阴源。
应补：rubric versioning（`source_sha256`）为何是 evaluation 的一等公民。
应补：四个 baseline 的 estimand（Open = 证据充分下的单次能力；Two-Pass = 补偿 Team 的额外 compute；Team = 编排；Oracle = 完美路由下的合成上界候选）。
应补：三种 `Passed` 定义必须区分——baseline 的 `Passed`（milestones ∧ grounding==0，`:615-616`）、Team attempt 的 `Passed`（额外要求 ma_delegation/ma_contribution/ma_efficiency，`:538-547`）、MD:416 的 "strict case success"（第三个更严的数）。三者在 5/6 上**巧合重合**。`Gfair` 用第一种，内部一致（MD:388 结论正确）。

**T13 Fault injection 与 graceful degradation — 当前 4.5/10（最弱一项）**
代码证据：6-case fault suite 存在（`evals/` 下共 9 个 YAML：bfcl 3、collaboration 3、fault-injection 6、finance-runtime 6、finance-workflow 6、runtime-tenant 8、smoke 4、swebench 3、tau-retail 3）。
**关键缺口**：fault-injection suite 在仓库中没有任何 artifact；且主 artifact `faults_expected = 0`（A14），所以主结果中的容错指标全部 vacuous。RQ4 目前完全建立在 harness 实现之上，无一次真实模型运行。MD:582 承认 "A repeated real-model fault run is still needed"，措辞诚实，但 MD:69 把 RQ4 列为与 RQ1-3 并列的研究问题。
处置：按 §12 采用的默认，RQ4 降级为 "instrument contributed, not exercised"，fault suite 执行写为规格明确的 Future Work。

**T14 Finance plugin / Thesis Ledger / evidence governance — 当前 7/10**
代码证据：17 typed tools（`plugin.py:104`）；`finance.tool.v1` envelope；整数 version + `expected_version` 乐观并发；immutable review；SHA-256 event fingerprint（`:1545-1572`）+ 86,400 s 重复窗口（`:2170`）；shell-free `subprocess.run` 45 s timeout（`:2304-2377`）；tenant rejection（`:2455-2473`）；completeness gate（`:2590-2647`）；10/10 Python 测试通过。
必须补：A10（本实验零工具调用，ledger 未执行）与 A11（证据为编译进的查表 + 抄写指令）。
应补：`observed_at` vs `as_of` 的形式化（MD:253 已有正确直觉），扩成完整 provenance 模型并连到 look-ahead 防护——这是未来 return study 的前置条件，也是与 FinQA/TAT-QA 的**真正差异点**（那两个数据集不建模时点）。注意 D13(b)：不能让 BCBS 239 承担这个形式化。
应补：乐观并发为何优于悲观锁（研究工作流中冲突罕见但代价高，且 stale write 覆盖一个更新的结论是不可接受的静默错误）。
应补：Serenity 的边界（MD:219-221 写得好："cannot make subjective inputs objective"），可直接进论文；但需按 F 组限定 "version-pinned" 的表述。

---

# 5. Experimental Methodology Audit

## 5.1 RQ → Hypothesis → Operational definition → Baseline → Metric → Artifact → 结论

| RQ | Hypothesis | Operational definition | Baseline | Metric | Artifact | 结论状态 |
|---|---|---|---|---|---|---|
| RQ1 运行时正确性 | H1（部分） | 控制路径在正常/中断请求下保持 tenant scope、tool-call 配对、终态流语义、有界执行 | 无（功能验证） | 测试通过/失败 + 覆盖率 | `go test ./...` 通过 | **部分支持**。总覆盖 28.0%；`policy`/`scope`/`session`/`plugin`/`mcp`/`skills` 为 0.0%，而这些恰是三处设计论证的载体 |
| RQ2 编排收益 | H2 | outcome success = 全 milestone 通过 ∧ grounding violations == 0 | `solo_open_book`（fair）、`solo_two_pass`（compute-matched） | `Gfair`、`Gcompute` | `r5`（+ r2–r4） | **不可判定**（见 5.2）。非"无收益"，也非"+12.5pp" |
| RQ3 效率 | H5 | tokens / model calls / P50-P95 latency / estimated cost，模型配置固定 | 历史 before/after；金融四模式 | 上述五项 | 历史 artifact + `r5` | **支持（描述性）**。计费口径下 Team = 2.13× Open、比 Two-Pass 少 41.6%。历史部分混杂 grader 效应且有未披露中间运行；单一 provider、单一定价日 |
| RQ4 容错 | H3 | fault observation / attribution / graceful degradation / unsupported claim rate | — | 四项比率 | **无 artifact**；主 artifact `faults_expected = 0` | **不支持**。全部指标空真值。应从 RQ 降级为 "instrument contributed, not exercised" |
| RQ5 金融工作流效度 | H4 | 精确状态转移 + 政策不变量 + 证据标识符召回 | 四模式 | milestone KPI、grounding、state transition | `r5` | **需重新定义**。实际测的是"最终答案是否写出了要求的状态转移措辞"，不是"系统是否正确转移了状态"——r5 中零次 `finance-tools.*` 调用；ledger 正确性仅由 10 个 Python 单元测试支撑 |

## 5.2 RQ2 的双轴敏感性——本论文真正的方法学贡献

观测到的 pass-count 差异对两条**与 orchestration 无关**的分析选择敏感，且两者方向相反：

| 轴 | 操作 | 结果 |
|---|---|---|
| 样本池 | r2–r5 在当前 grader 下合并（n=24/模式） | Team 75.0 / Open 62.5 / Two-Pass 66.7 / Oracle 75.0；配对差 **+12.5 pp**，exact 双侧 p = 0.5078 |
| rubric 词法 | r5 加一个轻量 `-ed/-ing/-ion` 词干器 | Team 6/6 · Open 6/6 · Two-Pass 6/6 · Oracle 4/6；`Gfair` 与 compute-matched gain 仍 **0.0 pp** |

因此：**"打平"这个结论对该 grader 变更稳健，但各模式的 pass 计数不稳健**；而 pooled 方向为正的信号，我未在 pooled 数据上跑第二轴（这是本次分析自身的局限，必须在论文中承认）。

r5 的五个失败被逐一定位，**全部是表层措辞未命中，输出的决策正确**：

| Case / mode | 未命中的期望词 | 模型实际写的 |
|---|---|---|
| thesis-invalidation / Open | `above 25 percent \|\| exceeding 25 percent`；`invalidate` | "more than 25 % of revenue"；只有 "invalidated"/"invalidation" |
| duplicate-event / Oracle | `do not create a second alert` | "No new alert is created"；"policy dictates no second alert" |
| incomplete-screening / **Team** | `not estimate \|\| instead of estimating` | "No estimation"；"must not be imputed, inferred, or estimated" |
| portfolio-concentration / Two-Pass | `above the 10 percent risk limit \|\| exceeds … \|\| over …` | "exceed**ing** the 10 % risk limit"（备选表里有 `exceeds`，没有 `exceeding`） |
| portfolio-concentration / Oracle | 同上 | "exceeds the risk limit"（缺中间的 "10 percent"） |

**零 grounding 违规、零 delegation/efficiency 失败、零基础设施错误。本实验中没有任何一个失败可归因于推理、路由或状态错误。**

这直接定量化了 MD:598-600 那句 "the runtime is therefore part of the experimental treatment rather than neutral infrastructure"——**并把它从 runtime 扩展到 grader**。这是本论文可贡献的最强命题，且由自己的实验数据支撑：rubric 单独可移动 r1 的 4/6 个 cell，词法单开关可移动 r5 的 3/5 个失败。

## 5.3 三处必须在论文中显式分开的概念

1. **三种 `Passed` 定义**：见 T12。三者在 5/6 上巧合重合。
2. **可比性 ≠ 配对**：`multiAgentBaselinesComparable`（`runner.go:461-466`）只检查 `team.Evaluated == comparator.Evaluated` 与 `Errored == 0`，**代码中不存在 case 级配对**。MD:388 的 "paired attempts" 措辞不当；本审查中的 pooled 配对分析是手工建立的，harness 不提供。（此处更正我此前沿用 MD:388 措辞的表述。）
3. **`maxAssertionTokenGap = 8` 是逐步 gap，不是窗口**：见 T12(a)。（此处更正我此前把它描述为"窗口"的表述；MD:570 的 "one local assertion window" 同样不精确。）

## 5.4 一个必须解释的读者陷阱

MD:568 报告 Team P50 = 21.30 s **高于**均值 19.45 s。原因是近邻秩取整：`index = int((n−1)q + 0.5)`（`runner.go:486-492`），n=6 时 P50 取第 4 小值。六个延迟为 [16536.7, 16952.9, 17884.5, 21297.1, 21521.5, 22493.8] ms。算术正确，但不加一句解释读者会认为数据有误。

## 5.5 当前实验能回答什么

1. runtime 的主要控制路径在单元/集成层面可执行（RQ1，附覆盖率限定）。
2. 在固定证据、固定模型的六个金融 case 上，Team 与两个证据匹配的 Solo baseline 的成功率**差异未达到可检出水平**；Team 的成本/延迟位于 one-pass 与 two-pass 之间（RQ3 的金融部分）。
3. coordinator/specialist 的 token、cost、latency 可被完整归因，54/54 model calls 100% pricing coverage——这是一个真实的、可复现的 measurement 能力。
4. Team 的优势在 case 层面**异质**（A7）。这正是 H2 预测的模式，是本项目对 H2 的第一份真实证据。

## 5.6 当前实验不能回答什么

1. **不能**给出任何统计显著性。n=6 全 discordant 时最小可达 p = 0.0312；5/6 vs 5/6 时 discordant 对很可能为 0，此时 exact McNemar **无定义**，应如实报告这一事实而非给出 p 值。即使 pooled n=24（9 个 discordant pair，McNemar 才有定义），p = 0.5078。
2. **不能**分离 runtime 效应与 grader 效应（历史 0/8→8/8，A5）。
3. **不能**声称 orchestration 无收益，也不能声称有收益（A6 与词法轴方向相反）。
4. **不能**把 `oracle_team` 当理论上界（4/6 < Team 5/6；pooled 相等）。
5. **不能**声称 factual grounding（A8：hedge 豁免命中 1 次）。
6. **不能**回答 RQ4（无 artifact + 零分母）。
7. **不能**外推到 retrieval——固定证据只测编排；且证据是抄写指令下的 fixture（A11）。
8. **不能**声称验证了 state transition 或 ledger 正确性（A10：零工具调用）。
9. **不能**从当前记录复现 `r5`（A3 + A4 + E1–E6）。

## 5.7 论文级实验章节方案（14 项）

1. **Experimental objectives** — 三层：runtime 控制路径可行性（RQ1）；orchestration 的 outcome 与成本效应（RQ2/RQ3）；金融证据治理不变量（RQ5）+ 容错（RQ4，降级）。
2. **RQ / hypotheses** — 保留 RQ1-5；H1/H3/H5 明确标注"未在本工作中检验"。H2 因 A7 首次获得证据，应升级为主假设。
3. **System / model configuration** — coordinator `deepseek/deepseek-v4-pro`、specialists `deepseek/deepseek-v4-flash`、provider endpoint class、pricing table（0.14/0.28/0.0028 与 0.435/0.87/0.003625）与其生效日期、timeout 10m、**commit hash + Go 版本**。
4. **Case construction** — 六个金融 case 到六类机制的映射（MD:322-331 已有，质量高）；明确 case 由作者构造、oracle 在模型执行前固定、证据固定不检索且为抄写 fixture。
5. **变量** — 自变量：execution mode（4 水平）。因变量：outcome pass、milestone KPI、grounding violations、tokens（prompt/cache-read/uncached-prompt/completion/total）、latency、cost。控制变量：模型、证据、grader、timeout、session 隔离、repetition。
6. **Baseline definitions** — 四模式 + estimand（见 T12）；显式说明 `solo_closed_book` 为 legacy evidence-access 诊断，不参与 fair 比较。
7. **Metric formulas** — 全部公式（MD:386-396、:444-448 已有）+ `multiAgentOutcomePass` 的合取定义 + validity 条件（**已评估计数相等 ∧ errors == 0，非 case 级配对**）。
8. **Error / exclusion policy** — errored 不进成功率与 latency 分母、进成本账本（双账本，M11）；配对缺失时 gain 报 N/A。
9. **Statistical analysis** — 配对二值 → exact McNemar / 二项符号检验（并说明 discordant=0 时无定义）；比率 → Wilson 与 Clopper-Pearson；比值 → case-level bootstrap CI；**显式声明检验力**："n=6 时 α=0.05 下最小可达 p=0.0312，需全部 6 例 discordant；本设计不具备检出中等效应的能力。"配以 §7 的 T12 引文簇，把"未做显著性检验"从遗漏转为有文献支撑的方法学选择。
10. **Ablation** — 保留 MD:458-465 的 A0–A5 累积消融（设计合理），必须标 proposed；新增一个**可立即执行**的零成本消融：同一批已有输出在 grader 的**六个开关**（negation / hedge / conditional / clause-gap / plural-morphology / `-ed/-ing/-ion` 词干）下重评，报告每个开关翻转多少 cell。零新模型调用，直接产出双轴敏感性分析所需的全部数据。
11. **Fault-injection study** — 写为 Future Work 规格：跑现有 6-case suite；报告 observation/attribution/degradation/unsupported-claim；明确 simulated 边界（`multiagent.go:259` 拒绝在 runtime 模式注入，故 fault 研究与 real-runtime 研究是两个不同的执行路径，不可混表）。
12. **Case-level qualitative analysis** — A7 矩阵 + 每个失败按 MD:701 的八层分类**加第九层：measurement**。incomplete-screening 属第九层，这是分类体系当前缺的一格。
13. **Threats to validity** — 四类分表：internal（rubric 校准泄漏、代码脏、单次运行、dedup 测量装置影响 delegation precision、pooled 分析为事后）；external（6 case、作者构造、单一 provider、单一模型家族、固定证据）；construct（**state validity 实为散文措辞检查**、**specialist 证据为 fixture**、**faults_expected=0 使容错指标空真值**、lexical grounding ≠ factual accuracy、hedge 豁免、outcome 合取定义使 grounding 与 milestone 不可分、total_tokens 双计 cache read）；conclusion（n=6 检验力、双轴方向相反）。
14. **Reproducibility package** — commit、Go 版本、suite SHA、artifact SHA、完整 CLI（含 repetition override）、pricing date、tenant 配置模板（**不含 key**）、grader 开关矩阵、regrade 脚本；并解决 E1–E6。

---

# 6. Academic Style Findings

区分：**[事实]** = 内容/方法错误，必须改；**[语言]** = 表述不够严谨。共 24 组。

**1. Abstract [事实]**
现："A historical eight-case, two-mode experiment **shows** that runtime controls can materially change realized cost and reliability, but evidence visibility was not matched and the result is treated only as a regression study."
改："In a historical eight-case, two-mode run, strict success rose from 0/8 to 8/8 while total tokens fell 94.2% (1,274,742 → 73,729). Because evidence visibility differed between modes and the output grader was normalised in the same change set, this run is reported as a regression study; **the relative contributions of the runtime and the grader are not separated in this work**."
理由：`shows` 断言了因果；grader 与 runtime 同时变更（A5），因此该运行无法归因。改写把观测（数字）与解释（归因）分开，并显式声明未分离的混杂。

**2. Abstract [事实]**
现："Team, Solo Open-Book, and Solo Two-Pass each passed 5/6 cases (83.3%) … and both fair and compute-matched gains were 0.0 percentage points."
改："…each passed 5/6 cases (83.3%), yielding fair and compute-matched gains of 0.0 pp. **With six paired cases and one repetition, the design cannot detect a difference smaller than a complete reversal of all six pairs (minimum attainable two-sided p = 0.0312); the observed 0.0 pp is therefore consistent with a wide range of true effects and is not evidence of equivalence.**"
理由：0.0pp 目前被当作发现使用（MD:578、:606、:684 三处基于它推论）。加上检验力声明，把它正确地降级为"未检出"。

**3. Introduction [语言]**
现（MD:26）："The central research question is not whether a stronger model can improve a score. It is whether an engineered runtime can make the same model configuration more reliable, cheaper, faster, and easier to diagnose."
改："The present work asks whether runtime-level controls measurably change the outcome, cost, latency, and diagnosability of a fixed model configuration, and whether existing agent benchmarks are able to detect such changes at all."
理由：原句是修辞性对立（"not X, it is Y"），且引入了 RQ1-5 之外的第六个隐含 RQ；"more reliable, cheaper, faster" 四个褒义形容词无比较对象也无度量。改写给出可操作的因变量，并把问题接到 §2 的 research gap 上。

**4. Introduction [事实]**
现（MD:26）："The experimental results in Section VII directly address this question."
改："Section VII reports two runs that bear on this question partially: the historical run varies the runtime but confounds the grader, and the financial confirmation varies the execution mode while holding the runtime fixed. **Neither isolates the runtime as a single factor; the ablation design in Section VII-I is proposed for that purpose.**"
理由：`directly address` 不成立（B11）。改写如实说明两个实验各自的自变量，并把缺口指向已有的 proposed ablation。

**5. Architecture [事实]**
现（MD:101）："Each task has a deadline, state (`pending`, `running`, `done`, `failed`, or `cancelled`), timestamps, result, owner, agent, and observability metadata."
改："Each task carries a state (`pending`, `running`, `done`, `failed`, `cancelled`), timestamps, result, owner, agent, and observability metadata, and executes under **a single queue-wide timeout rather than a per-task deadline**. Per-task deadlines would allow long-running research turns to coexist with short interactive turns and remain future work."
理由：B6 是事实错误；改写同时把它转成一条有价值的设计限制。

**6. Architecture [事实]**
现（MD:125）："In store-backed mode, a session is reloaded on every access so a request handled by another replica observes the latest persisted history."
改："In store-backed mode a session is reloaded on each access. **The reload path fails open: if the store returns an error, the in-memory copy is served instead, so cross-replica freshness is best-effort rather than guaranteed.** This differs from the identity path (Section IV-B), which fails closed. Unifying the two failure policies remains future work."
理由：B5。原句陈述了一个未成立的一致性保证。改写还揭示了一处真实的设计不一致，比原句信息量更高。

**7. Architecture [事实]**
现（MD:119）："A `load_skill` tool also exists, but progressive disclosure is not yet the default."
改："Progressive disclosure is not implemented. **A `load_skill` registration function is present in the source tree but is never invoked, and is therefore unreachable**; the design and its expected context-budget effect are discussed as future work in Section IX-C."
理由：B1。"also exists" 让评审推断存在部分实现。改写如实标为死代码，并把它接到 Limitations。

**8. Evaluation [语言/事实]**
现（MD:359）："Auth, storage, queueing, provider parsing, tool routing, cancellation, tenant isolation, ledger, alerts."
改："Auth, storage, queueing, provider parsing, sub-agent correlation, store contention, ledger, and alerts. **Overall statement coverage is 28.0%; the `policy`, `scope`, `session`, `plugin`, `mcp`, and `skills` packages have no tests, so the corresponding design arguments in Sections III-E, IV-C, and IV-D rest on code inspection rather than executed tests.**"
理由：A9。当前表格声称了未被测试覆盖的能力，且正好覆盖到三处设计论证。主动披露把一个可被评审抓住的漏洞变成一条 limitation。

**9. Evaluation [语言]**
现（MD:388）："A gain is valid only when the two compared modes have equal numbers of successfully evaluated paired attempts."
改："A gain is reported only when both compared modes contribute the same number of successfully evaluated attempts and neither records an error; otherwise it is recorded as not available. **The implemented check compares counts, not cases: `internal/eval/runner.go:461-466` performs no case-level pairing. Any paired analysis in this thesis was constructed manually from stored per-case outcomes and is reported as such. Validity here refers to the comparability of denominators, not to the statistical adequacy of the comparison.**"
理由："valid" 在方法学语境里被读作"结论有效"，而代码里的 `*_valid` 只是分母可比标志；且 "paired" 一词无实现支撑（见 5.3(2)）。

**10. Results [事实]**
现（MD:570）："The bounded assertion grader nevertheless required `source refresh` and the anti-estimation clause to occur within one local assertion window; the answer placed them in separate sections."
改："Value-level re-evaluation of the recorded output shows that `insufficient_data`, `exclude`, and `source refresh` each matched; the single unmatched value was `not estimate || instead of estimating`. The answer stated that missing metrics 'must not be imputed, inferred, or estimated'. **The matcher accepts `not estimated`, `must not be estimated`, and `no estimation`, but not `not estimate` against the inflected form `estimated`; the failure is a morphological gap in the normaliser, not a clause-distance effect.** The lightweight plural/inflection handling had been deliberately narrowed to avoid over-matching, and this case shows the cost of that choice."
理由：A1。原句错误诊断，且用它支撑了一条错误的方法学结论。改写给出可复现的值级证据，并把它接到真实的设计张力（严格化 vs 宽松化）上。

**11. Results [事实]**
现（MD:570）："The only Team failure was `incomplete-screening-data`."
改："`incomplete-screening-data` was the only failing Team case. It produced **two grader failures from a single rubric value**: the `decision` milestone and the finance-governance contribution assertion both require `not estimate || instead of estimating`. Consequently contribution utilisation is 0.667 and the coordination score 0.833 for that case, and 0.944 / 0.972 in aggregate."
理由：A2。原句省略了 artifact 中记录的第二个失败，并使聚合指标 0.9444/0.9722 无法从正文推导。

**12. Results [事实]**
现（MD:568）："Across each baseline, 44 configured forbidden assertions were evaluated and no violation was recorded. This 100% configured grounding accuracy is a lexical assertion check, not proof that every generated statement is entailed by evidence."
改："…no violation was recorded **under the configured rule set**. **One of these clearances is rule-dependent: on `contradictory-primary-evidence` the Team output contains the forbidden phrase 'higher evidentiary weight' within the hedged clause 'the filing may carry higher evidentiary weight', and is cleared because a hedge preceding the candidate suppresses the violation.** The 100% figure therefore reflects both the absence of unhedged violations and the hedge-suppression rule, and is a lexical check rather than an entailment judgement."
理由：A8。原句的限定是抽象的；改写给出具体的、可核验的一个豁免实例，把限定从声明变成证据。

**13. Discussion [事实]**
现（MD:606）："In the frozen confirmation, Team tied both Solo baselines while Oracle underperformed them, so no claim of routing benefit or an oracle upper bound is warranted."
改："In the six-case confirmation Team, Open-Book Solo, and Two-Pass Solo each passed 5/6 and Oracle 4/6. **The observed pass counts are sensitive to two analysis choices unrelated to orchestration and acting in opposite directions. Pooling the four runs that share the frozen suite hash and re-grading them under the final rubric (n = 24 per mode) gives Open-Book 62.5%, Two-Pass 66.7%, Team 75.0%, and Oracle 75.0%, with a paired Team–Open difference of +12.5 pp (6 gains, 3 losses, exact two-sided p = 0.5078). Conversely, adding a single inflectional rule to the grader's normaliser raises Team, Open-Book, and Two-Pass to 6/6 and leaves the gain at 0.0 pp. The orchestration question is therefore not resolvable with this instrument.** No oracle upper bound is warranted in either analysis.
理由：A6 + 词法轴。这是全文最重要的一处改写。它修正了单轴结论、加入了不确定性、并把 pooled 分析显式标为事后（本身是一条必须披露的 threat to internal validity）。

**14. Discussion [语言]**
现（MD:598）："The runtime is therefore part of the experimental treatment rather than neutral infrastructure."
改：保留此句——它是全报告最好的一句论点句。但需紧接证据："This is not only a conceptual claim: re-grading the five financial runs under the final rubric changes 4 outcome cells in `r1`, 1 in `r2`, 2 in `r3`, 1 in `r4`, and 0 in `r5`, so the grader alone can move up to 4/6 of a run's outcome. **The same argument extends from the runtime to the grader.**"
理由：原句是本报告的核心洞见，但目前没有紧邻的量化证据支撑。regrade drift 把一句好的断言变成一条被证据支撑的发现。

**15. Conclusion [语言]**
现（MD:684）："The principal demonstrated contribution is therefore an auditable runtime and evaluation harness—not superior financial judgment."
改："The principal demonstrated contribution is therefore a runtime and an evaluation harness whose measurement decisions are themselves auditable and revisable. **The strongest single piece of evidence for this is negative: the harness detected, localised, and quantified a defect in its own grader, and the corrected rubric changed earlier published outcomes. No claim of superior financial judgement is made or supported.**"
理由：原句的 contribution 表述是"我们做了一个 harness"（implementation as contribution，审查约束明确禁止）。改写把 contribution 定位在**可审计性作为可验证属性**上，并用自我否证作为证据。

**16. Conclusion [事实]**
现（MD:684）："The six-case four-mode confirmation provides the fairer financial comparison: Team tied both evidence-matched Solo baselines at 83.3%, produced no measured collaboration gain…"
改："…provides the evidence-matched comparison. At six cases and one repetition it produced no detectable collaboration gain. **Two sensitivity analyses move the result in opposite directions — pooling four runs raises the Team–Solo difference to +12.5 pp without significance, and one inflectional grader rule reduces it to zero at 6/6 for three of four modes — so the work leaves RQ2 open rather than answered in the negative, and specifies the holdout design required to close it.**"
理由：把"回答为否"改为"未能判定"是本次审查中对结论真实性影响最大的一处修正。"leaves open + specifies the design to close it" 是论文级 Conclusion 的标准写法。

**17. Evaluation / Methodology [事实]**
现（MD:417-418）："State validity: exact thesis, watchlist, or alert transition and optimistic-version requirement."
改："State validity is graded as the presence of required state-transition **wording** in the coordinator's final answer. No ledger mutation occurs during the experiment: the bench coordinator runs under the `delegate-only` policy preset, which admits only `spawn_subagent`, and the specialists run under `no-tools`. All 18 recorded trace events in the confirmation run are `spawn_subagent` calls. The SQLite ledger, optimistic version checks, and alert deduplication are exercised only by the ten plugin unit tests."
理由：A10。原句把一个词法检查表述为状态机验证，是全文最严重的 construct-validity 错配。

**18. Methodology [事实]**
现（MD:381）Team 行："three real specialist calls through the runtime"
改："Three specialist turns execute through the real runtime, but their **evidence is a fixture**: `internal/evaltenant/tenant.go:340-377` compiles a per-specialist lookup table of verbatim evidence lines, injected through a generated `SOUL.md` that instructs the specialist 'You have no tools. Do not use outside knowledge… Copy the matching evidence line below verbatim into evidence.' The experiment therefore measures delegation, correlation, and coordinator synthesis; it measures neither specialist retrieval nor specialist language generation."
理由：A11。"real specialist calls" 对调用为真，但会让读者推断证据处理能力被测量。伴生文件 `evals/finance-runtime-formal-r5.md:129` 已有正确表述，正文必须搬过来。

**19. Results [事实]**
现（MD:566）："Team used 4.17 times as many tokens as Open-Book and 33.7% more tokens than Two-Pass…"（尾句轻描淡写 cache）
改："On billable tokens (uncached prompt plus completion), Team used **2.13×** Open-Book and **41.6% fewer** than Two-Pass. On provider-reported totals, which count cache reads inside prompt tokens, the same comparisons are 4.17× and +33.7%. Both bases are reported because `total_tokens = prompt + completion` while `cache_read ⊆ prompt`, so provider totals double-count cache reads."
理由：A12。这处修正对报告**有利**——Team 的计费成本优于 Two-Pass，却因口径不当被写成更贵。

**20. Results [事实]**
现（MD:493-506 表格，无限定）
改：表格加脚注："The optimized configuration was itself iterated: an intermediate run six minutes before the reported one recorded 4/8 strict success, milestone KPI 0.833, coordination 0.931, and contribution 0.862. The table therefore reports the endpoints of a 0/8 → 4/8 → 8/8 sequence, not a single before/after pair. Neither artifact is present in a clean clone (`.gitignore:76` excludes `/runtime-*.json`)."
理由：A13 + E3。单一 before/after 呈现构成选择性报告。

**21. Results [事实]**
现（MD:568 容错相关表述与 :446-450 的 unsupported-claim 指标）
改："The confirmation suite declares no faults (`faults_expected = 0`), so every fault-observation, fault-attribution, graceful-degradation, and unsupported-claim value in this run is **vacuous rather than favourable**. The six-case fault-injection suite exists in `evals/` but has not been executed against a live model, so RQ4 rests on harness implementation only."
理由：A14。零分母指标被列在 RQ4 语境下会被读作容错证据。

**22. Results [事实]**
现（MD:559-570 完全未报 §VI-G 承诺的指标）
改：补一段："Milestone KPI was 0.944 (17/18), contribution utilisation 0.944, delegation precision 1.000, recall 1.000, and the coordination score 0.972. The oracle gap was **−16.7 pp**: the perfect-routing diagnostic scored below Team (4/6 vs 5/6). Both Oracle failures were lexical-surface misses on correct decisions, so the inversion reflects grader lexicon rather than a routing effect and confirms that `oracle_team` cannot be interpreted as an upper bound."
理由：A15。承诺却不报是评审最容易抓的一类缺陷；而 −16.7 pp 是全文最该被解释的数字。

**23. Results [语言]**
现（MD:568）：直接并列 mean 19.45 s 与 P50 21.30 s，无解释。
改：加一句 "Percentiles use nearest-rank selection with rounding (`index = ⌊(n−1)q + 0.5⌋`); with six observations the median therefore selects the fourth-smallest latency, which exceeds the arithmetic mean."
理由：5.4。算术正确但反直觉，不加解释读者会怀疑数据有误。

**24. Reproducibility [事实]**
现（Appendix B 为规范性 checklist）
改：新增记录段："The suite file audited in this thesis (`evals/multiagent-finance-runtime.yaml`) and all five financial artifacts are untracked in git; the two historical artifacts are excluded by `.gitignore:76`. The SHA-256 recorded in Section VII therefore pins a file that exists in no commit. The suite is also absent from the regression pin in `internal/eval/multiagent_test.go:409-435`, which fixes case counts for four other suites only. The harness is reproducible — `go test ./internal/eval/...` and the ten plugin tests pass — **the experiment is not**."
理由：E1–E6。这段自我披露把一个致命缺陷转成一条被记录的限制；隐瞒则是评审必然发现的问题。

---

# 7. Related Work Plan

当前报告只有 12 条参考文献，且无独立 Related Work 章节（相关讨论散落在 §II 与 §VIII）。目标 **≈46 条**，落在 30–50 区间内，无填充。

下表中 **[已核验]** = 作者/题名/年份/venue/DOI 已逐字段确认，可直接写入；**[待核验]** = 写入前须逐条确认，无法确认则以描述性方式提及研究方向而不给引用。

| # | 主题 | 建议 primary source | 该工作解决什么 | 与 FastClaw 的共同点 | FastClaw 的差异 / 研究空白 | 放置 |
|---|---|---|---|---|---|---|
| 1 | ReAct 与 tool-augmented LM | ReAct（ICLR 2023，已在 `[1]`）[已核验]；Toolformer arXiv:2302.04761 [待核验 venue]；MCP 规范 rev 2026-07-28 [已核验，须加访问日期] | 交错推理与动作；工具调用的自监督学习；工具互操作协议 | 一个 turn 就是 reasoning–action–observation | ReAct 是 prompting 策略，FastClaw 把它实现为**带持久化、取消、panic 隔离、遥测的生产状态机**——这是论文的主要技术区分点 | Background |
| 2 | Agent runtime / agent OS | AIOS，arXiv:2403.16971，**COLM 2025 full paper** [已核验]；CAMEL，**NeurIPS 2023**，arXiv:2303.17760 [已核验]；MetaGPT，**ICLR 2024** [已核验]；AutoGen [待核验 venue，OpenReview 有三个 forum ID]；LangGraph 官方文档 `docs.langchain.com/oss/python/langgraph/overview` [已核验；旧 `langchain-ai.github.io` URL 现为重定向提示页，**不得引用**] | 把 agent 编排提升为系统层关注点：调度、内存、工具、状态图 | MessageBus + TaskQueue + 租户所有权 | 这些工作提出编排抽象但**不把 runtime 当作实验变量测量**；FastClaw 的 novelty (ii) 正在此处 | Related Work（核心一节） |
| 3 | 多 Agent 协作与其怀疑性证据 | Cemri et al., "Why Do Multi-Agent LLM Systems Fail?", arXiv:2503.13657 [已核验]；Wang et al., "Beyond Frameworks: Unpacking Collaboration Strategies in Multi-Agent Systems," **ACL 2025, pp. 21361–21375** [已核验]；AgentVerse，**ICLR 2024 Poster** [已核验]；Self-Consistency，**ICLR 2023** [已核验]；Du et al. multi-agent debate [待核验] | 角色分工是否真的带来收益；失败模式分类；采样多样性作为替代解释 | 本项目正是在测同一个问题 | **这是全文最重要的对话对象**：Cemri 等的角色不是"解释一个 null"，而是"解释为何在此样本量与此 grader 下无法判定"；Self-Consistency 是 Two-Pass 基线的理论依据 | Related Work + Discussion |
| 4 | Benchmark 与评测方法 | BFCL，**ICML 2025, PMLR 267:48371–48392** [已核验，替换现 `[3]` 的裸 leaderboard URL；注意可达主机是 `gorilla.eecs.berkeley.edu`]；τ-bench，**ICLR 2025 Poster**，OpenReview `roNSXZpUDN` [已核验，替换现 `[4]` preprint]；SWE-bench（`[5]`）[已核验]；MultiAgentBench（`[6]`）[已核验]；AgentBench **ICLR 2024** [已核验]；WebArena **ICLR 2024 Poster** [已核验]；GAIA [待核验] | 函数调用正确性、政策遵循、真实仓库补丁、多 agent 协作评分 | FastClaw 的四个 style layer 直接对应 | 必须明确写成 **style subset, not official scores**；FastClaw 增加的是 evidence-visibility-matched 基线协议，这是 novelty (i) | Related Work + Ch.7 |
| 5 | Rubric grader 的合法性 | MT-Bench / Chatbot Arena，**NeurIPS 2023 D&B Track** [已核验] | 用 rubric/judge 而非精确匹配评开放式输出 | 本项目用词法 rubric | LLM-as-judge 引入模型方差；FastClaw 选择确定性词法 rubric 换取可复现性，代价是 A1 类形态学假阴——**这条 trade-off 必须成为 Ch.7 的一节** | Ch.7 Methodology |
| 6 | 小样本配对统计（新增 T12 引文簇） | Wilson，**J. Am. Stat. Assoc. 22(158):209–212, 1927**（现 `[12]`）[已核验]；Brown, Cai & DasGupta，**Statistical Science 16(2):101–133, 2001** [已核验]；McNemar，**Psychometrika 12(2):153–157, 1947**，DOI 10.1007/BF02295996 [已核验]；Efron，**Ann. Statist. 7(1):1–26, 1979** [待核验一次文献记录]；Dror et al.，**ACL 2018, pp. 1383–1392**，DOI 10.18653/v1/P18-1128 [已核验] | 二项区间的正确构造；配对二分设计的精确检验；bootstrap；NLP 中的显著性实践 | 本项目 n=6/n=24 的配对设计 | 把"我们未做显著性检验"从**遗漏**转为**有文献支撑的方法学选择**；须写明：5/6 vs 5/6 时 discordant pair 很可能为 0，exact McNemar **无定义**，这正是必须报告 pooled 敏感性分析的技术理由（pooled n=24 有 9 个 discordant pair，检验才有定义） | Ch.7 §统计计划 |
| 7 | 故障注入与韧性 | Basiri et al., Chaos Engineering，**IEEE Software 33(3):35–41, 2016**，DOI 10.1109/MS.2016.60 [已核验] | 在生产中主动注入故障以验证韧性 | `evals/` 的 fault-injection 套件 | Chaos Engineering 作用于真实基础设施；FastClaw 的注入是 **harness 层模拟**，且 `faults_expected=0` 使主 artifact 中该维度为空真值——必须如实写 | Ch.7 §故障注入 + Ch.10 |
| 8 | 可观测性与成本归因 | Dapper，**Google Technical Report dapper-2010-1, 2010**（须如实标注为技术报告，非会议论文）[已核验]；OpenTelemetry Specification **v1.59.0** [已核验] | 分布式追踪；遥测语义约定 | correlation ID、call path、per-tool latency、coordinator/specialist token 分解 | 这是 **novelty 四项中最弱的一项**（自 Dapper 2010 起即为标准工程），只能作为使结论可操作的 enabler，不得作为独立贡献 | Ch.5 §可观测性 |
| 9 | 多租户隔离与最小权限 | Saltzer & Schroeder，Proc. IEEE 63(9), 1975 [待核验一次文献记录；四个独立二次源一致]；OWASP Top 10 for LLM Applications **2025**（LLM01/LLM06/LLM08/LLM10）[已核验，**必须写版本号**——v1.1 (2023) 编号不同]；MCP Safety Audit，arXiv:2504.03767 [已核验]；Greshake et al. indirect prompt injection [待核验 venue] | 最小权限原则；LLM 应用威胁分类；MCP 特有攻击面 | policy-filtered registry、trusted `ToolCallContext`、sandbox required | **报告 :630 的九条控制实际对应 Saltzer–Schroeder 与 OWASP LLM01/06/10，而非现引的 NIST AI RMF**（D13）；policy-filtered registry 的核心论点"能力不在上下文中即不可被诱导调用"应引 LLM01 | Ch.3 threat model + Ch.10 |
| 10 | 金融推理数据集 | FinQA（`[7]`）[已核验]；TAT-QA（`[8]`）[已核验]；FinBen [待核验页码]；BloombergGPT [无 venue，preprint，须标注] | 数值推理、混合表格文本 QA、金融 LLM 评测 | 六个金融 case | 这些测 **QA 正确性**；FastClaw 测 **evidence contract 遵循与状态治理**，且在 r5 中连状态转移都未执行（A10）——差异必须写清，否则读者会期待 QA 分数 | Related Work + Ch.6 |
| 11 | 溯源、归因与数据质量 | RAG，**NeurIPS 2020** [已核验]；Rashkin et al., "Measuring Attribution in Natural Language Generation Models," **Computational Linguistics 49(4):777–840, 2023**，DOI 10.1162/coli_a_00486 [已核验]；PROV-DM，**W3C Recommendation, 30 April 2013** [已核验]；BCBS 239（现 `[11]`）[已核验] | 检索增强生成；归因的可测量定义；溯源数据模型；银行风险数据聚合原则 | `finance.tool.v1` envelope、as-of 强制、forbidden assertion | **术语建议：采用 Rashkin 的规范术语 `attribution` 替换报告中非正式的 "grounding"**，同时提升引用质量与 construct validity 表述精度。PROV-DM **事后描述**溯源且不门控执行；FastClaw 在 tool-call 边界**强制**该元组，使 completeness/freshness 在模型看到证据之前即可机检 —— 这是 novelty (iii) 的准确表述。BCBS 239 须写成**类比**，且 `observed_at`/`as_of` 双时间**不是** BCBS 239 概念（D13） | Related Work + Ch.6 |
| 12 | Human-in-the-loop 金融决策 | Amershi et al., **CHI 2019**，DOI 10.1145/3290605.3300233（18 条指南）[已核验]；Dietvorst, Simmons & Massey, algorithm aversion, **JEP: General 144(1):114–126, 2015** [已核验]；Diakopoulos, **CACM 59(2):56–62, 2016** [DOI 待核验] | 人机交互设计准则；人对算法建议的排斥；算法问责 | "research copilot, not autotrader" 的定位 | 报告目前把这个定位当作免责声明；有了这三条它就成为**有文献依据的设计决策**（immutable review、as-of 披露、不可跳过的人类判断） | Ch.3 design principles + Ch.10 Ethics |
| 13 | 嵌入式数据库并发（工程背景） | SQLite WAL 官方文档 [已核验] | WAL 的并发模型与限制 | `_txlock=immediate`、busy_timeout、WAL sidecar | **WAL 明确要求所有连接位于同一主机（不支持网络文件系统）**——这条对部署叙事是承重的且当前完全未引用。该主题**无实质学术文献，不要制造**；ARIES/Mohan, TODS 1992 是唯一可能的学术锚点 [待核验] | Ch.4 §持久化 + Ch.5.5 |

**两条不得使用**：Wang & Strong 1996 数据质量维度（三次核验尝试失败，须图书馆核对后方可印）；OpenAI function-calling 官方文档（跨主机 301 后目标 403，不得凭记忆引用）。

**引用完整性缺陷（须与 §2.4 D11–D14 同步修复）**：IEEE 编号顺序违规（首次出现顺序为 `[1]@14, [2]@32, [3]@32, [4]@38, [5]@38, [6]@38, [7]@42, [8]@42, [10]@115, [11]@253, [12]@473, [9]@630`；最小修复为 JSON-RPC `[10]→[9]`、BCBS 239 `[11]→[10]`、Wilson `[12]→[11]`、NIST AI RMF `[9]→[12]`，同步改四个正文引用点）；四条字段错误（MCP 裸年份、BFCL 仅 leaderboard、τ-bench 引 preprint、JSON-RPC 年份应为 2013 或 "2010, updated 2013-01-04"）；两处引用不支撑其论点（:630 NIST 装饰性、:253 BCBS 239 类比越界）；:473 全文最强的方法学主张目前只有一条 1927 年 Wilson 支撑——第 6 行的引文簇正是为此。

**引文核验的一条元备注**：核验过程中，若干被抓取的外部页面含有注入文本，声称自身为另一助手身份并质疑其指令。这类内容按不可信页面数据处理并忽略是正确处置；它也说明引文核验涉及的外部页面不能无条件信任。此事不进论文正文，但可作为 Ch.10 安全一章中 indirect prompt injection 的一条第一手观察（若写入，须标为轶事性观察而非受控实验）。

**Novelty 的四个诚实档位**（可直接进 Ch.1 contributions 与 Ch.9）：
1. **证据可见性匹配的三基线协议** — 最强，达 MSc/优秀本科论文级方法学贡献。可辩护表述："a three-baseline protocol that separates evidence access, additional inference compute, and orchestration structure, applied to a workflow where all three are otherwise conflated." **不可声称发明了 matched baseline**。`oracle_team` 是最弱一条腿（4/6 低于 Team），须显式报告这一反转。
2. **Runtime 作为实验处理** — 真实但仅为 framing，不是结果。**不得称为新评测范式**。其量化证据是 regrade drift 与双轴敏感性。
3. **`finance.tool.v1` envelope + 版本化 Thesis Ledger** — 组合层面中等新颖。避免 "evidence governance framework"（高估了一个 struct 加一个版本列）；改用 "an implementation pattern for enforcing evidence contracts at the runtime boundary rather than auditing them post hoc"，并把 as-of 强制明确命名为 **leakage control**。
4. **coordinator/specialist 成本归因** — 最弱，标准工程，仅作 enabler。可保留的真正价值是"多 Agent 文献几乎从不报告单位收益的成本"，但口号须从 "we report the price of the null" 改为 **"the price of a difference this suite cannot resolve"**。

---

# 8. Recommended Thesis Outline

当前 11,869 words / 754 行，IEEE 会议式 §I–§X 结构。目标 **14,000–16,000 words 正文，40–44 页**（附录与参考文献另计）。注意：**扩写量不大（+2,100~4,100 words），但需要大幅重排**——当前结构把方法学、结果与讨论压在三个短节里，而把实现细节铺得过开。

## 8.1 推荐章节树

| 章 | 标题 | 词数 | 核心论点 | 从当前报告迁入 | 必须新增 | 删除/移附录 |
|---|---|---:|---|---|---|---|
| 1 | Introduction | 1,100 | agent 系统的可靠性与成本由 runtime 决定，而现有 benchmark 无法检测 runtime 效应 | §I（:14-28）、§VIII-A 的 gap 论述（**应提升为本章的 research gap，这是全报告最好的一段**） | problem statement 与 research gap 分离；contributions 按 §7 四档位写；thesis organization | "not whether a stronger model…" 的修辞对立（改写 3） |
| 2 | Background and Related Work | 2,000 | 三条文献线（agent runtime、多 agent 收益的怀疑性证据、evidence governance）各自留下的空白正是本文的 RQ | §II 的 ReAct/MCP 段 | **全新章节**，按 §7 的 13 个主题；须有一段明确的"本文与 Cemri et al. 的关系" | — |
| 3 | Requirements, Threat Model, and Research Method | 1,300 | 设计原则来自威胁模型与 evidence 需求，而非工程偏好 | §III-A/B 的需求片段、§IX 的安全段 | 功能/非功能需求表；**完整 threat model**（模型伪造 scope、越权 tool、间接注入、租户越界、C1）；design principles（fail-closed identity、capability-not-prompt、no silent fallback）；research design（自变量/因变量/控制变量） | — |
| 4 | FastClaw Architecture | 1,900 | 分层与租户边界是所有后续保证的前提 | §III 大部、§IV-A/B | 一个 turn 的状态机**完整叙述**（identity → prompt → session repair → streaming → tool → persist）；SQLite 事务竞争的机制解释（deferred upgrade → `SQLITE_BUSY_SNAPSHOT` → 为何 busy_timeout 无效 → `_txlock=immediate` 的代价）；session 失败策略与 identity 失败策略的不一致（改写 6） | tool 清单细节移 App B；`load_skill` 死代码如实标注（改写 7） |
| 5 | Multi-Agent Runtime Design and Implementation | 2,000 | 委派协议的正确性依赖一组可枚举的 invariant，而非"编排框架" | §IV-C/D、§V | correlation ID / root execution ID / call path 的 invariant 列表；cycle detection 的 wait-graph 算法（含 `owner:agent` lane）；`sync.Once` 恰一次完成；`context.WithoutCancel` + 双 `AfterFunc` 的取消语义；per-chat FIFO + root semaphore + 256-slot internal capacity 的背压推导；production `(agentID, task)` dedup 与 eval target-only dedup 的**语义差异**；per-task deadline 缺失（改写 5） | — |
| 6 | Evidence-Grounded Financial Research Application | 1,600（原计划 −200） | evidence contract 在 tool-call 边界强制执行，因此 completeness/freshness 在模型看到证据之前即可机检 | §VI-A~F | `as_of` vs `observed_at` 双时间的形式化（**不引 BCBS 239 作为依据，只作类比**）；as-of 强制命名为 **leakage control**；六个 case 到六种失效模式的映射表；Serenity Skill 的方法论作用与其**不能替代真实数据源**的边界；`shasum -c` 24 OK / 2 FAILED 的如实限定 | 工具参数细节移 App B |
| 7 | Evaluation Methodology | 2,300（原计划 +300） | 评测仪器本身是实验处理的一部分，因此仪器的设计空间必须与结果一并报告 | §VI-G、§VII-A 的定义片段 | 五基线的 estimand 精确定义；`Gfair`/compute-matched 公式与 **counts-only（非配对）** valid 条件（改写 9）；**三种 `Passed` 定义的区分**；grader 内部机制一节（per-step gap ≈9(N−1)、` and ` 硬分句、negation 5-token lookback 假阴、hedge 抑制、conditional scope、`expectedContainsNegation`、normalizer 缺 `-ed/-ing/-ion`）；rubric grader 对 LLM-judge 的 trade-off（引 MT-Bench）；统计计划（Wilson、exact McNemar 的**无定义条件**、bootstrap，引 §7 第 6 行簇）；三概念分离（static fixture / real runtime call / live retrieval） | benchmark style 的营销式表述 |
| 8 | Experimental Results | 2,300（原计划 +400） | 每个数字都正确；每个数字的**含义**都比报告当前赋予的更窄 | §VII 全部 | 双基准 token 表（计费口径在前，改写 19）；三点历史序列 0/8→4/8→8/8（改写 20）；六个未报指标含 oracle gap −16.7 pp（改写 22）；**零工具调用与 trace-event 组成**（改写 17）；specialist fixture 披露（改写 18）；`faults_expected=0` 的空真值声明（改写 21）；五个失败的期望词 vs 实际措辞表；P50>mean 的成因（改写 23）；**双轴敏感性分析表** | commit/PR/机器人评审流水账（若有）；artifact SHA 移 App C |
| 9 | Discussion | 1,500（原计划 −200） | RQ2 在本仪器下不可判定，而这个不可判定性本身是可量化的发现 | §VIII | 逐 RQ 回答（RQ1 部分肯定但混杂 grader；RQ2 **不可判定 + 判定所需设计**；RQ3 双口径；RQ4 harness-only；RQ5 wording-only）；"runtime is part of the treatment" 紧邻 regrade drift 证据（改写 14）；pooled 分析须显式标为**事后**（一条 internal validity threat） | 结论性形容词 |
| 10 | Security, Ethics, and Limitations | 1,200（原计划 +200） | 限制不是免责，是研究结果的边界条件 | §IX | C1（`internal/api/openai.go:348-363` 缺 `CanAccessAgent`）**必须披露并列为 Future Work**；四类 validity threats 表；human-in-the-loop 的文献依据（改写 12 项引文）；28.0% 覆盖率与六个无测试包（改写 8） | — |
| 11 | Future Work | 700 | 判定 RQ2 所需的最小设计是可枚举的 | §X 片段 | 24-case holdout（3 rep × 8 case，预注册 rubric）；六开关 grader ablation；fault suite 实跑；progressive disclosure；per-task deadline；PostgreSQL 与跨实例锁 | 与 Limitations 重复的段 |
| 12 | Conclusion | 600 | 主贡献是**测量决策本身可审计**，证据是 harness 否证了自己的 grader | §X | 改写 15、16 | 摘要复述 |
| App A | Case Specifications | — | 六个 case 的 rubric 全文 | §VII 附表 | 明确标注 State checks 为 **wording checks** | — |
| App B | Metric Definitions and Tool Catalogue | — | 17 工具签名、10 指标公式 | 正文迁出 | — | — |
| App C | Reproducibility Package | —（原计划 +300） | 从干净 clone 可复现的最小集 | Appendix B | 完整 CLI（含 repetition override）、Go 版本、suite SHA、artifact SHA、pricing date、tenant 模板（**不含 key**）、grader 开关矩阵、regrade 脚本；**E1–E6 的如实记录**（改写 24） | — |
| App D | Selected Source Listings | — | 状态机、cycle detection、matcher 的关键片段 | — | — | — |

## 8.2 章节逻辑链

Ch.1 提出"runtime 效应无法被现有 benchmark 检测" → Ch.2 用三条文献线证明该空白真实存在 → Ch.3 把空白转成需求与威胁模型 → Ch.4–5 给出满足这些需求的实现及其 invariant → Ch.6 把通用 runtime 特化到一个 evidence 约束强的领域 → Ch.7 设计能够检测 runtime 效应的仪器 → Ch.8 报告仪器的输出**以及仪器自身的敏感性** → Ch.9 发现仪器的分辨率不足以判定 RQ2，并证明这一发现正是 Ch.1 论点的定量形式 → Ch.10 界定边界 → Ch.11 给出判定所需的最小设计 → Ch.12 收束到"可审计性"这一唯一被证据支撑的贡献。

这条链的关键性质：**Ch.8 的负面结果不是论文的弱点，而是 Ch.1 论点的证明**。当前报告的结构没有让这条链闭合——§VIII-A 已经写出了正确的论点，但它被放在 Discussion 里当作事后反思，而不是放在 Introduction 里当作 research gap。这一处重排是整个大纲中收益最高的单项改动。

---

# 9. Figures, Tables, and Algorithms Plan

当前三张图（architecture、multiagent sequence、finance workflow）覆盖了"系统长什么样"，未覆盖"系统如何运转"与"实验如何得出结论"。

## P0（论文成立所必需）

| ID | 内容 | 数据来源 | 章 | 服务的 RQ / 论证 | 不能误导的边界 |
|---|---|---|---|---|---|
| Fig 1 | System context diagram（用户、租户、provider、plugin、MCP、store 的外部边界） | `internal/api`、`internal/setup` | Ch.4 | 界定 threat model 的攻击面 | 不得画出代码中不存在的组件（Kafka/Redis/K8s/vector DB） |
| Fig 2 | 分层组件架构（现有 architecture.png 重绘，加租户边界与 policy 过滤层） | 现有资产 + `internal/policy` | Ch.4 | 支撑"capability-not-prompt"论点 | 层间箭头须与实际调用方向一致 |
| Fig 3 | **One-turn state machine**（identity → system prompt → session repair → provider stream → tool dispatch → tool result → persist；含 panic containment 与 fail-closed/fail-open 分支） | `internal/agent/loop.go`、`context.go`、`sdkbridge.go` | Ch.4 | RQ1；ReAct 与生产 runtime 的区分 | identity 路径 fail-closed 与 session 路径 fail-open 必须画成**不同**的分支样式 |
| Fig 4 | Coordinator–specialist sequence（现有资产重绘，加 correlation ID、call path、tenant ownership、consume-once tool-call-ID 关联） | `internal/agent/tools/subagent.go`、`internal/bus` | Ch.5 | RQ2 的机制说明 | **必须标注 specialist 证据为编译进的 fixture**，否则图会暗示检索 |
| Fig 5 | MessageBus/TaskQueue 并发与取消（per-chat FIFO、root semaphore、256-slot internal capacity、`WithoutCancel` + 双 `AfterFunc`、wait-graph cycle detection） | `internal/taskqueue/queue.go`、`internal/bus/internal.go` | Ch.5 | 背压与取消的正确性论证 | 两个 256 是**不同**的容量（bus `maxInternalPending` vs internal-task capacity），不得合并画成一个 |
| Fig 6 | SQLite 事务竞争与修复（deferred read-to-write upgrade → `SQLITE_BUSY_SNAPSHOT` → busy_timeout 为何无效 → `_txlock=immediate` 及其序列化代价） | `internal/store/database.go:50-52, 79-88, 103-109` | Ch.4 | T9；一处真实且非平凡的并发缺陷修复 | 必须标注 WAL 要求**同主机**，不适用于网络文件系统 |
| Table 1 | 五基线的 estimand 表（evidence access × inference compute × orchestration 三维） | `internal/eval/multiagent.go` | Ch.7 | novelty (i) 的核心 | `oracle_team` 行须标注"diagnostic, not upper bound" |
| Table 2 | 指标公式表（10 项，含 `Gfair`、compute-matched、三种 `Passed` 的区分） | `multiagent.go:538-547, 615-616` | Ch.7 | 所有结果的可解释性前提 | 三种 `Passed` 在 5/6 上的重合是**巧合**，须写明 |
| Table 3 | Case-level pass/fail 矩阵（6 case × 4 mode，含失败原因分类） | `finance-runtime-formal-r5.json` | Ch.8 | RQ2 的原始证据 | 失败须分类为 lexical-surface / reasoning / routing / infra；本运行**全部为第一类** |
| Table 4 | Per-mode cost/token/latency 分解（**双口径**：计费在前，provider total 在后） | `model_calls[]` + suite pricing | Ch.8 | RQ3 | 不得只报 total（双计 cache read） |
| Algo 1 | 一个 turn 的伪代码 | `loop.go` | Ch.4 | Fig 3 的形式化 | 须包含错误与取消路径，否则伪代码会美化实现 |
| Algo 2 | 一次多 Agent attempt 的伪代码（含 dedup、cycle check、correlation） | `subagent.go` | Ch.5 | Fig 4 的形式化 | eval dedup 与 production dedup 须分别标注 |

## P1（论文级深度）

| ID | 内容 | 来源 | 章 | 边界 |
|---|---|---|---|---|
| Fig 7 | 租户/认证/policy 边界图（cookie session、Bearer key、agent ACL、workspace namespace） | `internal/auth`、`internal/scope` | Ch.3 | **须标出 C1 缺口位置**，不得画成完整闭合 |
| Fig 8 | Evaluation 数据流与指标血缘（case YAML → attempt → model_calls → metric → gain） | `internal/eval/runner.go`、`report.go` | Ch.7 | 须显示 grader 位于血缘的哪一环——这是双轴敏感性的图形依据 |
| Fig 9 | Evidence-to-decision 工作流（现有 finance workflow 重绘，加 envelope 字段与 forbidden-assertion 检查点） | `plugins/finance-tools/plugin.py` | Ch.6 | 须标注 r5 中该路径**未被执行** |
| Table 5 | 需求→设计→证据映射表 | Ch.3–5 | Ch.3 | 无测试覆盖的行须标注（六个包） |
| Table 6 | **Threats to validity 表**（internal / external / construct / conclusion 四类）。construct 行至少含：state validity 为 wording check、grounding 为 lexical 非 entailment、specialist fixture、`faults_expected=0` | §2 全部 | Ch.10 | 这是全表中最重要的一张；不得写成泛泛的 "small sample" |
| Table 7 | 历史运行三点序列（0/8 → 4/8 → 8/8）含各点配置差异 | 三个 artifact | Ch.8 | 须声明两个 artifact 被 `.gitignore:76` 排除 |

## P2（版式与呈现）

| ID | 内容 | 说明 |
|---|---|---|
| Fig 10 | Grader 敏感性图（六开关 × 5 run 的 outcome 变化热图） | 依赖 P0-12 消融的执行；零新模型调用 |
| Table 8 | 缩略语表 | 40+ 页论文的必需件 |
| — | 自动目录、图目录、表目录 | 当前单栏模板需加 |

## 本次审查新增的四项

| ID | 内容 | 章 | 为何必需 |
|---|---|---|---|
| **Table 9** | **双轴敏感性表**（行：样本池 r5 / pooled r2–r5；列：当前 rubric / +词干器；单元：四模式 pass 率与 Team–Open 差） | Ch.8 §敏感性 | RQ2"不可判定"结论的唯一图形化证明；是全文方法学贡献的落点 |
| **Table 10** | **Trace-event 组成表**（18 events = 6 cases × 3 specialists，全部 `spawn_subagent`，`finance-tools.*` = 0） | Ch.8 | A10 的直接证据；一张表就使 construct-validity 声明不可回避 |
| **Table 11** | **期望词 vs 实际措辞表**（五个失败：期望 pattern、模型实际输出、失配类型） | Ch.8 §失败分析 | 支撑"零推理/路由/基础设施失败"这一强断言；也是 Fig 10 的定性配对 |
| **Fig 11** | **双口径 token 柱状图**（每模式两根柱：billable / provider total，cache-read 部分单独着色） | Ch.8 | A12 的视觉化；使 4.17× 与 2.13× 的差异一目了然 |

---

# 10. Exact Expansion Blueprint

排序原则：**P0 = 事实、实验或结论可信度问题**（不修则论文不可提交）；**P1 = 结构与技术深度缺口**；**P2 = 版式与表达**。P0 内部按 §2.8 的依赖顺序执行。

## P0（18 项）

| # | 内容 | 依据 | 验收条件 |
|---|---|---|---|
| P0-1 | 修正 MD:570 的失败诊断：从 "clause distance" 改为形态学失配，给出值级证据 | A1 / 改写 10 | :570 出现 `not estimate` 与 `estimated` 的对照，且不再出现 "one local assertion window" |
| P0-2 | 补报 `incomplete-screening-data` 的**第二个**失败（contribution assertion），使 0.944/0.972 可从正文推导 | A2 / 改写 11 | 正文出现 "two grader failures from a single rubric value" 及 0.667/0.833 的 per-case 值 |
| P0-3 | 声明检验力：n=6、1 rep、最小可达 p=0.0312；0.0 pp 为"未检出"非"等价" | A6 | Abstract、§VII、§VIII 三处均加限定 |
| P0-4 | 修正 MD:26 与 §VII 的"directly address"表述，如实说明两个实验各自的自变量与混杂 | B11 / 改写 4 | 不再出现 `directly address`；出现 grader–runtime 混杂声明 |
| P0-5 | 修正 B5（session fail-open）、B6（无 per-task deadline）、B1（`load_skill` 死代码） | B 组 | 三处均改为如实表述并接到 Limitations/Future Work |
| P0-6 | 修正 MD:388 的 "paired" 表述为 counts-only，并声明本文配对为手工构建 | 5.3(2) / 改写 9 | :388 出现 "the check is not case-paired" |
| P0-7 | 披露 A8（hedge 抑制使一处 forbidden 短语被豁免），给出具体实例 | A8 / 改写 12 | :568 出现 "higher evidentiary weight" 实例 |
| P0-8 | 修正 Abstract 与 Conclusion 的因果动词（`shows` → 观测+未分离声明） | 改写 1、15、16 | Abstract 无因果动词；Conclusion 出现 "leaves RQ2 open" |
| P0-9 | 披露测试覆盖率 28.0% 与六个无测试包，并标明受影响的三处设计论证 | A9 / 改写 8 | §VII 出现覆盖率数字与包名列表 |
| P0-10 | 加入 regrade drift 证据（r1 改 4 cell、r2 改 1、r3 改 2、r4 改 1、r5 改 0）紧邻 MD:598 | 改写 14 | :598 后紧跟量化证据句 |
| P0-11 | 历史 8-case 两模式结果与金融四模式结果**分表、分 estimand**，且历史表标为 regression study | A5 | 两表不共用列头；历史表有 "not an independent validation" 标注 |
| P0-12 | **六开关 grader 消融**：negation / hedge / conditional / clause-gap / plural-morphology / **`-ed/-ing/-ion` 词干**，× 5 run | 双轴 | 产出 Fig 10 与 Table 9 所需全部数据；**零新模型调用**——全部 P0 中性价比最高的一项 |
| P0-13 | Pooled 敏感性分析（r2–r5，n=24/mode）写入 §VIII，并**显式标为事后分析** | A6 | 出现 "post hoc" 与 exact p=0.5078，且列为 internal validity threat |
| P0-14 | 披露 A10（零金融工具调用；state validity 为散文检查）与 A11（证据为编译进的查找表 + 逐字抄写指令） | A10、A11 / 改写 17、18 | §V–VII 出现明确句子；Appendix A 的 "State checks" 改标为 wording checks；Table 10 存在 |
| P0-15 | 修正 A12：双口径 token 对比，**计费口径在前** | A12 / 改写 19 | :566 同时给出 2.13× / −41.6% 与 4.17× / +33.7% |
| P0-16 | 披露 A13：0/8 → 4/8 → 8/8 三点序列，非单一 before/after | A13 / 改写 20 | :493-506 表格加脚注，含中间运行的四个指标 |
| P0-17 | 补报 A15 的六个指标（含 oracle gap **−16.7 pp** 及其解释），并声明 A14（`faults_expected=0` 使容错指标为空真值） | A14、A15 / 改写 21、22 | §VII-E 出现全部六个数字；RQ4 语境下不再列空真值指标 |
| P0-18 | 解决 E1–E6。最小集：套件 YAML 与 r5 artifact 入库；`multiagent-finance-runtime.yaml` 加入 `TestLoadBundledMultiAgentSuite` 钉定；artifact 中写入运行配置（repetitions、mode list、timeout、execution mode、case filter、endpoint class、pricing date）；vendored 一份 finskills fixture 或明确标注为外部依赖 | E1–E6 / 改写 24 | 从干净 clone 可复现 r5 的 grader 判定；App C 如实记录未能入库的部分 |

## P1（9 项）

1. 新建 Ch.2 Related Work（§7 的 13 个主题，约 2,000 words）。
2. 新建 Ch.3 完整 threat model 与 design principles，含 C1 的位置。
3. Ch.7 新增 grader 内部机制一节：per-step gap ≈9(N−1)、` and ` 硬分句、negation 5-token lookback 假阴（`req("exclude from ranking, source refresh", "source refresh")` = False）、hedge 抑制、conditional scope、`expectedContainsNegation`、normalizer 的形态学缺口、三种 `Passed` 定义。
4. Ch.7 新增统计计划一节，引 §7 第 6 行的引文簇；写明 exact McNemar 在 discordant pair = 0 时**无定义**。
5. Ch.4/5 补齐 T1–T5、T9、T10 的机制叙述（invariant、取消、恢复、替代方案、trade-off）。
6. Table 6 Threats to validity（四类），construct 行至少四条。
7. Ch.10 披露 C1 并列入 Future Work；补 human-in-the-loop 的三条文献依据。
8. 术语统一：采用 Rashkin 的 **attribution** 替换非正式的 "grounding"；统一 "four specialists"（:402）与 `evals/README.md:13-15` 的 "five-agent" 计数口径。
9. §2.4 的两条限定：Serenity skill 的 `shasum -c SHA256.txt` 为 **24 OK / 2 FAILED**（`./README.md`、`./README.zh-CN.md`；可执行文件与 `SKILL.md` 均通过），MD:219 的 "locally verified and version-pinned" 须据此限定。

## P2（5 项）

1. 加自动目录、图目录、表目录、缩略语表。
2. Fig 1–6 绘制/重绘（P0 图表清单）。
3. P50 > mean 的成因解释句（改写 23）。
4. 修复 D11 编号顺序与 D12 四条字段错误；处理 D13 两处不支撑引用与 D14 无引用主张。
5. 检查 40–44 页下的分页：表格断裂、孤立 caption、图片分辨率、参考文献格式。

## 执行阶段与验收

**阶段 A｜事实与表述修正（不需新实验）** — P0-1..P0-11、P0-14..P0-17。验收：所有数字与其含义一致；无因果动词无据；三个 artifact 事实（零工具调用、fixture 证据、零故障）均已披露。**这是唯一必需的阶段；只做到此处，报告即从"数字对但含义超发"变为"诚实的高质量项目报告"。**

**阶段 B｜零成本再分析** — P0-12、P0-13。仅需 regrade 脚本，无新模型调用。验收：Table 9 与 Fig 10 可生成；§VIII 的 RQ2 结论改为"不可判定 + 双轴证据"。

**阶段 C｜可复现性** — P0-18。验收：干净 clone + 已提交 artifact 能重放 grader 判定并得到同一 24 个 outcome cell。

**阶段 D｜论文结构与深度** — P1 全部 + P2 全部。验收：14,000–16,000 words；Ch.2/Ch.3 存在；Table 6 与 Fig 3–6 存在；参考文献 ≈46 条且无 fabricated 条目。

**如需真正回答 RQ2**（超出本次范围，属 Future Work）：预注册 rubric 的 24-case holdout（8 case × 3 rep），grader 开关在数据收集前冻结，fault suite 实跑。

---

# 11. Safe Abstract and Conclusion Boundary

## 11.1 当前证据支持的 Abstract（约 340 words）

> Large-language-model agents are increasingly deployed as long-running services rather than single prompts, yet published evaluations attribute outcomes almost exclusively to the model. This thesis argues that the runtime—the layer that constructs prompts, routes tool calls, enforces tenant boundaries, persists state, and grades outputs—is itself part of the experimental treatment, and that current agent benchmarks are not instrumented to detect its effects.
>
> FastClaw is a Go agent runtime comprising a single-turn execution state machine with fail-closed identity resolution and tool-panic containment, a per-chat FIFO task queue with root-level concurrency admission and cooperative cancellation, an internal message bus with correlation identifiers and transitive wait-graph cycle detection, a policy-filtered tool registry, and a multi-tenant persistence layer whose SQLite configuration resolves a deferred read-to-write transaction upgrade that a busy timeout alone cannot. A financial research plugin exposes seventeen deterministic tools behind a versioned evidence envelope that carries as-of dates, source identifiers, completeness flags, and structured errors, together with a tenant-isolated thesis ledger under optimistic version control.
>
> Two experiments are reported. A historical eight-case, two-mode run recorded strict success rising from 0/8 to 8/8 and total tokens falling 94.2%; because evidence visibility differed between modes and the grader was normalised in the same change set, it is reported as a regression study whose runtime and grader contributions are not separated. A six-case, four-mode confirmation with evidence-visibility-matched baselines recorded 5/6 for the coordinator-and-specialists mode and for both solo baselines, 4/6 for a perfect-routing diagnostic, and fair and compute-matched collaboration gains of 0.0 percentage points.
>
> The observed pass counts are shown to be sensitive, in opposite directions, to two analysis choices unrelated to orchestration: pooling four runs that share the frozen suite hash raises the paired coordinator–solo difference to +12.5 pp (exact two-sided p = 0.5078), whereas adding one inflectional rule to the grader's normaliser raises three of four modes to 6/6 and leaves the gain at zero. The orchestration question is therefore not resolvable at this suite's resolution. The demonstrated contribution is a runtime and harness whose measurement decisions are auditable and revisable—evidenced most directly by the harness detecting and quantifying a defect in its own grader—rather than superior financial judgement.

## 11.2 当前证据支持的 Conclusion 要点（约 450 words 展开）

1. **可作断言的工程结果**：单 turn 状态机、correlation/cycle detection、per-chat FIFO + root semaphore、`_txlock=immediate` 修复、policy-filtered registry、evidence envelope、版本化 ledger——均有代码与测试证据，可作为已实现能力陈述（但须附 28.0% 覆盖率与六个无测试包的限定）。
2. **可作断言的评测方法结果**：证据可见性匹配的三基线协议是本文最强的方法学贡献；harness 检测并量化了自身 grader 的缺陷，且修正后的 rubric 改变了此前发布的结果。
3. **可作断言的负面/不确定结果**：在 n=6、1 rep 下未检出 collaboration gain；该观测对样本池与 grader 词法两条分析选择敏感且方向相反，因此 RQ2 **不可判定**；论文给出判定所需的最小设计（24-case 预注册 holdout + 冻结开关）。
4. **可作断言的成本结果**：按计费口径 Team 为 Open-Book 的 2.13×、比 Two-Pass 少 41.6%；provider total 口径为 4.17× 与 +33.7%。双口径并列陈述。
5. **可作断言的元结论**：runtime 与 grader 都是实验处理的一部分，其证据是 regrade drift（单一 grader 变更可移动一次运行中 4/6 的 outcome cell）。

## 11.3 禁止出现的结论（18 条）

1. 不得声称多 Agent 优于 Solo，或 Solo 等价于多 Agent（前者无证据，后者是把未检出当等价）。
2. 不得声称 0.0 pp 是 "no collaboration gain exists"。
3. 不得称 `oracle_team` 为 theoretical upper bound（本运行中它低于 Team）。
4. 不得称 r5 为 independent validation / holdout（它是 post-fix frozen confirmation）。
5. 不得对任一结果附加 statistically significant 或 p < 0.05。
6. 不得把 100% configured grounding accuracy 写成 factual accuracy 或 entailment。
7. 不得把 style subset 写成 BFCL / τ-bench / SWE-bench / MultiAgentBench 官方分数。
8. 不得把 fixed evidence 写成 live market data retrieval。
9. 不得把 workflow correctness 写成 alpha、Sharpe、收益率或预测准确率。
10. 不得声称 94.2% token 削减由 runtime 单独造成（grader 同时变更）。
11. 不得声称 progressive disclosure 已实现或部分实现。
12. 不得声称存在 per-task deadline。
13. 不得声称 store-backed session 保证 cross-replica 最新历史（fail-open）。
14. 不得引入代码中不存在的 Kafka / Redis / Kubernetes / vector DB / RAG / gVisor / 交易执行 / 实时行情架构。
15. 不得把 implementation detail（如"我们实现了 telemetry"）写成 research contribution。
16. **不得声称 r5 验证了 state transition 或 ledger 正确性**（该运行零金融工具调用）。
17. **不得声称 r5 涉及 specialist 的语言能力或检索能力**（指令为逐字抄写编译进的字符串）。
18. **不得把 `faults_expected = 0` 下的容错指标当作容错证据**。

---

# 12. 已采用的默认决定

原 §12 为"需作者决定的问题（Q1–Q7）"。按作者指示（"不要管 q1-q7，只用管 Thesis-level review"），本节改为**已采用的默认决定**，使本审查可独立成立、无需作者回答任何问题即可执行。

| # | 决定项 | 采用的默认 | 理由 |
|---|---|---|---|
| 1 | 学位档位与篇幅 | **本科毕业论文档位，14,000–16,000 words 正文，40–44 页** | 现有 11,869 words 与证据基础落在此档；硕士档位需要 §10 阶段 A–D 之外的新实验（holdout），超出当前 artifact 支持范围 |
| 2 | 是否新增实验 | **只做零成本再分析**：regrade + 六开关 grader 消融（P0-12、P0-13）。**fault suite 实跑与 24-case holdout 列为 Future Work** | 零新模型调用即可产出双轴敏感性分析所需全部数据，性价比最高；新实验会引入新的 leakage 与成本，且不改变本轮结论方向 |
| 3 | 主结果的选取 | **主结果保留 r5**；pooled r2–r5 作为 §8.3 的**事后敏感性分析**呈现，不作为独立证据 | pooled 是事后合并，方向为正但不显著；单独呈现会构成第二次选择性报告 |
| 4 | RQ2 的结论表述 | **"本仪器不可判定"**，附双轴敏感性表（样本池 × rubric 词法），并给出可判定所需设计 | 观测差异对两条与 orchestration 无关的分析选择敏感且方向相反；"不可判定"比"点估计为正但不显著"或"为 0"都更强、更可辩护，且它本身就是 MD:598-600 论点的定量证明 |
| 5 | 模板与版式 | **保留现有单栏模板**，加自动目录、图目录、表目录、缩略语表；表格宽度按 40+ 页重排 | 更换模板成本高于收益；单栏在 40–44 页下仍适用 |
| 6 | C1 安全缺口的处理 | **在 Ch.10 明确披露**（`internal/api/openai.go:348-363` 缺 `CanAccessAgent` 校验），并列为 Future Work P0 | 论文中隐瞒已知授权缺口是伦理问题；披露 + 列入 Future Work 是标准做法 |
| 7 | Artifact 版本控制策略 | **新建 `project-report/artifacts/` 存放论文引用的产物副本**，保留 `.gitignore:76` 的 `/runtime-*.json` 原意 | 不动既有 ignore 语义，同时使论文自洽；r5 artifact 170 KB，五个 finance artifact 合计约 1 MB 量级，入库无负担。备选 (a) 白名单例外会污染 ignore 规则；备选 (c) "可按需索取" 学术上可接受但明显更弱 |
| 8 | Git 操作 | **不 commit、不 push** | 作者未授权 |
| 9 | 本轮是否修改项目报告 | **不修改** | 作者明确指示"不用改，我只需要你给出对 project-report 的 review" |

---

# 附：本次审查的执行边界

- **未修改任何文件**，除本审查文档本身。`project-report/` 与全部源码保持原样。
- **未生成 DOCX/PDF**，未执行 `build_report.py`。
- **未 commit、未 push**。
- **`runtime-benchmark-tenant.json` 全程未被读取**，其中的 API key 未出现在本文档、对话或任何产物中。
- 核验方式：逐行读取 `project-report/fastclaw_project_report.md`（754 行）与 §1–§7 所列全部代码路径；对 `finance-runtime-formal-r5.json` 的 24 个 outcome cell 用独立重实现的 matcher 逐一复核（**24/24 与 artifact 完全一致**）；对全部 12 条现有参考文献逐字段核验；执行 `go test ./internal/eval/...` 与 10 个 Python plugin 测试（均通过）。
- 历史 artifact 仅用于 calibration、缺陷发现与工程演进说明，未作为独立验证结果使用。
- 一切标记 **[待核验]** 的引用在写入论文前须逐条确认；无法确认者以描述性方式提及研究方向，不给引用。








