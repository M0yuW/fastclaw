# FastClaw Python 独立代码库可行性与实施方案

> 结论先行：**可以，而且应该新建独立代码库，而不是在 Go 仓库里开一个长期 Python 分支。** 原 `fastclaw` Go 项目完整保留并继续维护；新建例如 `fastclaw-python` 的仓库，从空目录按 Python 的工程习惯实现。两者不共享源码，只共享版本化的外部协议、兼容 fixtures 与验收标准。Go 项目是参考实现和可回退产品，不是等待被删除的旧代码。

## 1. 评估范围与方法

本评估基于当前仓库代码，而不是只根据 README 推断：

- Go 后端约 4.3 万行，核心集中在 `internal/eval`、`internal/agent`、`internal/setup`、`cmd/fastclaw`、`internal/sandbox`、`internal/gateway`、`internal/api` 与 `internal/store`。
- 前端是独立的 Next.js 静态站点；迁移后端时可以原样保留构建产物与 HTTP 接口。
- 现有边界已经有较清晰的接口：LLM Provider、Store、Workspace Store、Sandbox Executor、Session Store、MCP Client、工具注册表等。这些边界比语言本身更适合作为迁移切面。
- 真正的难点不是 HTTP CRUD，而是流式响应、会话消息的无损回放、租户隔离、并发串行化、沙箱同步、插件/MCP 子进程协议和停机清理。

本文件中的人力数字是用于排序的工程估算，不是承诺日期。进入实施前，应通过第 8 节的试点重新校准。

### 1.1 与现有交接手册的关系

仓库内的 `PROJECT-HANDOFF.md` 明确说明它只描述 FastClaw fork 的源码补丁与维护线，外部总交接手册则描述 FastClaw + FinSkills 的应用运行现状，两者不能混用。本方案遵守这个边界：

- Go 仓库继续按其自己的维护线演进，不为 Python 重实现改造成混合语言 monorepo；
- Python 仓库只通过公开 API、持久化格式和测试 fixtures 对齐 Go 行为；
- `spawn_subagent` 的 MessageBus → TaskQueue → sub-agent → reply 链路、cross-tenant 拒绝、取消传播、exactly-once completion 与 call-path/correlation 可观测性，均视为 Python 版必须达到的行为契约，而不是可以省略的 Go 内部细节；
- 现有 eval、故障注入和 runtime tenant suite 应被当作跨仓库验收资产，而不是把 Go 测试源码复制到 Python 仓库。

当前执行环境只能读取仓库内的交接手册，无法读取 IDE 中 `/Users/wangzheyu/PROJECT-HANDOFF.md` 的正文。因此涉及 FinSkills 的启动方式、外部依赖和运行坑，应在创建新仓库时从外部手册另行提取为 integration requirements，不能在此凭路径猜测。

## 2. 当前系统的结构拆解

### 2.1 启动与控制面

`cmd/fastclaw` 提供 gateway、daemon、eval、provider、plugin、policy、sandbox、skill、admin 等 CLI。Gateway 是运行时组合根，负责：

1. 读取并解析配置；
2. 打开文件或 PostgreSQL Store，以及本地或 S3 Workspace Store；
3. 创建按用户惰性加载的 UserSpace；
4. 装配 Provider、Agent Manager、Message Bus、Task Queue、Sandbox Pool；
5. 启动 API、setup 管理端、channel、cron、webhook 和 plugin；
6. 接收信号并按依赖关系关闭资源。

Python 对应建议：Typer/Click（CLI）+ FastAPI/Starlette（HTTP、SSE、WebSocket）+ lifespan（资源装配与关闭）。不要把所有资源放入模块级单例；以 `Runtime`/`UserSpace` 容器显式持有，才能复现租户作用域和测试替身注入。

### 2.2 Agent 数据面

Agent 是 ReAct 循环的聚合体，包含 Provider、Tool Registry、Session Manager、Memory、Context Builder、MCP Manager、Hooks、Policy、Workspace Store、Sandbox Pool、Skills Learner 与 usage/cost 跟踪。一次请求的关键路径是：

```text
HTTP / Channel / Webhook
  -> 鉴权并解析 user_id + agent_id + session/chat key
  -> TaskQueue（同一 chat 串行，全局并发受限）
  -> UserSpace -> Agent
  -> 加载身份、记忆、技能与会话，构建上下文
  -> Provider.ChatStream
  -> 累积文本/思考/tool-call 增量
  -> policy + hook -> Tool Registry -> 本地/MCP/plugin/sandbox 工具
  -> 工具结果写回会话并继续模型循环
  -> workspace 同步、usage 记录、SSE/渠道回复
```

迁移时必须保持以下语义，而不只是“最后文本相同”：

- assistant 原始 JSON 的 `_raw` 字段要无损保存并回放，以维持 prompt-cache 前缀；
- multimodal `content_parts`、thinking、tool calls、tool call ID、timestamp 和 UI metadata 要保持字段名及省略规则；
- streaming 的终态必须在流关闭前可见，错误不能被普通 EOF 吞掉；
- 每个 Agent 的 session-bound registry 状态当前通过 turn gate 串行化；Python 版要用 `asyncio.Lock` 或消除可变共享绑定，不能仅依赖 GIL；
- max tool iterations、取消、超时、hook 顺序、policy 拒绝和工具错误回灌模型的行为都应纳入契约测试。

### 2.3 Provider 与流式协议

当前有 OpenAI-compatible 和 Anthropic Messages 两条实现，并统一为 `Chat`/`ChatStream`。它们承担的不只是 HTTP 调用，还包括：

- provider/model 前缀处理；
- 不同消息与工具 schema 转换；
- SSE 分片解析与 tool-call arguments 拼接；
- thinking/signature 处理；
- token/cache usage 归一化；
- 原始 assistant 消息保真。

Python 可以使用 `httpx.AsyncClient` 自行实现薄适配层，或谨慎引入供应商 SDK。初期不建议用“大一统 LLM 框架”替代：框架的消息规范化可能破坏 `_raw`、thinking signature、缓存和现有异常语义。Provider 是适合最先做双实现契约测试的模块。

### 2.4 工具、MCP 与插件

内置工具覆盖文件、shell、web、memory、cron、message、sub-agent、skill install、image、TTS 等。外部扩展有两套边界：

- MCP：stdio 或 streamable HTTP/JSON-RPC；
- Plugin：独立子进程，通过逐行 JSON-RPC 通信，并有通知、pending request、stderr、超时和退出清理。

Python 的 `asyncio.create_subprocess_exec`、HTTP streaming 与 JSON 编解码能够覆盖这些能力。必须保留协议级兼容，优先让现有插件和 MCP Server 不改代码即可连接；不要把 Python import/plugin entry point 当作唯一插件机制。

### 2.5 状态与存储

状态并不只在数据库：

| 状态 | 当前介质 | Python 兼容要求 |
|---|---|---|
| 全局配置、密钥引导 | JSON/文件 | 原路径、camelCase 字段、默认值和环境变量优先级不变 |
| 会话与身份/记忆 | 文件或 Store | JSONL/数据库记录可被两种实现交替读取 |
| agent/shared skills | 文件/对象存储同步 | 目录布局、frontmatter 与加载优先级不变 |
| 生成文件 | LocalFS 或 S3-compatible | key、agent/session namespace、content type 不变 |
| FTS | SQLite FTS5 | 可先保持数据库格式；验证 tokenizer 与查询结果差异 |
| 用户、API key、usage | Store | schema、migration ownership、事务边界不变 |

建议 Python 首版只读现有 schema，数据库 migration 继续由 Go 版或独立 migration job 独占。确认双版本兼容后，再转移 schema ownership；绝不能让两个进程同时以不同 migration 逻辑自动升级。

### 2.6 并发和隔离

Go 版本大量使用 goroutine、channel、mutex、context cancellation。Python 并非不能实现，但需要明确映射：

| Go 语义 | Python 建议 |
|---|---|
| `context.Context` | 显式 request context + AnyIO cancel scope/deadline |
| goroutine | AnyIO task group；禁止无法追踪的裸后台 task |
| channel | `asyncio.Queue`/AnyIO memory stream |
| mutex/turn gate | `asyncio.Lock`，并按 user/agent/session 定义锁 key |
| counting semaphore | `asyncio.Semaphore` |
| signal shutdown | ASGI lifespan + task group cancel + 有序 `aclose()` |
| blocking DB/filesystem/SDK | 原生 async 驱动，或受限 thread pool |

关键不变量是：同一 chat FIFO、不同 chat 可并行、根任务有全局上限、内部 sub-agent 有独立容量、取消只影响正确的调用树、每个 `(agent_id, session_id)` 沙箱隔离。

## 3. 可迁移性分级

### 3.1 低风险：适合直接迁移

- 配置模型、默认值、环境变量映射；
- policy、privacy scrub、纯 JSON/YAML 转换；
- Provider 的非流式部分；
- Skills/frontmatter 发现和摘要；
- 管理端 CRUD 和大多数 setup handler；
- eval 的 grader、report、compare 等纯逻辑；
- LocalFS Workspace 和普通 HTTP tool provider。

建议用 Pydantic v2（alias + strict validation）、dataclass/Protocol，以及 pytest 参数化复用 fixture。

### 3.2 中风险：有成熟生态，但需要契约验证

- FastAPI SSE/WebSocket/OpenAI-compatible API；
- PostgreSQL/SQLite Store、事务与 FTS；
- S3 对象存储；
- Slack/Telegram/Discord adapter；
- cron、webhook、rate limit、auth；
- MCP stdio/HTTP；
- Docker/E2B API 客户端；
- CLI 与 daemon/service 管理。

风险来自默认行为差异，例如 JSON `omitempty`、时间格式、HTTP header、断连取消、SQLite 并发、path normalization，而不是库缺失。

### 3.3 高风险：必须先做试点

- Agent streaming loop 和 tool-call delta 聚合；
- `_raw` assistant 的字节级保真与 prompt cache；
- TaskQueue 与 recursive sub-agent 的公平性、容量和取消传播；
- 多租户 UserSpace 的 lazy load/reload/eviction；
- sandbox hydrate、远端 workspace 每次工具调用后同步、evict flush；
- plugin 子进程在崩溃、半包、超时、并发 pending call 下的行为；
- 热重载与有序关闭；
- 全套 eval tenant/runtime harness。

这些模块决定迁移是否能达到生产等价，不应靠单元测试数量来宣告完成。

## 4. 方案比较

| 方案 | 描述 | 优点 | 主要问题 | 建议 |
|---|---|---|---|---|
| A. 独立仓库、一次性交付 | Python 仓库闭门开发，全部完成后才发布 | Go 仓库完全不受扰动 | 很晚才发现协议/并发差异，长期没有可用成果 | 不采用 |
| B. 独立仓库、垂直切片交付 | 两个仓库共享外部契约，Python 按端到端能力逐步发布 | 从零设计、可验证、可独立发布，Go 始终保留 | 需要跨仓库契约与两套实现的维护机制 | **推荐** |
| C. Python SDK/编排层 | Go runtime 保留，Python 只提供客户端、工具和业务编排 | 风险最低、最快提供 Python 开发体验 | 不是完整 Python runtime | 可作为第一阶段成果 |
| D. 仅做机械转译 | 按 Go 包逐文件翻译 | 易分工 | 会复制 Go 惯用结构，无法自然处理 asyncio/ASGI | 仅用于参考，不作为架构 |

推荐在独立 Python 仓库中先实现 C，再沿 B 推进。这样即使最终压测证明网关、队列或沙箱仍更适合 Go，项目也已获得可用的 Python SDK 和可插拔服务；Go 仓库继续作为完整产品存在，而不是进入待废弃状态。

## 5. 新代码库与目标架构

### 5.1 仓库决策

建议在与 Go 仓库同级的组织空间创建：

- **仓库名**：`fastclaw-python`（若希望强调实现独立，也可用 `fastclaw-py`）；
- **Git 历史**：空仓库初始化，不 fork、不复制 Go 的 `.git`，不使用 orphan branch；
- **默认分支**：`main`，日常功能分支使用 `feat/<slice>`；
- **发布物**：Python distribution 使用 `fastclaw-runtime` 或组织确认后可用的 PyPI 名，CLI 命令可继续叫 `fastclaw-py`，避免和 Go 二进制冲突；
- **许可证**：在新仓库明确放置 LICENSE，并在借鉴 Go 实现或测试数据时保留必要归属；新仓库建立前由维护者确认名称、PyPI namespace 和版权主体；
- **Go 仓库改动原则**：仅在确有需要时增加语言无关 schema/fixtures 或导出测试数据，不加入 Python package、虚拟环境和 Python CI。

这意味着“从 0 开发”是重新设计 Python 模块与运行时，而不是忽略现有行为。新实现可以不复刻 Go package 结构，但必须对用户已经依赖的接口保持兼容。

### 5.2 Python 仓库初始结构

新仓库建议从以下结构开始：

```text
fastclaw-python/
  pyproject.toml
  src/fastclaw/
    cli/
    config/
    contracts/       # Message、Tool、Event、Store DTO
    providers/
    agent/
    tools/
    api/
    runtime/         # Gateway、UserSpace、lifecycle
    stores/
    workspace/
    sandbox/
    mcp/
    plugins/
    channels/
    evals/
  tests/
    unit/
    contract/
    integration/
    parity/
  contracts/
    fixtures/        # 从版本化 contract bundle 导入的 golden files
  docs/
    compatibility.md
    decisions/       # ADR：async 模型、存储、序列化、插件等
```

不要在当前 Go 仓库中直接创建上述 `python/` 目录。两个仓库之间的 contract bundle 可以通过独立版本化 artifact、GitHub Release 或专门的 `fastclaw-contracts` 小仓库分发；初期最简单的是由 Go 仓库发布 fixture tarball，Python CI 固定其版本和来源 commit。

架构约束：

1. **contract first**：对外 JSON、SSE event、数据库 schema、文件布局、JSON-RPC 是源语言无关的产品接口。
2. **async core**：从 HTTP 到 Provider、Tool、Store 全链路 async；同步代码只允许在明确的 adapter/thread boundary。
3. **structured concurrency**：每个后台任务属于 lifespan 或请求 task group，具备 owner、取消与关闭路径。
4. **依赖倒置**：使用 `typing.Protocol` 定义 Provider/Store/Executor；业务层不直接依赖 boto3、Docker 或具体数据库。
5. **不共享内存状态做互操作**：Go/Python 通过 HTTP、JSON-RPC、数据库或对象存储协作。
6. **可观测性先行**：trace 中统一 user/agent/session/correlation/call-path，才能影子对比。

## 6. 必须冻结的兼容契约

建立 Python 代码前，先从 Go 行为生成 golden fixtures：

### HTTP/API

- `/v1/chat/completions` 的 streaming/non-streaming 请求、响应、usage 和错误 envelope；
- `/v1/agents` 的鉴权与可见性；
- `/ws` frame、setup `/api/*`、chat SSE、session/file/upload 接口；
- CORS、认证 header、agent/session header、status code、断连取消。

### 会话与消息

- JSON 字段的 snake_case/camelCase 差异必须按具体边界固定；
- 空值、缺省值、未知字段、tool arguments 字符串、multimodal parts；
- `_raw` 的保存/读取/重放以及历史附件前缀清理；
- session ID、title、updated time、消息顺序。

### 运行时事件

- text delta、tool start/result、thinking、usage、done、error 的顺序；
- provider stream 中途中断、客户端取消、工具超时、非法 JSON；
- sub-agent correlation ID、call path、防递归和 completion exactly-once。

### 持久化与文件

- 文件根目录、agent/session namespace、路径穿越拒绝；
- PostgreSQL/SQLite schema 与事务结果；
- skill metadata/frontmatter 与环境变量注入；
- LocalFS/S3/Docker/E2B hydrate-sync-snapshot 的结果。

### 生命周期

- 启动部分失败时已创建资源的回收；
- SIGTERM、队列 drain、stream cancel、plugin/MCP/sandbox close 顺序；
- reload 前后新旧请求看到的配置版本。

## 7. 分阶段路线图与退出条件

### Phase 0：基线与契约（1–2 人周）

- 固定 Go commit 和测试数据；
- 生成 API、SSE、Provider、session、Store、plugin/MCP golden fixtures；
- 建立 parity runner：同一 fixture 分别运行 Go/Python，比较结构化结果；
- 记录基线的延迟、吞吐、内存、取消与沙箱冷启动。

**退出条件**：契约清单有 owner；关键 fixture 能在 CI 中重放；差异比较不是人工查看日志。

### Phase 1：Python SDK + 无状态垂直切片（2–4 人周）

- 建立 package、类型检查、lint、测试、镜像；
- 实现 config/contracts、OpenAI-compatible Provider、基础 Registry；
- 实现一个无状态 `/v1/chat/completions` 路径，支持 streaming 与单个工具；
- 保持前端不变，通过 base URL 切换后端。

**退出条件**：文本、工具调用、usage/error、取消的契约测试通过；不接生产状态。

### Phase 2：Agent、Session、Memory、Skills（4–7 人周）

- 完成 ReAct loop、hooks、policy、compaction、memory 和 skill loader；
- 实现文件 Store/Workspace，读取 Go 生成的 session；
- 迁移内置低风险工具；
- 运行 smoke、BFCL 与 Agent 单元/集成 parity。

**退出条件**：代表性多轮对话可在 Go/Python 间交替继续；固定 provider stub 下事件轨迹一致。

### Phase 3：数据库、多租户与管理面（4–7 人周）

- PostgreSQL/SQLite Store adapter；
- auth、API key、UserSpace、setup/admin handler；
- S3 workspace、usage、rate limit、reload；
- Python 仍不拥有 schema migration。

**退出条件**：租户越权负例全部通过；双实现对同一数据库/对象集互读；滚动切换无需数据迁移。

### Phase 4：并发、sub-agent 与 sandbox（5–9 人周）

- TaskQueue、channel serialization、internal capacity、recursive call path；
- Docker/E2B pool、session 隔离、hydrate/sync/snapshot/evict；
- MCP 与 plugin；
- fault injection、race-like stress、泄漏和关闭测试。

**退出条件**：无跨 session/tenant 污染；取消与超时压力测试稳定；sandbox 和 sub-agent eval 达标。

### Phase 5：外围能力与生产验证（3–6 人周）

- channels、cron、webhook、daemon、完整 CLI、eval runner；
- 影子流量、按租户 canary、性能调优；
- 发布、升级、回滚和运维文档。

**退出条件**：连续观察窗口内正确性、安全性和 SLO 达标；回滚演练成功；才讨论默认 runtime 切换。

粗略总量为 **19–35 人周的净开发量**，另加评审、线上观察和不可预见兼容成本。2–3 名熟悉 asyncio、ASGI、数据库和 LLM streaming 的工程师，通常应按 **4–7 个月**规划可上线等价版本，而不是把行数按语言转换速度估算。

## 8. 两周可行性试点（Go/No-Go）

创建独立 Python 仓库后，第一项工作应是一个受控试点，而非铺开所有 package：

1. 用 deterministic fake provider 输出拆分的 text/tool/thinking SSE；
2. Python 实现 OpenAI-compatible endpoint + ReAct loop + `read_file` 工具；
3. 读取一份 Go 版 session，继续一轮并再由 Go 版读取；
4. 模拟客户端断连、provider 半途错误、工具 timeout；
5. 用 1/10/100 并发、同 session 与不同 session 两组场景验证锁粒度；
6. 比较事件序列、最终 session JSON、错误类型、内存和 P95 延迟。

Go 条件：所有 P0 契约一致；无死锁/任务泄漏；Python P95 不超过基线 1.5 倍且内存处于部署预算内。否则先修正架构；若两轮仍不能达到，应停在 Python SDK/sidecar 方案，而非继续全量重写。

## 9. 测试策略

迁移不能只运行两套各自的 unit tests，应建立测试金字塔：

- **Schema tests**：Pydantic/JSON Schema 验证请求、消息、配置、事件；
- **Golden parity**：相同输入和 fake clock/provider/ID generator，比较 Go/Python 结构化输出；
- **Store compatibility**：Go 写 Python 读、Python 写 Go 读，覆盖文件/SQLite/PostgreSQL/S3；
- **Protocol simulation**：SSE 任意分片、JSON-RPC 半包/乱序 notification、进程异常退出；
- **Concurrency/property tests**：Hypothesis 生成任务交错，验证 FIFO、exactly-once、容量、取消；
- **Security negative tests**：tenant/agent/session 越权、path traversal、SSRF、shell policy、secret scrub；
- **Fault injection**：DB/S3/provider/MCP/sandbox 延迟、短读、重试、断连；
- **Performance**：首 token、完整请求、并发连接、RSS、event-loop lag、sandbox cold/warm；
- **现有 eval**：smoke、BFCL、τ、SWE、多 Agent 与 tenant runtime 都应成为切换门禁。

LLM 输出本身非确定，因此 parity 不比较真实模型的自然语言逐字相等；Provider 使用确定 stub 时比较精确轨迹，真实模型时比较协议、grader、工具轨迹和统计阈值。

## 10. 风险登记与缓解

| 风险 | 概率/影响 | 缓解 |
|---|---|---|
| Go 主线持续变化导致两个仓库行为漂移 | 高/高 | 契约变更发布新 bundle；Python compatibility matrix 固定 Go commit/tag；自动发起升级 PR |
| Python 库自动规范化消息破坏缓存 | 中/高 | 自有 DTO/serializer；保留 raw bytes；对供应商 SDK 做 adapter contract test |
| async 中混入阻塞 I/O 导致尾延迟 | 高/高 | event-loop lag 指标；async driver；受限线程池；CI 压测 |
| 锁粒度错误造成串话或吞吐下降 | 中/高 | 锁 key 明文化；交错/取消 property tests；尽量请求内不可变状态 |
| 双版本写数据库发生 schema 分叉 | 中/高 | 单一 migration owner；expand/contract schema；双向互读测试 |
| 沙箱同步遗漏导致文件丢失 | 中/高 | 每次成功 exec 后同步契约；evict snapshot；故障注入 |
| 单二进制交付优势丢失 | 高/中 | 自包含容器/zipapp 评估；明确 Python 版不承诺 Go 式单文件；镜像 SBOM |
| CPU/内存成本上升 | 中/中 | 基线压测；横向进程；热点保留 Go sidecar；用数据决定替换范围 |
| 安全边界回归 | 中/极高 | 默认拒绝 host shell fallback；租户负例；威胁建模和独立安全评审 |
| 团队同时维护两套代码疲劳 | 高/中 | 设置阶段截止与退出条件；按仓库明确 owner；自动化 contract CI，避免人工同步实现细节 |

## 11. 双代码库、CI 与发布治理

建议：

- Go 仓库 `fastclaw` 与 Python 仓库 `fastclaw-python` 各自使用 `main`/维护分支和独立 release cadence；不建立跨仓库的“迁移分支”；
- Python 仓库的 `compatibility.md` 记录每个 release 验证过的 Go tag/commit、contract bundle 和已知差异；
- 语言无关 contracts 由明确的单一 owner 发布不可变版本；Go 和 Python CI 都消费同一版本，不通过复制粘贴维持两份真相；
- 每个 Python 实现 PR 必须说明对应 Go 行为、兼容 fixture、性能变化和回滚路径；Go 的功能 PR 若改变外部行为，则必须升级 contract version；
- Go/Python 版本使用独立 artifact 名（如 `fastclaw` 与 `fastclaw-py`）和同一协议版本；
- 采用 expand/contract：先让旧版忽略新字段，再上线写新字段的版本，最后才移除旧字段；
- canary 以 user/agent 为稳定路由键，不能把同一 session 的连续轮次随机分到两种实现；
- 未通过 Phase 4 前，不允许 Python 版直接执行 host shell，也不允许成为生产默认入口。

### 11.1 新仓库创建清单

仓库管理员可以直接按以下顺序落地：

1. 在与 `fastclaw` 相同的 GitHub/GitLab organization 新建空仓库 `fastclaw-python`，设置可见性和 CODEOWNERS；
2. 添加 LICENSE、README、SECURITY、CONTRIBUTING、Python `.gitignore` 与 `pyproject.toml`；
3. 固定支持的 Python 版本（建议创建时选择仍受安全维护的版本范围），配置 lock file 和依赖更新机器人；
4. CI 至少运行 format、lint、type check、unit、contract、integration、package build 和 vulnerability scan；
5. 首个 tag 只发布 SDK/试点能力，版本保持 `0.x`，compatibility matrix 明确“不具备 Go runtime 全功能等价”；
6. 为两个仓库建立 cross-repo issue/label，Go 行为变更和 Python parity 工作相互链接，但不要求 commit 历史同步；
7. 生产部署使用不同 service/image 名和独立配置前缀，避免安装、端口、数据 migration owner 相互覆盖。

## 12. 最终建议

**建议批准新建 `fastclaw-python` 独立仓库，立项描述为“从零实现、协议兼容的 Python runtime”，而不是 Go 仓库中的迁移分支，也不是以删除 Go 版为目标的全量翻译。**

立即可执行的决策：

1. 创建空的 `fastclaw-python` 仓库，首批只合入 package skeleton、compatibility matrix 和 parity harness；
2. 用两周完成第 8 节试点，以 Agent streaming loop 为最早风险验证点；
3. 先交付 Python SDK/无状态服务，尽快获得用户价值；
4. Store schema、外部 API、session 格式、plugin/MCP 协议保持兼容；
5. 迁移顺序为 Provider/config → Agent/session → Store/tenant → queue/sandbox → peripheral；
6. 每阶段以可量化退出条件决定继续、保留混合架构或停止，而不是以“已翻译文件比例”判断进度；
7. Go runtime 长期保留并独立发布；真实压测只决定 Python 版的生产适用范围，不决定是否删除 Go 项目。

因此答案是：**可以新建代码库，而且这比长期迁移分支更符合“Go 项目保留、Python 从 0 开发”的目标。** Python 项目的成功标准应是形成可独立安装、部署、维护的实现；它可以逐步达到协议与能力等价，但不需要取代或删除 Go 项目。若首要诉求是生态与二次开发，先交付 Python SDK + 可插拔 Agent/Tool 服务能以约四分之一风险获得大部分收益，再根据独立仓库的阶段门禁推进完整 runtime。
