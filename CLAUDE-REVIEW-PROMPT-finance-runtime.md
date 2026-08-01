# Claude Review Prompt: FastClaw Financial Runtime Evaluation

## 使用方式

1. 将 Claude 的工作目录设置为 `/Users/wangzheyu/fastclaw`。
2. 先使用“主 Review Prompt”，要求只审查、不修改。
3. 根据首轮发现，再使用“指标方法论专项”或“生产运行时专项”。
4. 确认需要修复的问题后，最后使用“修复实施 Prompt”。
5. 不要把 `/Users/wangzheyu/fastclaw/runtime-benchmark-tenant.json` 的 API key
   粘贴到对话、报告或提交中。

---

## Prompt 1：主 Review

```text
你是一名 Principal Go Systems Engineer、LLM Evaluation Scientist 和金融科技测试架构师。

请对 FastClaw 当前分支上的“金融多 Agent Runtime 评测”进行一次严格、可证伪、以生产风险和指标可信度为中心的代码审查。第一轮只审查，不要修改代码。

仓库：/Users/wangzheyu/fastclaw
当前分支：codex/finance-agent-runtime
基线分支：m0yuw-project
当前 HEAD：351ee422f25ef86fc3c0159f7894739be95ac1a6

重要：当前工作区还有尚未提交的修改和 untracked 实验文件。不要只看 commit history。至少执行：

git status --short
git diff --stat
git diff
git diff m0yuw-project...HEAD

并主动阅读这些文件：

- internal/eval/multiagent.go
- internal/eval/runner.go
- internal/eval/types.go
- internal/eval/report.go
- internal/eval/compare.go
- internal/eval/multiagent_test.go
- internal/agent/sdkbridge.go
- internal/agent/sdkbridge_test.go
- internal/agent/loop.go
- internal/agent/context.go
- internal/agent/context_contract_test.go
- internal/store/database.go
- internal/store/factory.go
- internal/store/database_integration_test.go
- internal/evaltenant/tenant.go
- internal/evaltenant/tenant_integration_test.go
- evals/multiagent-finance-runtime.yaml
- evals/multiagent-finance-workflow.yaml
- evals/finance-runtime-formal-r1.md
- project-report/fastclaw_project_report.md
- project-report/build_report.py
- project-report/artifact.md
- project-report/FastClaw_Project_Report_Zheyu_Wang.docx
- project-report/FastClaw_Project_Report_Zheyu_Wang.pdf
- project-report/assets/fastclaw_architecture.png
- project-report/assets/finance_workflow.png
- project-report/assets/multiagent_sequence.png
- /Users/wangzheyu/PROJECT-HANDOFF.md

实验原始数据：

- finance-runtime-formal-r1.json：正式四基线单次实验。
- finance-runtime-parallel-team-r2.json：修复并发和 SQLite 后的 Team-only 复测。
- finance-runtime-parallel-team-r1.json：故障发现运行，存在 SQLITE_BUSY 和身份读取失败，不能用于质量或延迟结论。

本轮声称实现了：

1. 新增 solo_two_pass，作为与 Team 更接近的两阶段 compute-matched baseline。
2. 新增 forbidden_output_values 和 grounding accuracy，grounding 违规会使 Team 和 baseline outcome 失败。
3. 空输出即使 executor 返回 nil error，也作为 baseline error，且不进入成功率分母。
4. 报告和 compare 增加 compute-matched gain、grounding、分 baseline token/cost/latency。
5. 新增 6 个固定时点金融案例，以及 source/methodology/governance 三个真实 Flash specialist。
6. distinct target 的 spawn_subagent 可并发；同一 target 的重复调用仍串行。
7. 修复 tool hook latency 起始时间丢失。
8. SQLite 默认启用 WAL、foreign_keys 和 busy_timeout(5000)，并验证并发 writer 会等待。
9. required identity file 读取保留底层 store error，不再把 SQLITE_BUSY 误报成 missing/empty。
10. 真实实验记录 coordinator/sub-agent token、成本和延迟分解。

请重点验证，不要默认相信上述声称：

A. 指标和基线公平性
- solo_two_pass 两次请求是否真的共享第一遍分析上下文，是否与 Team 的两次 coordinator pass 足够可比。
- baseline err/empty output 是否从 Evaluated 分母剔除；gain 是否在任一侧无有效样本时标记为不可计算。
- Team success、Team outcome、baseline success 是否使用一致的 milestone + grounding 口径。
- MATotal cost 是否能和各 baseline cost 对账；token、latency 是否混入不该混入的 baseline。
- compare/report 是否正确处理缺失 baseline、旧报告兼容和 Valid 标记。
- grounding 分子分母是否可能超过 100%、重复计数或被空配置污染。

B. Grader 正确性
- containsAllInOrderFold 是否会跨句、跨段或跨无关事实产生假阳性；测试名称中的“bounded”是否与实现一致。
- 数字、单位、方向和版本号是否可能被 normalize 后错误匹配，例如 8→5 与 5→8、>25 与 <25。
- forbidden assertion 的否定、条件、引用、反事实和不确定表达是否仍可能误判。
- 当前 6 个金融 case 是否存在模型越正确、grader 越容易判错的表达。
- pilot 后补 alternatives 是否造成 calibration leakage；正式分和人工复核分是否被清楚分离。

C. 生产运行时语义
- spawn_subagent 并发判定是否只并发真正独立的 distinct target；空/畸形参数、重复 target、多组 tool call 和取消时是否安全。
- 并发是否改变 tool result 顺序、trace 归属、session 语义、usage collector 或 parent-turn dedup 行为。
- 同一批里对同一 target 的不同 task 被强制串行是否符合原有语义；是否仍会被更早的 dedup 逻辑错误复用。
- hook StartTime 通过 slice index 对齐结果是否可靠；SDK 是否保证 results 与 toolCalls 顺序一致。
- SQLite DSN 拼接对 file URI、已有 query、已有 busy_timeout、内存数据库和自定义 DSN 是否正确。
- WAL 和 busy_timeout 是否真正覆盖多连接写入场景；测试是否可能因为 timing 而 flaky。
- identity store error 与 filesystem fallback 的优先级是否会隐藏真实存储故障或破坏旧安装兼容。

D. 实验方法论和对外表述
- 6 cases × 1 repetition 能支持哪些结论，不能支持哪些结论。
- 静态 evidence in identity files 能测到 runtime 的哪些能力，不能测到金融数据检索、预测或收益能力。
- Team vs Solo Open-Book、Team vs Solo Two-Pass、Oracle Team 的 estimand 是否准确。
- “并发节省 9.3%”的 within-run serial counterfactual 算法是否成立，是否遗漏 runtime overhead 或 provider overlap。
- 价格配置、cache token 和成本分解是否与原始 JSON 一致。
- 请用 jq 或脚本从 JSON 独立重算关键数字，不要只相信 Markdown 报告。

E. Project Report 的学术可信度和产物一致性
- 将 project-report/fastclaw_project_report.md 视为正文事实源，逐项核对代码、测试、YAML 和 JSON，不要只做语言润色。
- 当前正文仍称“四模式重复金融结果尚未报告”，但 finance-runtime-formal-r1.json 已产生一次四基线真实运行；找出所有类似的过期陈述。
- 检查 baseline 定义是否遗漏 solo_two_pass，fair gain 和 compute-matched gain 的公式、分母、Valid 语义及 outcome grader 是否与代码一致。
- 检查 Results、Discussion、Limitations、Future Work 和 Conclusion 是否纳入最新金融实验、Grounding、并发执行、SQLITE_BUSY 故障发现及修复，同时保留 8-case 历史两基线结果的独立口径。
- 审查“100%”“Grounding”“公平”“compute-matched”“因果”“真实 runtime”“并发节省 9.3%”等词是否被过度解释。
- 验证项目报告没有把固定 identity evidence 描述成真实市场检索，没有把工作流正确性描述成预测能力或投资收益。
- 核对 build_report.py 中的表格和正文常量，防止 Markdown 已更新但 DOCX/PDF 仍使用旧硬编码数据。
- 检查 artifact.md 中的 authoritative evidence、HEAD、测试覆盖率、测试数量和 fidelity gates 是否过期。
- 检查三张架构图是否与当前实现一致，图注是否清楚区分 production runtime、eval harness 和 finance plugin。
- 检查引用是否真实支持相邻论点、编号是否连续、是否存在虚构论文、伪 IEEE 发表信息或未经验证的覆盖率/性能数字。
- 渲染并目视检查 DOCX/PDF：分页、表格宽度、图片清晰度、caption、孤行、页眉页脚、字体、裁切和参考文献格式。
- 检查 Markdown、build_report.py、DOCX、PDF 四者是否同源且可重复生成；列出 stale generated artifact。

输出要求：

1. 先给结论：可合并 / 修复后可合并 / 不建议合并。
2. Findings 按 Critical、High、Medium、Low 排序。
3. 每条 finding 必须包含：文件与行号、触发场景、实际后果、为什么现有测试没挡住、最小修复建议。
4. 将“代码 bug”“指标口径 bug”“实验设计限制”“文档表述问题”分开，不要混为一类。
5. 对没有问题的关键路径也简要说明验证依据。
6. 单独列出需要新增的测试，优先行为测试和并发测试。
7. 单独给一份“简历/论文可安全使用的结论”和“当前不能声称的结论”。
8. 单独给出 Project Report 的事实错误清单、过期段落清单和重新生成 DOCX/PDF 前的阻塞项。
9. 不要给泛泛而谈的重构建议，不要因为 PR 大就要求无关重构。
10. 第一轮不要修改文件，不要提交代码。
```

---

## Prompt 2：指标与实验方法论专项

```text
基于你上一轮对 /Users/wangzheyu/fastclaw 的审查，现在只审计评测指标和金融实验方法论，不修改代码。

请逐项建立“metric definition → numerator → denominator → error handling → JSON field → text report → comparison delta”的数据血缘，覆盖：

- Team full harness success
- Team outcome success
- Solo Open-Book success
- Solo Two-Pass success
- Oracle Team success
- fair collaboration gain
- compute-matched collaboration gain
- delegation precision/recall/F1
- contribution utilization
- grounding accuracy
- per-baseline tokens/cost/latency
- coordinator/sub-agent tokens/cost/model latency

要求：

1. 从 internal/eval/multiagent.go、runner.go、types.go、report.go、compare.go 追踪每个字段。
2. 使用 finance-runtime-formal-r1.json 独立重算结果并与 evals/finance-runtime-formal-r1.md 对账。
3. 找出所有可能导致指标被虚增、虚减、超过 100%、错误进入分母或显示为 0 而实际不可计算的路径。
4. 审查 lexical matcher、ordered matcher 和 forbidden assertion matcher 的假阳性/假阴性。
5. 评估 pilot 后扩充 alternatives 对正式实验的污染，并提出 calibration/validation/holdout 划分方案。
6. 最后设计一个至少 30 case × 3 repetitions 的后续实验，包括 bootstrap CI、paired comparison、失败分类和成本预算。

输出以“可复现公式、发现、修复优先级、后续实验设计”四部分组织。
```

---

## Prompt 3：生产 Runtime 与并发专项

```text
基于你上一轮对 /Users/wangzheyu/fastclaw 的审查，现在只审查生产 runtime 变更，不修改代码。

重点文件：

- internal/agent/sdkbridge.go
- internal/agent/sdkbridge_test.go
- internal/agent/loop.go
- internal/agent/context.go
- internal/agent/context_contract_test.go
- internal/store/database.go
- internal/store/factory.go
- internal/store/database_integration_test.go
- internal/taskqueue 和 session/store 相关调用链

请沿真实调用链回答：

1. 三个 distinct spawn_subagent 如何被 SDK executor 分组并发，结果顺序如何回填。
2. duplicate target、malformed agentId、context cancel、部分失败和 panic 时会发生什么。
3. usage collector、trace event、tool call ID、hook latency 是否能正确归属到对应调用。
4. 并发 sub-agent 的 session 写入为何触发 SQLITE_BUSY，WAL + busy_timeout 是否是充分修复。
5. SQLite 配置是否会影响已有用户、自定义 DSN、内存库或 PostgreSQL。
6. identity file store error 是否会通过 streaming/non-streaming 路径向调用方暴露正确错误。
7. 是否存在数据竞争、goroutine 泄漏、重复执行、结果复用或取消不及时。

请提出可执行的 race/concurrency 测试矩阵，并标出哪些测试应该使用 go test -race、哪些必须做真实 gateway integration test。Findings 必须给文件和行号。
```

---

## Prompt 4：Project Report 学术与产物专项

```text
现在只审查 /Users/wangzheyu/fastclaw/project-report，不修改文件。你同时扮演学术论文审稿人、实验方法学审计员和技术文档发布工程师。

必须检查：

- project-report/fastclaw_project_report.md
- project-report/build_report.py
- project-report/artifact.md
- project-report/FastClaw_Project_Report_Zheyu_Wang.docx
- project-report/FastClaw_Project_Report_Zheyu_Wang.pdf
- project-report/assets/*.png
- evals/finance-runtime-formal-r1.md
- finance-runtime-formal-r1.json
- finance-runtime-parallel-team-r2.json
- 相关 Go 实现和测试

审查目标：

1. 事实核验：所有架构、功能、测试、覆盖率、性能、成本和实验数字必须能追溯到代码或原始 artifact。
2. 时效核验：找出仍声称金融实验“未运行”、仍只列旧四模式、未包含 solo_two_pass/Grounding/并发修复的段落。
3. 方法核验：检查研究问题、假设、estimand、baseline 公平性、误差分母、人工语义复核和 calibration leakage 是否被诚实描述。
4. 结论边界：不得将固定 evidence workflow success 扩张为金融预测、选股 alpha、回测收益或真实数据检索能力。
5. 历史口径：8-case 两基线优化结果与 6-case 四基线金融结果必须分表、分口径，禁止直接比较总 tokens 和 attempt latency。
6. 产物一致性：检查 Markdown、build_report.py、DOCX、PDF 的标题、表格、数字、图、参考文献和结论是否一致。
7. 视觉 QA：将 DOCX/PDF 渲染为页面图片，检查裁切、重叠、表格断行、图片分辨率、caption、页眉页脚和参考文献悬挂缩进。
8. Academic style：避免营销化、绝对化、因果过强和“benchmark score”误导；检查术语定义、公式、图表自解释性和 limitation 完整性。
9. 引用核验：逐条检查文献存在性和支持关系，不允许虚构引用或只因关键词相关就引用。
10. 可复现性：检查 build_report.py 是否能从当前 Markdown 和资产稳定生成 DOCX/PDF，是否存在硬编码旧结果。

输出格式：

- Overall verdict
- Critical factual inconsistencies
- Experimental-methodology issues
- Unsupported or overstated claims
- Stale sections and exact replacement intent
- DOCX/PDF visual defects
- Reference/citation issues
- Build reproducibility issues
- Safe abstract/conclusion claims
- Regeneration checklist

每条问题给出文件、页码或 Markdown 行号、证据来源和建议修改方向。不要在第一轮直接重写整篇报告。
```

---

## Prompt 5：确认问题后的修复实施

```text
现在根据已确认的 review findings 修改 /Users/wangzheyu/fastclaw。

约束：

1. 只修复已确认问题，不做无关重构。
2. 先列 3–7 步实施计划，再开始修改。
3. 每个生产行为修复必须附行为测试；每个指标修复必须附分子/分母或 invalid-state 测试。
4. 保持旧 JSON 报告兼容，新增字段使用零值和 Valid 标记区分“0”和“不可计算”。
5. 不得把 benchmark/eval 行为泄漏到默认生产 turn。
6. 不得输出或提交 runtime-benchmark-tenant.json 中的 API key。
7. 修改后执行：

go test ./internal/eval ./internal/agent ./internal/agent/tools ./internal/store ./internal/evaltenant ./cmd/fastclaw
git diff --check

8. 如果改动涉及并发，再执行适用包的 go test -race，并说明未执行的真实网络测试。
9. 最终报告：修复项、测试、剩余风险、是否需要重跑真实金融实验。
10. 如果修改 project-report，先更新 Markdown 和 build_report.py，再重新生成并视觉检查 DOCX/PDF；不得只手改生成产物。
11. 不要 commit 或 push，除非我明确要求。
```
