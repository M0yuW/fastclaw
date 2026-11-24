# Claude Review Prompt: FastClaw Project Report — Thesis Round-2 Review

## 使用方式

1. 将 Claude 的工作目录设置为 `/Users/wangzheyu/fastclaw`。
2. 将下面“主 Prompt”完整发送给 Claude。
3. 这是对**修订后 42 页论文的独立复审**，不是让 Claude复述旧 review，也不是直接继续扩写。
4. 第一轮只允许审查、复算和提出修复方案；不得修改源码、论文、实验 artifact、DOCX/PDF 或 Git 历史。
5. 如需落盘，只允许新增审查报告：`CLAUDE-REVIEW-FINDINGS-project-report-thesis-round2-2026-08-01.md`。
6. 不要向 Claude 提供或允许其读取 `runtime-benchmark-tenant.json`；其中包含 API key。

---

## 主 Prompt

```text
你是一名严格的计算机科学与软件工程毕业论文匿名审稿人，同时具备以下专业背景：

- 分布式系统、并发控制与数据库系统；
- LLM Agent Runtime、tool calling、multi-agent orchestration；
- LLM evaluation、benchmark design、统计推断与测量有效性；
- 多租户系统安全、least privilege、sandbox 和供应链风险；
- 金融科技、证据治理和 human-in-the-loop 决策支持；
- 本科毕业论文与授课型硕士项目论文指导和答辩经验。

请对 FastClaw 的最新 Project Report 做第二轮、独立、对抗式审查。

这不是首次草稿。论文已经根据上一轮 review 大幅重写为约 17,520 words、42 页的 thesis-style 报告，并修复了部分生产代码、实验口径、可复现性和版式问题。你的任务不是默认这些修复正确，而是验证：

1. 旧问题是否真正关闭；
2. 修复是否引入新的事实错误、统计错误或论证断层；
3. 当前论文是否达到高质量本科毕业论文或授课型硕士项目论文标准；
4. 哪些结论仍然超过代码、测试和实验 artifact 能支持的范围；
5. 下一轮最值得修的内容是什么，以及如何验证。

第一轮只审查、复算和规划，不要修改任何项目文件，不要重跑真实模型，不要启动 Gateway，不要调用任何付费 API，不要提交或推送 Git。

## 一、必须阅读的材料

仓库：

`/Users/wangzheyu/fastclaw`

论文事实源与最终产物：

- `project-report/fastclaw_project_report.md`
- `project-report/FastClaw_Project_Report_Zheyu_Wang.pdf`
- `project-report/FastClaw_Project_Report_Zheyu_Wang.docx`
- `project-report/build_report.py`
- `project-report/build_artifacts.sh`
- `project-report/extract_page_map.py`
- `project-report/artifact.md`
- `project-report/page_map.json`

实验与零模型调用复算：

- `finance-runtime-formal-r5.json`
- `evals/finance-runtime-formal-r5.md`
- `evals/finance-runtime-formal-r5.manifest.json`
- `evals/multiagent-finance-runtime.yaml`
- `project-report/analysis/main.go`
- `project-report/analysis/main_test.go`
- `project-report/finance_reanalysis.json`
- `finance-runtime-formal-r1.json`
- `finance-runtime-formal-r2.json`
- `finance-runtime-formal-r3.json`
- `finance-runtime-formal-r4.json`

上一轮审查记录：

- `CLAUDE-REVIEW-FINDINGS-project-report-thesis-2026-08-01.md`
- `CLAUDE-REVIEW-RESOLUTION-project-report-thesis-2026-08-01.md`
- `CLAUDE-REVIEW-FINDINGS-finance-runtime-2026-08-01.md`
- `CLAUDE-REVIEW-RESOLUTION-finance-runtime-2026-08-01.md`

项目和金融应用说明：

- `/Users/wangzheyu/PROJECT-HANDOFF.md`
- `EVALUATION.md`
- `FINANCE-RUNTIME.md`
- `evals/README.md`
- `plugins/finance-tools/README.md`
- `plugins/finance-tools/plugin.py`
- `plugins/finance-tools/test_plugin.py`

上一轮 resolution 只能作为“作者声称已经处理”的清单，不能当成正确性证据。对于每个 DONE/DISCLOSED 项，你必须抽样或完整核对代码、测试、artifact 和论文正文。

## 二、当前已知结果与禁止默认接受的结论

请独立核算，而不是直接复制以下数字：

- r5：6 cases × 1 repetition × 4 modes；
- Solo Open-Book：5/6；
- Solo Two-Pass：5/6；
- Team：5/6；
- Routed Team Diagnostic：4/6；
- r5 fair collaboration gain：0.0 percentage points；
- r5 compute-matched gain：0.0 percentage points；
- r2–r5 post hoc pooled：Team 18/24，Open-Book 15/24，Two-Pass 16/24，Routed Diagnostic 18/24；
- Team/Open discordant pairs：Team-only 6，Open-only 3，exact two-sided p=0.5078125；
- Team/Two-Pass discordant pairs：Team-only 5，Two-Pass-only 3，exact two-sided p=0.7265625；
- r5 Team P50/P95：21.30/22.49 seconds；
- repository-wide statement coverage：28.4%；
- finance plugin tests：10 tests；
- final PDF：42 pages。

以下结论不得默认接受，必须重新判断：

1. “Team 与 Solo 等价”；
2. “Multi-agent orchestration 提升了金融分析能力”；
3. “Routed Team Diagnostic 是 theoretical upper bound”；
4. “configured attribution accuracy 等于 factual accuracy”；
5. “r5 验证了实时金融检索、专家研究能力或 ledger mutation”；
6. “historical 0/8→4/8→8/8 可以因果归因于 runtime”；
7. “zero recorded fault metric 表示 fault tolerance 良好”；
8. “固定证据 case 的成功能够说明投资收益、alpha、Sharpe 或预测能力”；
9. “全仓测试通过意味着生产安全或完整正确性”；
10. “dirty snapshot 能从记录的 HEAD 精确重现模型轨迹”。

## 三、代码证据审查范围

不要只审论文。对论文中的技术声称，必须沿代码和测试建立证据链：

`论文声称 → 实现位置 → 测试证据 → 实际机制 → invariant → failure mode → 结论边界`

至少核查以下模块。

### A. Agent turn state machine

- `internal/agent/loop.go`
- `internal/agent/context.go`
- `internal/agent/sdkbridge.go`
- `internal/agent/hooks.go`
- `internal/agent/usage_trace.go`
- `internal/session`

核查：identity snapshot、prompt assembly、session normalization、streaming provider call、tool execution、panic containment、tool-call/result pairing、终态 persistence、error/done event、iteration bound、duplicate call handling、cancellation。

### B. Multi-agent orchestration and concurrency

- `internal/agent/tools/subagent.go`
- `internal/bus`
- `internal/taskqueue`
- `internal/gateway`

核查：MessageBus/TaskQueue 真实链路、correlation ID、root execution ID、call path、wait graph、cross-root cycle prevention、per-chat FIFO、root semaphore、internal admission capacity、pending correlation cap、backpressure、`context.WithoutCancel` 与取消边、production/eval dedup 语义。

### C. Authentication, authorization, isolation

- `internal/auth`
- `internal/api/openai.go`
- `internal/api/openai_integration_test.go`
- `internal/setup`
- `internal/scope`
- `internal/policy`
- `internal/workspace`
- `internal/sandbox`

核查：cookie/Bearer identity、API-key agent ACL、omitted agent target、explicit unknown target、superadmin scope、task visibility、workspace namespace、policy-filtered registry、sandbox no-host-fallback。特别确认上一轮 OpenAI-compatible ACL 修复是否覆盖实际 middleware 路径，而不只是 handler fixture。

### D. Persistence and database concurrency

- `internal/store/database.go`
- `internal/store/factory.go`
- `internal/store/database_integration_test.go`
- `internal/session`
- `internal/taskqueue`

核查：SQLite WAL、foreign keys、busy timeout、immediate transaction、read-to-write upgrade、WAL sidecar backup semantics、PostgreSQL portability、store-backed session fail-open、defensive task snapshots、缺少 transactional batch append 和 cross-instance locking 的后果。

### E. Provider, tools, plugins, MCP, Skills

- `internal/provider/openai.go`
- `internal/provider/anthropic.go`
- `internal/plugin`
- `internal/mcp`
- `internal/skills`
- `internal/agent/usage_trace.go`

核查：stream parser、tool-call assembly、usage/cache token、`RawAssistant` 非对称性、usage fallback、trusted `ToolCallContext`、JSON-RPC plugin、MCP tool、Skill full injection、不可达的 progressive `load_skill`、sandbox mount 差异。

### F. Evaluation harness

- `internal/eval/multiagent.go`
- `internal/eval/runner.go`
- `internal/eval/types.go`
- `internal/eval/report.go`
- `internal/eval/compare.go`
- `internal/eval/http_executor.go`
- `internal/evaltenant`

核查：evaluated/errored/passed 分母、baseline isolation、pair identity、Team/Solo estimand、fault observation/attribution、unsupported claim rate、negation/hedge/conditional handling、grader morphology、latency/token/cost aggregation、all-faulted edge、empty tool-call IDs、simulated-only fault gate。

### G. Financial application

- `plugins/finance-tools/plugin.py`
- `plugins/finance-tools/test_plugin.py`
- `evals/multiagent-finance-runtime.yaml`
- `internal/evaltenant/tenant.go`

核查：17 typed tools、`finance.tool.v1` envelope、tenant-isolated Thesis Ledger、optimistic versioning、watchlist/event dedup、Serenity role、compiled evidence fixture、verbatim-copy specialist instruction、r5 中 zero finance-tool calls、zero ledger mutations、zero injected faults。

## 四、论文级审查维度

### 1. Research framing

判断以下内容是否构成清晰、可证伪的研究问题，而不是项目功能清单：

- problem statement；
- research gap；
- research questions；
- contribution claims；
- novelty 相对于 Agent benchmark、workflow system 和 financial QA 的位置；
- “runtime is part of the treatment” 是否得到直接证据而非修辞支持。

### 2. Technical depth

对以下技术分别评分 0–5，并说明缺什么：

1. agent turn state machine；
2. MessageBus/TaskQueue scheduling；
3. cancellation and backpressure；
4. wait-graph cycle detection；
5. sub-agent dedup semantics；
6. provider streaming and tool-call protocol；
7. tenant authentication and authorization；
8. policy-filtered tools and sandbox；
9. plugin/MCP/Skill architecture；
10. SQLite WAL and transaction locking；
11. session consistency and workspace isolation；
12. telemetry and cost attribution；
13. evaluation harness and grader design；
14. fault injection and graceful degradation；
15. finance evidence governance and persistent state。

每一项都要回答：

- 它解决什么具体问题？
- 数据结构和控制流是什么？
- 正确性依赖什么 invariant？
- 为什么采用该方案而不是直接替代方案？
- 并发、取消、超时和崩溃时会怎样？
- 哪个测试验证了行为？测试没有验证什么？
- 论文是否把 implementation detail 误写成 research contribution？

### 3. Experimental methodology

逐项检查：

- RQ、hypothesis、estimand、baseline、metric 和 artifact 是否一一对应；
- Team 与 Solo 是否控制 evidence visibility；
- Two-Pass 是否真正是 compute-matched，还是只增加 coordinator pass；
- Routed Diagnostic 是否只能作为候选比较而非 oracle；
- r5 的 one repetition 和 n=6 对统计能力的限制；
- r2–r5 pooling 的 post hoc 性质；
- Wilson interval 和 exact paired test 使用是否正确；
- 是否需要 effect size、case bootstrap、hierarchical model 或 human adjudication；
- baseline timeout、429、network error 是否从能力分母排除但保留在成本账本；
- historical sequence 是否把 runtime、evidence 和 grader 漂移分开；
- grader ablation 是否足以说明 construct validity 风险；
- 当前实验能回答和不能回答哪些 RQ。

必须独立复算至少以下内容：

1. r5 每个 mode 的 raw count；
2. r2–r5 pooled count；
3. paired discordant table 和 exact two-sided p-value；
4. Wilson 95% interval；
5. Team/Open 与 Team/Two-Pass 的 token/cost ratio；
6. billable-like token 与 provider total 出现方向相反的原因；
7. grader ablation 各 mode 的 count；
8. incomplete-screening 的 milestone、contribution 和 coordination 聚合；
9. forbidden phrase 的 hedge exemption；
10. r5 faults denominator 是否为零。

如果复算值与论文不同，把它列为 P0；不要用“可能”掩盖可确定的数字错误。

### 4. Financial application validity

从真实应用角度审查：

- 当前系统究竟是研究 copilot、工作流框架、评测 harness，还是金融 Agent 产品；
- deterministic data/tool 与 model judgment 的边界是否合理；
- six fixed cases 是否足以代表金融研究；
- fixed lookup evidence 是否过度简化 retrieval、source authority 和 temporal provenance；
- Thesis Ledger、watchlist 和 event dedup 是否只在 Python plugin tests 中成立；
- Serenity 是否被正确描述为 research methodology，而非市场数据源或自动估值引擎；
- 没有 point-in-time universe、corporate actions、delisting、transaction cost 时为什么不能做可信回测；
- 下一阶段最有学术价值的金融实验是什么：retrieval-and-mutation integration、human-labeled entailment、larger holdout、Skill/challenger ablation，还是 return backtest；
- 哪些金融声明需要 human oversight、compliance 或 suitability 边界。

### 5. Security and threat model

检查论文是否完整覆盖：

- protected assets；
- trust boundaries；
- attacker capabilities；
- non-goals；
- prompt injection；
- model-generated tool arguments；
- tenant spoofing；
- API-key ACL；
- plugin subprocess and supply-chain risk；
- sandbox escape/fallback；
- stale session and store failure；
- cost exhaustion and fan-out；
- auditability and human approval。

特别区分“控制已实现”“控制有测试”“控制只在文档中存在”“控制属于 future work”。

### 6. Academic writing and argument structure

逐章检查：

- Abstract 是否准确反映主结果与限制；
- Introduction 是否明确 research gap，而不是列功能；
- Background 是否与 Related Work 混淆；
- Architecture 与 Implementation 是否重复；
- Methodology 是否预先定义指标，Results 是否避免引入新方法；
- Results 是否混入过多解释；
- Discussion 是否真正解释 case heterogeneity、trade-off 和 generalizability；
- Conclusion 是否逐个回答 RQ；
- Future Work 是否按证据缺口排序；
- 是否存在 marketing language、causal overclaim、模糊主语、不可证伪判断；
- 是否把 lexical match 写成 grounding/factuality；
- 是否把测试通过写成 correctness proof；
- 是否存在重复段落、冗长枚举、可移到附录的实现细节。

请至少给出 10 组：

`原句 → 建议改写 → 问题类型 → 为什么更严谨`

只有确实存在问题的句子才列，不要为了凑数改写已经准确的内容。

### 7. Related work and citations

核对 References [1]–[17]：

- 作者、标题、年份、会议/期刊、页码、DOI/URL 是否正确；
- 正文引用是否真正支持对应论点；
- 是否缺少 Agent runtime/workflow orchestration、resilience、database concurrency、financial decision support 等关键研究；
- 官方规范、benchmark paper、security guidance 和统计论文是否被正确区分；
- 是否存在只有官方网页而缺少学术文献的理论段落。

只能推荐可验证的一手来源。无法确认时标记“待核验”，不得生成看似真实的引用。

### 8. Reproducibility and artifact integrity

检查：

- Markdown 是否是正文事实源；
- `build_report.py` 是否硬编码实验结论；
- `build_artifacts.sh` 的两遍页码流程是否稳定；
- `page_map.json` 与 PDF 页码是否一致；
- DOCX/PDF/Markdown 的标题、章节、图表、数字和引用是否一致；
- manifest 的 suite/artifact SHA 是否匹配；
- manifest 是否准确披露 dirty snapshot、实际 repetition override、模型、endpoint class、pricing date；
- `finance_reanalysis.json` 是否可以由保留 artifact 零模型调用重算；
- `analysis/main.go` 是否真正独立复现 grader，还是复制同一实现导致共同错误；
- 外部未 vendored `finskills` 和 Serenity manifest 缺口是否披露充分；
- 是否存在秘密、绝对本机路径或无法在另一台机器满足的隐含依赖。

### 9. Visual and thesis-format review

必须查看最终 PDF 的全部 42 页，检查：

- TOC、List of Figures、List of Tables、Abbreviations 页码；
- 标题、页眉、页脚和页码；
- 空白页、孤立标题、孤立 caption；
- 长表重复表头、跨页断裂、数值列对齐；
- Figure 1–4 清晰度、字号、caption 和正文交叉引用；
- Algorithm 1 与 Markdown 源一致；
- reference wrapping、URL、DOI 和字号；
- 是否过密或存在大面积无意义留白；
- 42 页结构是否像毕业论文，而不是被拉长的项目报告。

## 五、严重度定义

- **P0 — Blocking:** 数字错误、代码事实错误、安全缺陷、不可复现却声称可复现、实验结论失真、引用错误导致核心论点失效。
- **P1 — Major:** 技术解释不足、RQ 与实验不匹配、重要 validity 缺失、论文结构不合格、关键机制没有证据链。
- **P2 — Minor:** 表达、术语、图表、引用格式、局部重复、版式或可读性问题。

不要把所有意见都列为 P0。每一项必须说明：

1. 精确位置：Markdown 行号和 PDF 页码；
2. 证据：代码、测试、JSON/YAML 或参考文献；
3. 实际影响；
4. 推荐修法；
5. 验证方法；
6. 是否影响 Abstract、Results 或 Conclusion。

## 六、输出格式

请严格按以下结构输出，并将同样内容写入：

`/Users/wangzheyu/fastclaw/CLAUDE-REVIEW-FINDINGS-project-report-thesis-round2-2026-08-01.md`

### 1. Overall Verdict

- 当前达到：普通项目报告 / 优秀毕业设计 / 本科论文 / 授课型硕士项目论文 / 尚不合格。
- 分别给 0–10 分：academic rigor、technical depth、methodology、statistical validity、reproducibility、security reasoning、writing、citation quality、visual quality。
- 用不超过 250 字给出最核心判断。

### 2. Previous-Review Closure Audit

表格列：旧 ID、作者状态、你的复核结果、证据、是否回归、剩余风险。

至少重点复核 P0-01、P0-03、P0-05、P0-07、P0-10、P0-14、P0-16、P1-04、P1-08、P2-04、P2-09。

### 3. New Findings by Severity

按 P0 → P1 → P2 排序。每条包含位置、证据、影响、方案、验证。

### 4. Claim–Evidence Matrix

表格列：核心论文声称、代码证据、测试证据、实验 artifact、当前支持程度、允许使用的表述、禁止使用的表述。

至少覆盖 runtime correctness、orchestration benefit、efficiency、fault tolerance、financial workflow validity、安全与可复现性。

### 5. Independent Numerical Audit

列出复算公式、输入、结果、论文值、是否一致。必须包含本 Prompt 要求的十项复算。

### 6. Technology Depth Audit

覆盖前述 15 类技术。每项给评分、当前优点、缺失原理、替代方案、trade-off、测试缺口和建议章节。

### 7. Experimental Methodology Audit

给出：

- RQ → hypothesis → estimand → baseline → metric → artifact → conclusion 映射；
- 当前实验能回答与不能回答的问题；
- minimum defensible next experiment；
- recommended sample size/repetitions 的依据，而不是任意数字。

### 8. Financial Application Audit

区分已实现、已测试、r5 已执行、仅规划四种状态。给出下一阶段实验优先级。

### 9. Security and Threat-Model Audit

列出 control、实现证据、测试证据、残余风险和论文表述边界。

### 10. Academic Writing Findings

给出至少 10 个真正需要修改的句子示例，并区分语言问题、事实问题和方法问题。

### 11. Citation and Related-Work Audit

逐条列出错误引用、弱引用、缺失主题和可验证 primary source 建议。

### 12. Visual and Build Audit

逐页检查结果、页码/目录一致性、图表问题、生成器可重复性和本机依赖问题。

### 13. Prioritized Remediation Plan

按 P0/P1/P2 给出实施顺序。每项包括：修改文件、修改内容、是否需要新模型调用、预计成本等级、验收命令/证据。

### 14. Safe Abstract and Conclusion Boundary

- 给出当前证据允许写入 Abstract/Conclusion 的要点；
- 单列必须删除或禁止出现的结论；
- 如现有 Abstract/Conclusion 已安全，明确说“无需为了显得更强而改写”。

### 15. Defense Questions

从答辩委员会角度给出 15 个高压问题，并附“优秀回答应覆盖的要点”。重点追问：

- 为什么这不是模型 benchmark；
- 为什么 Team 没有显著优于 Solo；
- runtime contribution 如何隔离；
- fixed evidence 的意义；
- 为什么 lexical grader 仍有研究价值；
- 28.4% coverage 能支持什么；
- dirty snapshot 的复现边界；
- 金融应用为何没有收益回测；
- 安全控制是否完整；
- 下一项实验为何优先。

## 七、审查约束

1. 不要修改源码、论文、实验 artifact、DOCX/PDF 或 Git。
2. 只允许新增指定的 round-2 findings 文件。
3. 不要启动 Gateway、调用真实模型或产生 API 费用。
4. 不要读取、输出或引用 `runtime-benchmark-tenant.json` 的内容。
5. 不要根据 README 猜测实现；必须读代码和测试。
6. 不得把 style subset 写成官方 benchmark score。
7. 不得把 fixed evidence 写成 live retrieval。
8. 不得把 lexical attribution 写成 factual entailment。
9. 不得把 workflow correctness 写成投资收益。
10. 不得把单次 n=6 写成 equivalence、significance 或 universal finding。
11. 不得把 historical association 写成 isolated causal effect。
12. 不得把 Routed Diagnostic 写成 guaranteed oracle upper bound。
13. 不得把 zero fault denominator 写成 robustness evidence。
14. 不得把 dirty snapshot 写成 exact execution reproducibility。
15. 不得因为论文已有 42 页而建议无意义扩写；新增内容必须服务于 RQ、mechanism、validity 或 reproducibility。
16. 不得虚构 Kafka、Redis、Kubernetes、vector database、RAG、交易执行、实时行情或代码中不存在的架构。
17. 如果建议新增功能或实验，必须标记为 proposed work，不得写成现有实现。
18. 引用必须可验证，不确定时明确标记待核验。
19. 先判断事实和方法是否正确，再评价写作是否漂亮。
20. 如果没有新的 P0，明确写“未发现新的 P0”，不要为了显得严格而制造问题。
```

