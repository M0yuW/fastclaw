# FastClaw Go Runtime、金融实验与论文交接文档

> 更新时间：2026-08-09
>
> 用途：交给新的对话，继续基于 **Go 版本 FastClaw**、既有多智能体评测和金融实验完善实验与论文。
>
> 当前原则：先保护实验资产，再恢复正确代码分支；先修实验方法与论文证据链，再产生新的付费模型调用。

---

## 1. 一句话状态

FastClaw 已经从一个可调用工具的 Go Agent 项目扩展为：

1. 支持真实 coordinator → MessageBus → TaskQueue → sub-agent 调用的多租户 Agent Runtime；
2. 支持公平 Team/Solo baseline、故障注入、逐角色 token/费用/延迟归因的 Eval Harness；
3. 支持 tenant-isolated 金融研究状态、watchlist 和事件告警的金融 Runtime；
4. 支持基于锁定 SEC 一手资料的检索—分析—综合实验；
5. 已形成一篇 thesis-style Project Report 和一个尚未执行的 Stage 2 确认性实验协议。

当前已有实验没有证明“多智能体天然提高金融答案准确率”。已有证据更支持以下结论：

- 简单固定证据任务会被强 Solo baseline 饱和；
- 增加纵向、计算和状态冲突后，Team 与最强 Open-Book Solo 仍未出现稳定准确率差异；
- 在 SEC 检索 Pilot 中，共享检索和并行 specialist 改善了特定任务的延迟、费用、上下文复制和 grounding；
- 这些效率差异同时受到检索压缩、并发执行和 Pro/Flash 异构模型分配影响，不能全部归因于“Agent 数量”。

---

## 2. 当前 Git 与本地资产状态：开始工作前必须读

### 2.1 当前工作区不是实验代码分支

截至 2026-08-09：

```text
repo: /Users/wangzheyu/fastclaw
HEAD: detached at 792417b
base: m0yuw-project
```

当前 `HEAD` 停在 `m0yuw-project` 的基础提交，不包含后续完整 Eval/金融实验 Go 代码。

完整实现仍保存在本地分支：

```text
codex/eval-runtime-harness       5c553f0
codex/finance-agent-runtime      351ee42
codex/snapshot-finance-eval-r2   b93787f
codex/finance-e2e-study          27b6d4d
```

其中继续论文和金融端到端实验时，应以：

```text
codex/finance-e2e-study
```

作为完整代码与历史实验 artifact 的主读取分支。

### 2.2 当前 detached 工作区含大量未跟踪本地资产

当前本地未跟踪内容包括：

```text
project-report/                              # 论文 Markdown、生成器、图片与本地 PDF/DOCX
evals/finance_e2e/.cache/sources/            # 已下载的 SEC 一手资料缓存
evals/finance_e2e/STAGE2-EXPERIMENT-PROTOCOL.md
plugins/finance-tools/                       # 在目标分支中已有对应提交
runtime-pilot*.json                          # 历史本地实验报告
runtime-benchmark-tenant.json                # 含 API key，禁止提交或公开
CLAUDE-REVIEW-*.md                           # 论文 Review 与闭环记录
```

目录规模约为：

```text
evals/              19 MB
project-report/     23 MB
plugins/finance-tools/ 120 KB
```

### 2.3 禁止执行的操作

在没有确认快照前，不要执行：

```text
git clean -fd
git clean -fdx
git reset --hard
git checkout -- .
git switch codex/finance-e2e-study
```

最后一条并非永久禁止，而是当前存在可能被目标分支覆盖的未跟踪文件，直接切换可能失败或使人误判本地资产边界。

### 2.4 推荐的新对话启动方式

最安全的方式是创建独立 worktree，不改动当前 detached 脏工作区：

```bash
cd /Users/wangzheyu/fastclaw
git worktree add ../fastclaw-finance-e2e codex/finance-e2e-study
```

然后仅复制目标分支中没有的本地资料：

```bash
rsync -a project-report/ ../fastclaw-finance-e2e/project-report/
mkdir -p ../fastclaw-finance-e2e/evals/finance_e2e/.cache
rsync -a evals/finance_e2e/.cache/ ../fastclaw-finance-e2e/evals/finance_e2e/.cache/
cp evals/finance_e2e/STAGE2-EXPERIMENT-PROTOCOL.md \
  ../fastclaw-finance-e2e/evals/finance_e2e/STAGE2-EXPERIMENT-PROTOCOL.md
```

不要复制 `runtime-benchmark-tenant.json` 到任何会提交的目录。模型 key 继续使用环境变量或本机凭据文件注入。

若只需要阅读目标分支文件，可以在当前工作区使用：

```bash
git show codex/finance-e2e-study:<path>
```

不要为了阅读 artifact 强制切换分支。

---

## 3. 论文与实验的核心研究主线

### 3.1 研究对象

论文研究对象不是 DeepSeek 模型本身，而是：

> FastClaw Agent Runtime 及其信息流、工具约束、子 Agent 调度、故障传播、证据治理和成本归因机制。

### 3.2 金融应用问题

更贴近现实的金融研究过程是：

```text
锁定的一手金融资料
        |
        v
检索与证据压缩
        |
        v
不同金融分析视角
  |- 趋势/时间序列
  |- 会计口径/计算
  `- 风险/治理状态
        |
        v
Coordinator 综合
        |
        v
有证据边界的研究结论
```

单 Agent 必须在同一条执行链中完成检索、多角度分析和综合，其上下文会不断累积。

多 Agent 路径由一个 retriever 建立一次共享 evidence packet，多个 specialist 并行分析，coordinator 只接收专家摘要并综合。实验要测的是：

- 是否保持证据与计算正确；
- 是否减少大原始上下文的重复传输；
- 是否减少 coordinator 的上下文负担；
- 是否改善 wall-clock latency；
- 是否降低费用；
- 是否在 specialist 失败时安全降级；
- 是否值得额外的委派、trace 和系统复杂度。

### 3.3 论文不能声称的内容

当前实验不支持以下结论：

- 多智能体普遍优于单智能体；
- 多智能体提高投资判断准确率；
- FastClaw 具有选股 Alpha、Sharpe 或收益预测能力；
- Oracle Team 是理论能力上限；
- 当前结果是官方 BFCL、τ-bench、SWE-bench 或 MultiAgentBench 分数；
- 当前 grounding 指标等价于完整事实正确率或语义蕴含；
- 已完成大样本、独立 holdout 或显著性验证；
- Stage 2 已经执行。

---

## 4. 已完成内容

## 4.1 Go 多智能体 Runtime 基础能力

已完成并进入 `m0yuw-project` 基础线的主要能力：

- 打通 `spawn_subagent` 的真实内部调用链；
- coordinator 不再直接同步调用兄弟 Agent，而是经过 MessageBus 和 TaskQueue；
- request/reply correlation 与 internal task metadata；
- root execution ID 和不可变 call path；
- pending 容量、backpressure、cycle detection；
- cross-tenant target 拒绝；
- caller cancellation 传播；
- shutdown 中释放等待 caller 和 exactly-once completion；
- Web chat 真 token streaming；
- Stop 从前端请求传播到 Agent/provider；
- React effect、stale response、session 竞态修复。

## 4.2 Eval Harness

完整 Eval 实现在 `codex/finance-e2e-study` 分支，包括：

- 通用 suite schema、runner、grader、report、compare；
- BFCL V4 simple style subset；
- τ-bench-style retail state task；
- SWE-bench-style local fixtures；
- MultiAgentBench-style collaboration suite；
- simulated collaborator 与真实 Gateway runtime 两种执行模式；
- case filter、repetition、timeout、isolated session；
- JSON/text report；
- pass@k、consistency、latency、token、cost；
- delegation precision/recall/F1；
- contribution utilization 与 coordination score；
- coordinator/sub-agent usage tree；
- suite pricing 与 pricing coverage；
- runtime benchmark tenant 自动 provision。

## 4.3 公平 Team/Solo baseline

已实现：

```text
solo_closed_book
solo_open_book
solo_two_pass
team
oracle_team
```

关键修复：

- `team - solo_closed_book` 只保留为 evidence-visibility 乐观诊断；
- 公平协作指标使用 `team - solo_open_book`；
- compute-matched 指标使用 `team - solo_two_pass`；
- baseline timeout、429、空输出和 transport error 单列为 `Errored`；
- errored baseline 不进入成功率分母；
- 任一必要 baseline 无有效样本时，gain 为 `n/a`；
- 每个 baseline 使用独立 context timeout 和独立 session key。

## 4.4 Fault Injection Eval

已实现请求级 simulated fault：

- delay/timeout；
- explicit error；
- malformed response；
- contradictory evidence；
- multiple partial failures；
- non-critical dependency failure。

已实现指标：

- fault observation rate；
- fault attribution rate；
- graceful degradation rate；
- unsupported claim rate。

故障只允许 `simulated` suite 声明，不能写入或修改生产 Agent。延迟遵守 `ctx.Done()`，并有最大延迟限制。

重要：金融 `r5` 中 `faults_expected = 0`，因此 `r5` 不能作为故障处理能力的实证结果。Fault Injection 目前主要是 harness 功能和自动化测试证据，尚需正式重复运行。

## 4.5 Runtime 工程修复

评测暴露并推动修复了以下生产路径问题：

1. required identity 文件缺失时 fail fast，并将错误发到 streaming event；
2. `no-tools` / `delegate-only` policy 真正接入每轮 tool registry；
3. 无工具 Agent 不再被 system prompt 诱导调用文件/Skill/workspace 工具；
4. 生产 turn 与 Eval request-scoped 去重/工具环境隔离；
5. OpenAI/Anthropic streaming usage 解析；
6. usage collector 跨 MessageBus/TaskQueue 传递；
7. coordinator/sub-agent token、cost、latency 和 call path 拆分；
8. 不同 target 的 `spawn_subagent` 真并发；
9. batch `spawn_subagent`：一个 `sharedContext` 加多个 delegation；
10. batch trace 结构化压缩，保留合法 JSON 和 agent identity；
11. OpenAI API Agent ACL 修复；
12. `/api/tasks` 鉴权和 tenant/ACL 过滤；
13. SQLite WAL、foreign keys 和 busy timeout；
14. identity 读取保留底层 store error，不再将 `database is locked` 误报为文件缺失；
15. tool hook 起始时间传播，修复极大无意义 latency；
16. clean clone 下 `go:embed all:web` 的 CI 编译修复。

## 4.6 金融 Runtime 与插件

已完成：

- `finance-tools` 原生 JSON-RPC 插件；
- 统一 `finance.tool.v1` 返回契约；
- runtime 注入可信 `userId`、`agentId`、`sessionId`；
- tenant-isolated Thesis Ledger；
- thesis/assumption/catalyst/invalidation/evidence 管理；
- `expected_version` 乐观并发保护；
- watchlist 生命周期；
- event alert 稳定指纹与重复事件去重；
- new/acknowledged/dismissed 状态；
- Serenity Skill 固定版本、hash 检查与研究方法定位；
- 六案例金融 workflow suite。

`r5` 没有调用真实 finance-tools，也没有执行 ledger mutation。它验证的是固定证据下的 runtime 编排和最终文本约束，不是完整金融端到端状态变更。

## 4.7 SEC 数据与金融端到端实验

已完成：

- NVDA、AMD、Intel、NIKE 一手资料抓取；
- SEC document 和 company facts 本地缓存；
- source lock；
- source/evidence audit；
- point-in-time 与 longitudinal case builder；
- small/medium/large corpus load；
- 24 配置的 suite 生成；
- `finance-retrieval` runner；
- 五种 retrieval treatment；
- retrieval、summary、synthesis、grounding 和 cost 指标；
- 最终 NVDA medium-context 描述性 Pilot；
- Stage 2 预执行协议草案。

## 4.8 论文

本地论文主源：

```text
/Users/wangzheyu/fastclaw/project-report/fastclaw_project_report.md
```

当前论文已经包括：

- Agent Runtime 架构；
- 多智能体执行机制；
- 金融研究应用；
- 公平 baseline；
- Fault Injection；
- 历史 8-case regression；
- 金融固定证据 `r5`；
- longitudinal SEC `R3`；
- retrieval-mediated Pilot；
- threats to validity；
- Stage 2 设计记录。

论文 Markdown、构建脚本和生成物当前只做本地存档，未要求提交。PDF/DOCX 在内容未定稿前不是工作重点。

---

## 5. 关键技术决策与实验设计思路

## 5.1 Runtime 必须作为被测系统，而不是绕过它

真实 runtime Eval 必须经过：

```text
Eval CLI
  -> HTTP/Gateway
  -> Agent Loop
  -> spawn_subagent
  -> MessageBus
  -> TaskQueue
  -> specialist Agent Loop
  -> provider
  -> correlated result/trace
```

只调用一个 mock coordinator 函数不能测到：

- tenant ACL；
- cancellation；
- session isolation；
- TaskQueue state；
- provider usage；
- streaming error；
- SQLite contention；
- trace attribution。

因此项目同时保留 simulated mode 和真实 Gateway mode：前者做确定性回归，后者测真实系统链路。

## 5.2 Evidence fairness 优先于“漂亮的协作增益”

早期 `team - solo_closed_book` 将“Team 能看到 specialist evidence、Solo 看不到”误计为编排收益。

最终设计要求：

- Team 与公平 Solo 获得相同 substantive evidence；
- 只改变信息分配、委派和执行拓扑；
- Closed-book 仅作为诊断，不作为对外协作提升证据；
- 两遍 Solo 用于近似控制 synthesis opportunity；
- model-capacity 仍需单独 ablation。

## 5.3 基础设施错误不能算模型失败

Timeout、429、网络错误、provider 空输出和 malformed stream 如果直接计为 fail，会虚增 Team gain 或 Solo/Team 差异。

因此：

- `Errored` 与 `Evaluated` 分开；
- gain 只在配对双方都有效时计算；
- provider 调用即使 errored 仍可能产生费用，成本保留；
- 报告显示每 mode 的 error count。

## 5.4 固定 evidence 与 retrieval-mediated track 必须分开

固定 evidence suite 测：

- runtime routing；
- tool isolation；
- synthesis；
- evidence preservation；
- governance wording。

Retrieval-mediated suite 测：

- 原始语料读取；
- evidence selection；
- context compression；
- specialist summary retention；
- final synthesis retention；
- raw context replication。

不能用固定 evidence 结果声称已经测了真实金融数据检索，也不能把 retrieval Pilot 与 fixed-evidence `r5` 混成一个总体分数。

## 5.5 金融数据必须 source-locked

每个进入正式 suite 的事实需要：

- issuer/ticker；
- filing/accession；
- filing date；
- reporting period；
- document type；
- exact locator；
- local path/URL；
- SHA-256；
- unit；
- accounting basis；
- scope；
- calculation formula。

模型答案不是 ground truth。任何数据修改都必须产生新 suite/source-lock 版本，不能静默覆盖历史正式实验。

## 5.6 上下文成本是实验 treatment 的一部分

实验不再只比较“拿到完整 evidence 后 Team 和 Solo 谁答得更好”。

五种 retrieval mode：

```text
solo_monolithic
solo_staged
team_shared_retrieval
team_raw_context
oracle_evidence
```

其中：

- `team_shared_retrieval`：一份检索后的 evidence packet，通过 batch shared context 分配给三个并行 specialist；
- `team_raw_context`：同一 Team topology，但直接共享完整 raw corpus；
- 两者差异用于估计 context compaction 和 allocation 的系统效果；
- `solo_staged` 与 shared Team 是主要 Team/Solo 系统比较；
- `oracle_evidence` 只做诊断。

## 5.7 Latency、token 与 cost 必须使用不同口径

- mode-level `latency_ms` 是 end-to-end wall-clock；
- specialist model-service time 在并行时可求和做资源归因，但不能当作 wall-clock；
- Team-only latency/token 不能与四档完整 harness 总耗时混用；
- cache-read token 单列；
- provider total token 与 billable-like token 分开；
- 费用使用 suite 中冻结的 pricing，而不是运行时查询最新价格；
- pricing coverage 必须报告。

## 5.8 Calibration 与 confirmatory observation 必须分开

任何用于修改以下内容的运行都属于 calibration：

- prompt；
- grader；
- runtime batching；
- thinking mode；
- trace compaction；
- assertion alternatives；
- output limits。

Retrieval `v1`–`v7` 已明确排除。最终 Pilot 使用 `v8`–`v10` 的指定 mode observations，但仍只有一个 case、一次重复，属于 descriptive Pilot，不是确认性实验。

---

## 6. 修改过的核心文件

以下文件应从 `codex/finance-e2e-study` 分支读取。

## 6.1 Eval CLI

```text
cmd/fastclaw/cmd_eval.go
cmd/fastclaw/cmd_eval_tenant.go
cmd/fastclaw/cmd_eval_test.go
cmd/fastclaw/main.go
cmd/fastclaw/main_test.go
```

## 6.2 Eval 核心

```text
internal/eval/types.go
internal/eval/suite.go
internal/eval/runner.go
internal/eval/grader.go
internal/eval/report.go
internal/eval/compare.go
internal/eval/http_executor.go
internal/eval/bfcl.go
internal/eval/tau.go
internal/eval/swe.go
internal/eval/multiagent.go
internal/eval/finance_retrieval.go
```

对应测试：

```text
internal/eval/*_test.go
internal/eval/runner_integration_test.go
```

## 6.3 固定 Eval Tenant

```text
internal/evaltenant/tenant.go
internal/evaltenant/tenant_integration_test.go
```

## 6.4 Agent Runtime 与子 Agent

```text
internal/agent/loop.go
internal/agent/context.go
internal/agent/sdkbridge.go
internal/agent/usage_trace.go
internal/agent/tool_context.go
internal/agent/skills.go
internal/agent/hooks.go
internal/agent/tools/subagent.go
internal/agent/tools/registry.go
internal/agent/tools/execution_scope.go
```

## 6.5 Provider 与 OpenAI API trace

```text
internal/provider/provider.go
internal/provider/openai.go
internal/provider/anthropic.go
internal/provider/thinking.go
internal/api/openai.go
internal/api/openai_trace.go
```

## 6.6 TaskQueue、Store、Gateway、Policy、Plugin

```text
internal/taskqueue/queue.go
internal/store/database.go
internal/store/factory.go
internal/gateway/gateway.go
internal/gateway/userspace.go
internal/policy/defaults.go
internal/policy/engine.go
internal/plugin/protocol.go
internal/plugin/tool_adapter.go
internal/plugin/manager.go
internal/plugin/hook_adapter.go
internal/setup/handlers.go
internal/setup/server.go
```

## 6.7 API 与集成测试

```text
internal/api/openai_integration_test.go
internal/auth/auth_integration_test.go
internal/setup/api_integration_test.go
internal/store/database_integration_test.go
internal/gateway/subagent_integration_test.go
internal/gateway/plugin_tools_test.go
internal/taskqueue/queue_test.go
```

## 6.8 金融插件

```text
plugins/finance-tools/plugin.py
plugins/finance-tools/plugin.json
plugins/finance-tools/test_plugin.py
plugins/finance-tools/README.md
FINANCE-RUNTIME.md
```

## 6.9 Suite、数据和实验脚本

```text
evals/multiagent-runtime-tenant.yaml
evals/multiagent-collaboration-subset.yaml
evals/multiagent-fault-injection.yaml
evals/multiagent-finance-runtime.yaml
evals/multiagent-finance-workflow.yaml
evals/multiagent-finance-sec-e2e.json
evals/multiagent-finance-sec-hard.json
evals/finance-retrieval-sec.json
evals/finance_e2e/fetch_sources.py
evals/finance_e2e/audit_evidence.py
evals/finance_e2e/build_suite.py
evals/finance_e2e/build_hard_suite.py
evals/finance_e2e/build_retrieval_suite.py
evals/finance_e2e/analyze_report.py
evals/finance_e2e/sources.json
evals/finance_e2e/evidence.json
evals/finance_e2e/source-lock.json
evals/finance_e2e/runtime-agent-evidence.json
evals/finance_e2e/runtime-agent-evidence-hard.json
```

## 6.10 论文

```text
project-report/fastclaw_project_report.md
project-report/analysis/main.go
project-report/analysis/main_test.go
project-report/finance_reanalysis.json
project-report/build_report.py
project-report/build_artifacts.sh
project-report/artifact.md
```

`project-report/artifact.md` 当前仍是过期的 20 页构建说明，不能作为可靠事实源，见“仍存在的问题”。

---

## 7. 实验数据与报告位置

## 7.1 历史 8-case Runtime Harness

当前 detached 工作区本地文件：

```text
/Users/wangzheyu/fastclaw/runtime-pilot.json
/Users/wangzheyu/fastclaw/runtime-pilot-optimized.json
/Users/wangzheyu/fastclaw/runtime-pilot-optimized-v2.json
/Users/wangzheyu/fastclaw/runtime-smoke-optimized.json
```

凭据文件：

```text
/Users/wangzheyu/fastclaw/runtime-benchmark-tenant.json
```

该文件含 API key，只能本地使用，禁止提交或写进论文。

## 7.2 六案例金融固定证据 `r5`

目标分支：

```text
finance-runtime-formal-r5.json
evals/finance-runtime-formal-r5.md
evals/finance-runtime-formal-r5.manifest.json
evals/multiagent-finance-runtime.yaml
```

关键哈希：

```text
artifact: 5366a91398ca575d303af56d62da179f2a3f1fb13a1d0f5aae5c1773debfbc00
suite:    4fbf54eca61dc7363342ea1db364cb84426e1541937a99c1e1266dbfb3e5dc44
```

## 7.3 简单四公司 SEC Pilot

目标分支：

```text
evals/multiagent-finance-sec-e2e.json
evals/finance_e2e/results/2026-08-02-pilot-r7-4cases.json
evals/finance_e2e/results/2026-08-02-pilot-r7-4cases-analysis.json
evals/finance_e2e/results/2026-08-02-pilot-r7-summary.md
```

`r2`–`r6` 是数据和 grader 校准历史，不作为独立 holdout。

## 7.4 Longitudinal SEC Hard `R3`

目标分支：

```text
evals/multiagent-finance-sec-hard.json
evals/finance_e2e/runtime-agent-evidence-hard.json
evals/finance_e2e/results/2026-08-02-hard-r3-final.json
evals/finance_e2e/results/2026-08-02-hard-r3-final-analysis.json
evals/finance_e2e/results/2026-08-02-hard-r3-final-summary.md
```

关键哈希：

```text
suite:       6b1933347fcead04b68732f99bc892b8e6b2d4a6bb8a8ae555e71dc2441b970e
evidence:    c3d8dbb511f74101e5bdbd2f661693babc5a05d5ae4e9ca5f37d9153a4890690
raw report:  61fab590cea3884ad37e4cc97e31adffc0e0fea3fd470cd81bd74128c7365209
analysis:    5702b3642d77fbfcc82af25017ccf7a903cfac4dbdeb344a1ae8385552a67f16
```

## 7.5 SEC Retrieval-Mediated Pilot

目标分支：

```text
evals/finance-retrieval-sec.json
evals/finance_e2e/source-lock.json
evals/finance_e2e/results/2026-08-02-retrieval-pilot-final-summary.md
evals/finance_e2e/results/2026-08-02-retrieval-pilot-final.manifest.json
evals/finance_e2e/results/2026-08-02-retrieval-pilot-v8-nvda-medium-final.json
evals/finance_e2e/results/2026-08-02-retrieval-pilot-v9-nvda-medium-baselines.json
evals/finance_e2e/results/2026-08-02-retrieval-pilot-v10-nvda-medium-raw-trace.json
```

关键哈希：

```text
suite:       7b73f4b82a3f97cb1151b372dcf8172eb88c04d37e1e137ed80b2a87bfb44e20
source lock: a4d4b4dc3be440238e3d428d60d04fb4a4a9d21d8c0b4eec4cb313e2e181fe22
summary:     3f4f5e61ebe153cd19511ac7a54d924008610e4570e09a1078e8a7f39d031608
```

Calibration exclusion：

```text
v1-v7 全部排除
v9 中早期 team_raw_context observation 被 v10 supersede
```

## 7.6 Stage 2 协议

本地未提交协议：

```text
/Users/wangzheyu/fastclaw/evals/finance_e2e/STAGE2-EXPERIMENT-PROTOCOL.md
```

它是 `draft`，不是已执行实验。

---

## 8. 已有实验结果

## 8.1 历史 8-case Runtime Harness 优化

同模型、同 8 个固定案例、单次重复：

| 指标 | 初始运行 | 优化后 |
|---|---:|---:|
| 严格通过 | 0/8 | 8/8 |
| Milestone KPI | 16.7% | 100% |
| Coordination score | 38.2% | 100% |
| Delegation precision | 42.0% | 100% |
| Delegation recall | 100% | 100% |
| Contribution utilization | 17.2% | 100% |
| 模型调用 | 194 | 53 |
| 总 tokens | 1,274,742 | 73,729 |
| P50 | 110.1 s | 46.0 s |
| P95 | 201.6 s | 60.0 s |
| Pricing coverage | 0% | 100% |

优化后：

```text
总费用                   USD 0.019599
Team                     USD 0.013751
Solo closed-book         USD 0.005848
Coordinator Team         USD 0.009911
Specialists              USD 0.003840
```

解释边界：

- 这是对同一固定 regression suite 的工程修复；
- 早期运行包含证据注入、工具隔离、重复委派和 grader 缺陷；
- 不能把 `0/8 → 8/8` 说成模型能力提升；
- 当时只使用 closed-book Solo 与 Team，两档 attempt token/latency 口径不能直接与后来四档实验比较；
- 单次重复，没有稳定性区间。

## 8.2 六案例金融固定证据 `r5`

模型：

```text
Coordinator: deepseek/deepseek-v4-pro
Specialists: deepseek/deepseek-v4-flash
```

实验：6 cases × 4 modes × 1 repetition，24 baseline executions，54 model calls。

| Mode | Passed | Success | Tokens | Cost | Mean latency |
|---|---:|---:|---:|---:|---:|
| Solo Open-Book | 5/6 | 83.3% | 9,885 | USD 0.005510 | 13.65 s |
| Solo Two-Pass | 5/6 | 83.3% | 30,822 | USD 0.017798 | 42.65 s |
| Team | 5/6 | 83.3% | 41,219 | USD 0.008335 | 19.45 s |
| Oracle Team | 4/6 | 66.7% | 8,902 | USD 0.004320 | 11.32 s |

其他结果：

```text
fair collaboration gain       0.0 pp
compute-matched gain          0.0 pp
baseline errors               0
pricing coverage              100%
configured grounding          44 assertions, 0 violations
Team P50/P95                  21.30 / 22.49 s
Team coordinator cost share   84.7%
```

结论：

- Team 没有比 evidence-matched Solo 更准确；
- Team 被 one-pass Open-Book Solo 在成本和延迟上支配；
- Team 比 Pro-only Two-Pass Solo 更便宜、更快，但该差异混合了异构模型价格、输出长度和并发；
- Oracle 不是保证上限；
- `r5` 是 post-fix confirmation，不是 untouched validation；
- 固定 evidence，不是 SEC retrieval，也没有 finance-tool call。

## 8.3 简单四公司 SEC Pilot：baseline 饱和

NVIDIA、AMD、Intel、NIKE 的简单单观察任务最终四种 mode 全部 4/4。

该结果证明：

- 锁定一手证据、Agent identity 和 runtime 链路可执行；
- 简单任务没有剩余 outcome variance，无法识别多智能体增量准确率。

该结果不能证明 Team 与 Solo 等价，也不能证明多智能体有准确率提升。

## 8.4 Longitudinal SEC Hard `R3`

4 个公司，每例组合 3 个锁定 SEC 观察，要求：

- chronology；
- calculation control；
- `0→1→2→3` 状态链；
- final research-state decision；
- stale candidate rejection。

| Mode | Strict success | Tokens | Cost | Mean latency |
|---|---:|---:|---:|---:|
| Solo Open-Book | 3/4 | 27,847 | USD 0.018099 | 57.32 s |
| Solo Two-Pass | 1/4 | 51,556 | USD 0.029369 | 94.31 s |
| Team | 3/4 | 78,800 | USD 0.022718 | 65.31 s |
| Routed diagnostic | 1/4 | 24,021 | USD 0.014562 | 48.69 s |

```text
Team - Open-Book             0 pp
Team - Two-Pass             +50 pp
Delegation F1               100%
Contribution utilization    91.7%
Contribution-item coverage  95.6%
Grounding accuracy          100%
Evidence-ID retention       100%
Team P50/P95                65.20 / 86.56 s
```

关键失败：AMD governance specialist 连续返回空结果。Coordinator 重试后达到 5 次委派，超过预算，仍缺 STATE/STALE evidence。

结论：

- 提高难度消除了简单 suite 的饱和；
- Team 与最强 Open-Book Solo 仍为 3/4，准确率差异为 0；
- Team 相对 Two-Pass 的 +50 pp 只有四例、一次重复，不能作推断；
- specialist availability 与 retry policy 是 treatment 的一部分；
- 空 sub-agent 输出需要结构化状态和有界重试。

## 8.5 SEC Retrieval-Mediated NVDA Pilot

Case：`nvda-longitudinal-medium`。输入 30,518 characters，一次重复。

| Mode | Pass | Milestones | Final evidence | Grounding | Latency | Tokens | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| Solo monolithic | No | 2/3 | 100% | 98.29% | 55.96 s | 15,259 | USD 0.008263 |
| Solo staged | Yes | 3/3 | 100% | 95.45% | 141.04 s | 37,693 | USD 0.020690 |
| Team shared retrieval | Yes | 3/3 | 100% | 98.28% | 89.81 s | 42,829 | USD 0.011987 |
| Team raw context | No | 3/3 | 100% | 94.87% | 104.61 s | 69,553 | USD 0.022884 |
| Oracle evidence | Yes | 3/3 | 100% | 100% | 37.89 s | 7,095 | USD 0.002464 |

Shared Retrieval Team 相对 Staged Solo：

```text
latency              -36.32%
estimated cost       -42.06%
provider tokens      +13.63%
retrieval precision  66.67% -> 100%
grounding            +2.82 pp
compression          6.12x -> 7.58x
```

Shared Retrieval Team 相对 Raw Context Team：

```text
latency       -14.15%
tokens        -38.42%
cost          -47.62%
grounding     94.87% -> 98.28% (+3.40 pp)
```

结论：

- Shared Team 与 Staged Solo 都是 3/3 milestone、100% final evidence recall；
- 没有增量准确率证据；
- Pilot 支持 context allocation 和系统效率的机制性解释；
- cost reduction 包含 Pro/Flash 异构模型分配；
- 一公司、一 load、一次重复、未随机 mode order，不能进行显著性推断；
- grounding 是 numeric support 检查，不是完整语义 entailment。

---

## 9. 尝试过但失败或不应继续使用的方案

| 方案 | 发生的问题 | 处理结果 / 经验 |
|---|---|---|
| Team 与 Closed-Book Solo 比 collaboration gain | Evidence visibility 不一致，虚增编排收益 | 增加 Open-Book 与 Two-Pass baseline；Closed-Book 仅诊断 |
| 只看模型最终答案 | 无法区分 retrieval、routing、specialist、synthesis、provider、grader | 增加分层指标、trace 和 failure taxonomy |
| Specialist 仅靠 prompt 禁止工具 | 模型仍调用文件/记忆工具并进入 sandbox loop | Runtime `no-tools` policy + prompt capability removal |
| Coordinator 仅靠 prompt 限制每个专家调用一次 | 重复委派，precision 42%，token/延迟膨胀 | request-scoped dedup、budget 和结构化 contract |
| 对所有生产 turn 全局按 agent ID 去重 | 同一专家处理不同 task 会错误复用第一次结果 | Eval 行为限制请求作用域；生产语义不能被 Eval 假设改变 |
| Baseline error 计为普通 fail | 429/timeout 会虚增 Team gain | `Errored` 移出 evaluated denominator |
| Forbidden value 直接 substring match | `not verified` 会命中 `verified`，正确否定句被判错 | 否定语境处理、ID 类 forbidden 优先、人工复核 |
| unsupported claims / faults 直接相除 | 一个 fault 多个 forbidden value 时比例可超过 100% | 按“发生违规的 fault 数 / fault 数”计数 |
| Attempt latency/token 累计所有 baselines 后作为 Team 指标 | 四档实验与 Team 成本混淆 | 增加 per-mode 与 team-only 指标 |
| `spawn_subagent` 日志显示 concurrent 即认为真并发 | SDK 实际把工具放在 sequential group | 修改 concurrency classification，并加 distinct/duplicate target 测试 |
| 并行 specialist 直接复用旧 SQLite 配置 | `SQLITE_BUSY`、session flush/identity read 失败 | WAL、foreign keys、busy timeout、store integration tests |
| 将 store error 包装成 identity missing | 错误语义失真，排障方向错误 | 保留底层 store error；只有真实空/缺失才报 identity contract |
| 将同一大 evidence 放进三个 tool arguments | 请求/trace 体积膨胀，截断后 JSON 和 agent attribution 损坏 | 一个 `sharedContext` + batch tasks；结构化 trace compaction |
| 普通字节截断 batch trace | 产生非法 JSON，tool result 无法归属 | 按字段压缩，保留 ID/target/task/result identity |
| Retrieval Pilot 保持 thinking mode | reasoning 可能耗尽输出预算，正文为空或截断 | 金融实验关闭 thinking，并记录 exact setting |
| 简单四公司 SEC 案例继续增加同类样本 | 四 mode 全 4/4，baseline 饱和 | 改为 longitudinal、计算、状态冲突与 retrieval-mediated 任务 |
| 将完整证据先交给所有模式后再比较 | 忽略真实检索的上下文成本 | 单独设计 retrieval、shared packet 和 raw-context treatments |
| Retrieval v1-v7 直接合并统计 | Prompt/runtime/grader/thinking/batching 同时变化 | 全部标记 calibration，禁止进入确认性统计 |
| 将 Oracle 当作理论上限 | Oracle 在 r5 和 hard suite 可能低于非 Oracle | 改称 diagnostic；完美路由不等于完美综合 |
| 根据每次模型措辞不断添加 synonym | calibration leakage，grader 对当前输出过拟合 | 冻结 matcher；新增 holdout 或人类标注验证 |

---

## 10. 仍存在的问题

## 10.1 工作区与复现

1. 当前主工作区处于 detached HEAD；
2. 论文、Stage 2 协议、SEC cache 和部分 runtime JSON 未跟踪；
3. `codex/finance-e2e-study` 只在本地，最新 `27b6d4d` 尚未显示为远端分支；
4. `r5` 和 retrieval Pilot 都记录了 dirty execution tree；
5. `r5` 未保存当时完整 dirty patch，因此能重评分，但不能声称 provider trajectory 可由 HEAD 精确复现；
6. API key 文件必须继续排除。

## 10.2 Runtime 与 Eval

1. Hard R3 暴露 empty specialist response 和无效重试；
2. 需要明确 sub-agent status：success/empty/timeout/malformed/provider error；
3. retry 要同时限制 per-specialist 与 total delegation budget；
4. 空 tool-call ID 仍应 fail closed 或记录诊断，不能静默错配；
5. provider cache accounting 对 OpenAI-compatible 与 Anthropic 仍有不对称风险；
6. `HookRegistry` 无 mutex，当前主要是 startup-time latent risk；
7. Skill 删除路径缺少严格 allow-list/prefix assertion；
8. policy、scope、session、plugin、MCP、Skills 等关键包测试覆盖仍弱或为零；
9. Fault Injection 需要真实重复执行，不能用 `r5` 的零故障分母代替；
10. 当前 lexical/numeric grader 未经过系统的人类标注一致性验证。

## 10.3 金融实验

1. 所有保留的真实 runtime 研究都只有一次 repetition；
2. 6-case `r5` 没有 untouched holdout；
3. Hard R3 只有四公司四案例；
4. Retrieval Pilot 只有一个 NVDA medium case；
5. Mode order 未随机；
6. Team 使用 Pro coordinator + Flash retriever/specialists，Solo staged 使用 Pro，多种效应混合；
7. 24 个 retrieval 配置尚未正式执行；
8. 24 个配置只对应 8 个 company-task clusters，不是 24 个独立发行人；
9. Numeric grounding 不等于语义 entailment；
10. 尚未做真实 finance-tool retrieval + ledger mutation 的端到端评分；
11. Stage 2B 新公司还没有完成 source lock 和双人 audit；
12. 没有金融收益、回测或真实投资绩效实验；当前论文不需要强行加入收益结论。

## 10.4 论文内容

Round-2 Review 中与内容和学术完整性有关、当前仍需优先核对的问题：

1. `project-report/artifact.md` 仍描述过期 20 页构建、旧 margin、旧 hash 和旧 branch，是 submission integrity P0；最简单方案是删除其事实源角色，或从实际构建自动生成；
2. H1–H6 已在论文中声明，但没有逐项 `supported / not supported / not tested` 的正式结论；
3. `r5` 的 `state_graders`、`communication_graders`、`policy_graders`、`tool_trace_graders` 实际为 0，论文不能写成这些 grader 已在 `r5` 工作；
4. repository coverage 28.4% 包含 `project-report/analysis`，生产 package 口径约 27.2%，应并列或改用生产口径；
5. RQ2 当前只能写“未检出准确率差异”，不能写等价；
6. RQ3 的效率结果必须区分 context allocation、parallelism 和 heterogeneous model allocation；
7. RQ4 的故障假设未被 `r5` 测试，因为 `faults_expected = 0`；
8. RQ5 需要区分固定文本 assertion 与真实 finance-tool/ledger state mutation；
9. Skills 目前全文注入，`load_skill` progressive disclosure 在生产不可达；
10. PostgreSQL 路径是 implemented，不是 automated-test verified；
11. OpenAI-compatible `RawAssistant` 是由 stream fragments 重建的 synthetic payload，不是原始 wire replay；
12. benchmark-adjacent 名称要继续使用 `style` / `inspired`，避免官方分数暗示；
13. 文献需要补强 claim attribution/entailment、多智能体成本与 Agent security，而不是只增加泛引用；
14. Stage 2 必须始终标记为 proposed/draft，直到第一个正式请求前完成 freeze checklist。

---

## 11. 继续实验与完善论文的推荐顺序

## Phase 0：保护资产并恢复正确开发环境

1. 不清理当前 detached 工作区；
2. 建立 `codex/finance-e2e-study` 独立 worktree；
3. 复制论文、Stage 2 协议和 SEC cache；
4. 核对目标分支中的结果 artifact 和 manifest hash；
5. 将新 worktree 设为后续实验唯一执行目录；
6. Gateway 保持关闭，直到所有 zero-cost gate 完成。

验收：

```text
git status 清楚区分 tracked code 与 local-only paper/cache
所有正式 artifact 均可读取
没有 secret 进入 Git
```

## Phase 1：先修论文零成本完整性问题

不调用模型，优先完成：

1. 修复或废弃过期 `project-report/artifact.md`；
2. 为 H1–H6 增加结论表：supported/not supported/not tested；
3. 明确 `r5` 中空 grader families；
4. 将 coverage 分为 all-package 28.4% 与 production-only 27.2%；
5. 逐项核对 Abstract、RQ、Results、Discussion、Conclusion 数字和口径；
6. 保持 fixed-evidence、hard longitudinal、retrieval Pilot 三条结果分开；
7. 补充核心文献：attribution/entailment、agent security、multi-agent cost/context allocation；
8. 不处理 PDF 排版，直到 Markdown 内容冻结。

## Phase 2：零模型调用的 Grader 人工验证

这是 Round-2 Review 推荐的最高价值下一步。

使用保留的 `r5` 输出和 retrieval final outputs，不重新调用模型：

1. 两名人工 reviewer 独立标注 material claims；
2. 标签：supported / derived / unsupported / not assessable；
3. 对 44 grounding assertions 和 18 milestones 建 confusion matrix；
4. 报告 raw agreement 与 Cohen's kappa；
5. 将 lexical grader 与人工结论的 FP/FN 分类；
6. 此后冻结 grader，不再按模型输出补 synonym。

验收：

```text
有独立标注文件
有 disagreement resolution 记录
有 grader confusion matrix
论文能准确解释 numeric support 与 semantic entailment 的差异
```

## Phase 3：修 Runtime 中会污染正式实验的问题

优先实现：

1. sub-agent 结构化状态；
2. empty/malformed/timeout/provider error 显式返回；
3. per-specialist retry cap；
4. total delegation budget；
5. recovery success 与 first-attempt success 分开统计；
6. 空 call ID fail closed；
7. 所有改动增加 unit/integration/race tests；
8. 不使用 formal Stage 2 case 调试这些改动，使用独立 smoke fixture。

## Phase 4：完成 Stage 2 八个实现门禁

协议文件：

```text
evals/finance_e2e/STAGE2-EXPERIMENT-PROTOCOL.md
```

必须完成：

1. seeded within-block mode randomization；
2. Stage 2 suite v2，final evidence recall threshold = 90%，新 suite hash；
3. all-Pro Team capacity-matched mode；
4. stable company-task cluster ID 与 pair ID；
5. consolidated primary-mode table，显示 errored denominator；
6. secret-free manifest：source/suite/grader/prompt/model/pricing/environment hash；
7. 只读取保留 JSON 的离线 paired/cluster-aware analysis command；
8. calibration/superseded artifact 自动排除测试。

## Phase 5：冻结数据与协议

在首次正式 provider request 前：

1. 24 个 Stage 2A 配置无 diff 再生成；
2. 所有 source hash 匹配；
3. source audit 完成；
4. oracle calculation audit 完成；
5. model alias、thinking mode、max output、pricing 固定；
6. seed 固定为 `20260802`，除非在首次正式请求前版本化修改；
7. output 目录不含 calibration artifact；
8. protocol 从 draft 改为 frozen；
9. 记录预算和停止规则接受状态。

## Phase 6：低成本 smoke，不进入正式统计

先选一个非正式 smoke case 验证：

- 三个 primary modes 都能运行；
- random order 正确写入 artifact；
- pair/cluster ID 正确；
- batch trace JSON 完整；
- role usage/cost 归因对账；
- failure taxonomy 可用；
- analysis command 不调用模型；
- calibration 标记阻止该结果进入 formal set。

## Phase 7：Stage 2A 正式执行

Stage 2A：

```text
companies: NVIDIA, AMD, Intel, NIKE
task families: point-in-time, longitudinal
loads: small, medium, large
configurations: 24
clusters: 8 company-task clusters
primary modes: solo_staged, team_shared_retrieval, team_raw_context
repetitions: 3
primary observations: 216
diagnostics: solo_monolithic + oracle_evidence, each once = 48
total observations: 264
```

再做 8 个预声明配置的 all-Pro Team ablation，每个 3 repetitions。

运行规则：

- 一个 case block 串行；
- block 内 mode 随机；
- Team 内 specialist 并行是 treatment；
- cumulative cost 超过 USD 10 停止；
- serial runtime 超过 12 小时暂停；
- baseline error >5% 暂停；
- rolling 20 attempts 中 429/provider unavailable >10% 暂停；
- source/suite/grader/model/pricing hash 变化时终止当前版本。

## Phase 8：离线统计与失败分析

正式运行后不修改 grader：

1. 先做 hash/manifest validation；
2. 将 errored attempts 与 model failures 分开；
3. 生成 paired raw table；
4. configuration pass 定义为 3 次中至少 2 次通过；
5. 按 company-task cluster bootstrap；
6. 报告 load-stratified paired differences；
7. 报告 quality、latency、tokens、cost，不做事后 composite score；
8. 每个失败归入 source/retrieval/calculation/specialist/delegation/synthesis/policy/grader/infrastructure taxonomy；
9. 不因结果不理想修改阈值。

## Phase 9：更新论文

只有 Stage 2A 分析冻结后再更新论文：

1. Abstract 只保留最主要、最保守结果；
2. Methodology 写入真实执行协议而不是计划；
3. Results 区分 Pilot、confirmatory、diagnostic；
4. Discussion 明确收益来源：retrieval、context allocation、parallelism、model allocation；
5. 对零效应、负效应和 infrastructure failure 如实报告；
6. Threats 更新 cluster 数、provider instability、human grader agreement；
7. Conclusion 从预声明结果类别中选择：
   - quality improvement；
   - quality preservation with efficiency improvement；
   - efficiency improvement with unacceptable quality loss；
   - no material difference；
   - indeterminate；
8. Markdown 内容冻结后，最后再生成 PDF/DOCX。

## Phase 10：可选 Stage 2B

Stage 2A 完成并通过数据审计后，考虑增加：

```text
JPMorgan Chase
Visa
PayPal
Microsoft
```

候选事实进入 suite 前必须重新完成 source lock、period/unit/basis 和 oracle audit。

---

## 12. 常用验证命令

在正确的 `codex/finance-e2e-study` worktree 中运行：

```bash
go test -count=1 ./...
go test -race -count=1 ./cmd/fastclaw ./internal/api ./internal/eval ./internal/gateway
go vet ./...
git diff --check
```

金融 Python 测试根据目标分支现有文件运行：

```bash
python3 -m unittest discover -s evals/finance_e2e -p 'test_*.py'
python3 -m unittest plugins/finance-tools/test_plugin.py
```

不要在 smoke gate 前启动 Gateway。启动后也必须确认端口和凭据只服务于隔离 benchmark tenant。

---

## 13. 新对话的建议第一条指令

可以把本文件交给新对话，并使用：

> 请先完整阅读 `/Users/wangzheyu/fastclaw/THESIS-EXPERIMENT-HANDOFF.md`。不要立即切换分支、清理工作区、启动 Gateway 或调用模型。先核对 detached HEAD、`codex/finance-e2e-study` 分支和所有未跟踪论文/SEC 资产，提出安全恢复方案。后续重点是 Go FastClaw Runtime、Stage 2 金融实验和论文内容，不优先处理 PDF 排版。所有金融数据必须来自锁定一手资料，不得捏造；所有实验结论必须区分 Pilot、calibration、diagnostic 与 confirmatory。

---

## 14. 最终边界

这个项目当前最有价值的论文贡献不是“证明多智能体更准确”，而是：

1. 建立了可以真实经过 Go Runtime 的多智能体评测基础设施；
2. 发现并修复了会让协作指标失真的 runtime、baseline、grader、trace 和成本口径问题；
3. 将金融研究中的 retrieval、context allocation、specialist analysis 和 synthesis 变成可分阶段测量的系统；
4. 用负结果和零增益结果明确了简单任务饱和、公平 baseline 和样本依赖问题；
5. 为下一阶段确认性实验预注册了数据、随机化、质量门槛、预算和停止规则。

继续工作时，优先保护这套方法论可信度，不要为了得到正向 Team gain 而改动 grader、阈值或实验口径。
