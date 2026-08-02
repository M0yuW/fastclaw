# FastClaw Fork Handoff

> 这份文档只记录 `fastclaw` 仓库本身的源码补丁和分支状态。外部总交接文档在 `/Users/wangzheyu/PROJECT-HANDOFF.md`，写的是本机上 FastClaw + FinSkills 的应用现状、启动方式和运行坑。两份文档不要混用。

> 更新：2026-07-27。当前这组 FastClaw 补丁已经从 `feat/wire-spawn-subagent` 合并进 `m0yuw-project`；`feat/wire-spawn-subagent -> dev` 的 PR `#109` 只是旧的公开分支视图，不是当前维护线。

## 1. 当前状态

- `spawn_subagent` 已接通内部 `MessageBus -> TaskQueue -> sub-agent -> reply` 路径，不再直接调用兄弟 agent。
- `m0yuw-project` 是当前应继续维护的分支，已经包含这批改动。
- `feat/wire-spawn-subagent` 是历史 feature 分支名，作用是承载最初的源码补丁，现在已经并入 `m0yuw-project`。
- `feat/prompt-injection-guard` 仍然是这条 fork 线上的另一处补丁来源。

## 2. 分支关系

- `m0yuw-project`
  - 当前远端分支：`origin/m0yuw-project`
  - 当前状态：已合并 `feat/wire-spawn-subagent`
  - 作用：后续 FastClaw fork 的维护线
- `feat/wire-spawn-subagent`
  - 当前远端分支：`origin/feat/wire-spawn-subagent`
  - 当前状态：历史 feature 分支，内容已被 `m0yuw-project` 吸收
  - 作用：保留作为补丁来源和历史引用
- `dev`
  - 仓库默认分支
  - 现在不作为这批补丁的交付目标

## 3. 已完成的源码补丁

### Internal MessageBus RPC

- trusted internal request / delivery / reply 类型
- request/reply 关联与 correlation ID
- 有界 pending 容量和非阻塞 backpressure
- call-path 与 wait-graph cycle detection
- shutdown 时拒绝新请求并释放等待中的 caller
- root execution ID 和不可变 sub-agent call path 的上下文辅助函数

### TaskQueue internal tasks

- internal / external response 分流
- internal task execution 的上下文继承
- `maxConcurrent=1` 下的内部任务串行执行
- shutdown 期间 exactly-once completion
- required-field 校验和 parent re-entry 校验
- call-path defensive copy
- completion panic containment 与 capacity release
- coordinator -> MessageBus -> TaskQueue -> sub-agent -> reply 的完整链路
- cross-tenant sub-agent target 拒绝
- caller cancellation 传播到 internal task state

### Observability

- `GET /api/tasks` 暴露 `internal`、`sourceAgentId`、`correlationId`、`callPath`、`parentChatKey`
- task observability 返回不可变快照，避免并发读取被修改中的状态
- recent-task retention 改为 `O(n log n)` 排序

## 4. 测试覆盖

- Internal MessageBus round trip
- call-path 和 cross-root wait-cycle rejection
- shutdown 时释放 pending internal callers
- `spawn_subagent` source / call metadata 和错误传播
- internal TaskQueue execution inheritance at `maxConcurrent=1`
- exactly-once completion during shutdown
- required-field 与 parent re-entry validation
- defensive call-path copying
- completion panic containment 与 capacity release
- coordinator -> MessageBus -> TaskQueue -> sub-agent -> reply integration
- cross-tenant sub-agent target rejection
- caller cancellation propagation
- immutable task observability snapshots
- Auth / Setup / Store / OpenAI API 集成测试
- Eval CLI、请求级工具隔离、trace/state 返回链路

### Agent Eval

- 已实现自建 Eval、BFCL V4 子集、τ-bench-style retail 子集、SWE-bench-style local 子集。
- 已实现 MultiAgentBench-style collaboration 子集，支持确定性模拟协作者和真实 Gateway runtime 两种模式。
- runtime 模式保留 coordinator 的真实 `spawn_subagent` 工具，用于验证现有多智能体链路。
- 指标包括 milestone KPI、team/solo success、collaboration gain、delegation precision/recall/F1、contribution utilization 和 coordination score。
- runtime Eval 可按 coordinator / sub-agent 拆分每次模型调用的 token、估算成本、模型延迟、agent ID 和 call path。
- 定价由 suite 的 `pricing` 显式提供，报告同时输出 pricing coverage，避免把未知模型误算成默认价格。
- TaskQueue 现在会在保持独立取消传播的同时继承请求 context values，使 telemetry collector 可跨 MessageBus/TaskQueue 跟随真实子任务。
- 新增可重复 provision 的独立 runtime benchmark tenant：1 个 coordinator、4 个 specialist、8 个固定证据任务和专属 Agent ACL API key。
- 固定 runtime suite 位于 `evals/multiagent-runtime-tenant.yaml`，覆盖 incident、release、access、pipeline、support、privacy、capacity 和 dependency 场景。
- Multi-Agent suite 现支持 `solo_closed_book`、`solo_open_book`、`team`、`oracle_team` 四档基线；公平协作增益使用 `team - solo_open_book`，避免把证据访问差异误算成编排收益。
- 新增 `evals/multiagent-fault-injection.yaml` 六个固定故障案例，覆盖 timeout、显式错误、畸形响应、矛盾证据、多点部分失败和非关键依赖失败。
- 请求级 Eval 工具支持按参数匹配的 delay/error/result 故障，延迟等待遵守 context cancellation，且仅允许 simulated suite 声明故障。
- baseline 执行错误会单列为 `errored` 并移出成功率分母；任一必要基线没有有效输出时，closed/fair collaboration gain 显示为 `n/a`。
- 新指标包括 fault observation rate、fault attribution rate、graceful degradation rate、unsupported claim rate，以及每档基线的成功率、错误数、token、费用和延迟。
- unsupported claim 按“出现无依据断言的故障数 / 故障数”计数，否定或不确定语境不会误判，比例上限为 100%。
- 报告新增 team-only P50/P95、总 token 和 token/success；四档 baseline 的成本分别入账，完整 harness 成本不再与 team 成本混用。
- 这些结果是项目自定义的确定性代理指标，不是官方 benchmark 分数；简历中应明确写成 “style subset”。
- 金融 SEC 简单四案例在 R7 被四档模式全部 4/4 饱和，只能证明证据约束和 runtime 链路可执行，不能证明多智能体增量准确性。
- 新增 `evals/multiagent-finance-sec-hard.json` 四个纵向案例：每家公司串联三份锁定 SEC 观察，要求计算口径控制、`0→1→2→3` 状态链和 stale candidate 拒绝。
- 冻结 R3 中 Team 与公平 `solo_open_book` 均为 3/4，公平增益 0pp；Team 相对 `solo_two_pass` 为 +50pp，但样本仅四个且单次重复，不支持显著性或等价性结论。
- R3 Team 的 AMD 失败来自 governance sub-agent 连续空结果：coordinator 共发出五次委派、超过三次预算，最终缺失 STATE/STALE 证据。下一优先级是结构化空结果错误和按 specialist/turn 双重约束的重试预算。
- 纵向实验、校准剔除、成本和失败归因见 `evals/finance_e2e/results/2026-08-02-hard-r3-final-summary.md`；论文主报告已增加对应结果段落。

当前量化结果：

```text
总语句覆盖率：7.4% -> 22.9%
internal/api：0.0% -> 52.1%
internal/eval：0.0% -> 73.8%
internal/evaltenant：新增包，75.3%
CLI：0.0% -> 15.0%
集成测试函数：0 -> 19
```

### Runtime Harness 真实评测优化

使用固定 benchmark tenant 和同一组 DeepSeek 模型完成了两轮 8-case
真实 Gateway 评测：

```text
coordinator: deepseek/deepseek-v4-pro
specialists: deepseek/deepseek-v4-flash
```

首次真实运行暴露的主要问题：

- specialist 虽有固定 `SOUL.md` evidence，仍会调用文件/记忆工具并触发
  sandbox access denied，部分任务最终达到最大 tool iterations。
- coordinator 能找到全部目标 agent，但会重复委派，delegation recall 为
  100%、precision 只有 42.0%。
- coordinator 会在 evidence 缺失后生成看似合理但不属于 fixture 的事实。
- grader 仅做原始字符串包含，对 `10%` / `10 percent`、`4` /
  `four` 和 Markdown 格式产生假阴性。
- suite 未提供 V4 pricing，报告 pricing coverage 为 0。

按根因顺序完成的 runtime 改进：

1. `requiredIdentityFiles` 在每轮模型调用前验证 `SOUL.md` /
   `IDENTITY.md`，缺失时 fail fast，并记录不含内容的 identity revision。
2. 将 policy 真正接入 Agent tool registry：
   - specialist 使用 `no-tools`；
   - coordinator 使用 `delegate-only`。
3. 无工具 agent 的 system prompt 不再注入文件工具、技能和 workspace
   self-update 指导。
4. `spawn_subagent` 对 parent turn 内同一 target 去重，重复调用复用首次结果。
5. specialist 使用 `{case_id, role, evidence}` 结构化返回 contract。
6. grader 对 Markdown、百分比、数字词、轻量词形和显式 alternatives
   做规范化。
7. runtime suite 增加 DeepSeek V4 Flash/Pro pricing。
8. Eval CLI 增加 `--case`，支持先跑低成本 smoke。

同模型、同 8 case、同 1 repetition 的历史结果（当时使用
`solo_closed_book + team` 两档；下表延迟和总 token 是完整两档 harness
口径，不可与当前四档完整 attempt 直接横比）：

| 指标 | 优化前 | 优化后 |
|---|---:|---:|
| 严格通过率 | 0%（0/8） | 100%（8/8） |
| Milestone KPI | 16.7% | 100% |
| Coordination score | 38.2% | 100% |
| Delegation precision | 42.0% | 100% |
| Contribution utilization | 17.2% | 100% |
| 总 tokens | 1,274,742 | 73,729（-94.2%） |
| 模型调用 | 194 | 53（-72.7%） |
| P50 延迟 | 110.1 秒 | 46.0 秒 |
| P95 延迟 | 201.6 秒 | 60.0 秒（-70.2%） |
| Pricing coverage | 0% | 100% |

优化后两档运行估算费用为 `$0.019599`；其中 team `$0.013751`、
closed-book solo `$0.005848`，每个成功 team case `$0.001719`。这些结果是
项目固定 evidence suite 的 runtime harness 指标，不应表述为 DeepSeek
官方 benchmark 分数。

### 金融研究 Runtime 第一阶段

金融应用不再采用“coordinator 固定 spawn 选股专家和新闻专家”的方式。
当前设计把确定性数据查询、研究方法和模型推理拆成独立层：

- 新增 `plugins/finance-tools`，通过原生 JSON-RPC 插件包装 Finskills。
- 工具结果统一使用 `finance.tool.v1`，包含来源、时间、完整度、结构化错误
  和缓存信息。
- 筛选结果默认执行完整性门禁，缺失筛选所需指标的股票不能作为通过项。
- 修复原生 tool plugin 只启动但未注册到用户 Agent registry 的运行时缺口。
- 安装固定提交
  `muxuuu/serenity-skill@c2fe93deedfd0d1bd9fe7ef0601ea1b9c20ea24a`，
  仅用于产业链卡点、证据等级、研究优先级和反证方法。
- Serenity score 是主观输入上的可重复研究优先级，不是收益预测或评测真值。
- 原生插件协议现在传递 runtime 注入的 `userId`、`agentId`、`sessionId`，
  模型参数不能伪造租户作用域。
- `finance-tools` 新增用户级隔离的 SQLite Thesis Ledger，支持假设、催化剂、
  失效条件、证据、事件复核历史和 `expected_version` 并发保护。
- Ledger schema 升级到 v2，新增用户级隔离的 watchlist 和 event alert：
  watch 可关联同市场同标的 thesis，并配置事件类型、关键词阈值和去重窗口。
- `event_alert_ingest` 使用稳定事件指纹；窗口内重复事件只更新
  `duplicate_count`、最新证据和 `last_seen_at`，不会重复触发 Agent 复核。
- Alert 支持 new、acknowledged、dismissed 状态和 `expected_version`，
  观察列表支持 active、paused、archived 生命周期。
- coordinator 与同用户 specialist 可共享研究状态，但所有查询都按可信
  `userId` 过滤，避免跨租户读取。
- 事件流程采用“数据工具抓取 → 确定性匹配 → Agent 证据判断 → 版本化落库”，
  不把关键词匹配直接解释成利好、利空或交易信号。
- 新增 `evals/multiagent-finance-workflow.yaml` 六案例固定证据评测，覆盖
  催化剂确认、失效条件、重复告警、数据缺失、组合集中度和一手证据冲突。
  公平提升只比较 team 与相同 evidence 的 solo_open_book，不使用未来收益。

### 金融检索—分析—综合端到端实验

为避免“先把完整证据喂给所有模式”掩盖真实上下文成本，新增独立的
`finance-retrieval` runner，并使用锁定 SEC 原始记录构造 24 个案例：
NVDA、AMD、Intel、NIKE × point/longitudinal × small/medium/large。

- 实验模式包括单体一次完成、单体分阶段、共享检索多智能体、原始上下文
  多智能体和 Oracle evidence 五档。
- 非 Oracle 模式只共享分析协议，不共享预期计算答案；suite 与 source lock
  使用 SHA-256 固定，禁止捏造或替换来源数据。
- 评测分解检索 recall/precision、摘要保真、最终 evidence recall、计算与决策
  milestone、数值 grounding、delegation、各阶段延迟、token 和费用。
- `spawn_subagent` 新增 batch 形式：一份 `sharedContext` 加多条 delegation，
  对不同目标并行执行，避免把同一份 SEC 证据复制进三次工具参数。
- trace 对 batch 调用和结果执行结构化压缩，保留合法 JSON、agent ID 与任务，
  防止普通字节截断破坏 delegation/contribution 归因。
- DeepSeek V4 支持请求级 thinking 开关；金融实验关闭 thinking，避免 reasoning
  占满输出预算后正文为空，并保持 token 与费用口径稳定。

最终中等上下文 Pilot 使用 `nvda-longitudinal-medium`，输入 30,518 字符，
suite SHA-256 为
`7b73f4b82a3f97cb1151b372dcf8172eb88c04d37e1e137ed80b2a87bfb44e20`。
共享检索 Team 与分阶段 Solo 都达到 3/3 milestone 和 100% 最终证据召回，
因此本例不能证明多智能体带来增量准确率。相比分阶段 Solo，共享检索 Team
延迟降低 36.32%、费用降低 42.06%，但 provider-total tokens 增加 13.63%；
检索 precision 从 66.67% 提升到 100%，grounding 提升 2.82 个百分点。
这组成本差异包含 Pro coordinator/Solo 与 Flash retriever/specialist 的异构
模型配置，属于系统级比较，不是等模型容量比较。

共享检索与原始上下文 Team 都使用一次并行 batch delegation。共享检索相对
原始上下文 Team 降低 14.15% 延迟、38.42% tokens 和 47.62% 费用，并把
grounding 从 94.87% 提升到 98.28%。原始上下文模式仅以 0.128 个百分点
未达到预声明的 95% grounding 门槛，主要问题是模型生成了证据未直接支持的
附加比率和符号变体。详细结果、失败解释、校准排除和确认性实验设计见
`evals/finance_e2e/results/2026-08-02-retrieval-pilot-final-summary.md`。

当前数据只有一个公司、一个上下文档位和一次重复，只能作为机制 Pilot。
正式论文实验应冻结 suite/grader，运行四家公司 × 三个上下文档位 × 至少
三次随机顺序重复，并用配对差值与 bootstrap 区间报告结果；`v1` 到 `v7`
是开发校准数据，不得混入确认性统计。

完整架构、工具契约、默认工作流和 Eval 方案见 `FINANCE-RUNTIME.md`。

### CI 可复现性修复

- **问题**：`internal/setup/embed.go` 使用 `//go:embed all:web`，但
  `internal/setup/web/` 是被忽略的前端构建目录。开发机已有构建产物时测试
  正常，全新 clone 或 GitHub Actions 执行 `go test ./...` 会因目录不存在而
  在编译阶段失败。
- **修复**：保留 `internal/setup/web/.gitkeep` 作为最小嵌入文件，并继续
  忽略该目录下的真实前端构建产物。
- **效果**：后端测试不再依赖开发机历史构建状态；正式构建仍由
  `make build-web` 生成并复制完整静态资源。

## 5. 现在该怎么理解这份手册

- 外部 `/Users/wangzheyu/PROJECT-HANDOFF.md` 是项目总览和运行手册。
- 这份文件只负责解释 FastClaw fork 的源码补丁、分支关系和当前维护线。
- 如果以后再看到 `feat/wire-spawn-subagent -> dev`，把它当作历史 PR 视图，不要当作当前维护目标。

## 6. 验证

本轮整理后，分支和远端状态已确认：

```text
origin/m0yuw-project 现在指向包含当前补丁的 merge commit
feat/wire-spawn-subagent 已被 m0yuw-project 吸收
PR #109 仍然是 feat/wire-spawn-subagent -> dev 的旧视图
```

本地质量门已通过：

```text
go test -count=1 ./...
go test -race -count=1 ./cmd/fastclaw ./internal/api ./internal/eval ./internal/gateway
go vet ./...
git diff --check
```

## 7. 后续注意事项

- 如果以后要继续推进这条 fork 线，优先从 `m0yuw-project` 开新工作。
- 不要再把外部应用总交接文档和这个 FastClaw 源码手册混在一起写。
- 需要时再单独更新 PR 说明，不要用分支名去替代文档定位。
