# FastClaw Project Report Thesis Review — Round 3

- Review date: 2026-08-09
- Primary manuscript: `project-report/fastclaw_project_report.md`
- Scope: thesis content, technical accuracy, experimental validity, financial validity, statistical reasoning, and academic expression
- Excluded: typography, pagination, PDF/DOCX generation, visual design, citation formatting, and repository workflow

## A. 总体结论

**结论：Major Revision。**

论文已经具备一条可成立的金融科技研究主线：金融研究质量不仅受模型影响，也受检索、证据可见性、上下文分配、专家委派、并行执行、运行时错误和 grader 共同影响。固定证据实验、四公司 SEC 扩展和 NVDA 检索 Pilot 也总体如实报告了零增益、负效率和不确定结果。

但当前版本更接近一篇**研究意识较强的 Agent Runtime artifact-evaluation project report**，尚未完全收束为确认性实证论文。最可辩护的贡献是：

1. 一个可审计的 Agent Runtime artifact；
2. 一套区分证据访问、计算机会、编排和故障的评测方法；
3. 一个有边界的实证结果：**现有实验未建立多智能体准确率增益，但单案例 Pilot 观察到了不同上下文分配方案的成本、延迟和 grounding 差异。**

不能成立的扩张性结论包括：多智能体提高金融分析准确率、FastClaw 已验证完整金融研究工作流、检索压缩具有一般因果效应、系统达到生产级可靠性，或当前结果支持投资收益、Alpha、Sharpe、自动交易及市场泛化。

## B. Blocking Issues

### P0

#### P0-1：论文提交快照中的核心证据包不自包含

论文引用的 hard-suite summary、retrieval summary、retrieval manifest、source lock 和部分原始 JSON 不在当前引用路径。它们可以在本地保留的研究快照中找到；复核显示：

- retrieval suite SHA-256 匹配；
- source-lock SHA-256 匹配；
- 三个最终 observation SHA-256 均匹配 manifest；
- r5 suite 和 raw report SHA-256 均匹配；
- 论文中的主要表格数字与 retained reports 一致。

因此这不是已经发现的数字矛盾，而是**提交包完整性与独立复核阻断问题**。答辩前必须把冻结 suite、source lock、raw reports、analysis JSON、summary 和 manifest 放回论文引用的固定路径，或发布 content-addressed archive。

### P1

1. **RQ4/H4 未执行。** Fault Injection 已实现于模拟评测路径，但主要金融实验 `faults_expected=0`。RQ4 不能作为已完成研究问题，应移入 prospective validation。
2. **“Compute-matched”表述不准确。** Two-Pass 只匹配了两次 coordinator pass；Team 还有三次 specialist 调用。应改成 `coordinator-pass-matched` 或 `planning-opportunity-matched`。
3. **单案例机制措辞过强。** NVDA Pilot 只有一个 case、一次 repetition、非随机 mode order，且 Team/Solo 模型分配不同。“identifies the mechanism”“can improve the Pareto frontier”应降为“is consistent with”。
4. **r2–r5 统计没有处理 case dependence。** Wilson 区间和 exact-binomial p-value 把同一六个 case 的重复输出当作独立 attempt，只能作为 naive descriptive sensitivity。
5. **Stage 2 pairing key 定义错误。** `STAGE2-EXPERIMENT-PROTOCOL.md:323` 把 `mode` 放入 canonical pair key，使不同 mode 不可能共享同一个 pair key。
6. **RQ1/RQ5 范围大于证据。** 测试支持 selected control paths 和 selected workflow invariants，不支持完整 Runtime correctness 或 end-to-end financial-workflow validity。
7. **“Negative result”不够准确。** 当前没有建立 superiority、inferiority 或 equivalence，应称为 `inconclusive accuracy result` 或 `no detected incremental effect at the present resolution`。
8. **贡献列表仍偏项目清单。** `fastclaw_project_report.md:31` 的前三项主要描述系统组件，应重写为 artifact、measurement method 和 bounded empirical finding。

### P2

1. Runtime error 应同时报告 assigned-attempt success 和 completed-output conditional success，不能只从模型成功率分母排除。
2. Source lock 有 URL、全局 retrieval time、字节数和 SHA-256；44 个 gold facts 也都有 unit、basis 和 locator，但仍建议建立统一的逐事实 provenance 表。
3. 所有 cost 都是基于冻结价格表的估算，不是 provider invoice 或一般化成本结论。
4. Stage 2 的八个 company-task cells 是 analysis clusters，不是严格证明独立的抽样单元。
5. 系统、suite、grader 和分析主要由同一作者开发，缺少独立金融领域标注，应列入 researcher-independence threat。
6. `RQ2 remains not determinable` 应改为 `The evidence for RQ2 remains inconclusive`；“preregistered”若无外部注册记录，应改为“prespecified”。

## C. Claim–Evidence Audit

| 论文主张 | 证据状态 | 审计结论 |
|---|---|---|
| 八案例从 0/8 提升到 8/8 | 有 retained JSON | 数字支持；仅一次 repetition，且为 bundled before/after，不支持组件级因果归因 |
| Token 1,274,742→73,729，P95 201.6s→60.0s | 有 retained JSON | 数字支持；报告未被当前提交包内容寻址，应补 manifest/hash |
| r5 中 Open-Book、Two-Pass、Team 均为 5/6 | suite、raw JSON、manifest hash 匹配 | 支持；说明当前分辨率下准确率差为零，不证明等效 |
| 四公司 longitudinal Team 与 Open-Book 均为 3/4 | hard-r3 raw/analysis/summary 一致 | 支持；一胜一负两平，不能推断一般协作收益 |
| Retrieval Pilot 中 Team 与 staged Solo 均 strict pass | 三个 observation 和 manifest hash 匹配 | 支持；没有增量 final-answer accuracy |
| Team 相对 staged Solo latency −36.32%、cost −42.06% | retained Pilot report | 支持为单次 observation；成本方向来自异质模型价格，不来自更少 provider tokens |
| Shared retrieval 优于 raw-context Team | retained Pilot report | 支持描述性关联；不能隔离 provider load、顺序和 prompt-level 差异 |
| SEC 数据 source-locked | source lock、16 个条目、SHA-256、URL | 基本支持；提交快照不自包含，且建议增加 accession/accepted-at/reporting-period 的统一索引 |
| 44 个 gold financial facts 有 unit/basis/locator | `evidence.json` | 支持；模型输出不是 ground truth，gold facts 才是人工核验 oracle |
| Numeric grounding 等于事实正确率 | 无 | 论文大体没有这样声称；必须继续明确它只检查授权数值/证据支持，不是完整 entailment |
| Fault tolerance 已验证 | 无主要金融执行结果 | 不支持；只实现了模拟 Fault Injection 协议 |
| Stage 2 已完成 | 无 | 论文已正确标记为 future experiment，但“frozen suite”措辞需避免暗示协议已完全冻结执行 |

## D. Research Question Audit

| RQ | 是否有对应方法 | 当前可回答范围 | 判断 |
|---|---|---|---|
| RQ1 Runtime correctness | 单元/集成测试、控制路径测试 | selected tenant、stream、cancel、ordering 和 bounded-execution paths | 部分回答；不是形式证明或生产认证 |
| RQ2 Orchestration benefit | r5、longitudinal、retrieval Pilot | 未检测到相对 evidence-matched Solo 的准确率增益 | 回答较诚实；不能称为负效应或等效 |
| RQ3 Context allocation | 五模式 Pilot、token/cost/latency/grounding | 一个 NVDA case 的描述性 trade-off | 部分回答；不支持一般机制因果结论 |
| RQ4 Fault tolerance | harness/protocol | 没有主要执行结果 | 未回答；应移出 evaluated RQs |
| RQ5 Financial validity | plugin tests、固定证据、SEC Pilot | selected workflow invariants 和一个 archived-document path | 范围过宽，应改为 selected financial-research invariants |

H1–H6 不宜统一称为 confirmatory hypotheses。建议改为 **evaluation propositions**：H1 不可从 bundled change 隔离；H2/H3 仅有 Pilot 描述性证据；H4 未执行；H5 混合确定性状态和开放文本 matcher；H6 方向依赖具体 baseline。

## E. Experiment Audit

| 实验 | 公平性与有效性 | 可成立结论 |
|---|---|---|
| 8-case Runtime 优化 | 前后多个修复同时变化、每 case 一次、无 ablation | harness bundle 与大幅改善相关 |
| 6-case r5 | 证据可见性匹配；Two-Pass 未匹配 specialist 总计算量；grader 有 calibration history | Team、Open-Book、Two-Pass 同为 5/6；无增量准确率结果 |
| 4-company longitudinal | 同证据 paired comparison；只有四个 case、一次 repetition | Team 与 Open-Book 总分相同，方向不稳定 |
| NVDA retrieval Pilot | source locked；单 case、单次、非随机顺序、异质模型 | 描述性效率和 grounding 差异；无 collaboration accuracy gain |
| Stage 2 | 24 configurations 嵌套于 8 company-task cells，计划三次 repetition | 尚未执行；必须先修 pair key、完成 freeze checklist 和随机顺序 |

`solo_open_book` 是有效的 evidence-visibility control；`solo_two_pass` 只是更严格的 planning-pass control，不是完整 capacity match；`oracle_team`/`oracle_evidence` 是诊断上限，不应计入 deployable baseline 排名。

## F. Financial Validity Audit

1. NVDA、AMD、Intel、NIKE 的 44 个 oracle facts 均带 value、unit、GAAP/non-GAAP basis、period label、source ID 和 locator，这是论文中较强的金融数据治理部分。
2. Source lock 保存了 16 个 SEC/Company Facts 文件的 URL、字节数、全局 retrieval timestamp 和 SHA-256；URL 中可恢复 accession，但最好显式存储 accession、filing/accepted time 和 reporting-period end。
3. 当前 longitudinal 研究是披露序列分析，不是收益回测；论文正确排除了 Alpha、Sharpe、自动交易和投资建议。
4. 对未来 point-in-time 研究，必须为每个 case 固定 `as_of_timestamp`，强制 `accepted_at <= as_of_timestamp`，并记录所有被排除的后续 filing。
5. Ratio 和 percent-change oracle 应继续记录公式、输入 fact IDs、单位转换、舍入规则和 expected result。Numeric corpus membership 不能替代金融语义正确性。
6. 当前没有证据表明模型输出被当作 ground truth；但论文应明确 ground truth 来自人工核验、source-locked oracle，而不是 grader 或模型共识。

## G. Technical Accuracy Audit

| 技术主张 | 判断 |
|---|---|
| Per-chat FIFO 和 root-level concurrency admission | 代码支持；internal execution 继承 root execution ID，避免重复占用 root semaphore |
| Timeout/cancellation propagation | 代码支持；`context.AfterFunc` 和 bounded queue timeout 存在 |
| MessageBus correlation、CallPath 和 cycle detection | 代码支持；包含 transitive wait-cycle prevention 和 bounded pending requests |
| Streaming content/error/done terminal semantics | 代码和测试支持；应称 tested invariant，不是绝对无故障保证 |
| Concurrent tool-result attribution | 原始 tool-call ID 用作 join key，支持；不再依赖完成顺序 zip |
| Identity fail-fast | required identity 缺失、为空或 store error 时失败，支持 |
| Tool isolation | request-scoped eval registry 和 policy filter 支持；不要泛化为所有生产 specialist 已有完整角色级 RBAC |
| Tenant ACL | resolved OpenAI target 重新授权并有行为测试，支持；不等于所有未来 endpoint 自动安全 |
| SQLite WAL/`busy_timeout(5000)` | 支持降低瞬时锁失败；没有消除 SQLite 单 writer 和 25-connection contention |
| Provider usage/cache/cost | role-level prompt/completion/cache token 和估算成本支持；依赖 provider usage 字段与冻结价格表 |
| Fault Injection | 模拟执行路径支持六类故障；主要金融 artifact 未执行 |
| 子 Agent 会话 | 每次 `spawn_subagent` 生成新 ChatID；当前无 resume handle，不应声称自动续接历史 |

## H. Recommended Revision Plan

1. **恢复证据包。** 将 suite、source lock、manifest、raw JSON、analysis JSON、summary 和验证脚本放到论文引用路径，并生成总 manifest。
2. **重写研究结构。** 把 RQ1/RQ5 定义为 validity preconditions，RQ2/RQ3 设为主要 empirical questions，RQ4 移入 future validation。
3. **改写贡献。** 从五项组件清单压缩为 artifact、evaluation method、bounded empirical finding 三类。
4. **修正 baseline 术语。** 将 `compute-matched` 改为 `coordinator-pass-matched`，明确 specialist 调用、模型容量、token 和成本仍不同。
5. **降格统计和因果语言。** 将 r2–r5 区间/p-value 标为 naive descriptive；将 Pilot 中的 `identifies`、`therefore`、`can improve` 改为关联性措辞。
6. **修复 Stage 2。** Observation key 包含 mode；pair key 排除 mode。报告 `4 issuers / 8 analysis clusters / 24 configurations / 72 repeated attempts`。
7. **补 financial provenance 表。** 每个 gold fact 记录 concept、value、unit、basis、scope、period、filing/accepted time、accession、locator、SHA-256 和 derivation。
8. **最后统一 Abstract、Results、Discussion、Conclusion。** 全文只保留“未检测到增量准确率效应”和“单案例描述性效率观察”两条实证主结论。

## I. Suggested Replacement Passages

### 1. Abstract

> This thesis studies how agent-runtime choices shape observable quality and efficiency in evidence-grounded financial research. FastClaw is presented as an auditable multi-tenant runtime with bounded execution, policy-filtered tools, shared-context delegation, and role-level telemetry. Selected runtime and plugin tests verify specific control paths and deterministic workflow invariants, but do not constitute production certification. Across the fixed-evidence and longitudinal comparisons, coordinator-specialist execution did not demonstrate an incremental accuracy advantage over evidence-matched Solo baselines. A one-case retrieval pilot observed lower latency and estimated cost for shared-retrieval Team than for staged Solo under heterogeneous model allocation. These findings are descriptive; the full Stage 2 experiment has not been executed.

### 2. Contributions

> The thesis makes three contributions: an auditable agent-runtime artifact; an evaluation method that separates evidence visibility, planning opportunity, orchestration, model assignment, runtime failure, and grader behavior; and a bounded empirical finding that the current experiments do not establish incremental collaboration accuracy, while suggesting that context allocation may affect the observed latency-cost-grounding trade-off.

### 3. Baseline wording

> Solo Two-Pass matches the Team coordinator’s two planning and synthesis opportunities but does not match total model calls or specialist compute. It is therefore treated as a coordinator-pass-matched baseline rather than a fully capacity-matched baseline.

### 4. Statistical interpretation

> The pooled r2–r5 Wilson intervals and exact binomial comparisons treat repeated outputs from the same six cases as independent attempts. They are reported as naive descriptive sensitivity analyses and do not provide cluster-aware inference over financial task families.

### 5. Retrieval mechanism

> In this single non-randomized pilot, shared retrieval was associated with lower latency and estimated cost and higher configured grounding than raw-context Team. The contrast is consistent with a contribution from retrieval compaction and one-copy shared context, but it does not isolate that contribution from provider variability, execution order, prompt differences, or heterogeneous model allocation.

### 6. Financial provenance

> Each gold numeric fact is linked to a source-locked filing artifact and records its unit, accounting basis, reporting period, and source locator. Model outputs are evaluated against these manually verified oracle facts; neither model agreement nor grader acceptance is treated as ground truth.

### 7. Stage 2 pairing

> An observation is identified by `(company, task family, corpus load, repetition, mode)`. Modes are paired on `(company, task family, corpus load, repetition)`; mode is not part of the pair key. The eight company-task cells are analysis clusters rather than demonstrably independent financial events.

### 8. Conclusion

> The principal contribution is a measurement-oriented agent runtime together with a transparent, presently inconclusive result on incremental collaboration accuracy. The current evidence is stronger for auditability, evidence-flow control, and experimental diagnosis than for financial intelligence, collaboration superiority, or general deployment efficiency.
