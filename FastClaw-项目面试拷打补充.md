# FastClaw 项目面试拷打补充

> 适用方向：AI 测试开发、Agent Eval、Go 后端、平台质量工程  
> 参考资料：`/Users/wangzheyu/FastClaw-多Agent项目面试手册.md`、仓库内 `PROJECT-HANDOFF.md`  
> 当前代码范围：`m0yuw-project` 及 `codex/eval-runtime-harness`

## 0. 先修正旧手册中的过时口径

旧手册主要基于 `453ac8b`、`41a1f13`、`2cd93e0`，后续实现已经改变了部分结论。面试前必须使用以下新口径：

| 旧口径 | 当前准确口径 |
|---|---|
| Sub-agent 直接调用目标 `Agent.HandleMessage`，绕过 TaskQueue | Sub-agent 通过内部 MessageBus RPC 进入 Gateway 校验，再由 TaskQueue 调度 |
| 只能防止 self-spawn，无法防止 A→B→A | CallPath 和 MessageBus wait graph 同时检查递归调用与等待环 |
| 浏览器刷新不取消任务，Stop 只是停止观看 | 真流式改造后重新使用请求 context；浏览器断连和 Stop 会取消 Provider 请求与工具执行 |
| Web 只流式展示工具进度，正文最终一次性返回 | Provider、Agent、SSE、前端 reducer 已支持 token 级真流式输出 |
| 前端 lint 仍有 19 errors / 9 warnings | React effect 和异步竞态清理后 lint 为 0 errors / 0 warnings，生产构建通过 |
| 缺少针对核心链路的自动化测试 | 已补 TaskQueue、MessageBus、Provider streaming、Agent loop、Gateway、API/Auth/Setup/Store/Eval 等测试 |
| 仅能讲金融和赛事两个业务应用 | 已具备自建 Eval、BFCL/τ-bench/SWE-bench/MultiAgentBench-style 子集及真实 Runtime Harness |

面试中可以把项目演进分成四个阶段：

1. 补齐多 Agent Runtime 的真实委派链路。
2. 治理长任务、Session、流式协议和前端异步竞态。
3. 建立集成测试与 CI，保证代码在干净环境中可复现。
4. 建立 Eval Harness，用成功率、协作、Token、费用和延迟量化系统改进。

---

## 1. 专业面试官会重点判断什么

面试官通常不会满足于“用了 Multi-Agent、SSE、DeepSeek”，而会判断以下能力：

### 1.1 是否真正理解调用链

需要能够不看代码讲清楚：

```text
Coordinator ToolCall
→ spawn_subagent Tool
→ MessageBus.CallInternal
→ Gateway.processInternal
→ tenant / source / target / call-path 校验
→ TaskQueue.SubmitInternal
→ target Agent ReAct Loop
→ correlated InternalReply
→ parent ToolResult
→ Coordinator 继续推理
```

### 1.2 是否理解并发与失败语义

必须能解释：

- 哪些任务串行，哪些任务可能并发。
- 全局并发、单 Chat FIFO、内部任务容量分别解决什么问题。
- 父任务等待子任务时为什么不会占满全局 semaphore 后死锁。
- Context value、取消信号、timeout 如何跨 MessageBus 和 TaskQueue 传播。
- exactly-once、at-most-once、幂等在当前系统里分别做到什么程度。

### 1.3 是否理解评测结论的边界

必须主动说明：

- 8/8 是固定 evidence suite 的 Runtime Harness 回归结果，不是 DeepSeek 官方 Benchmark 分数。
- 结果同时受到模型、Prompt、工具策略、Runtime、Grader 和测试数据设计影响。
- 从 0/8 到 8/8 不能单独证明模型能力提高，只能说明该固定任务集上的系统完成质量提高。
- 如果只优化到当前 8 个案例，存在针对测试集过拟合的风险。

### 1.4 是否具备测试开发思维

需要从“功能可用”继续追问：

- 如何证明真的发生了委派，而不是模型自己完成。
- 如何注入断连、超时、重复消息、跨租户访问等故障。
- 为什么测试选择 fake Provider，但仍能覆盖真实 Gateway 边界。
- Coverage 提升说明了什么，又不能说明什么。
- 如何将真实线上式故障固化为稳定回归用例。

---

## 2. 必须复习的知识点

### 2.1 Go 并发与 Context

需要掌握：

- goroutine、channel、buffered channel、select。
- counting semaphore 的实现与释放时机。
- `sync.Mutex`、`sync.Once`、`atomic` 的适用场景。
- `context.WithCancel`、`WithTimeout`、`WithoutCancel`、`AfterFunc`。
- 父子 Context 的取消传播、value 继承和 deadline 语义。
- channel 关闭方原则、重复关闭 panic、goroutine 泄漏。
- race detector 能发现什么，不能发现什么。

结合项目理解：

- `Task.completeOnce` 防止同一 Task 被正常执行、排队取消和队列停止等多个路径重复完成。
- `internalSlots` 是容量 256 的内部任务 admission control，不是执行并发 semaphore。
- `sem` 控制根任务全局并发；内部任务继承 root execution ID 后不重复占用 root slot，避免父任务持有 slot 等待子任务造成嵌套死锁。
- 单 Chat 通过独立 `chatQueue` FIFO 串行执行，但不同 Chat 可以并发。

### 2.2 消息总线、队列和 RPC

需要掌握：

- MessageBus 与 TaskQueue 的职责差异。
- correlation ID 如何把请求和响应配对。
- 背压、队列容量、超时、late reply。
- FIFO、公平性、head-of-line blocking。
- 同步 RPC 包装在异步消息系统上的优缺点。
- 分布式场景下如何替换为 Redis Streams、NATS、Kafka 或专用任务系统。

结合项目理解：

- MessageBus 负责可信内部请求传输、请求响应关联和 wait graph。
- Gateway 是安全与租户边界，不能让 Tool 直接信任模型传入的 Agent ID。
- TaskQueue 负责单 Chat 串行、全局并发、timeout、状态和任务快照。
- 当前都是进程内语义，服务重启会丢失 pending task，不是持久化消息队列。

### 2.3 ReAct 与工具调用协议

需要掌握：

- ReAct 的 Thought/Action/Observation 循环。
- Provider 返回 ToolCall 后为什么必须追加对应 ToolResult。
- 一轮多个 ToolCall 的执行顺序和并发可能性。
- `maxToolIterations` 为什么既是成本限制也是安全边界。
- Structured Output、JSON Schema 与纯 Prompt 契约的差异。
- Tool 幂等、重试和副作用控制。

结合项目理解：

- 每个 ReAct round 只应发起一次上游模型请求。
- ToolCall arguments 在 SSE 中可能被拆成多个片段，需要 accumulator 合并。
- `RawAssistant`、thinking/signature 和完整 ToolCall 必须保留，才能在下一轮正确 replay。
- Session normalizer 是恢复非法历史的兼容层，不等价于事务化 Turn。

### 2.4 SSE 与前端流式状态

需要掌握：

- SSE 与 WebSocket 的差异。
- HTTP chunk 不等于 SSE frame，解析必须以空行分帧。
- 同一网络 chunk 可能包含多帧，一帧也可能跨多个 chunk。
- `data:` 多行、CRLF、UTF-8 decoder tail。
- 增量 delta、最终 snapshot、序号和幂等 reducer。
- AbortController、stale response、generation token。

结合项目理解：

- `content_delta` 用于低延迟增量展示。
- legacy `content` 快照用于兼容旧客户端并纠正可能的 delta 丢失。
- `turnId/messageId/round/seq` 用于事件关联和顺序校验。
- 前端使用 request identity/generation，防止旧请求的 `finally`、history 或上传结果污染新 Session。

### 2.5 Session 一致性

需要掌握：

- append-only event log 与 materialized view。
- 乐观锁、revision、CAS、事务。
- 同 Session 串行化与跨实例锁。
- late result、duplicate result、orphan result。
- 幂等键和消息去重。

结合项目理解：

- normalizer 会把真实结果移动到对应 assistant ToolCall 后面，缺失时补 synthetic stopped，并删除重复和 orphan。
- 这是 heuristic repair，可能丢失真实时间顺序，也可能在 synthetic 和 late real result 之间做出不理想选择。
- 更完整方案是 Turn 状态表 + append-only event + revision/CAS，而不是反复覆盖整段 history。

### 2.6 多租户与安全

需要掌握：

- authentication 与 authorization 的区别。
- tenant boundary、Agent ACL、API key scope。
- confused deputy、IDOR、跨租户枚举。
- Prompt Injection 与传统权限控制的区别。
- sandbox、tool allowlist、secret isolation、审批。

结合项目理解：

- Gateway 同时检查 source 和 target 都属于 `OwnerUserID`。
- Agent-scoped API key 只能访问 allowlist 中的 Agent。
- Prompt Scanner 只能降低部分直接注入风险，不能替代权限和 sandbox。
- 真实安全边界是“即使模型被诱导，也没有权限执行越权操作”。

### 2.7 Eval 与统计基础

需要掌握：

- deterministic Eval、model-based Eval、human Eval。
- `pass@1`、`pass@k`、consistency。
- precision、recall、F1。
- P50/P95 延迟。
- baseline/candidate 与 A/B 对比。
- 方差、置信区间、重复次数和样本量。
- 数据泄漏、过拟合、Grader false positive/negative。

结合项目理解：

- Milestone KPI 衡量任务关键事实是否完成。
- Delegation precision 衡量实际委派中有多少是期望目标。
- Delegation recall 衡量期望专家中有多少真正被调用。
- Contribution utilization 衡量专家提供的关键 evidence 有多少进入最终回答。
- Coordination score 是系统定义的组合指标，必须能说明计算规则，不能把它当行业统一标准。
- Pricing coverage 防止未知模型被默认为零成本或错误价格。

### 2.8 集成测试与 CI

需要掌握：

- Unit、component、integration、E2E 的边界。
- fake、mock、stub、spy 的区别。
- `httptest.Server`、临时 SQLite、fixture。
- hermetic test、可重复性、测试隔离。
- GitHub Actions workflow、job、runner、step、artifact。
- clean clone 与本地缓存/构建产物差异。

结合项目理解：

- Eval 集成测试使用 deterministic fake Provider，不依赖真实 Key，验证 Harness 本身。
- 真实模型评测验证系统与模型共同表现，但有费用、波动和限流，不适合作为每个 PR 的强制门禁。
- CI 中暴露的 `go:embed all:web` 问题说明本地通过不等于仓库在干净环境可构建。

---

## 3. Runtime 与架构拷打

### Q1：这个项目到底有多少是你开发的，多少是原项目能力？

**回答：**

FastClaw 的基础 Gateway、Agent、Provider、Session 和工具框架来自开源项目。我没有从零实现整个框架，核心贡献集中在四部分：

1. 补齐 `spawn_subagent` 的运行时装配，使 Coordinator 能真实调用独立 Agent。
2. 将内部委派接入 MessageBus 和 TaskQueue，补充租户校验、调用环检测、背压、取消和状态观测。
3. 重构 Provider/Agent/Web 的真流式链路并处理 Session、事件和前端竞态。
4. 建立集成测试、CI 和 Eval Harness，量化 Runtime 改进。

金融和赛事应用是业务验证场景，固定 8-case tenant 是可重复评测场景。这样既不夸大“从零开发”，也能说明改动已经深入 Runtime 核心链路。

### Q2：为什么 `spawn_subagent` 有代码却不能用？你怎么发现的？

**理解：**

这是 composition root 漏装配，而不是工具函数本身错误。

**回答：**

业务现象是 Coordinator 的 Prompt 明确要求委派，但日志中没有 `spawn_subagent` ToolCall，只看到 Coordinator 自己调用普通工具。继续检查模型收到的 Tool Definitions，发现根本没有这个工具。静态搜索后确认注册函数、Spawner 接口和实现都存在，但 `SetSubAgentSpawner` 没有调用者。

修复是在 UserSpace 组件构造完成后注入 Spawner，使 Agent Registry 注册工具。验证不能只看最终回答，而要同时检查父 ToolCall、独立 child Session 和父 ToolResult。

### Q3：为什么不让 `spawn_subagent` 直接调用目标 Agent？

**回答：**

直接调用链短，但会绕过统一的租户校验、队列串行、背压、取消和任务观测。当前实现把 Tool 请求发送到内部 MessageBus，由 Gateway 重新校验 source、target、owner 和 call path，再提交 TaskQueue。

这增加了一层复杂度和进程内消息开销，但把“模型请求另一个 Agent”变成受 Runtime 治理的内部任务，而不是任意对象调用。

### Q4：MessageBus 和 TaskQueue 为什么不能合成一个组件？

**回答：**

两者关注点不同：

- MessageBus 负责内部请求传输、correlation、pending waiter 和等待环检测。
- Gateway 负责身份和租户边界。
- TaskQueue 负责执行调度、单 Chat FIFO、全局并发、timeout、状态和快照。

拆开后，路由协议和执行策略可以独立演进。代价是调用链更长，需要清楚定义错误和取消如何跨层传播。

### Q5：父 Agent 等待子 Agent 时，为什么不会把全局并发槽位耗尽后死锁？

**回答：**

根任务第一次进入 TaskQueue 时获取全局 semaphore，并把 root execution ID 写入 Context。内部子任务继承这个 execution ID，因此不再重复获取 root semaphore。

如果父任务持有一个 slot，同时每个 child 又必须获取新 slot，在并发上限较小时就可能出现所有父任务都占着 slot 等 child、child 永远拿不到 slot 的嵌套死锁。当前设计通过“同一执行树共享 root slot”避免这一点。

需要承认：内部任务仍受 `internalSlots=256` 和单目标 ChatQueue 约束，不是无限制执行。

### Q6：怎么防止 A→B→A 或更长的 Agent 调用环？

**回答：**

有两层：

1. 请求携带不可变 CallPath，目标已经出现在路径中就拒绝。
2. MessageBus 维护 owner+agent 维度的 wait graph；如果新增 source→target 等待边会让 target 已经可达 source，则拒绝，防止并发等待形成环。

CallPath 防显式递归链，wait graph 防运行时等待依赖环。当前是进程内检测，多实例场景需要分布式 trace 和调度层统一判断。

### Q7：为什么同一个 Specialist 的内部 ChatKey 是固定的？会有什么影响？

**回答：**

内部任务使用 tenant+target Agent 构造队列键，使同一租户的同一 Specialist 串行执行，降低 Agent 实例或工具 Registry 中可变状态被并发污染的风险。

代价是 head-of-line blocking：一个慢任务会阻塞该 Specialist 后续任务，也限制吞吐。生产演进可以按 target+session 分片，并把 Agent/Registry 改造成请求级无状态或安全 clone，再提高并发。

### Q8：TaskQueue 的三种容量限制分别是什么？

**回答：**

- 每个 ChatQueue channel 容量 100：限制单队列瞬时积压。
- `internalSlots` 容量 256：限制内部任务排队加执行总数，满时 fail-fast。
- root semaphore：限制独立根执行树的全局并发。

三者分别解决局部积压、内部 fan-out 爆炸和系统总体资源上限。面试时要避免把“队列容量”和“执行并发”混为一谈。

### Q9：当前 TaskQueue 能保证 exactly-once 吗？

**回答：**

不能保证分布式 exactly-once。`sync.Once` 只保证单进程内一个 Task 的 completion callback 最多执行一次。服务在任务完成但响应前崩溃、客户端重试、进程重启等场景仍可能丢任务或重复副作用。

对于有副作用的工具，应使用业务幂等键、状态机和持久化任务表。当前更准确的说法是“进程内 completion at-most-once”。

### Q10：为什么任务快照要做 defensive copy？

**回答：**

`RecentTasks` 是观测接口。如果直接返回内部 Task 指针及其中的 slice，API 序列化或调用方修改数据时可能与执行线程产生数据竞争，甚至篡改 live state。

当前会复制 Task 和消息中的 slice，再返回 snapshot。这个问题体现的是“可观测性也不能绕过并发封装”。

---

## 4. 流式、取消与 Session 拷打

### Q11：什么叫“真流式”，原实现为什么是假流式？

**回答：**

原实现虽然 HTTP 返回 SSE，但模型正文通过非流式 `Chat` 完整生成后才一次发送，只有工具进度是流式的。真流式要求 Provider 收到的 token chunk 立即经过 Agent Event、HTTP SSE 和前端 reducer 更新同一个回答气泡。

当前链路统一到 `ChatStream`，每个 ReAct round 只发一次模型请求，流结束后从 accumulator 读取完整 Response，判断是 ToolCall 还是最终回答。

### Q12：为什么不能先 `Chat` 判断结果，再 `ChatStream` 展示？

**回答：**

这样会对同一轮发起两次模型请求：

- 成本和延迟翻倍。
- 两次采样结果可能不一致。
- ToolCall 可能第一次有、第二次没有。
- Session 中保存的内容与用户看到的内容可能不同。

正确方式是一次 `ChatStream` 同时承担展示和终态聚合。

### Q13：流式 ToolCall 为什么比文本流复杂？

**回答：**

OpenAI-compatible SSE 可能把 function name 和 JSON arguments 拆成多个 delta；Anthropic 还可能包含 thinking、signature 和不同事件类型。Runtime 必须按 ToolCall index/ID 聚合片段，直到流结束才能得到完整参数。

如果只拼文本 content，会导致 JSON 截断、ToolCall 丢失或下一轮 replay 不符合 Provider 协议。

### Q14：为什么同时发送 `content_delta` 和最终 `content` 快照？

**回答：**

Delta 提供低延迟，但客户端可能因解析、重连或旧版本逻辑丢帧。最终 snapshot 可以校正完整内容，也兼容只认识旧 `content` 事件的客户端。

代价是 reducer 必须根据事件类型原位更新，不能把 snapshot 再追加一次，否则会重复正文。

### Q15：为什么 child Agent 的事件不能直接进入父 SSE？

**回答：**

父 stream 代表顶层 Turn。如果 child 继承同一 event channel，它的 content、tool 和 done 会污染父协议，尤其 child done 会让客户端误判整个任务完成。

当前把 child 视为父级的一个黑盒 Tool：child 内部事件隔离，最终结果只通过对应 `spawn_subagent` ToolResult 返回。若未来要展示 child 进度，应增加 invocationID、parentID、agentID 和独立事件 namespace，而不是复用无标识 channel。

### Q16：当前浏览器刷新和 Stop 的准确语义是什么？

**回答：**

在真流式改造后，Web SSE 重新继承请求 Context。浏览器断开或点击 Stop 会取消 Provider HTTP 请求和工具执行，避免后台继续产生费用。被取消的残缺 assistant 不会保存成完整回答，后续 Turn 可以继续。

这与早期版本“刷新只停止观看、后台继续跑”不同。面试时要说明这是一次产品语义调整：优先选择费用可控和显式取消，而不是断线后台执行。

如果需要断线继续，应把任务提升为持久化 Job，并支持 task ID、状态查询、SSE replay 和显式 cancel，而不是简单 `WithoutCancel`。

### Q17：前端为什么需要 AbortController 加 generation，而不是只用一个？

**回答：**

AbortController 能取消支持 signal 的网络请求，但不能保证所有异步步骤都会及时停止，也不能阻止已经完成的旧 Promise 在 `finally` 中修改新状态。

Generation/request identity 用于 latest-wins：每个 await 后检查当前请求是否仍是最新。两者结合才能防止旧 history、上传、stream 或 finally 覆盖新 Session 的 optimistic message 和 loading 状态。

### Q18：Stop 后 Session 为什么容易损坏？

**回答：**

ToolCall 可能已经持久化，但 ToolResult 尚未写入；此时如果用户继续发送消息，历史可能变成：

```text
assistant(tool_calls)
user(new message)
tool(late result)
```

Provider 要求 ToolResult 紧跟对应 ToolCall，因此下一轮会返回 400。取消不仅是网络问题，还会破坏对话协议状态。

### Q19：Session normalizer 的价值和风险是什么？

**回答：**

价值是兼容并修复历史坏数据：移动可配对结果、补缺失结果、删除重复和 orphan，使历史重新满足 Provider 协议。

风险是它属于 heuristic projection：

- 可能改变真实发生顺序。
- synthetic result 和晚到真实 result 的优先级可能不理想。
- 覆盖式持久化不适合多实例并发。

生产方案应保留 append-only 原始事件，再生成规范化 LLM view，并使用 Turn revision/CAS。

### Q20：流式链路如何测试，而不依赖真实模型？

**回答：**

使用 deterministic fake StreamReader：

- 控制 content 和 ToolCall argument 的分片方式。
- 注入提前 EOF、scanner error、Context cancel。
- 断言 `Chat` 与耗尽 `ChatStream` 后的完整结果等价。
- 断言每个 ReAct round 只有一次 Provider 调用。
- 断言 ToolCall/ToolResult 配对、最终 Session 只保存完整 assistant。

真实 DeepSeek smoke 用于验证兼容性和实际取消，不替代确定性自动化测试。

---

## 5. Eval Harness 拷打

### Q21：你为什么要自建 Eval，而不直接跑官方 Benchmark？

**回答：**

官方 Benchmark 主要衡量模型或通用 Agent 能力，但我的目标是评估 FastClaw Runtime 是否正确传递工具、状态、委派、Session、成本和调用链。

因此分两层：

- 引入 BFCL、τ-bench、SWE-bench、MultiAgentBench 的任务形式和指标思想，验证通用能力。
- 自建固定 Runtime tenant，使用真实 Gateway、MessageBus、TaskQueue 和 Agent Registry，定位系统层问题。

官方子集提供外部参照，自建 Eval 提供可诊断性，两者不能互相替代。

### Q22：8 个固定案例分别在测什么？

**回答：**

案例覆盖 incident、release/security、access/audit、data pipeline、payment support、privacy、capacity 和 dependency 等场景。每个案例要求 Coordinator 从 3 到 4 个 Specialist 获取互补 evidence，并完成明确 milestones。

它们不是金融或世界杯预测题，因为后者缺少稳定即时真值；固定 evidence task 更适合 Runtime 回归和根因定位。

### Q23：0/8 到 8/8 说明了什么，不说明什么？

**回答：**

说明同一模型组合、同一固定任务集下，修复身份文件、工具策略、重复委派、输出结构、Grader normalization 和 pricing 后，端到端 Runtime 完成质量显著提高。

不说明：

- DeepSeek 通用能力提高。
- 对未知任务也能 100%。
- 系统已经达到生产可靠性。
- 所有提升都来自某一个单独改动。

准确表述是“固定 8-case Runtime Harness 严格通过率从 0/8 提升到 8/8”。

### Q24：为什么第一轮失败不一定是模型能力差？

**回答：**

失败可来自多个层次：

- Runtime 没加载 identity/evidence。
- Tool policy 没生效，Specialist 调用了不允许的文件工具。
- Coordinator 重复委派，浪费预算。
- 输出格式和 Grader 规范不一致。
- Pricing 缺失导致成本报告错误。

Eval 的价值不只是打分，而是把失败归因到模型、Prompt、Tool、Runtime、Grader 或数据。

### Q25：如何证明团队比 Solo 更好？

**回答：**

要在同一案例、同一 Grader、尽量相同模型和预算下分别运行 team 与 solo，比较成功率、milestone、延迟、Token 和 cost/success。

只看 team 通过率不够，因为更高成本本身可能带来收益。需要同时报告 collaboration gain 和成本变化，并控制 Prompt 暴露的信息量，避免 team 获得 solo 没有的额外答案泄漏。

当前固定 tenant 主要用于 Harness 回归，若要严谨证明“多 Agent 优于单 Agent”，还需要扩大 unseen case、重复运行和统计置信区间。

### Q26：Delegation precision、recall 分别怎么解释？

**回答：**

假设案例期望调用 A、B、C：

- 实际调用 A、B、C、D、A。
- Recall 关注 A/B/C 是否都被覆盖，结果可达到 100%。
- Precision 关注实际委派中有多少属于期望目标，重复 A 和无关 D 会拉低。

因此早期结果可能 recall 100%，precision 只有 42%。这说明 Coordinator 知道该找谁，但存在重复或无关委派，属于编排效率问题。

### Q27：Contribution utilization 与最终正确率有什么区别？

**回答：**

Specialist 返回了 evidence，不代表 Coordinator 真正使用。Contribution utilization 检查关键证据是否进入最终回答，衡量信息融合效率。

最终正确率只看结果是否过 Grader，可能掩盖“专家都调用了但结果被忽略”或“Coordinator 猜对但没有证据链”的问题。

### Q28：Token、费用和延迟如何按 Coordinator/Sub-agent 拆分？

**回答：**

每次模型调用记录 Agent ID、role、model、prompt/completion/cache token、estimated cost、latency 和 call path。请求级 telemetry collector 通过 Context value 进入根任务，并沿 MessageBus/TaskQueue 传到内部子任务。

聚合时按 role 和调用路径拆分 Coordinator 与 Sub-agent，再计算 team cost、solo cost 和 cost per successful run。

关键点是使用请求 Context，而不是全局变量，否则并发 Eval 会串数据。

### Q29：费用估算为什么需要 Pricing coverage？

**回答：**

模型名称没有价格配置时，如果直接按零成本计算，会得到虚假的低成本结果；如果套默认价格也可能严重偏差。

因此每次调用标记是否成功定价，报告 pricing coverage。只有 coverage 100% 时总费用才适合直接比较；否则必须标注为部分估算。

### Q30：为什么 Token 能下降 94.2%？

**回答：**

主要不是模型突然变聪明，而是系统减少了无效工作：

- Specialist 不再调用无关工具并耗尽迭代。
- Coordinator 不再重复委派同一目标。
- 输出改为结构化、限制无关内容。
- 工具策略真正生效。

这说明 Runtime policy 和 orchestration 对成本影响很大。回答时不能把全部下降归因于模型版本。

### Q31：Grader normalization 会不会为了通过测试而放宽标准？

**回答：**

有这个风险，所以 normalization 只能处理语义等价的表示差异，例如：

- `10%` 与 `10 percent`。
- `4` 与 `four`。
- Markdown 格式和大小写差异。

不能把缺失关键 evidence、错误 ID 或相反结论归一成正确。修改 Grader 后应该回放 positive/negative fixture，验证降低 false negative 时没有显著增加 false positive。

### Q32：怎么防止对固定 8 个案例过拟合？

**回答：**

可以采用：

- 保留完全未参与调试的 hidden cases。
- 为同一能力生成参数化变体和反例。
- case ID 不携带答案语义。
- 将开发集、回归集和验收集分离。
- 对新模型和 Prompt 做重复运行。
- 使用 metamorphic testing，例如调整无关描述后结果应保持一致。
- 定期引入真实故障样本，但进行脱敏和冻结。

当前 8-case 更适合作为回归基线，不足以证明泛化能力。

### Q33：为什么真实模型 Eval 不放到每个 PR 强制执行？

**回答：**

真实模型 Eval 有费用、限流、网络波动、模型版本漂移和非确定性。如果作为每个 PR 的 blocking check，容易产生 flaky CI 和不可控成本。

更合理的分层：

- PR：fake Provider + deterministic Eval + integration tests。
- 手动 workflow：真实 Runtime Eval，可选择 model、case 和预算。
- Nightly：固定模型和重复次数，保存 JSON artifact，监控趋势。
- Release gate：只对关键模型组合运行有限 smoke。

### Q34：你如何判断一次 Eval 失败应该改 Runtime 还是改 Prompt？

**回答：**

先按层次定位：

1. 输入 fixture 和 identity 是否正确加载。
2. 模型是否看到正确 Tool Definitions 和 policy。
3. ToolCall 是否被 Runtime 正确执行、参数和结果是否完整。
4. Specialist 是否返回预期 evidence。
5. Coordinator 是否正确融合。
6. Grader 是否准确判定。

如果模型根本没有拿到工具或 evidence，优先修 Runtime；如果链路正确但选择和表达不稳定，再考虑 Prompt 或模型。

---

## 6. 测试、CI 与质量拷打

### Q35：为什么这些测试叫集成测试，而不是端到端测试？

**回答：**

它们使用真实 API route、认证、SQLite migration、Agent、MessageBus、TaskQueue 和 Eval Runner，但 Provider 使用本地 deterministic fake，且不经过真实浏览器和公网模型。

因此覆盖多个生产组件边界，属于进程内 integration test；真正 E2E 应从浏览器或外部客户端进入，并包含真实 Gateway 进程、Provider 和完整部署环境。

### Q36：Fake Provider 会不会让测试失去意义？

**回答：**

Fake Provider 不验证模型质量，但能稳定验证 Harness 和 Runtime：

- 请求是否携带正确 Agent/API key/session。
- Tool schema 和 ToolCall 是否正确执行。
- 状态和 trace 是否返回。
- 重复运行、聚合、错误传播是否正确。
- Gateway 内部委派和 ACL 是否生效。

真实模型测试负责兼容性和能力效果，两层测试目标不同。

### Q37：Coverage 从 7.4% 到 22.9% 有多大意义？

**回答：**

它说明更多代码路径进入自动化回归，但不能直接证明缺陷减少或测试质量高。FastClaw 有很多外部 adapter 包为 0%，所以总覆盖率会被稀释。

更有价值的是同时看关键包覆盖率和场景覆盖，例如 `internal/api`、`internal/eval`、`internal/evaltenant`，并说明测试发现了 API-key ACL、跨租户 task visibility 和 clean clone embed 等真实问题。

### Q38：为什么要跑 `go test -race`，普通测试不够吗？

**回答：**

普通测试只验证某次调度下结果正确，race detector 会检测并发 goroutine 对共享内存的未同步访问。Agent streaming、TaskQueue 状态、telemetry collector 和前端式取消都涉及并发，数据竞争可能低概率出现但造成状态污染。

Race detector 不能证明没有死锁、goroutine 泄漏或业务竞态，所以还需要 timeout、并发压力和状态断言。

### Q39：CI 为什么在本地通过、GitHub Actions 却失败？

**回答：**

`internal/setup/embed.go` 使用 `//go:embed all:web`，开发机已有被 Git 忽略的前端构建目录，所以编译成功；GitHub Runner 是 clean clone，该目录不存在，编译阶段失败。

修复是保留最小 `.gitkeep` 让 embed pattern 在干净仓库中有匹配，同时继续忽略真实构建产物。

这个问题说明 CI 的核心价值之一是验证仓库可复现性，而不仅是重复执行本地测试。

### Q40：为什么 CI 要拆 backend/frontend 两个 Job？

**回答：**

两部分依赖和失败原因不同，拆分后可以并行执行、独立缓存并快速定位问题。Backend 运行 Go Test、race、vet；Frontend 安装锁定依赖、lint 和 production build。

代价是两个 Job 都要 checkout，并且跨 Job 不能直接共享未上传的构建产物。若后续做完整二进制打包，可增加 artifact 或第三个 packaging job。

### Q41：测试如何验证跨租户隔离？

**回答：**

至少覆盖三条：

- Coordinator 不能 spawn 另一个 tenant 的 Agent。
- Agent-scoped API key 不能访问 allowlist 外的 Agent。
- Task observability 按 tenant 和 API key scope 过滤。

测试不能只断言 HTTP 403，还应构造两个真实 tenant、不同 Agent 和数据，确认越权请求没有返回目标存在性、任务内容或其他敏感字段。

### Q42：如何测试取消传播？

**回答：**

使用可控阻塞的 fake Provider 或 Tool：

1. 发起 Coordinator→Sub-agent 请求。
2. 等待 child 已进入 running。
3. cancel caller Context。
4. 断言 MessageBus waiter 返回 canceled。
5. 断言 TaskQueue 状态变为 cancelled。
6. 断言 Provider/Tool 收到 Context cancel。
7. 断言 completion 只执行一次，没有 goroutine 泄漏。

只断言最外层返回 `context canceled` 不足以证明整条链路传播正确。

---

## 7. 安全与生产化拷打

### Q43：Prompt Injection Scanner 是不是安全边界？

**回答：**

不是。Scanner 只能拦截部分已知直接攻击和不可见字符，容易误报也容易被语义改写绕过。安全边界应是：

- system/user role 隔离。
- tenant 与 Agent ACL。
- tool allowlist 和最小权限。
- sandbox、文件和网络限制。
- secret isolation。
- 高风险操作审批。
- 脱敏审计。

Scanner 属于纵深防御的一层。

### Q44：为什么 Gateway 要重新查 source 和 target 的 owner，Tool 中不是已经有 userID 吗？

**回答：**

Tool 参数和上游 Context 都可能被错误构造，不能直接作为授权事实。Gateway 通过 Store 查询 source、target 的真实 owner，并确认都属于请求 tenant，防止 confused deputy 和跨租户 Agent ID 调用。

授权校验应在靠近资源访问的位置再次执行，而不是只依赖入口层。

### Q45：如果攻击者知道其他 Agent ID，会发生什么？

**回答：**

知道 ID 不等于有权限。内部路由会检查目标 Agent owner；外部 API key 也有 Agent allowlist。正确行为是统一返回 unavailable/forbidden，避免通过不同错误泄露目标是否存在。

还应测试 timing 和错误消息是否造成枚举侧信道。

### Q46：SQLite 能否支持生产多实例？

**回答：**

当前适合本地和单节点验证。即使 WAL 能改善读写并发，也不解决多副本共享、跨进程锁、持久化任务和高写吞吐问题。

生产应切 PostgreSQL，并为 Session/Task 增加事务、revision、索引和归档；内部 MessageBus/TaskQueue 需要外部化或明确 sticky routing。

### Q47：当前系统重启会发生什么？

**回答：**

SQLite 中已持久化的 Session 和配置可以恢复，但内存中的 MessageBus pending request、TaskQueue queue、Context 和 stream 都会丢失。正在执行的任务无法自动恢复。

若要求生产级恢复，需要持久化 Job 状态、lease/heartbeat、幂等执行和启动时 reconciliation。

### Q48：如何限制失控 Agent 的成本和影响？

**回答：**

当前已有 timeout、max Tool iterations、internal capacity、目标去重和 tool policy。进一步应增加：

- 每 Turn 和整棵调用树的 Token/费用预算。
- 最大递归深度、最大子任务数和并发数。
- Tool 级 timeout、重试和 circuit breaker。
- 读写/外部副作用工具分级。
- 高风险工具审批与幂等键。
- 超限后基于 partial result fail-soft。

### Q49：真实模型返回格式变化怎么办？

**回答：**

Provider adapter 应把不同厂商流事件规范化成统一 Response，并保留原始字段用于 replay。测试要覆盖未知 event、字段缺失、ToolCall 分片、提前 EOF 和非 2xx。

模型版本升级不能只跑“能回答”，还要对 baseline Eval 比较成功率、Tool trace、Token、延迟和成本。

### Q50：你认为当前最大技术债是什么？

**回答：**

优先级可以这样回答：

1. 固定 8-case 样本量小，需要 hidden/parameterized cases 和统计置信度。
2. TaskQueue/MessageBus 是内存实现，任务不可恢复。
3. Session normalizer 是事后修复，缺少事务化 Turn。
4. Specialist 串行保护吞吐有限，Agent/Registry 仍需进一步无状态化。
5. Prompt Injection 只覆盖直接输入，间接注入和高风险工具授权仍需加强。
6. 真实模型 Eval 尚未形成 nightly artifact 和趋势看板。

主动承认这些边界，反而能证明你理解系统。

---

## 8. 五个高压追问的完整回答模板

### 8.1 “你这个 8/8 是不是调 Prompt 调出来的？”

确实包含 Prompt 和 fixture 约束优化，所以不能把 8/8 表述成模型通用能力。我的评测对象是整个 Runtime Harness。第一轮失败中，有些是 Specialist 身份文件没有正确加载，有些是 tool policy 没生效导致无效工具调用，还有重复委派和 Grader 表示差异。修复这些系统问题后，在同一模型组合、同一固定 8-case 下严格通过率从 0/8 到 8/8，同时 Token 和 P95 明显下降。

为了避免过拟合，我会把这 8 个案例定位为回归集，后续增加不参与调试的 hidden cases、参数化变体和重复运行，而不会声称系统对未知任务达到 100%。

### 8.2 “为什么不用单 Agent？多 Agent 成本更高吧？”

多 Agent 不是天然更好。它适合知识和工具边界清晰、需要独立证据或风险复核的任务。代价是额外模型调用、延迟和编排失败。

所以我的 Harness 同时记录 team/solo success、milestone、Token、费用和 cost/success。只有质量收益能够覆盖额外成本时，多 Agent 才有价值；简单任务应该路由到 solo 或 fast path。

### 8.3 “你怎么证明 Runtime 真的提升了模型能力？”

更准确的说法不是提升模型参数能力，而是提升模型在系统中的可实现能力。证明链包括：

1. 固定模型和任务。
2. 保存 baseline 与 candidate 报告。
3. 检查 Tool Definitions、Tool trace、委派路径和 Specialist evidence。
4. 比较成功率、milestone、协作、Token、费用和延迟。
5. 对失败按模型、Prompt、Runtime、Tool、Grader 分层归因。

如果只看最终答案，无法证明是 Runtime 改进；调用链和成本数据是关键证据。

### 8.4 “你的队列会不会死锁？”

风险主要来自父任务持有全局并发 slot 并同步等待 child。当前内部 child 继承 root execution ID，不重复获取 root semaphore；同时 CallPath 和 MessageBus wait graph 拒绝调用环，降低嵌套等待死锁。

仍可能存在业务层长时间阻塞和同 Specialist 的 head-of-line blocking，所以有 task timeout、internal capacity 和 caller cancellation。若多实例部署，还需要把等待图和任务状态外部化。

### 8.5 “为什么 Coverage 才 22.9%，是不是测试很少？”

总覆盖率受大量外部渠道、Provider 和部署 adapter 的 0% 包影响，单看总数会失真。我更关注本次改动的关键包和风险场景：`internal/api` 52.1%、`internal/eval` 73.8%、`internal/evaltenant` 75.3%，并新增 19 个集成测试函数。

更重要的是测试发现并防止了 API-key ACL、跨租户任务可见性和 clean clone embed 等真实缺陷。覆盖率是辅助指标，不是质量结论。

---

## 9. 面试前复习优先级

### P0：必须能脱口而出

1. 完整 Coordinator→Sub-agent 调用链。
2. MessageBus、Gateway、TaskQueue 三者职责。
3. root execution ID 如何避免嵌套 semaphore 死锁。
4. 真流式为何每个 ReAct round 只能调用一次模型。
5. Stop/断连的当前取消语义。
6. 8/8、Token -94.2%、P95 -70.2% 的准确口径。
7. fake Eval 与真实模型 Eval 的分工。
8. 19 个集成测试覆盖哪些边界。

### P1：面试官继续深挖时回答

1. wait graph 环检测。
2. internalSlots、ChatQueue buffer、root semaphore 的区别。
3. Session normalizer 的一致性风险。
4. ToolCall SSE 分片聚合。
5. telemetry Context 跨子任务传播。
6. Delegation precision/recall、contribution utilization。
7. Grader false positive/negative。
8. Coverage 和 CI 可复现性。

### P2：高级或架构面加分

1. append-only event + materialized LLM view。
2. PostgreSQL revision/CAS 与持久化 Job。
3. NATS/Redis Streams 替代进程内 Bus。
4. hidden case、metamorphic testing、置信区间。
5. distributed tracing 与 cost budget。
6. 高风险 Tool 的 capability security 和审批。

---

## 10. 面试表达边界

建议说：

- “基于开源 FastClaw Fork 深度开发 Runtime 核心链路。”
- “补齐并治理真实多 Agent 委派，而不是只做多角色 Prompt。”
- “固定 8-case Runtime Harness 回归通过率从 0/8 提升到 8/8。”
- “按 Coordinator/Sub-agent 追踪 Token、费用、延迟和调用路径。”
- “用 deterministic integration test 验证 Harness，用真实模型 Eval 验证联合效果。”
- “在当前固定任务集上提升系统完成质量。”

不要说：

- “从零开发整个 FastClaw。”
- “DeepSeek Benchmark 达到 100%。”
- “多 Agent 一定比单 Agent 强。”
- “实现分布式消息队列和 exactly-once。”
- “彻底解决 Prompt Injection。”
- “22.9% Coverage 证明系统没有问题。”
- “金融或世界杯命中率证明 Agent 通用能力。”

---

## 11. 需要立即处理的非面试问题

外部交接手册中存在明文运行凭据和第三方 API Key。即使文件当前只在本机，也不应继续出现在可分享的面试材料、Git 仓库、截图或日志中。

建议：

1. 立即轮换相关密码和 API Key。
2. 将手册中的值替换为环境变量名或脱敏占位符。
3. 检查 Git 历史和远端仓库是否曾提交这些值。
4. 面试演示使用单独的低权限测试账号和限额 Key。

