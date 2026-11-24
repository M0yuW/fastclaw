# Project Report Thesis Review Resolution

审查输入：`CLAUDE-REVIEW-FINDINGS-project-report-thesis-2026-08-01.md`

目标：按证据风险而非排版便利排序，先修会造成错误结论、越权或不可复现的问题，再扩展技术论证与论文结构，最后重建并逐页验证 DOCX/PDF。本文只记录当前修复批次的学术可追踪性，不在论文正文中叙述开发提交历史。

状态含义：`TODO` 未实施；`IN PROGRESS` 正在实施；`DONE` 已实施并有验证证据；`DISCLOSED` 无法在本轮以零成本重跑消除，但已在论文中明确限定。

## P0 — 结论有效性、安全与可复现性

| ID | 问题 | 解决方案 | 验证 | 状态 |
|---|---|---|---|---|
| P0-01 | r5 失败原因误写为窗口距离 | 改为 `estimate`/`estimated` 形态归一化缺口，并讨论保守匹配的权衡 | 对照 suite、输出与 matcher | DONE |
| P0-02 | r5 同一 case 的 milestone 与 contribution 双失败未披露 | 报告两条失败、2/3 contribution、0.8333 case coordination 及全局聚合来源 | 对照 r5 artifact | DONE |
| P0-03 | 单次 n=6 被表述为相等或无优势 | 明确最小双侧精确 p 值 0.03125；0 pp 解释为“未检出”，不作等价性结论 | 统计段与摘要用语审计 | DONE |
| P0-04 | 历史实验混杂 runtime 与 grader 漂移 | 改为 historical regression study；披露 0/8→4/8→8/8 与未按最终 rubric 重评 | 对照历史 artifacts | DONE |
| P0-05 | r2–r5 稳定套件信息未利用 | 增加 post-hoc pooled sensitivity、精确配对表、Wilson 区间与 per-case 4-run 矩阵 | 独立脚本复算 | DONE |
| P0-06 | forbidden grounding 的 hedge 豁免未披露 | 报告 44/44 中一次 `may` hedge exemption，避免把零违规解释为短语从未出现 | 对照 trace 与 grader | DONE |
| P0-07 | 覆盖声明超过实测证据 | 重跑覆盖率；报告总覆盖率、关键包与零覆盖包；把 scanner 降格为未验证启发式 | `go test -coverprofile` = 28.4% | DONE |
| P0-08 | r5 未执行金融工具或持久化状态变更 | 将 RQ5 改为回答措辞/治理决策正确性；ledger 正确性只由 Python 测试支持 | trace 工具名审计 | DONE |
| P0-09 | specialist 证据是硬编码逐字复制 fixture | 明确真实 runtime 调用与受控证据 fixture 的边界，不声称 retrieval 或 specialist reasoning | 对照 `tenant.go` 与 SOUL | DONE |
| P0-10 | token 口径因 cache-read 双计而误导 | 计费近似口径优先，同时报告 provider total；重写 Team/Open 与 Team/Two-Pass 比较 | 从 r5 usage 复算 | DONE |
| P0-11 | RQ4 容错指标分母为零 | 将 RQ4 标为 instrument contributed but not exercised；不把零值解释为表现 | 对照 `faults_expected=0` | DONE |
| P0-12 | 核心指标承诺但未报告 | 补 milestone、contribution、delegation P/R、coordination 与 diagnostic oracle gap | 对照 r5 metrics | DONE |
| P0-13 | baseline gain 仅守卫计数，不验证 case 配对 | 报告实现守卫边界，并说明论文统计由 case/repetition 标识手工配对 | 代码与统计方法交叉审计 | DONE |
| P0-14 | OpenAI 兼容端点省略 agent header 时绕过 API-key ACL | 解析 agent 后强制 `Identity.CanAccessAgent`；显式未知 agent 不再回退默认 agent | 允许、拒绝、未知目标行为测试 | DONE |
| P0-15 | 主实验缺少实际运行配置 | 新增 r5 reproducibility manifest：命令、override、modes、timeout、模型角色、端点类别、pricing date | `jq` 内容检查 | DONE |
| P0-16 | 主实验来自 dirty source snapshot | 记录 dirty 状态、HEAD、Go 版本、关键文件 SHA 与复现边界；不伪造可复现 commit | manifest 与附录一致性 | DISCLOSED |
| P0-17 | suite 与 artifacts 未被仓库钉定 | 将 suite 纳入 bundled-suite 解析测试；文档列明 canonical artifact 与 SHA | Go 测试 + SHA 校验 | DONE |
| P0-18 | `finskills` 是外部未 vendored 依赖 | 标记 external dependency；区分插件 subprocess 单测与 r5 未调用该插件的事实 | 文档依赖审计 | DISCLOSED |

## P1 — 技术深度与论文论证

| ID | 问题 | 解决方案 | 验证 | 状态 |
|---|---|---|---|---|
| P1-01 | Related Work 薄弱 | 扩展 runtime benchmark gap、ReAct、BFCL、τ-bench、SWE-bench、MultiAgentBench、MCP、安全与统计方法；仅引用一手来源 | 17 项来源逐条核验 | DONE |
| P1-02 | 缺少 threat model | 增加资产、信任边界、攻击面、假设、非目标、控制与残余风险表 | 与代码路径核对 | DONE |
| P1-03 | 并发与调度机制只有行为描述 | 补 semaphore、per-chat FIFO、`WithoutCancel`、双取消边、背压与替代方案 | 与 queue/bus 代码核对 | DONE |
| P1-04 | MessageBus 跨 root 环检测缺少论证 | 给出双 root 反例、wait graph invariant、持锁 DFS 代价与替代方案 | 图与算法核对 | DONE |
| P1-05 | Agent turn 未形式化 | 增加状态机、终态副作用、tool-call/result 配对 invariant 与流式事件契约 | 与 loop/session 代码核对 | DONE |
| P1-06 | Provider 描述存在对称性过度声称 | 区分 OpenAI/Anthropic `RawAssistant` 与 usage 装配；说明 fallback 局限 | 适配器代码核对 | DONE |
| P1-07 | Skills、sandbox、session、task deadline 等表述不准确 | 更正 `load_skill` 不可达、五类有效路径、两固定挂载、session fail-open、queue-wide timeout、双 256 上限 | 代码证据核对 | DONE |
| P1-08 | 实验方法缺少 grader ablation | 对现有 artifacts 做六开关零模型调用消融，量化形态、否定、hedge 等规则影响 | Go 重分析与回归测试 | DONE |
| P1-09 | 缺少 validity 与 ethics 结构 | 按 construct/internal/external/conclusion validity 重组限制；增加金融责任边界与 human-in-the-loop | 章节审计 | DONE |
| P1-10 | RQ/H/metric/artifact 关系不清 | 增加映射表，未执行假设明确标 not tested | 表格一致性检查 | DONE |
| P1-11 | Oracle 被暗示为上界 | 统一改为 diagnostic routed-team candidate，并解释其低于 Team 的原因 | 全文术语检索 | DONE |
| P1-12 | Serenity 完整性表述过强 | 改为 executable content verified；披露 README 哈希失败与五/三 specialist 计数边界 | 文件清单核对 | DONE |

## P2 — 论文产物与版式

| ID | 问题 | 解决方案 | 验证 | 状态 |
|---|---|---|---|---|
| P2-01 | 日期不一致 | 元数据加入报告日期，标题页与页脚统一为 August 2026 | DOCX/PDF 视觉检查 | DONE |
| P2-02 | Algorithm 1 不在 Markdown 单一事实源 | 把算法内容移入 Markdown，生成器只负责渲染 | 源码/产物对照 | DONE |
| P2-03 | 表格忽略数值列对齐且宽度规则有限 | 解析 Markdown alignment，按列内容和对齐标记生成 2–6 列宽度 | 渲染检查 | DONE |
| P2-04 | 缺 TOC、图目录、表目录和缩略语 | 增加两遍渲染的静态目录、图表页码与缩略语表 | 页码映射二次校验 | DONE |
| P2-05 | 图表交叉引用不足 | 所有主图表有稳定编号并在正文显式引用 | 全文检索 | DONE |
| P2-06 | Figure 2 缺 MessageBus | 重绘为 Client→Gateway→TaskQueue→Coordinator→Provider/MessageBus→parallel specialists | 图像审查 | DONE |
| P2-07 | 长表跨页可读性不足 | 重复表头、保持行完整、标题与表格同页；必要时拆分表格 | 42 页逐页视觉检查 | DONE |
| P2-08 | 引用编号与元数据不规范 | 按首次出现重排，核验 MCP/BFCL/τ-bench/JSON-RPC/统计与安全来源 | 一手来源链接检查 | DONE |
| P2-09 | 构建流程依赖本机隐含环境 | 增加可执行两遍式构建脚本和依赖覆盖变量；生成 DOCX/PDF 与渲染页 | `build_artifacts.sh` 重建 | DONE |
| P2-10 | 篇幅与论文结构不足 | 扩展为 thesis-style 章节并提升技术、方法和讨论占比 | 17,520 words / 42 pages；为保留审查所需技术证据高于原字数目标 | DONE |

## 验证门禁

1. 生产代码：相关 Go 包测试通过；ACL 行为有允许、拒绝、未知目标三类测试。
2. 实验数字：所有新增表格由 artifact 机器复算，禁止手工抄算作为唯一证据。
3. 引用：仅使用可访问的一手论文、规范或权威安全资料；正文论点与来源匹配。
4. 文档：Markdown 为主要事实源；DOCX/PDF 从同一生成器重建。
5. 视觉：最终 PDF 每页渲染为 PNG，逐页检查裁切、重叠、孤立标题、表格和图注。
6. 安全：不读取或输出 `runtime-benchmark-tenant.json` 中的密钥。

## 最终验证记录

- `go test ./internal/api ./internal/eval ./project-report/analysis -count=1`：通过。
- `go test ./... -count=1`：通过。
- `go test ./... -coverprofile=/tmp/fastclaw-thesis.cover -count=1`：通过；总 statement coverage 28.4%。
- `plugins/finance-tools` 的 `python -m unittest -v`：10/10 通过。
- r5 suite/artifact SHA-256 与 manifest、正文和附录一致；manifest JSON 可解析且不含 API key。
- `finance_reanalysis.json` 重跑前后 SHA-256 相同，零模型调用重分析幂等。
- DOCX/PDF 经两遍式构建，最终 42 页；全部页面已从最新 PDF 渲染 PNG 并逐页检查。
- `git diff --check`：通过。
