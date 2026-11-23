# FastClaw 评测框架面试拆解

> 适用范围：简历项目介绍、系统设计面试、LLM/Agent 评测面试、Go Runtime 深挖。
>
> 证据边界：核心评测实现在后续评测分支，主要参考 `codex/finance-e2e-study` 的提交 `27b6d4d`，并结合 `ba348b1`、`5513150`、`582cca9`。当前工作树是 detached `792417b`，不包含可直接编译的 `internal/eval`。两份 Runtime 结果 JSON 当前未被 Git 跟踪，覆盖率没有提交 profile。面试时应主动说明这些边界。

## 1. 先用一句话讲清项目

我做的不是单纯的 prompt benchmark，而是一套把模型能力、编排能力和 Runtime 可靠性拆开测量的多智能体评测系统：用 Suite 描述案例和判分规则，用独立 Session 和超时边界执行每次 attempt，用模拟 specialist 做可复现实验，再用真实 Gateway Runtime 做端到端验证，最后统一输出正确性、协作质量、故障恢复、延迟和 Token 成本报告。

## 2. 90 秒项目介绍

FastClaw 原本能运行多 Agent，但缺少回答三个问题的统一方法：第一，结果变好到底来自模型拿到了更多证据，还是来自多 Agent 编排；第二，系统失败时是模型能力问题，还是超时、限流、空输出等基础设施问题；第三，子 Agent 超时或返回矛盾证据时，协调器能否安全降级。

为此，我设计了 Suite 驱动的评测 Harness。Suite 用严格 YAML 定义 case、模型、重复次数、超时、工具、初始状态和 grader；Runner 为每个 attempt 创建独立 SessionKey 和 context timeout，经 Executor 调用模拟环境或真实 Gateway，再对输出文本、工具 trace、最终状态和多 Agent 协作过程评分，最终生成 JSON 报告。

为了公平比较，我没有直接用 Team 对比闭卷 Solo，而是设计了 Solo Open-Book、Solo Two-Pass、Team 和 Oracle Team。Open-Book 控制证据可见性，Two-Pass 进一步控制模型调用次数和分析/综合机会，Oracle Team 给出路由完全正确时的综合上界。这样 Team 的增益才更接近编排本身的收益。

可靠性方面，我通过请求内 specialist fault fixture 注入超时、显式错误、畸形响应、矛盾证据和多点部分失败，并定义委派 precision/recall、贡献利用率、故障归因率、安全降级率和 forbidden-claim incidence。评测暴露出重复委派、流式错误丢失、并发结果错配、SQLite 锁竞争等问题，随后通过 turn-scope 去重、tool-call ID join、错误事件传播、WAL/busy timeout 和取消传播进行修复。

在同一固定 8-case Runtime suite、每 case 一次运行的前后对比中，严格通过从 0/8 提升到 8/8，有效委派 precision 从 42.0% 提升到 100%，报告总 Token 从 1,274,742 降到 73,729，P95 从 201.6 秒降到 60.0 秒。这个结果是固定回归集上的工程验证，不外推成生产 SLA，也不把总提升归因于某一个单独修复。

## 3. 评测框架的架构

```text
YAML Suite
   |
   v
Strict Loader ---- schema validation / unknown-field rejection
   |
   v
Runner ----------- repetitions / case filter / timeout / unique session
   |
   +--> Simulated execution: deterministic specialist fixtures
   |
   +--> Gateway HTTP executor: real model + request-scoped tools
   |
   +--> Runtime mode: real coordinator + real spawn_subagent routing
   |
   v
ExecutionResponse - output / tool trace / state / usage / model calls
   |
   v
Graders ----------- text / JSON / tool trace / state / communication / MA
   |
   v
Report ------------ pass@1 / pass@k / consistency / latency / cost / MA metrics
```

### 3.1 为什么用 Suite 驱动

Suite 把测试数据、执行参数和判分规则从 Go 代码中抽离。新增案例通常只需要增加 YAML，不需要修改 Runner。核心 schema 包括：

- `Suite`：名称、描述、默认参数、case 列表。
- `Defaults`：默认 Agent、模型、重复次数和超时。
- `Case`：prompt、工具、初始状态、预期输出和 grader。
- `ExecutionRequest`：Agent、模型、SessionKey、工具、状态及是否隔离工具。
- `AttemptResult/CaseResult/Report`：单次、单 case 和整套报告。

Loader 使用 YAML `KnownFields(true)`，未知字段直接失败，并拒绝多文档 YAML。这比“忽略拼错字段然后继续跑”更适合评测，因为静默降级会使实验条件与作者预期不一致。

证据：`27b6d4d:internal/eval/types.go:37-53`、`27b6d4d:internal/eval/suite.go:17-41`。

### 3.2 Session 隔离

Runner 为整次运行生成 `runID`，再按下面的结构生成每个 attempt 的 SessionKey：

```text
<runID>-<suite>-<caseID>-<attempt>
```

因此：

- 不同 case 不共享聊天历史。
- 同一 case 的不同 repetition 不共享历史。
- 重跑同一 suite 也不会复用上次会话。
- 可以避免前一个样本泄漏答案、工具状态或长上下文到后一个样本。

证据：`27b6d4d:internal/eval/runner.go:82-102`。

### 3.3 超时控制

每个 attempt 使用独立的 `context.WithTimeout`。多 Agent 的各 baseline mode 也使用独立 timeout 和 SessionKey，避免某个慢 baseline 吃掉 Team 的预算或污染其他 mode 的历史。

这个设计提供的是有界执行和取消入口；要验证真实网络断连、SSE 半途中断和 provider 429，还需要更底层的 transport fault injection。

### 3.4 重复运行与稳定性

`repetitions` 可以在 suite 默认、case 或 CLI override 中配置。报告不只看一次通过率，还计算：

- Run pass rate：所有 attempt 中通过的比例。
- pass@1：每个 case 第一次 attempt 是否通过。
- pass@k：每个 case 的 k 次 attempt 中是否至少一次通过。
- Consistency：同一 case 的重复结果是否全部一致。

这能够区分“偶尔答对”和“稳定答对”。不过固定 Runtime 的 8-case 前后实验每 case 只有一次，不能用来证明统计稳定性。

### 3.5 状态与过程校验

评测不能只看最终自然语言。Runner 同时接收：

- 最终输出文本。
- `tool_call/tool_result` trace。
- 工具执行后的状态。
- Token usage 和模型调用记录。

Grader 可以验证：

- exact、contains、regex 和 JSON 结构。
- 工具名、参数、调用次数和非法调用。
- 最终环境状态。
- 必须向用户说明的事实。
- 多 Agent 的委派、贡献利用、故障归因和安全降级。

这避免了“答案文本看起来合理，但工具根本没调用或状态没有真正改变”的假成功。

### 3.6 JSON 报告

报告层使用结构化类型聚合 suite、case、attempt、grader、trace、usage、latency 和多 Agent 指标，并支持缩进 JSON 输出，便于：

- 保存 baseline 和 candidate。
- 做自动 diff 和回归门禁。
- 分析失败 case，而不是只保留一个总分。
- 后续接 CI、可视化或统计分析。

证据：`27b6d4d:internal/eval/report.go:9-12`。

## 4. 四类 Benchmark 子集怎么讲

这些是 benchmark-style 小型回归子集，不应声称完整复现官方 leaderboard。

### 4.1 BFCL V4 simple subset

目标：测单轮 function calling 的工具选择和参数正确性。

实现：

- 选取 3 条确定性的 `simple_python` 记录。
- 把函数 schema 作为 request-scoped tools 发送。
- 工具返回固定结果，不依赖真实外部服务。
- Gateway 在 `fastclaw.trace` 中返回结构化 tool call/result。
- 请求级工具替换当轮 Agent 工具，不修改共享 registry。

它主要回答：“模型是否选对函数、参数是否正确、Runtime 是否完整记录调用链？”

### 4.2 tau-bench-style retail subset

目标：测多轮记忆、状态迁移、用户沟通和策略约束。

实现：

- 3 个确定性的 retail case。
- 同一 case 的多轮使用同一个隔离 Session。
- 前一轮返回状态传入下一轮。
- 工具支持状态前置条件、参数插值和状态更新。
- 按最终状态而非唯一工具路径评分，因此允许不同但等价的成功轨迹。

指标包括状态准确率、沟通准确率、策略合规、端到端成功和平均轮数。

### 4.3 SWE-bench-style local subset

目标：测仓库问题理解、代码修改和隐藏测试通过能力。

实现：

- 3 个离线 Go issue fixture。
- Agent 只能通过虚拟 `list_files/read_file/write_file` 看可编辑源码。
- 测试文件对 Agent 隐藏。
- Runner 先确认 baseline 测试失败，再在临时 Git 仓库物化修改。
- 生成真实 patch，并在 timeout 下执行 hidden tests。

它不是完整 SWE-bench，而是把“issue -> patch -> hidden test”闭环缩小成稳定的本地回归集。

### 4.4 MultiAgentBench-style subset

目标：测共享目标下的委派、私有证据获取和综合。

实现：

- specialist 各自持有 coordinator 初始 prompt 不可见的私有 evidence。
- coordinator 必须决定委派给谁、如何描述任务、如何综合返回。
- 模拟模式用确定性 specialist，隔离 coordinator 的规划和综合能力。
- Runtime 模式使用真实 `spawn_subagent`，覆盖 MessageBus、TaskQueue、correlation、租户隔离、CallPath 和取消传播。

固定 Runtime tenant 包含 1 个真实 coordinator、4 个真实 specialist 和 8 个固定证据 case。

## 5. 公平 baseline 设计

多 Agent 实验最常见的问题是：Team 能看 specialist evidence，Solo 看不到，然后把 Team 的优势误称为“协作收益”。这实际混合了 evidence access、额外 compute 和 orchestration 三个变量。

### 5.1 Solo Open-Book

- 不提供委派工具。
- 把 Team 可获得的同一份 evidence 匿名、扁平化后直接放入 prompt。
- 使用与 Team 相同的输出 grader。

作用：控制证据可见性。`Team - Solo Open-Book` 才是较公平的 orchestration gain。

### 5.2 Solo Two-Pass

- 使用与 Open-Book 相同的匿名 evidence。
- 第一次模型调用做分析。
- 第二次模型调用基于同一 Session 做综合。
- usage 和 model-call 记录合并。

作用：进一步控制 Team 多出来的规划/综合机会和模型调用次数。`Team - Solo Two-Pass` 是 compute-matched gain。

证据：`27b6d4d:internal/eval/multiagent.go:635-651`。

### 5.3 Team

- coordinator 正常规划和调用 specialist。
- 模拟模式调用 request-scoped deterministic specialist tools。
- Runtime 模式走真实 `spawn_subagent`。
- 严格成功除了最终业务 milestone，还可要求委派、贡献利用、grounding 和效率满足约束。

### 5.4 Oracle Team

- 直接把带 specialist 身份的完整报告交给 coordinator。
- 假设路由、委派和交付完全正确。
- 测量 coordinator 综合阶段的上界。

如果 Team 明显低于 Oracle，问题更可能在路由、委派、交付或故障恢复，而不只是最终综合能力。

### 5.5 可选的 Solo Closed-Book

系统还支持闭卷 Solo，仅拿到任务、不拿 evidence。它可以诊断“额外证据总体有多大价值”，但 `Team - Closed-Book` 是乐观差值，不能作为 orchestration 本身的收益证明。简历列四档公平基线时可以不把它算入主对比，但面试中应知道它存在。

## 6. 基础设施错误的正确口径

这里是当前简历最需要修正的地方。

### 6.1 通用 Runner

通用 RunPassRate 是：

```text
PassedRuns / TotalRuns
```

所有 attempt 都先进入 `TotalRuns`。因此执行错误通常仍会压低主成功率。

### 6.2 Multi-Agent baseline

Baseline 聚合采用：

```text
baseline.Error != "" -> Errored++
否则                 -> Evaluated++
SuccessRate           = Passed / Evaluated
Attempted             = Evaluated + Errored
```

所以 baseline success rate 是“在获得有效模型输出条件下”的条件成功率。执行错误仍保留 Token/成本，但不进入 `Evaluated` 分母。

### 6.3 当前没有做到什么

当前结果结构只有通用 `Error`，没有独立的：

- `TimeoutCount`
- `RateLimit429Count`
- `EmptyOutputCount`
- `TransportErrorCount`

因此不能说“超时、429、空输出已经分别统计”。更准确的表述是：

> 将 baseline 执行错误聚合为 `Errored`，与有效模型输出分离；保留 attempt 级 Error 和输出用于事后归因，并避免把无有效输出的执行错误计入 conditional model success 分母。

面试中最好同时报告：

```text
Conditional model success = Passed / Evaluated
Operational success       = Passed / (Evaluated + Errored)
Infrastructure error rate = Errored / (Evaluated + Errored)
```

后两个公式是建议的补充报告口径；当前代码没有按 timeout/429/empty 细分聚合。

## 7. Fault Injection 设计

### 7.1 注入层级

故障挂在 case 内的 specialist fixture 上，按 `agentId` 构造当次请求内的 tool fault。它是 request-scoped specialist tool injection，不是 provider HTTP 层故障注入。

支持四种 primitive：

- `timeout`：确定性 delay 后返回工具错误。
- `error`：立即返回显式工具错误。
- `malformed`：以成功 tool result 返回畸形文本。
- `contradictory`：以成功 tool result 返回矛盾证据。

### 7.2 六个场景

1. Specialist timeout：关键专家超时后是否披露证据缺口。
2. Explicit error：工具显式失败后是否避免复述私有证据。
3. Malformed response：能否拒绝不可解析结果并保留其他贡献。
4. Contradictory evidence：能否报告冲突并停止高风险动作。
5. Multiple partial failures：多个 specialist 分别 error/malformed 时能否组合降级。
6. Noncritical failure：非关键证据缺失时能否给出可逆建议，但不编造预算。

### 7.3 执行和评分链路

```text
YAML fault fixture
 -> validate type/message/response/delay
 -> build request-scoped StateToolFault
 -> execute specialist tool
 -> inspect trace to confirm fault observed
 -> inspect final answer for attribution
 -> inspect forbidden claims
 -> evaluate remaining milestones
 -> compute graceful degradation
```

### 7.4 不能过度外推

- timeout 不等于真实 socket deadline 或连接断开。
- malformed/contradictory 主要测语义识别，不测 schema decoder。
- 没有独立注入 429、5xx、connection reset 或 SSE mid-stream failure。
- 多点失败是代表性场景，不是完整 N 点组合矩阵。

## 8. 多智能体指标

### 8.1 委派 Precision、Recall 和 F1

```text
Precision = ValidDistinctDelegatedAgents / UniqueDelegatedAgents
Recall    = ValidDistinctDelegatedAgents / ExpectedAgents
F1        = 2 * Precision * Recall / (Precision + Recall)
```

有效委派不仅要求 Agent ID 正确，还要求 task 包含该 specialist 要求的任务信息。重复调用同一 Agent 在总委派数中可见，但 precision 分母按 unique Agent 去重。

简历中的 `42% -> 100%` 实际是 delegation precision，不是通用“准确率”。Recall 原本已经是 100%，所以面试时必须说清：优化主要消除了错误/冗余目标，而不是解决漏派。

### 8.2 贡献利用率

```text
ContributionUtilization
= FullyUtilizedHealthyContributions / ExpectedHealthyContributions
```

只有 specialist 被正确委派，并且最终输出包含其全部预设 `contribution_values`，该 specialist 才算被完整利用；故障 specialist 从健康贡献分母排除。

这是确定性短语匹配意义的利用率，不是因果贡献，也不能证明引用语境一定正确。

### 8.3 故障观察率与归因率

```text
FaultObservationRate = ObservedInjectedFaults / ExpectedFaults
FaultAttributionRate = AttributedFaultInstances / ExpectedFaultInstances
```

观察率回答“工具故障是否真的发生并进入 trace”；归因率回答“最终答案是否向用户正确解释了故障”。工具失败但答案不披露时，observation 可以通过，attribution 必须失败。

### 8.4 安全降级率

单次 fault attempt 只有同时满足以下条件才算 graceful：

```text
AllMilestonesPassed
AND AllFaultsObserved
AND AllFaultsAttributed
AND UnsupportedClaims == 0
```

聚合：

```text
GracefulDegradationRate
= GracefullyDegradedFaultAttempts / FaultInjectedAttempts
```

这里的“安全”是 suite oracle 定义下的安全，不等同于形式化安全证明或生产风险审计。

### 8.5 无依据断言率

当前实现更准确的名字是“每故障实例 forbidden-claim incidence”：

```text
UnsupportedClaimRate
= FaultInstancesWithAnyForbiddenAssertion / ExpectedFaultInstances
```

它不是“无依据断言条数 / 全部断言条数”。同一故障产生多条编造内容也最多计一个 instance。判定还存在否定和 hedge 豁免，因此语义 grader 仍有假阴性风险。

## 9. Runtime 问题如何被定位和修复

### 9.1 Specialist 工具越权

问题：共享 registry 会让 Agent 看见不应暴露的工具；只在 prompt 中写“You have no tools”不是权限边界。

修复：

- 用 Context 为单 turn 替换 registry，不修改共享 registry。
- eval 请求可以启用 request-scoped tool isolation。
- 真正执行前再经过 policy engine filter。
- 复制 registry 时只保留 allow predicate 接受的工具。

证据：`ba348b1:internal/agent/tool_context.go:11-26`、`internal/api/openai.go:186-206`、`internal/agent/loop.go:630-635`。

诚实边界：硬隔离主要在受控 eval request 链；生产 specialist 仍存在 prompt-only 限制，不能声称全局角色级 ACL 已完整实现。

### 9.2 重复委派

问题：每次 `spawn_subagent` 都生成新 ChatID，模型重复调用同一 target/task 会真实执行两次，造成 Token 和延迟浪费。

修复：

- 每个父 turn 创建 dedup context。
- 生产 key 使用 `target + task`。
- 第一次调用保存 result；重复调用等待并复用结果。
- 等待过程响应取消。
- 同 target、不同 task 不会被错误合并。

证据：`582cca9:internal/agent/tools/subagent.go:41-130`、`internal/agent/loop.go:543`。

这是 turn-scope 去重，不是跨用户或跨请求缓存。

### 9.3 身份文件 Fail-Fast 与流式错误丢失

问题：SOUL/身份文件原本是 best effort；缺失时 Agent 仍可能运行。加入校验后，错误又可能只作为同步返回值返回，没有发送 SSE error event。

修复：

- required identity 缺失、为空或 store 读取失败时，在 turn 前失败。
- store error 不再悄悄 fallback 到本地文件。
- 失败先进入 `events.fail(...)`，再返回错误。

价值：同步调用和流式消费者看到一致错误，Agent 不会带着空身份继续执行。

证据：`ba348b1:internal/agent/context.go:84-125`、`5513150:internal/agent/loop.go:570-579`。

### 9.4 并发结果归属错误

问题：并发工具调用返回顺序不稳定。按 slice 位置 zip 会把 A 的结果归给 B；空、重复或缺失 ID 还会留下 orphaned `tool_use`。

修复：

- 调用前保存原始 tool-call ID metadata。
- 返回后按 `ToolUseID` 建 map，而不是依赖完成顺序。
- 按原始 call 顺序恢复结果和 stream event。
- 对空 ID、重复 ID、缺失结果生成显式错误 result。

核心思想：并发 join 必须基于稳定 identity，而不是基于数组位置。

证据：`582cca9:internal/agent/sdkbridge.go:31,225-315`、`internal/agent/loop.go:829-899`。

### 9.5 SQLite 锁竞争

问题：SQLite 是单 writer；没有 WAL 和 busy timeout 时，并发 writer 遇锁会立即失败。

修复：默认规范化 DSN，并补充：

```text
journal_mode(WAL)
foreign_keys(1)
busy_timeout(5000)
```

集成测试先证明 timeout=0 的 contender 立即失败，再证明默认配置会等待锁释放后成功。

边界：连接池仍允许 25 个 open connections，所以这是把瞬时冲突改成有界等待，不是消灭 SQLite 单写者限制。

证据：`582cca9:internal/store/database.go:27-91`。

### 9.6 取消传播

问题：父调用取消后，如果 MessageBus waiter 和 TaskQueue 子任务继续存活，会产生资源泄漏和无意义模型调用。

修复：

- MessageBus 用 correlation ID 注册 pending reply。
- 请求取消时清理 waiter。
- TaskQueue 使用 `context.AfterFunc` 把父取消传给任务 cancel。
- 保留父 context values，支持 trace/root execution 信息继续传播。

这属于 structured cancellation，不是只在最外层设置一个 timeout。

证据：`582cca9:internal/bus/internal.go:95-145`、`internal/taskqueue/queue.go:285-289`。

## 10. 量化结果怎么讲

### 10.1 实验条件

- Suite：`fastclaw-fixed-runtime-tenant`。
- Case 数：8。
- Repetition：每 case 1 次。
- 模型：前后顶层均记录 `deepseek/deepseek-v4-pro`，specialist 组合一致。
- Before：[runtime-pilot.json](/Users/wangzheyu/fastclaw/runtime-pilot.json)
- After：[runtime-pilot-optimized-v2.json](/Users/wangzheyu/fastclaw/runtime-pilot-optimized-v2.json)

### 10.2 数字核验

| 指标 | Before | After | 解释 |
|---|---:|---:|---|
| 严格通过 | 0/8 | 8/8 | 固定回归集全部通过 |
| Delegation precision | 42.0289% | 100% | 错误/冗余目标被消除；不是 recall |
| 报告总 Token | 1,274,742 | 73,729 | 下降 94.216%，四舍五入 94.2% |
| P95 latency | 201.590843s | 60.037384s | 写成 201.6s -> 60.0s 正确 |

Token 降幅计算：

```text
(1,274,742 - 73,729) / 1,274,742 = 94.2162%
```

### 10.3 不能声称什么

- 只有 8 个样本，P95 接近最大值，不能外推成生产 SLA。
- 每 case 只有一次，不能声称统计显著或稳定 100%。
- 两份 JSON 未跟踪，且只保存 suite 路径、不保存 suite hash，不能完全证明实验条件不可变。
- 没有 ablation，不能把 94.2% Token 降幅全部归因于委派去重。
- 更稳妥的说法是“整套 Runtime 优化前后对比”。

## 11. 测试与覆盖率怎么讲

### 11.1 19 个集成测试

可以从提交中枚举复核：

- CLI：5
- OpenAI API：3
- Auth：1
- Eval runner：3
- Eval tenant：1
- Gateway subagent：3
- Setup API：2
- Store：1

合计 19 个带 Integration 语义的测试函数。覆盖的关键路径包括请求级工具隔离、真实 HTTP 执行、tenant provision、subagent 权限/取消和数据库锁等待。

### 11.2 覆盖率 7.4% -> 22.9%

该数字只有 `ba348b1:PROJECT-HANDOFF.md:92` 的记录和 Makefile 中的测量命令，没有提交 before/after coverage profile 或 CI artifact。

面试建议说：

> 新增 19 个集成测试函数；当时本地 `go test ./...` 语句覆盖率记录由 7.4% 提升到 22.9%。

不要说“CI 可复现证明覆盖率提升”。

## 12. 建议修改后的简历表述

### 第一条

设计 Suite 驱动的多智能体评测框架，支持 attempt 级独立 Session、超时、重复运行、工具 trace/状态校验和 JSON 报告；构建 BFCL V4、tau-bench、SWE-bench 与 MultiAgentBench 风格的小型回归子集，并结合确定性 specialist 模拟与真实 Gateway Runtime 测试。

### 第二条

设计 Solo Open-Book、Solo Two-Pass、Team、Oracle Team 四档公平基线，分别控制证据可见性、模型调用次数与路由正确性，避免将 evidence access 或额外 compute 误判为多智能体编排收益；将 baseline 执行错误聚合为 `Errored`，与有效模型输出分离统计。

### 第三条

构建请求内 specialist Fault Injection，覆盖确定性超时、显式错误、畸形响应、矛盾证据及多点部分失败；定义 delegation precision/recall/F1、贡献利用率、故障观察/归因率、安全降级率和 forbidden-claim incidence 等多智能体指标。

### 第四条

通过评测定位重复委派、流式错误丢失、并发 tool result 错配和 SQLite 锁竞争；通过 turn-scope 委派去重、身份文件 Fail-Fast、tool-call ID join、取消传播及 WAL/busy timeout 提升 Runtime 稳定性，并在受控评测链中实现 request-scoped 工具隔离。

### 第五条

在固定 8-case、单次重复的真实 Runtime 回归中，将严格通过由 0/8 提升至 8/8、有效委派 precision 由 42.0% 提升至 100%，报告总 Token 降低 94.2%，P95 由 201.6s 降至 60.0s；新增 19 个集成测试函数，本地语句覆盖率记录由 7.4% 提升至 22.9%。

## 13. 高频面试追问与回答

### Q1：为什么不能直接 Team 对比 Solo？

因为 Team 天然获得 specialist evidence 和更多模型调用。直接对比闭卷 Solo 会把证据可见性和额外 compute 混进协作收益。Open-Book 控制 evidence，Two-Pass 再控制调用机会，Oracle 给出路由无损时的综合上界。

### Q2：为什么同时需要模拟和真实 Runtime？

模拟 specialist 是确定性的，适合重复实验和归因 coordinator 行为；真实 Runtime 覆盖 MessageBus、TaskQueue、Session、权限、取消和并发等系统问题。前者提高内部有效性，后者提高工程真实性。

### Q3：如何防止 case 之间相互污染？

每个 run、case 和 repetition 都生成唯一 SessionKey；每个 attempt 有独立 timeout；tau 风格的多轮只在同一个 case 内显式复用 Session 和状态。

### Q4：42% 到 100% 到底是什么？

是 delegation precision，即有效且唯一的目标委派数除以唯一委派目标数。不是泛化 accuracy，也不是 recall；该实验中 recall 原本已经是 100%，优化主要消除了错误或冗余委派。

### Q5：为什么贡献利用率不是简单数关键词？

当前实现确实以确定性 contribution values 做可复现判分，但按 specialist 要求全部贡献项被最终答案保留。它适合回归测试，不等于语义因果贡献；后续可以用结构化 evidence ID 和独立 judge 降低同义改写误差。

### Q6：什么叫安全降级？

不是“返回一个保守答案”就算通过，而是业务 milestone 完成、所有注入故障在 trace 中可观察、最终答案正确归因、且没有 forbidden unsupported claim 四项同时满足。

### Q7：基础设施错误为什么不直接算模型失败？

为了区分模型条件能力和系统可用性。Baseline 将执行错误放入 `Errored`，条件成功率只看有效输出；但生产视角还必须同时看 `Passed/(Evaluated+Errored)`。当前代码没有按 429/timeout/空输出细分，这是后续改进点。

### Q8：Token 为什么能下降 94.2%？

这是整套优化前后的总量差，包括重复委派减少、执行路径和上下文优化等共同作用。由于没有逐项 ablation，不能声称全部由某一个优化带来。

### Q9：SQLite 问题彻底解决了吗？

没有。WAL 提高读写并发，5 秒 busy timeout 把瞬时锁冲突变成有界等待，但 SQLite 仍是单 writer。更高写并发需要串行写队列、缩短事务或迁移 PostgreSQL。

### Q10：如果再做一版，你会补什么？

1. 给 suite 和 prompt 保存内容 hash、Git SHA、provider/model manifest。
2. 把 timeout、429、5xx、empty、SSE interruption 做成结构化错误 taxonomy。
3. 同时报 conditional model success 和 operational success。
4. 引入 transport/provider 层 fault proxy，而不只注入 tool fixture。
5. 为 8-case 实验增加 repetitions、置信区间和 bootstrap。
6. 增加逐项 ablation，拆解去重、prompt、模型和并发修复各自贡献。
7. 将生产 specialist 工具权限升级成服务端角色 allowlist。
8. 将结果 JSON、coverage profile 和 CI artifact 纳入版本化追踪。

## 14. 面试时必须守住的五条边界

1. 说“benchmark-style subset”，不要说完整复现官方榜单。
2. 说“delegation precision 42% -> 100%”，不要泛称准确率。
3. 说“执行错误聚合为 Errored”，不要声称 timeout/429/空输出已有独立 counter。
4. 说“缓解 SQLite 锁冲突”，不要说彻底解决并发写。
5. 说“固定 8-case 单次回归”，不要把 8/8 和 P95 外推为生产稳定性结论。

## 15. 术语速查：把评测框架类比成考试

可以把整个评测框架类比成一场考试：

```text
Suite（试卷）
  ├── Case 1（题目）
  │     ├── Attempt 1（第一次独立作答）
  │     ├── Attempt 2（第二次独立作答）
  │     └── Attempt 3（第三次独立作答）
  └── Case 2
        └── ...
```

### 15.1 Suite：整张试卷

`Suite` 是一整套评测任务及其规则，不只是问题集合。它通常包含：

- Suite 名称和描述。
- 多个测试 Case。
- 默认模型和 Agent。
- 每个 Case 的重复次数。
- 每次运行的超时时间。
- 可使用的工具。
- 初始环境状态。
- 预期结果。
- Grader 判分规则。

示例：

```yaml
name: finance-runtime-eval
defaults:
  repetitions: 3
  timeout: 120s

cases:
  - id: earnings-risk
    prompt: 分析该公司的财报风险
    expected_agents:
      - news-analyst
      - stock-screener
```

面试中可以说：

> Suite 把测试数据、执行参数和判分规则配置化。新增案例通常只改 YAML，不需要修改 Runner，因此实验条件更容易复现和审计。

### 15.2 Case：一道具体题目

`Case` 是 Suite 里面的一道题。例如：

```text
用户持有某公司股票。
新闻专家发现监管调查；
基本面专家发现现金流恶化；
请给出是否继续持有的建议。
```

一个 Case 可以包含：

- 输入问题。
- 预期调用的专家。
- 专家持有的私有证据。
- 最终答案必须包含的内容。
- 禁止出现的无依据断言。
- 是否注入 specialist 故障。
- 应达到的最终环境状态。

因此 Case 同时定义“给 Agent 什么题”和“什么答案才算通过”。

### 15.3 Attempt：一次独立作答

`Attempt` 是某个 Case 的一次独立执行，也就是一次作答。

如果 Case 配置：

```yaml
repetitions: 3
```

就会得到：

```text
Case A / Attempt 1
Case A / Attempt 2
Case A / Attempt 3
```

每个 Attempt 都有：

- 独立 Session。
- 独立聊天历史。
- 独立超时。
- 独立工具状态。
- 独立输出和 trace。
- 独立 Token、延迟和判分结果。

这能避免第一次运行的答案泄漏给第二次运行。多次 Attempt 还可以衡量稳定性：

- 三次都通过：结果稳定。
- 只有一次通过：可能是偶然成功。
- 三次结果不同：一致性较差。

需要注意：在多智能体评测中，一个 Attempt 内部还可能执行多个 baseline mode，例如 Open-Book、Two-Pass、Team 和 Oracle Team；这些 mode 仍然使用独立 Session 和超时。

### 15.4 Baseline：用于对照的实验组

`Baseline` 是用来对照 Team 的实验组。

如果只测 Team 得到 90% 成功率，无法判断结果变好是因为：

- 多 Agent 协作真的有效。
- Team 看到了更多证据。
- Team 调用了更多次模型。
- 任务本身比较简单。

所以需要设计多个 baseline，逐步控制变量。

### 15.5 Solo Open-Book：单 Agent 直接读证据

`Solo` 表示只有一个主 Agent，没有子 Agent 委派。`Open-Book` 表示该 Agent 可以直接看到 Team 能获得的全部证据。

Team 原本需要这样执行：

```text
Coordinator
  ├── 调用 news-analyst，获得新闻证据
  └── 调用 stock-screener，获得财务证据
```

Solo Open-Book 则直接收到：

```text
任务：判断是否继续持有股票。

可用证据：
- 公司正在接受监管调查。
- 公司经营现金流同比下降 35%。
```

它的特征是：

- 通常只有一次 coordinator 模型调用。
- 没有 `spawn_subagent`。
- 不需要决定委派给谁。
- 证据被匿名、扁平化。
- 证据内容与 Team 可获得的内容相同。
- 使用与 Team 相同的最终答案 grader。

它主要控制“证据可见性”。因此，`Team - Solo Open-Book` 比 `Team - Solo Closed-Book` 更接近编排收益；后者还混入了“是否获得证据”的差异。

### 15.6 Solo Two-Pass：单 Agent 两轮分析

`Solo Two-Pass` 仍然只有一个 Agent，也没有子 Agent。它使用两次连续模型调用：

```text
第一轮：分析证据，识别风险、冲突和缺失信息。
第二轮：基于第一轮分析，形成最终答案。
```

它的特征是：

- 同一个 Solo Agent。
- 同一个 Session。
- 相同的匿名证据。
- 没有子 Agent 和委派工具。
- 第一次调用负责分析。
- 第二次调用负责综合。
- 两次调用的 Token 和延迟合并统计。

它不是两个 Agent，也不是两个独立 Attempt，而是**同一个 Attempt 内的两次连续模型调用**。这样既控制了证据可见性，也给 Solo 一个与 Team 更接近的额外分析/综合机会。

因此：

```text
Team - Solo Two-Pass
```

是更严格的 compute-matched gain。如果 Team 仍然更好，收益更可能来自角色分工、并行分析、委派决策和故障处理，而不只是多调用了一次模型。

实现上，第一轮和第二轮复用同一个 `ExecutionRequest`/Session 上下文，先执行 `multiAgentTwoPassAnalysisPrompt`，再执行 `multiAgentTwoPassSynthesisPrompt`，并合并两轮 usage。代码位置：`27b6d4d:internal/eval/multiagent.go:635-651`。

### 15.7 Team：正常的多智能体协作

```text
用户问题
   ↓
Coordinator
   ├── 判断需要哪些专家
   ├── spawn news-analyst
   ├── spawn stock-screener
   ├── 接收专家结果
   └── 综合最终答案
```

Team 不只看最终答案是否正确，还可能评估：

- 是否委派给正确专家。
- 委派任务是否包含必要信息。
- 是否发生重复委派。
- 是否使用专家贡献。
- 专家故障后是否正确归因。
- 是否产生无依据断言。
- Token 和延迟是否在约束内。

### 15.8 Oracle Team：路由无损时的综合上限

`Oracle Team` 假设委派和路由完全正确。系统不要求 Coordinator 自己决定调用谁，而是把带 specialist 身份的完整报告直接交给它：

```text
news-analyst 报告：监管调查已经启动。
stock-screener 报告：现金流同比下降 35%。
```

它主要测“综合能力上限”。例如：

```text
Solo Open-Book：70%
Solo Two-Pass：78%
Team：80%
Oracle Team：96%
```

可以这样解释：

- Two-Pass 比 Open-Book 高 8 个百分点，说明额外分析机会有帮助。
- Team 比 Two-Pass 高 2 个百分点，说明真实协作带来有限增益。
- Oracle 比 Team 高 16 个百分点，说明瓶颈可能在委派、路由、专家结果交付或故障恢复，而不一定在最终综合。

### 15.9 模式对照表

| 模式 | 能否看到证据 | 模型调用 | 是否委派 | 主要控制变量 |
|---|---|---:|---|---|
| Solo Closed-Book | 否 | 1 次 | 否 | 无证据时的基础能力 |
| Solo Open-Book | 是，匿名扁平化 | 1 次 | 否 | 证据可见性 |
| Solo Two-Pass | 是，匿名扁平化 | 2 次 | 否 | 证据和额外计算机会 |
| Team | 通过专家获得 | 多次 | 是 | 真实编排效果 |
| Oracle Team | 是，带专家身份 | 1 次综合 | 路由已被替代 | 综合能力上限 |

面试总结可以直接说：

> Suite 是完整评测试卷，Case 是一道题，Attempt 是一次独立作答。Solo Open-Book 控制证据可见性，Solo Two-Pass 进一步控制模型调用和分析机会，Team 测真实编排，Oracle Team 测路由完全正确时的综合上限。通过逐层控制变量，才能避免把更多证据或更多计算误判为多智能体协作收益。

## 16. 代码级实现说明

这一节按一次 `eval run` 的真实调用链来理解代码：

```text
Cobra CLI
  -> LoadSuite(path)
  -> Suite.Validate()
  -> Runner{HTTPExecutor, RunOptions}
  -> Runner.Run(ctx, suite)
  -> runAttempt(ctx, case, attempt, runID)
  -> Executor.Execute(ExecutionRequest)
  -> Gateway /v1/chat/completions
  -> ExecutionResponse{Output, Trace, State, Usage}
  -> GradeAttempt(output, trace, graders)
  -> CaseResult / calculateMetrics
  -> Report
  -> text 或 JSON 文件
```

### 16.1 CLI 参数如何进入 Runner

入口是：

```bash
go run ./cmd/fastclaw eval run evals/smoke.yaml \
  --base-url http://127.0.0.1:18953 \
  --api-key "$FASTCLAW_API_KEY" \
  --agent-id coordinator \
  --repetitions 3 \
  --timeout 90s \
  --format json \
  --output baseline.json \
  --fail-under 0.8
```

`cmd/fastclaw/cmd_eval.go:395-450` 负责以下工作：

1. Cobra 校验必须传入一个 suite 路径。
2. 校验 `--format` 只能是 `text` 或 `json`。
3. 校验 `--fail-under` 在 `[0, 1]` 内。
4. 读取 `--base-url`，默认从 `FASTCLAW_EVAL_BASE_URL` 读取，否则使用 `http://127.0.0.1:18953`。
5. 读取 `--api-key`，默认从 `FASTCLAW_API_KEY` 读取。
6. 读取 Agent、重复次数和 timeout override。
7. 调用 `LoadSuite(args[0])`。
8. 构造：

```go
runner := eval.Runner{
    Executor: &eval.HTTPExecutor{
        BaseURL: baseURL,
        APIKey:  apiKey,
    },
    Options: eval.RunOptions{
        AgentID:     agentID,
        Repetitions: repetitions,
        Timeout:     timeout,
    },
}
```

9. 调用 `runner.Run(command.Context(), suite)`。
10. 将 Report 写成终端文本或 JSON；如果 `RunPassRate < fail-under`，命令返回失败，适合作为 CI 门禁。

CLI 参数不是直接覆盖所有 Case 字段，而是作为 Runner-level override。具体优先级在 Runner 内部决定：

```text
CLI override > Case value > Suite defaults > framework fallback
```

重复次数的 fallback 是 1；timeout 则回退到框架默认 timeout。代码位置：`27b6d4d:internal/eval/suite.go:118-142`。

### 16.2 Suite schema 的数据结构

通用 Suite 的核心 Go 类型是：

```go
type Suite struct {
    Version     int
    Name        string
    Description string
    Defaults    Defaults
    Cases       []Case
    Source      string
}

type Defaults struct {
    AgentID     string
    Model       string
    Repetitions int
    Timeout     Duration
}

type Case struct {
    ID          string
    Description string
    Prompt      string
    AgentID     string
    Model       string
    Repetitions int
    Timeout     Duration
    Tags        []string
    Tools       []ToolDefinition
    Graders     []GraderSpec
}
```

对应代码：`27b6d4d:internal/eval/types.go:37-64`。

`Duration` 不是裸整数，而是用 `time.ParseDuration` 解析 YAML，因此可以写 `90s`、`2m`。加载时使用严格 YAML decoder，并在 decode 后执行 `Suite.Validate()`：

- `version` 必须匹配当前 Suite version。
- suite 名称和 case ID 不能缺失。
- case prompt 不能为空。
- repetitions 和 timeout 不能是非法值。
- grader type 必须在支持集合内。
- grader 必须具备对应参数，例如 exact 需要 value，tool_trace 需要 expected calls。
- 不允许未知 YAML 字段或多个 YAML document。

这样可以在模型运行前发现配置错误，不把“配置写错”混成“模型失败”。

专用 benchmark 不强行复用通用 `Case`：

- τ-bench case 额外有 `InitialState`、`Tools` 和多轮 `Turns`。
- SWE case 有 fixture、editable files、test command 和 hidden tests。
- Multi-Agent case 有 coordinator、specialists、milestones、baselines 和 fault fixture。

所以代码结构是“共享 Runner 抽象 + benchmark-specific adapter”，而不是所有 benchmark 共用一份巨型 schema。

### 16.3 Runner 如何创建一次 Attempt

`Runner.Run` 首先检查 Executor 非空、校验 suite、生成本次 run 的 `runID`，然后按 case 遍历并按 repetitions 调用 `runAttempt`：

```go
runID = <session-prefix>-<unix-nano>-<sequence>
sessionKey = <runID>-<suite-name>-<case-id>-<attempt>
```

`runAttempt` 的顺序是：

```text
1. 选择 timeout
2. context.WithTimeout
3. 选择 AgentID 和 Model
4. 生成唯一 SessionKey
5. 复制 Case tools
6. Executor.Execute(request)
7. 记录 latency
8. 若 Execute 返回 error，生成 Passed=false、Error=...
9. 否则将 Output + Trace 交给 GradeAttempt
10. 保存 Model、Usage、Trace、Graders、State
```

关键实现位置：`27b6d4d:internal/eval/runner.go:83-124`。

执行错误和 grader 失败在数据结构上是两条不同路径：

```text
Executor error:
  AttemptResult.Error != ""
  AttemptResult.Passed = false
  没有有效 output/graders

模型正常返回但答案不合格：
  Error 为空
  Output/Trace/Graders 有值
  Grader 中至少一个 Passed=false
```

这就是为什么报告中必须同时保留 `error`、`output` 和逐项 `graders`，否则无法区分基础设施故障与模型错误。

### 16.4 HTTPExecutor 的真实请求

通用 `HTTPExecutor` 实现 `Executor` 接口，但它不是直接调用模型 Provider，而是调用 FastClaw Gateway：

```text
POST <baseURL>/v1/chat/completions
```

请求中包含：

```json
{
  "model": "...",
  "messages": [{"role": "user", "content": "..."}],
  "stream": false,
  "tools": [...],
  "fastclaw": {
    "eval": true,
    "include_trace": true,
    "include_usage_breakdown": true,
    "isolate_tools": false,
    "state": {},
    "tool_results": {},
    "tool_behaviors": {}
  }
}
```

HTTP 层行为：

- 有 API key 时设置 `Authorization: Bearer ...`。
- 有 Agent ID 时设置 `x-fastclaw-agent-id`。
- 使用 `http.NewRequestWithContext`，所以 Runner timeout 可以取消 HTTP 请求。
- 非 2xx 状态读最多 64 KiB 错误正文并返回 error。
- JSON decode 失败返回 error。
- 没有 choices 返回 `chat completion response has no choices`。
- 从第一条 choice 提取 output/model/usage。
- 从 `fastclaw` 扩展提取 trace/state/model calls。
- 如果 trace 中包含 error event，也返回 turn failed error。

代码位置：`27b6d4d:internal/eval/http_executor.go:68-166`。

### 16.5 Grader 的输入和输出

通用 grader 的入口是：

```go
GradeAttempt(output string, trace []TraceEvent, specs []GraderSpec)
    ([]GraderResult, bool)
```

它逐个执行 GraderSpec，并对所有结果做逻辑 AND：只要有一个 grader 失败，Attempt 就失败。

```go
type GraderResult struct {
    Type    string
    Passed  bool
    Message string
}
```

通用 grader 类型：

| Grader | 输入 | 判定 |
|---|---|---|
| `exact` | output + value | 归一化后完全相等 |
| `contains` | output + values | 每个 value 都出现 |
| `not_contains` | output + values | 禁止内容不能出现 |
| `regex` | output + pattern | 正则匹配 |
| `json_valid` | output | 能否解析为合法 JSON |
| `tool_trace` | trace + expected calls | 工具名、参数、顺序和额外调用是否符合 |

`tool_trace` 不看最终自然语言是否“声称调用过工具”，而是直接看 Gateway 返回的 trace。它先过滤 `tool_call` event，再检查：

- 实际调用数量是否达到预期。
- `allow_extra=false` 时是否严格等长。
- tool name 是否一致。
- 参数是否一致。
- `order_sensitive=true` 时顺序是否一致。

代码位置：`27b6d4d:internal/eval/grader.go:16-126`。

专用 grader 在 adapter 层执行：

```text
Generic Runner:
  output + trace -> exact/contains/regex/json/tool_trace

Tau Runner:
  multi-turn outputs + state -> state accuracy
  required user messages -> communication accuracy
  forbidden tool calls -> policy compliance

SWE Runner:
  returned editable files -> temporary Git patch
  patch + hidden command -> hidden test result

MultiAgent Runner:
  delegation trace + specialist evidence + final output
  -> milestone / delegation / contribution / fault metrics
```

因此面试中应说“共享执行和报告骨架，benchmark-specific adapter 负责领域判分”，不要说所有判分都在同一个 generic grader switch 中完成。

### 16.6 模拟 Executor 与真实 Runtime 的差异

这里要精确区分三件事：

1. `Executor` 是接口，便于 Runner 测试时注入 fake executor。
2. `HTTPExecutor` 是实际通过 HTTP 调 Gateway 的实现。
3. “模拟 specialist”并不一定意味着整个 Executor 是 fake。

在 Multi-Agent 模拟模式下，通常仍由真实 coordinator/Gateway 执行，但把 specialist 表示成 request-scoped deterministic tool：

```text
Case agents[].response
  -> tool result fixture
  -> coordinator 通过工具获得固定报告
```

好处是 specialist response、延迟和故障可控，可以隔离测 coordinator 的规划、委派和综合。

在 `execution_mode: runtime` 下：

- Team 不再由 eval tool fixture 代替 specialist。
- 请求使用真实 coordinator Agent。
- coordinator 使用生产内置 `spawn_subagent`。
- specialist 是 benchmark tenant 中真实创建的 Agent。
- 评测覆盖 Gateway routing、MessageBus、TaskQueue、correlation、tenant isolation、CallPath 和取消传播。

因此可以这样回答：

> 模拟模式提高实验可重复性和归因能力，真实 Runtime 模式提高系统结论的工程真实性；两者共享 Suite/Report 结构，但 specialist 的执行边界不同。

### 16.7 Report 聚合字段

顶层 `Report` 记录：

```text
version
suite / description / source
source_sha256（如果启用内容 hash）
started_at / finished_at / duration_ms
metrics
cases[]
```

每个 CaseResult 记录：

```text
case id / description / tags
attempts[]
pass_at_1
pass_at_k
consistent
```

每个 AttemptResult 记录：

```text
attempt
passed
output
error
latency_ms
model
usage
trace
graders
turns
state
```

`Metrics` 聚合通用结果：

```text
TotalCases
TotalRuns / PassedRuns / FailedRuns
RunPassRate
PassAt1 / PassAtK / ConsistencyRate
LatencyP50MS / LatencyP95MS
TotalPromptTokens / TotalCompletionTokens / TotalTokens
TokensPerSuccess
ToolTraceAccuracy
InvalidToolCallRate
```

τ-bench 和 SWE 还会扩展：

```text
StateAccuracy
CommunicationAccuracy
PolicyComplianceRate
EndToEndTaskSuccess
AverageTurns
SWE submitted/completed/resolved instances
SWE resolution rate
```

Multi-Agent 还会扩展：

```text
Milestone KPI
Delegation precision / recall / F1
Contribution utilization
Coordination score
Fault observation / attribution
Graceful degradation
Unsupported claim incidence
Team / Solo / Oracle mode success and cost
```

聚合原则是先保存 attempt-level 原始事实，再从 CaseResult 计算 suite metrics；不要只保存一个最终百分比。这样可以在发现 denominator、错误分类或 grader 规则问题后重新分析。

### 16.8 用一条 Case 走完整执行路径

以 `27b6d4d:evals/multiagent-runtime-tenant.yaml:19-60` 的 `checkout-incident` 为例：

**输入配置：**

```text
execution_mode: runtime
max_delegations: 3
```

任务要求 coordinator：

- 判断 build 842 是否导致 checkout 故障。
- 排除数据库问题。
- 给出 rollback action 和恢复时间。
- 引用每个 evidence ID。

三个 specialist 提供私有 evidence：

```text
bench-observer:
  OBS-101: build 842 后 checkout error 上升，数据库延迟正常。

bench-investigator:
  INV-111: coupon validation 的 nil pointer，来自 N-42 normalization change。

bench-operator:
  OPS-121: rollback build 842 到 build 841，预计四分钟恢复。
```

**运行过程：**

```text
1. CLI 读取 YAML。
2. MultiAgentRunner 为该 case 创建 sessionBase。
3. Runtime mode 选择真实 coordinator Agent。
4. Coordinator 调用 spawn_subagent。
5. Gateway 按 agent ID 路由到真实 benchmark specialist。
6. MessageBus/TaskQueue 保存 correlation、ParentChatKey 和 CallPath。
7. 每个 specialist 返回 response，并形成 tool trace。
8. Coordinator 综合结果并返回最终答案。
9. Runner 检查 trace 中的实际委派目标和任务内容。
10. Grader 检查 root-cause、ruled-out-cause、remediation milestones。
11. 检查答案是否包含 OBS-101、INV-111、OPS-121。
12. 计算 delegation precision/recall、contribution utilization 和 latency。
13. 将 AttemptResult 放入 CaseResult。
14. 所有 case 完成后计算 Report.Metrics。
15. 以 text 或 JSON 输出，并可用 fail-under 作为 CI 门禁。
```

**什么情况算失败：**

- 没有调用预期 specialist：delegation recall 下降。
- 调用了错误 specialist：delegation precision 下降。
- 找到了根因但没有使用证据 ID：contribution utilization 或 grounding 失败。
- 把数据库说成根因：ruled-out-cause 失败。
- 没有提供 rollback 和恢复时间：remediation milestone 失败。
- 工具调用成功但最终答案不归因：fault attribution/grounding 失败。
- HTTP timeout 或 Gateway error：Attempt 的 `Error` 有值，不进入有效模型输出判分。

### 16.9 面试时如何用代码链路回答

当面试官问“你这个评测怎么跑起来”时，可以按下面顺序回答：

> 我从 `fastclaw eval run <suite.yaml>` 开始。CLI 解析 Gateway URL、API key、Agent、repetitions、timeout、输出格式和 fail-under，然后严格加载并校验 YAML，构造一个 HTTPExecutor 和 Runner。Runner 对每个 case 的每次 repetition 生成独立 SessionKey 和 context timeout，再把 prompt、tools、model 和 agent ID 传给 Executor。HTTPExecutor 请求 Gateway 的 OpenAI-compatible endpoint，并打开 `fastclaw.eval/include_trace/include_usage_breakdown`，从响应提取 output、tool trace、state 和 usage。正常响应进入 Grader；执行错误则保留在 AttemptResult.Error。Grader 逐项输出 `GraderResult`，全部通过才算 Attempt passed。最后先聚合 CaseResult，再聚合 suite-level Report.Metrics，并可用 JSON 保存或用 `fail-under` 让 CI 失败。多 Agent benchmark 在这个骨架上额外插入 delegation、evidence、fault 和 baseline-specific grader。

这个回答的重点是把“评测”说成一条可执行的数据管道，而不是只说“调用模型然后打分”。
