# Prompt：审阅 FastClaw 评测系统并更新 Project Report

请在本地仓库中完成一次“先审阅证据、再更新报告”的任务。不要仅根据聊天历史或某一份总结改写报告，也不要发明代码、实验结果或统计结论。

## 任务目标

我要把 FastClaw 的自动化评测系统完整、准确地写入英文 Project Report。请完成以下工作：

1. 阅读现有评测系统的架构、代码、suite 配置、测试和保留结果；
2. 建立“报告主张 → 本地证据文件”的对应关系；
3. 检查现有 Project Report 对评测系统的描述是否缺失、过时、重复或超过证据边界；
4. 在不改变报告整体学术风格的前提下，补充或修订评测系统相关内容；
5. 最后给出修改摘要、证据索引、仍未满足的实验门槛和验证结果。

项目根目录：

```text
/Users/m0yuw/Downloads/fastclaw-complete-device-migration-2026-08-11/fastclaw-finance-e2e
```

目标报告：

```text
project-report/fastclaw_project_report.md
```

报告是英文、接近 IEEE 技术报告结构。请保持现有章节编号、术语、表格风格和审慎口径。以文字和表格为主，最多提出一张必要的评测数据流架构图，不要堆叠图像。

## 先做证据审阅，不要立即修改

请先输出一张简短的证据地图，至少包含：组件或结论、主要源文件、它能证明什么、不能证明什么。只有完成证据地图后，才开始编辑报告。

证据优先级如下：

1. 当前实现代码、suite 配置、保留的机器报告和 manifest；
2. 与结果配套的 final summary、实验 protocol、测试代码；
3. `PROJECT-HANDOFF.md` 中的工程演进记录；
4. 现有 Project Report；
5. 面试复习文档只能帮助理解，不能作为实验主张的主要证据。

如果不同文件冲突，不要自行挑选更好看的数字。请指出冲突，按机器报告、manifest 和最新边界说明处理，并在报告中保留不确定性。

## 建议阅读顺序

### 1. 先了解报告现状和工程边界

```text
project-report/fastclaw_project_report.md
PROJECT-HANDOFF.md
TESTING.md
evals/README.md
FINANCE-RUNTIME.md
```

重点阅读报告中的：

```text
III. FASTCLAW SYSTEM ARCHITECTURE
IV. AGENT RUNTIME EXECUTION MECHANISM
VI. EVALUATION METHODOLOGY
VII. RESULTS
VIII. DISCUSSION
IX. SECURITY, ETHICS, LIMITATIONS, AND FUTURE WORK
APPENDIX B. REPRODUCIBILITY CHECKLIST
```

`PROJECT-HANDOFF.md` 用于理解功能演进、8-case 真实 Gateway 回归、故障注入、金融 workflow 和 retrieval Pilot，但它不是替代代码与原始报告的唯一真值。

### 2. 查看评测系统入口和通用流水线

```text
cmd/fastclaw/cmd_eval.go
internal/eval/types.go
internal/eval/suite.go
internal/eval/runner.go
internal/eval/http_executor.go
internal/eval/grader.go
internal/eval/report.go
internal/eval/compare.go
```

需要准确说明以下数据流：

```text
YAML/JSON suite
→ Eval CLI 和 suite loader
→ Runner 为 case × repetition × mode 创建独立 session 和 timeout
→ HTTPExecutor 经过真实 Gateway，或确定性 fixture executor
→ Agent Runtime 执行模型、工具和子 Agent
→ Gateway 返回最终文本、Trace、usage 和状态
→ grader 分别评估结果、过程、状态和故障处理
→ report 聚合成功率、错误、延迟、Token、费用和专项指标
→ compare 对 baseline 与 candidate 做同口径比较
```

不要把 `TraceEvent`、最终文本和 `model_calls` 混成同一个字段。说明 tool call/result 通过 call ID 关联，usage 明细用于模型、角色、Token、费用和延迟归因。

### 3. 查看专项 runner 和 benchmark-style suite

```text
internal/eval/bfcl.go
internal/eval/tau.go
internal/eval/swe.go
internal/eval/multiagent.go
internal/eval/finance_retrieval.go
```

对应配置：

```text
evals/smoke.yaml
evals/bfcl-v4-simple-subset.yaml
evals/tau-retail-subset.yaml
evals/swebench-local-subset.yaml
evals/multiagent-collaboration-subset.yaml
evals/multiagent-runtime-tenant.yaml
evals/multiagent-fault-injection.yaml
evals/multiagent-finance-workflow.yaml
evals/multiagent-finance-runtime.yaml
```

必须区分：

- BFCL 文件只包含三个官方 V4 `simple_python` 记录的项目内派生子集；
- τ-bench、SWE-bench 和 MultiAgentBench 文件主要是项目手写的 style subset；
- 这些 suite 用 FastClaw 自己的 Gateway、fixture、Trace 和 grader；
- 它们用于 Runtime 回归，不能写成官方 benchmark 总分或排行榜结果。

### 4. 查看真实 Runtime 与可观测性如何支撑评测

```text
internal/api/openai.go
internal/agent/loop.go
internal/agent/usage_trace.go
internal/agent/tools/subagent.go
internal/taskqueue/queue.go
internal/evaltenant/tenant.go
internal/store/database.go
```

需要说明 Harness 不是独立于 Runtime 的纯脚本：真实模式通过 Gateway 进入生产式执行路径，并使用请求级 `eval` 配置、独立 session、Trace、usage breakdown、子 Agent 路由、超时和取消。也要区分模拟故障与真实故障：故障 suite 中的 timeout、error、malformed 和 contradiction 是请求内可控 fixture，不是破坏真实生产服务。

### 5. 查看测试证据

优先阅读：

```text
internal/eval/*_test.go
internal/evaltenant/tenant_integration_test.go
internal/agent/tools/subagent_test.go
internal/agent/sdkbridge_test.go
internal/api/openai_trace_test.go
internal/store/database_integration_test.go
```

确认代码路径是否真的有测试，再在报告中使用“tested selected path”“integration-tested invariant”等有限表述。不要把单元和集成测试写成生产可靠性证明或形式化验证。

### 6. 查看金融实验、结果保留规则和最新状态

先读：

```text
evals/finance_e2e/results/README.md
evals/finance_e2e/STAGE2-EXPERIMENT-PROTOCOL.md
```

再读已保留总结和对应机器报告：

```text
evals/finance_e2e/results/2026-08-02-hard-r3-final-summary.md
evals/finance_e2e/results/2026-08-02-retrieval-pilot-final-summary.md
evals/finance_e2e/results/2026-08-02-retrieval-pilot-final.manifest.json
evals/finance_e2e/results/2026-09-22-stage2a-nvda-point-small-three-mode-final-calibration-summary.md
evals/finance_e2e/results/2026-09-29-同模型校准实验摘要.md
```

最新冻结审核材料位于：

```text
evals/finance_e2e/stage2-freeze-audit-corrected-2026-10-10/
```

其中：

```text
AI-REVIEW-2026-10-10.md
reviewer-a.csv
reviewer-b.csv
```

当前边界必须写清楚：AI 技术复审记录为 42 个证据等价组未发现已知错配，但它不是两名独立人工审阅者的正式审核；`reviewer-a.csv` 和 `reviewer-b.csv` 的 verdict、independent_result、notes 仍为空。因此不得把 Stage 2 写成已经完成冻结并产生正式确认性结果。

## 报告需要覆盖的评测系统内容

请检查并按需要补充以下内容，而不是简单追加一个孤立章节：

1. **目标和测试对象**：结果质量、过程质量、系统稳定性、成本与延迟；
2. **配置和执行模型**：case、suite、repetition、mode、独立 session、timeout、request-scoped tools；
3. **执行器**：确定性模拟执行与真实 Gateway HTTP 执行的区别；
4. **评分层**：最终文本、工具轨迹、状态、隐藏测试、multi-agent milestone、delegation、evidence use、grounding 和 fault handling；
5. **公平基线**：`solo_closed_book`、`solo_open_book`、`solo_two_pass`、`team`、`oracle_team` 的证据和计算机会差异；
6. **错误分类**：assigned、evaluated、errored、unavailable；基础设施错误不得计成模型任务失败；
7. **可观测性**：Trace、call ID、model calls、Token、缓存口径、费用、角色和调用路径；
8. **故障注入**：timeout、显式错误、畸形结果、矛盾证据、部分失败和非关键依赖失败；
9. **可复现性**：suite/source hash、随机顺序 seed、价格表、manifest、校准剔除和原始 JSON 保留；
10. **有效性边界**：小样本、单次重复、模型异构、provider 波动、grader 调整、缺少完整消融和独立人工冻结。

## 必须保留的事实边界

### 历史固定 8-case 回归

- 使用真实 Gateway、固定 benchmark tenant 和固定 evidence；
- 当时每题一次，运行 `solo_closed_book + team` 两种模式；
- 历史对比包括 0/8 → 8/8、delegation precision 42% → 100%、模型调用 194 → 53、P95 201.6 s → 60.0 s；
- 权限、去重、结构化返回和 grader 规范化等多项修改共同落地，没有完整逐项消融；
- 因此只能写成整套工程修改后的固定回归改善，不能把全部变化归因于单一优化；
- 小样本顺序回归中的 P95 是描述性工程指标，不是并发容量或压力测试结论。

### 六案例金融 workflow confirmation

- Team、Solo Open-Book 和 Solo Two-Pass 都是 5/6；
- 没有建立 Team 的增量准确率优势，也不能声称统计等价；
- 机器评分失败包含 grader 表达窗口的局限，应区分模型输出与评分规则问题。

### Retrieval-mediated Pilot

- 当前报告中的主 Pilot 是一个公司、一个中等上下文案例、一次重复；
- 观察到的延迟、成本、Token 和 grounding 差异只能作描述性关联；
- 模型分配异构、顺序非随机或不平衡等因素限制因果解释；
- 不能推广为多智能体普遍更快、更便宜或更准确。

### Stage 2 校准与冻结准备

- 2026-09-22 三模式结果是一案例一次重复的 engineering calibration；
- 2026-09-28/29 同模型实验也是 calibration，且暴露基础设施错误分类问题；
- 这些校准结果明确不应作为正式英文报告中的确认性证据，除非只用于说明方法可执行和未满足门槛；
- 2026-10-10 包完成的是修复后的 AI 技术复审，不是双人独立人工冻结。

## 写作要求

- 先解释“为什么需要这个评测系统”，再讲架构、执行、评分、结果和限制；
- 使用清楚的工程语言，不堆叠自造术语；
- 每个重要数字都带样本数、模式、repetition、是否真实 Gateway 和结果状态；
- 把确定性软件测试证据和概率性模型评测证据分开；
- 把 runtime 失败、模型失败、grader 失败和数据/证据失败分开；
- 不使用“official benchmark”“完全无幻觉”“证明多智能体更优”“生产级可靠”等超出证据的表述；
- 不把调用某个操作角色等同于真实执行交易、回滚或生产操作；
- 不修改或删除保留的原始 JSON、manifest、source lock、审核任务和校准结果；
- 如果需要新增图，只给出一个简洁的评测数据流图和图注，正文仍以文字和表格为主。

## 期望交付

完成后请依次给出：

1. **证据地图**：报告主张、源文件、证据强度和边界；
2. **差距分析**：现有报告缺什么、哪里过时、哪里重复或口径不一致；
3. **实际修改**：直接编辑 `project-report/fastclaw_project_report.md`；
4. **修改摘要**：按章节说明新增和修订内容；
5. **验证**：检查 Markdown 结构、内部路径、数字与原始报告的一致性；如运行测试，列出确切命令和结果；
6. **剩余门槛**：尤其列出双人独立人工审核、冻结、正式随机配对重复和统计分析是否完成。

不要先承诺结论。先阅读上述文件、建立证据地图，再开始改报告。

## 当前仓库注意事项

该目录是设备迁移后的工作树，`.git` 文件仍指向旧路径：

```text
/Users/wangzheyu/fastclaw/.git/worktrees/fastclaw-finance-e2e
```

因此 `git status` 可能报“not a git repository”。不要为完成报告任务擅自修复、重建或删除 Git 元数据；直接审阅当前文件内容即可。如确实需要 Git 历史，应先向用户说明这一阻塞。
