# FastClaw 项目深度解析：从一次请求到多 Agent 运行时

> 面向第一次接触项目的研发、测试开发与 Agent 工程学习者。本文以当前工作树 `HEAD=792417b`（`m0yuw-project`）为源码基线，参考 `FastClaw-项目面试拷打补充.md`、`/Users/wangzheyu/PROJECT-HANDOFF.md` 和仓库内 `PROJECT-HANDOFF.md`，但所有架构结论以当前源码为准。
>
> 阅读目标：先在 10 分钟内建立系统地图，再能沿文件和函数追踪单 Agent、流式 Web、多 Agent 委派、配置持久化与评测链路。

## 1. 先建立正确的项目认知

### 1.1 FastClaw 是什么

FastClaw 不是一个固定业务 Agent，也不只是一个聊天页面。它更接近一个 **多租户 Agent 运行时与管理平台**：

1. 用户在控制台创建 Agent，为其配置模型、人格、技能、工具和渠道。
2. Gateway 按用户构造隔离的 `UserSpace`，装配 Provider、Session、Memory、Skills、MCP 和工具。
3. Agent 运行 ReAct 循环，在模型推理与工具执行之间迭代。
4. Coordinator 可以通过 `spawn_subagent` 委派给其他 Agent。
5. MessageBus、TaskQueue 和 Gateway 为委派补上 RPC 关联、租户校验、排队、取消、背压和循环检测。
6. Web、OpenAI-compatible API、WebSocket 和 IM Channel 是不同入口，共享底层 Agent 运行时，但并不共享完全相同的调度与流协议。

一句话概括：

> FastClaw 把“调用一次大模型”扩展成“可配置、可持久化、可调用工具、可委派、可流式观察的 Agent 执行系统”。

### 1.2 当前代码包含三类资产

理解仓库前必须区分以下三层，否则容易把实验结果误当成主干能力。

| 层次 | 当前状态 | 代表内容 |
|---|---|---|
| FastClaw 核心运行时 | 当前 `HEAD` 可直接阅读和测试 | `cmd/`、`internal/`、`web/`、tracked `skills/`、tracked `plugins/` |
| 独立实验分支能力 | Git ref 中存在，但不在当前工作树 | `codex/eval-runtime-harness`、`codex/finance-agent-runtime`、`codex/finance-e2e-study` |
| 本地未跟踪实验资产 | 当前目录可见，但不属于提交基线 | `runtime-*.json`、`evals/`、`project-report/`、`plugins/finance-tools/__pycache__` |

这意味着：

- 当前核心已有 Agent、Provider、Session、Web 真流、多 Agent 内部 RPC 和队列。
- 完整 `internal/eval` Harness 不在当前 `HEAD`，不能把它描述成当前分支的可编译包。
- 当前 `plugins/finance-tools/` 没有可运行插件源码，仅有缓存文件；完整源码位于其他 Git ref。
- 本地 benchmark JSON 是实验产物，不是自动具备版本、环境和统计可复现性的正式基准。

### 1.3 五分钟架构图

```text
                         ┌────────────────────────────┐
                         │        Web Console         │
                         │ Next.js 16 + React 19      │
                         └─────────────┬──────────────┘
                                       │ REST / POST SSE
     IM Channels ───────┐              │              ┌──── OpenAI-compatible API
     WebSocket ─────────┼───────┐      ▼      ┌───────┼──── /v1/chat/completions
     Cron ──────────────┘       │  Setup/API  │       └──── /ws
                                └──────┬───────┘
                                       │
                   Web/API direct ─────┼──────────────┐
                                       │              │
                                       ▼              │
                              ┌─────────────────┐      │
                              │     Gateway     │      │
                              │ auth + routing  │      │
                              └───────┬─────────┘      │
                         Channel /    │ internal RPC   │
                         sub-agent    ▼                │
                              ┌─────────────────┐      │
                              │    TaskQueue    │      │
                              │ FIFO + timeout  │      │
                              │ root semaphore  │      │
                              └───────┬─────────┘      │
                                      │                │
                                      ▼                ▼
           ┌──────────────────────────────────────────────────┐
           │ Agent.runTurn                                    │
           │ session -> prompt -> provider stream -> tools    │
           │               ^                       │          │
           │               └──── ReAct loop ───────┘          │
           └─────────┬───────────────┬───────────────┬────────┘
                     │               │               │
              Session/Memory     Skills/MCP      spawn_subagent
                     │             /Sandbox            │
                     ▼                                  ▼
              SQL / JSONL                    MessageBus internal RPC
              LocalFS / S3                            │
                                                     Gateway
                                                       │
                                                    TaskQueue
                                                       │
                                                   Child Agent
```

这里最容易出现的误解是“所有请求统一进入 TaskQueue”。当前源码并非如此：

- Web `/api/chat` 与 `/api/chat/stream` 直接调用 Agent。
- OpenAI-compatible HTTP 入口也直接调用 Agent。
- Channel 入站和 `spawn_subagent` 内部调用才进入 TaskQueue。

把系统拆成两个平面更容易理解：

- **控制面**：Web 管理台、身份/API Key、Agent/模型/技能/渠道配置、数据库。
- **执行面**：Gateway、TaskQueue、Agent ReAct、Provider、工具、MessageBus、流事件。

## 2. 目录与模块地图

| 目录 | 职责 | 初次阅读优先级 |
|---|---|---|
| `cmd/fastclaw/` | CLI、Gateway 启动、provider/eval 等命令入口 | 高 |
| `internal/setup/` | HTTP 服务、Web API handlers、静态前端挂载 | 高 |
| `internal/gateway/` | 用户空间、消息路由、Agent 与 TaskQueue 接线 | 最高 |
| `internal/agent/` | Agent 主循环、事件、上下文、Session/Memory 适配 | 最高 |
| `internal/agent/tools/` | 内置工具、Registry、`spawn_subagent` | 最高 |
| `internal/bus/` | 外部消息 channel 与内部 correlated RPC | 最高 |
| `internal/taskqueue/` | 每 lane FIFO、根任务并发、内部任务调度和状态 | 最高 |
| `internal/provider/` | OpenAI/Anthropic 适配与流式抽象 | 高 |
| `internal/store/` | SQLite/PostgreSQL Store、schema、迁移、FTS | 高 |
| `internal/session/` | 会话模型、SQL adapter、JSONL fallback | 高 |
| `internal/config/` | 环境启动配置、运行时配置类型与 Agent 合并 | 高 |
| `internal/api/` | OpenAI-compatible API、WebSocket 协议 | 中 |
| `internal/channels/` | Telegram、Discord、Slack 等渠道 | 中 |
| `internal/skills/` | 技能下载、安装、对象存储同步 | 中 |
| `internal/mcp/` | MCP stdio/HTTP client 和工具路由 | 中 |
| `internal/plugin/` | 子进程插件发现、JSON-RPC 和各类 adapter | 中 |
| `internal/sandbox/` | 工具执行隔离与生命周期 | 中 |
| `internal/workspace/` | Agent/session 文件的 LocalFS/S3 抽象 | 中 |
| `internal/cron/` | 定时触发 Agent 任务 | 低到中 |
| `web/src/app/` | Next.js App Router 页面 | 高 |
| `web/src/lib/api.ts` | 前端 REST/SSE 客户端和 DTO | 最高 |
| `web/src/lib/chat-stream.ts` | 流事件 reducer、去重和批处理 | 最高 |

推荐先追踪一条真实请求，再回头看各模块定义，不要按目录从头到尾顺序阅读。

## 3. 进程启动与依赖装配

### 3.1 交付形态

项目使用 Go 1.25，前端使用 Next.js 16、React 19。`Makefile` 的构建顺序是：

```text
pnpm build
  -> Next 静态产物 web/out
  -> 复制到 internal/setup/web
  -> go build ./cmd/fastclaw
  -> bin/fastclaw
```

所以开发时前后端目录独立，发布时控制台静态资源由 Go 服务托管，最终是一个二进制和一个进程。

### 3.2 准确启动链

程序入口是 `cmd/fastclaw/main.go:56` 的 `main`。直接运行根命令和 `fastclaw gateway` 最终都会进入 `runGateway`：

```text
runGateway                                      cmd/fastclaw/main.go:94
  -> config.LoadEnv                             internal/config/env.go:48
  -> 安装 bundled skills
  -> 写 PID
  -> gateway.New                                internal/gateway/gateway.go:133
       -> Store / Workspace / Usage Meter
       -> MessageBus / UserSpace registry
       -> Channel / Cron / Webhook
       -> Plugin Manager / TaskQueue
  -> auth.NewResolver
  -> setup.NewServer
  -> 注入 Queue / Store / Workspace / Usage / Auth
  -> api.NewServer
  -> goroutine 启动 HTTP
  -> 主 goroutine 执行 Gateway.Run
```

启动过程的本质不是“启动一个 HTTP Server”，而是先构建整套控制面和执行面依赖。

### 3.3 配置分为启动配置和用户配置

- **进程启动配置**：端口、bind、数据库、sandbox、日志等，来自 `FASTCLAW_*`，入口为 `internal/config/env.go`。
- **用户运行时配置**：Provider、Agent、Channel、MCP、Cron、Plugin 等，主要保存为数据库 scope records。

当前没有实际的 `fastclaw.json` 加载链路。README 中该文件的描述更接近旧版本产品模型，阅读当前源码应以环境变量加数据库配置为准。

### 3.4 生命周期和异常边界

`Gateway.Run` 自己监听 `SIGINT/SIGTERM`，取消内部 context，等待 UserSpace evictor、dedup cleaner、inbound router、Channel、Cron 和 Webhook，然后停止 internal bus、TaskQueue、Plugin 和仍在 registry 中的 SandboxPool。

外层 HTTP context 要等 `Gateway.Run` 返回后才取消，HTTP Server 再执行最多 5 秒的 graceful shutdown。

一个重要缺口是：如果 HTTP `Listen` 失败，当前入口只记录错误，不会取消 Gateway，进程可能继续常驻但没有 Web/API 服务。

## 4. 配置系统：从数据库 scope 到单个 Agent

### 4.1 配置模型

`internal/config/config.go` 的 `Config` 是运行时配置快照，覆盖：

- Providers
- Agents 与 Agent defaults
- Channels
- MCP servers
- Cron jobs
- Storage 与 Sandbox
- Tool providers
- Plugins

Provider 模型通常写成 `<providerKey>/<modelID>`。前半段定位 provider 配置，后半段是供应商模型 ID。

### 4.2 Scope 合并与 Agent 覆盖

配置不是一次简单的 map 覆盖，实际装配顺序是：

```text
system scope -> user scope                         assembleConfig
  -> env overlay -> defaults                      ApplyToConfig / ApplyDefaults
  -> ResolveAgents
       -> MergedAgentConfig
       -> DB agents.config 优先、agent.json fallback
  -> agent-scope agents.defaults 最终覆盖
```

`Gateway.New` 在 `internal/gateway/gateway.go:149` 将 `AgentFileConfigLoader` 接为 `makeStoreFirstAgentFileLoader(st)`；`MergedAgentConfig` 会实际调用它。因此当前主路径既包含数据库中的 Agent 配置，也保留 workspace `agent.json` fallback。`internal/gateway/userspace.go:375-400` 随后再叠加 agent scope 的 defaults。

### 4.3 UserSpace 是租户运行时容器

`loadUserSpace` 位于 `internal/gateway/userspace.go:346` 附近，过程包括：

1. 合并 system/user/agent 配置。
2. 解析默认模型对应的 Provider。
3. 查询该用户的 Agent records。
4. 应用 Agent scope override。
5. 创建 `agent.Manager`。
6. 注入绑定 user ID 的 Session StoreAdapter 与 Memory StoreAdapter。
7. 装配 skills、MCP、工具链、sandbox 和 sub-agent spawner。

UserSpace 不是启动时全量加载，而是首次鉴权访问时由 `getOrLoad` 懒加载，空闲 30 分钟后淘汰。配置写入后，`InvalidateUser` 删除缓存，下一次请求重建。

### 4.4 UserSpace 当前两个限制

1. 一个 UserSpace 当前按默认模型的 provider 前缀创建一个共享 Provider。若某个 Agent override 切到另一 provider 前缀，并不会自动重新选择 Provider。
2. invalidation/idle eviction 只是从 map 移除 UserSpace，没有关闭其中的 SandboxPool；退出时旧空间也不再出现在 `users.all()` 中。

## 5. 持久化：Store、Session、Memory 与 Workspace

### 5.1 Store 统一什么

`internal/store/store.go` 的 `Store` 接口统一保存：

- users 与 Web sessions
- API keys 与 Agent allowlist
- agents 与 agent files
- chat sessions/messages
- scope configs
- cron jobs 等控制面数据

`internal/store/factory.go` 默认创建 SQLite，默认文件为 `~/.fastclaw/fastclaw.db`；配置 PostgreSQL DSN 后可切换实现。`internal/store/database.go` 负责 schema 与迁移。

数据库隔离通常显式带 `userID`。Session 的逻辑主键至少包含：

```text
(userID, agentID, sessionKey)
```

这比只按 `sessionId` 查询更重要，因为 session ID 本身不是租户边界。

### 5.2 Session 的双路径

`internal/session/manager.go` 同时支持：

- 正常 Gateway 路径：注入 `session.StoreAdapter`，保存到统一 Store。
- 独立/旧构造路径：使用 Agent workspace 下的 JSONL 文件。

Web session key 会转换成 `web_<sessionId>`。Store 模式下 `Get` 会重新从数据库加载，以便多 pod 看见较新的共享状态；文件模式使用本地 JSONL cache。

Session 不只保存文本，还保存 tool calls、tool call ID、tool results、multimodal content parts、thinking 和 raw assistant。这些字段决定下一轮模型能否拿到合法、连续的工具协议历史。

### 5.3 为什么需要 Flush 和工具结果修复

流式响应中，浏览器可能在任意 token 或工具调用阶段断开。若历史停留在“assistant 发出 tool call，但没有 tool result”，下一次 Provider 可能拒绝非法消息序列。

Agent loop 因此有两类保护：

1. `Session.Flush()` 是发送流式 `done` 前的持久化屏障。
2. Stop/取消时 `padOrphanToolResults` 为孤立 tool call 补一个合成结果。

这不是 UI 小修，而是 Provider 协议一致性要求。

### 5.4 Memory、Workspace 与 FTS

| 数据 | 用途 | 主要落点 |
|---|---|---|
| Session | 当前对话消息和工具历史 | SQL Store 或 JSONL |
| Memory | `MEMORY.md`、`USER.md` 等长期信息 | agent files DB adapter 或本地 Markdown |
| Workspace | 上传文件和工具生成物 | LocalFS 或 S3，按 Agent/session 隔离 |
| FTS | 本地全文索引 | 独立 SQLite FTS5 文件 |

`internal/store/fts.go` 的 FTS 不属于统一 `Store` 抽象，且 `SetMaxOpenConns(1)`。它不自动具备 PostgreSQL或多副本同步能力。

## 6. Provider：屏蔽协议差异，保留运行时语义

### 6.1 核心抽象

`internal/provider/provider.go` 定义统一的 `Message`、`Tool`、`ToolCall`、`Response`、`StreamChunk`、`StreamReader` 和 `Provider.Chat/ChatStream`。

Provider 抽象的价值不是只统一一个 `content string`，而是保留工具调用、多模态、thinking、usage 和 raw assistant 等运行时语义。

### 6.2 当前两套原生适配器

| 适配器 | 文件 | 特点 |
|---|---|---|
| OpenAI-compatible | `internal/provider/openai.go` | `/chat/completions`，增量拼接 content 与 indexed tool calls |
| Anthropic | `internal/provider/anthropic.go` | Messages API，content block、thinking、tool use 转换 |

DeepSeek、Moonshot、OpenRouter 等没有各自独立 adapter，通常通过 OpenAI-compatible `apiBase` 接入。

OpenAI 上游 parser 要求收到 `[DONE]`，否则返回 `io.ErrUnexpectedEOF`，防止把截断响应误判为完整回答。

### 6.3 Web 真流与 OpenAI 输出流不是一回事

Web 管理台链路是真正的 token 级转发：

```text
Provider SSE frame
  -> OpenAI/Anthropic parser
  -> StreamChunk
  -> Agent runTurn emitter
  -> ChatEvent(content_delta)
  -> /api/chat/stream
  -> frontend reducer
  -> 同一回答气泡持续增长
```

OpenAI-compatible 输出适配器则有不同语义。`Agent.HandleMessageStream` 为避免把随后触发工具的中间轮文本暴露给客户端，会按 round 缓冲 delta，只在最终 `done` 时释放。因此它不是低延迟逐 token SSE。

结论：Provider 内部是流式的，Web SSE 是逐 token 的，但不能把这个结论泛化到所有外部流协议。

### 6.4 Provider 当前边界

- 没有统一重试、指数退避、429/5xx 策略。
- 没有统一供应商能力探测。
- HTTP timeout policy 不是集中配置。
- `CredentialManager` 主要被 provider CLI 使用；Gateway runtime API key 主路径来自 resolved DB config。
- 当前测试主要覆盖 OpenAI/Anthropic SSE 解析与流终态，未覆盖真实供应商差异。

## 7. Agent 核心：一次 `runTurn` 做了什么

### 7.1 Agent 的关键依赖

`internal/agent/loop.go` 中的 `Agent` 持有：

- Provider
- Tool Registry
- Session Manager
- ContextBuilder
- Skills/MCP/Sandbox/Workspace
- ReAct 轮数与事件 emitter
- 单槽 `turnGate`

`turnGate` 会串行化同一个 Agent 的所有 turn，不仅是同一个 session。它简化共享状态一致性，但限制了同一 Agent 的跨会话吞吐。

### 7.2 `runTurn` 主流程

所有同步和流式入口最终复用 `internal/agent/loop.go:518` 附近的 `runTurn`：

```text
runTurn
  1. 获取 turnGate
  2. 处理 slash command
  3. 刷新 skills
  4. 获取 Session 并绑定 sandbox/workspace
  5. 修复孤立 tool result
  6. 执行 hooks、构造 system prompt
  7. append user message
  8. context compression / PII scrub
  9. Provider.ChatStream
 10. 发送 delta 事件并解析 tool calls
 11. 执行工具并 append tool result
 12. 继续下一轮模型调用
 13. Flush session
 14. emit done
```

关键入口：

- `internal/agent/loop.go:320`：Web chat 转换。
- `internal/agent/loop.go:518`：`runTurn` 主体。
- `internal/agent/loop.go:603`：Provider/ReAct 迭代附近。
- `internal/agent/loop.go:755`：工具执行附近。
- `internal/agent/loop.go:980`：OpenAI 输出流适配。

### 7.3 ReAct 循环不是无限循环

默认逻辑最多执行约 20 个工具轮次。每轮模型返回两类结果：

- 没有 tool call：回答完成。
- 有 tool call：执行工具，把 tool result 写回消息，再请求下一轮模型。

另有重复工具防护：连续三次使用完全相同的工具名和参数时，系统把 warning 写入 Session 和本地消息历史，随后立即结束当前 ReAct 循环。当前 turn 不会再调用 Provider，因此模型只能在后续 turn 看到该警告。

### 7.4 两种 Context 不要混淆

项目中“上下文”至少有两层：

1. `ContextBuilder` 构造给模型看的 system prompt，包括身份、技能、记忆、工具说明。
2. Go `context.Context` 传递取消、deadline、root execution ID、CallPath 和事件通道。

`BuildRuntimeContext` 当前没有调用点；主循环使用的是 `BuildSystemPrompt`。不要仅因辅助函数存在就认为能力已经接线。

## 8. 工具体系：内置工具、Skills、MCP、Plugin

### 8.1 Tool Registry 与 SDK bridge

`internal/agent/tools/registry.go` 用 map 保存工具定义与 `ToolFunc`。`internal/agent/sdkbridge.go` 把 FastClaw 工具桥接到 open-agent SDK executor：

```text
model tool_call
  -> SDK executor
  -> FastClaw Registry ToolFunc
  -> ToolResult
  -> SDK tool result message
  -> Session.Append
  -> next provider round
```

当前统一 policy gate 未真正接入 executor：`canUseTool` 为 `nil`，`internal/policy` 包的 `Engine.CheckTool` 没有运行时调用点。实际权限依赖“工具是否被注册”、sandbox 和工具自身检查。

### 8.2 Skills 是提示词包

Skill 的核心是 `SKILL.md`，不是独立进程。`internal/agent/skills.go` 负责多层加载与优先级覆盖：

```text
extra / managed / user / team / agent workspace
```

越靠近 Agent workspace 的定义优先级越高。Bundled skills 通过 `go:embed` 进入二进制。最终技能摘要和正文进入模型上下文，`load_skill` 工具可按需展开技能。

技能安装来源包括 ClawHub、GitHub、skills.sh。tarball 解包有 `..` 路径检查，多 pod 通过 object store hydrate 到本地目录。

安全边界：远程 Skill 内容最终能影响模型行为。路径穿越检查不等于来源签名、供应链审核或 prompt injection 防护。

### 8.3 MCP 是外部工具协议客户端

`internal/mcp/manager.go` 在 Agent 构造时连接配置的 MCP server，初始化、列出工具，再用 server 前缀注册进 Tool Registry：

```text
Agent init
  -> MCP Manager.NewManager
  -> connect / initialize / list tools
  -> prefix tool names
  -> Registry.Register
  -> model tool_call
  -> Manager.CallTool
  -> target MCP server
```

当前支持 stdio 和 HTTP。连接失败只记录 warning，不阻止 Gateway 启动，因此运行时可能表现为“Agent 正常启动，但某组工具消失”。

当前限制：HTTP client 缺少请求 context 和统一 timeout，也没有完整 Streamable HTTP session/SSE 生命周期；MCP 包没有专项测试。

### 8.4 Plugin 是 JSON-RPC 子进程

Plugin 与 Skill 完全不同：`internal/plugin` 根据 `plugin.json` 启动子进程，通过 stdin/stdout 交换 JSON-RPC 2.0。

代码实现了 channel、provider、tool 和 hook adapter，但当前 Gateway 的真实接线只有：

```text
Discover
  -> ApplyConfig
  -> StartAll
  -> register plugin channels
  -> RegisterPluginProviders
```

全仓未找到 `RegisterPluginTools()` 和 `NewHookAdapter()` 的调用点。因此准确口径是：

- provider/channel 插件已接入主运行时。
- tool/hook adapter 有实现，但当前 Gateway 没有装配。

这也解释了为什么“目录中存在 tool plugin 代码”不等于“Agent 已经能调用该插件工具”。

## 9. 多 Agent 核心：`spawn_subagent` 完整调用链

### 9.1 为什么不能直接调用子 Agent

最简单的实现是父 Agent 直接执行 `targetAgent.HandleMessage(...)`，但这样会绕过 owner 校验、Queue 状态、调用环检测、统一 timeout/cancel、correlation、背压与观测字段。

当前实现将子调用视为一次受信任的内部 RPC，再由 Gateway 校验并由 TaskQueue 调度。

### 9.2 端到端链路

```text
父 Agent ReAct
  -> spawn_subagent ToolFunc
  -> gatewaySubAgentSpawner.SpawnSubAgent
  -> MessageBus.CallInternal
  -> Gateway.processInternal
  -> TaskQueue.SubmitInternal
  -> queue internal handler
  -> 子 Agent.HandleMessage / runTurn
  -> TaskResult completion
  -> MessageBus.ResolveInternal
  -> CallInternal correlation channel
  -> ToolResult
  -> 父 Session append tool_result
  -> 父 Agent 下一轮 Provider
```

| 阶段 | 文件与符号 |
|---|---|
| 注册 spawner | `internal/gateway/userspace.go:438` |
| 注册 `spawn_subagent` | `internal/agent/loop.go:359` |
| 工具参数与唯一 ID | `internal/agent/tools/subagent.go:44` |
| 构造内部调用 | `internal/gateway/routing.go:381` |
| correlated RPC | `internal/bus/internal.go:69` |
| Gateway 校验/路由 | `internal/gateway/routing.go:79` |
| 提交内部任务 | `internal/gateway/routing.go:117` |
| Queue 执行目标 Agent | `internal/gateway/gateway.go:240` |
| completion 回包 | `internal/gateway/routing.go:133` |
| 工具错误适配 | `internal/agent/sdkbridge.go:55` |

### 9.3 内部请求携带什么

`InternalRequest/Delivery/Reply` 不只是 `target + prompt`，还携带 owner ID、source/target Agent ID、correlation ID、root execution ID、CallPath、parent chat key 与原始 context。

这些字段分别服务于租户隔离、回包关联、并发继承、循环检测和取消传播。

### 9.4 子 Agent 的上下文隔离

子调用创建独立 `subagent_<id>` Session，不继承父聊天历史。它保留父 context 的取消/deadline、root execution ID 和 CallPath，但用 `ContextWithoutChatEvents` 屏蔽父 Web 流事件通道，避免子 Agent token 与工具细节污染父回答流。

内部执行还会禁用或抑制外发 `message` 与 media，避免子 Agent 绕过父 Agent 直接向用户发消息。

### 9.5 循环检测为什么有两层

仅禁止 self-spawn 只能阻止 `A -> A`，阻止不了 `A -> B -> A`。

1. **CallPath**：target 已在祖先路径中就拒绝，阻止单条调用链回到祖先。
2. **wait graph**：节点是 `<owner>:<agent>` lane，检测不同 root execution 形成的动态相互等待环。

没有独立最大 delegation depth；非重复 Agent 长链主要受 Agent 数量、每层 deadline 和 ReAct 轮数约束。

## 10. TaskQueue：并发、FIFO、超时与背压

### 10.1 两类任务

| 类型 | 来源 | root semaphore 语义 | 是否外发消息 |
|---|---|---|---|
| external/root task | Channel 入站 | 获取一个 root 槽 | 是 |
| 首层 internal task | `spawn_subagent`，context 中无 execution ID | 自己获取 root 槽并建立 execution ID | 否 |
| 嵌套 internal task | context 已有 execution ID | 继承 root，不重复占槽 | 否 |

Web 与 OpenAI HTTP 不经过 Queue。因此它们首次 spawn 时没有可继承的 Queue execution ID，首个 internal task 会占用一个 root semaphore；Channel Queue 任务发起的 spawn，以及更深层嵌套 spawn，才会继承现有 ID。Gateway 的 Queue 默认 `maxConcurrent=10`、`taskTimeout=300s`。

### 10.2 嵌套内部任务为什么不能重复占全局槽

假设 `maxConcurrent=1`，并且父任务已经在 Queue 中：

1. 父任务占唯一 semaphore。
2. 父任务同步等待子 Agent。
3. 子任务如果再次抢 semaphore，就永远无法开始。

这是父持槽等待子的资源死锁。`SubmitInternal` 只在请求 context 已有 internal execution ID 时免取 root 槽；没有 ID 的首层 internal task 仍会获取槽，并以自身 task ID 建立 root execution。无论是否继承，内部任务还受 256 个 `internalSlots` 限制，防止无限膨胀。

### 10.3 串行化层次

当前有多层串行：

1. 每个 chat queue 容量 100，lane 内 FIFO。
2. 同一 target Agent 的内部请求使用相同 synthetic key，因此串行。
3. `Agent.turnGate` 又把同一 Agent 的所有 session 串行。
4. `spawn_subagent` 没列入 SDK concurrency-safe 工具；同一模型响应中的多个 spawn 也顺序执行。

因此当前多 Agent 是“可委派”，但不是模型一次返回多个 spawn 后的真正并行 fan-out。

### 10.4 timeout 与 cancel

子任务可能同时受父请求 context、Queue 300 秒 timeout 和 spawner 10 分钟 timeout 控制，实际 deadline 取最早者。Queue 用 `context.AfterFunc` 将父取消传播给任务 context。

取消是协作式的：Provider、工具或 handler 必须响应 context；Go runtime 不会强制杀掉忽略 context 的 goroutine。

### 10.5 两层 admission control

- MessageBus pending internal RPC 上限为 256。
- TaskQueue internal slots 上限也为 256。

它们是独立的两层背压，不是同一个计数器。Bus 投递是非阻塞的，满载会立即返回错误。

### 10.6 失败与 exactly-once completion

Queue 会将 handler panic 转成 task failure，recover completion panic，并用 `sync.Once` 保证 completion 与内部槽只释放一次。Gateway shutdown 先释放 pending internal callers，late reply 被忽略。

注意：子 Agent 内很多 Provider/持久化错误会被转换成面向用户的字符串，因此 Queue 视角可能仍是“正常返回”。结构化 error 主要覆盖路由、Queue、context 和未被上层吞掉的工具错误。

## 11. Gateway：身份、路由与执行编排

### 11.1 Gateway 的职责

Gateway 负责：

- 接收 MessageBus 外部/内部消息
- 根据 owner 懒加载 UserSpace
- 定位 source/target Agent
- 执行 Agent allowlist 和 ownership 校验
- 生成 TaskQueue key 与 metadata
- 将执行结果发往 Channel 或 internal correlation reply
- 管理 Channel、Cron、Plugin 和 Queue 生命周期

它不负责模型推理细节；那属于 Agent/Provider。

### 11.2 三类请求的真实路径

```text
Web:
POST /api/chat[/stream]
  -> input scan -> resolveAgent -> Agent.HandleWebChat[Stream] -> runTurn

Channel:
adapter -> MessageBus.Inbound -> Gateway.processInbound
  -> routeDM/routeGroup -> TaskQueue.Submit -> Agent.HandleMessage
  -> MessageBus.Outbound -> channel adapter

Sub-agent:
spawn tool -> MessageBus.CallInternal -> Gateway.processInternal
  -> TaskQueue.SubmitInternal -> child Agent
  -> ResolveInternal -> parent tool result
```

### 11.3 外部与内部路由共享瓶颈

当前 `processInbound` 单个 goroutine 同时消费 external 与 internal channel。如果 Store/UserSpace 加载或外部 `Submit` 阻塞，两类消息可能一起发生 head-of-line blocking。

MessageBus、pending map、wait graph 和 TaskQueue 都是单进程内存结构。它适合单节点或 sticky routing，但不能自动跨 pod 完成内部 RPC，也不能在崩溃后恢复 pending reply。

## 12. 鉴权与多租户边界

### 12.1 身份解析

`internal/auth/auth.go` 的 Resolver 先尝试 session cookie，再尝试 Bearer API key；Bearer 也允许来自 `?token=`。`WithIdentity` 同时写入 `auth.Identity` 与 `config user_id`，后者驱动 UserSpace 选择。

Web Chat 的目标 Agent 授权集中在 `internal/setup/handlers.go:253` 的 `resolveAgent`，这里会调用 `Identity.CanAccessAgent`。

前端 `AuthGuard` 只是用户体验层，真正授权必须在后端 middleware 和 resolver 中完成。

### 12.2 已有隔离机制

- Web session 与 API key identity。
- API key Agent allowlist。
- UserSpace 按 owner 隔离运行时依赖。
- Store 查询显式带 user ID。
- internal RPC 再次校验 source/target ownership。
- workspace 按 Agent/session 分区。
- sub-agent 禁止直接外发 message/media。

### 12.3 当前安全缺口

- OpenAI handler 自己的 `resolveAgent` 没有调用 `Identity.CanAccessAgent`。若启用 `/v1`，API key 可能绕过 Agent allowlist 访问同一用户下其他 Agent。
- WebSocket 在 upgrade 前不鉴权，`CheckOrigin` 恒为 true。
- 统一 `policy.Engine` 未接入工具 executor。
- Skill 是进入 prompt 的远程内容，Plugin 是本机子进程，二者都需要额外供应链控制。
- 错误文本和响应时延可能形成 Agent 枚举侧信道。
- 本地 `runtime-benchmark-tenant.json` 含明文 API key，应轮换并移除，不应提交或分享。

## 13. API 与 Channel：不同入口，不同语义

### 13.1 管理台 REST/SSE

`internal/setup/handlers.go` 及同目录下以 `handlers_` 开头的文件提供状态、Agent、Session、Skills、Files、Provider、Channel、Cron、Plugin 等 REST API。

聊天流使用 POST SSE。后端事件 channel 容量 32，turn 上限 2 小时。连接写失败或浏览器 context 取消时，handler 取消 Agent context 并 drain 事件 channel，避免生产者因无人读取而阻塞。

这也修正了旧交接文档的过时描述：当前浏览器断连会取消执行，不再使用 `context.WithoutCancel` 让任务后台继续。

### 13.2 OpenAI-compatible API 的实际边界

`internal/api/openai.go` 实现 `/v1/chat/completions`，但当前默认启动装配很可能没有注册 `/v1/chat/completions` 与 `/v1/agents`：

- `runGateway` 构造 API 配置时只填 Port/Bind。
- `internal/api/server.go:69` 要求 `Enabled=true` 才注册路由。
- 当前源码没有看到其他赋值路径。

即使手动启用，它也只是有限兼容：

- 只取请求中最后一条 `role=user` 消息。
- 历史依赖 `x-fastclaw-session-key` 对应的服务端 Session。
- 请求 `model` 只改变响应标签，不改变 Agent 实际模型。
- 输出流按 round 缓冲，不是 Web 的逐 token 流。
- 当前存在前述 API key Agent ACL 校验缺口。

### 13.3 WebSocket

`internal/api/websocket.go` 暴露独立 `req/res/event` envelope，当前只实现 `connect` 和 `agents.list`，不是聊天传输面，现有 Next.js 控制台也没有使用它。

WebSocket upgrade 后才用 connect frame 的 Bearer token 鉴权。`agents.list` 重建 Identity 时丢失 `APIKeyAgents`，普通 API key 的列表可能被过滤为空。

### 13.4 IM Channels 与 Cron

Telegram、Discord、Slack 等 Channel 把平台消息转换为统一 `bus.InboundMessage`；Agent 结果再通过 `OutboundMessage` 返回渠道。

Cron 本质上也是消息生产者：到时生成任务，进入 Gateway/Agent，而不是把业务逻辑直接写进 scheduler。

## 14. Web 前端：页面、状态与流式状态机

### 14.1 页面架构

前端采用 Next.js App Router，没有 Redux/Zustand。状态主要由页面级 `useState/useRef`、Context、URL query 和浏览器事件协作。

根布局：

```text
ThemeProvider -> AuthGuard -> AppShell -> ActAsBanner
```

顶层页面覆盖 overview、agents、chat、models、skills、providers、channels、API keys、cron、plugins、tools、settings 和 admin/users。

Agent 子页面包括 chat、chats、customize、skills、models。`sessions` 页面目前只是占位，真实会话管理在 `chats`。Sidebar 的 Agent 子路由 allowlist 还缺少 `chats`，进入该页会退回平台导航语义。

### 14.2 前端 API 单一入口

`web/src/lib/api.ts` 同时承担 REST client、auth header/cookie 注入、DTO、文件上传、Session API 和 SSE parser，是理解前后端契约的第一入口。

Web UI 主凭证是 cookie session，可选 bearer token 保存在 `localStorage.fastclaw_token`。`apiFetch` 注入 Authorization，并固定 `credentials: "same-origin"`。

### 14.3 为什么不用 `EventSource`

聊天需要 POST JSON body、附件上下文和 AbortController，因此使用：

```text
fetch(POST /api/chat/stream)
  -> response.body.getReader()
  -> byte buffer
  -> 按 SSE 空行分帧
  -> 合并多行 data:
  -> JSON.parse(ChatStreamEvent)
```

客户端必须看到 `done`；若连接直接结束，则视为失败，而不是把半截回答当成功。

### 14.4 流事件如何合并成 UI

`web/src/lib/chat-stream.ts` 的 reducer 使用：

- `turnId`：一次用户发送对应的执行 turn
- `messageId`：定位同一条 assistant/tool message
- `round`：ReAct 轮次
- `seq`：事件顺序和去重

事件大致为：

```text
content_delta -> content snapshot -> tool_call -> tool_result -> ... -> done
```

`createChatStreamBatcher` 用 `requestAnimationFrame` 合并 React 更新，`done/error` 强制 flush，减少 token 级 setState 的渲染压力。

### 14.5 一次前端发送

```text
AgentChatPage.handleSend
  -> 将 session 固定到 ?session=
  -> 上传附件到 session workspace
  -> 记录执行前文件快照
  -> sendChatStream
  -> backend resolveAgent
  -> Agent.HandleWebChatStream / runTurn
  -> ChatEvent SSE
  -> batcher + reducer
  -> 更新同一回答气泡
  -> done 后重新拉 workspace
  -> diff 新产物并挂到消息
  -> 刷新 session list
```

URL 中的 session ID 是刷新恢复和避免 Next remount 丢会话的关键。

### 14.6 Stop 与刷新

Stop 没有独立 endpoint，按钮执行 `AbortController.abort()`：

```text
AbortController
  -> fetch cancelled
  -> r.Context().Done()
  -> cancel Agent/provider/tool context
  -> pad orphan tool results
  -> frontend mark running tool as stopped
```

页面使用 generation ref 和各请求自己的 AbortController，防止切 Agent、切 session 后旧请求继续写入新页面状态。

刷新后页面从 URL 恢复 session，重新请求 history 和 workspace。Sidebar 监听 `fastclaw:sessions-changed` 刷新会话列表。

## 15. 三条最重要的完整时序

### 15.1 Web 单 Agent 流式聊天

```text
Browser
  -> POST /api/chat/stream
  -> auth middleware / resolveAgent
  -> UserSpace agent lookup
  -> HandleWebChatStream
  -> runTurn
  -> Session.Get + Append(user)
  -> BuildSystemPrompt
  -> Provider.ChatStream
  -> content_delta SSE
  -> model emits tool_call
  -> Registry / SDK executor
  -> Session.Append(tool result)
  -> next Provider round
  -> Session.Flush
  -> done SSE
  -> frontend workspace diff + session refresh
```

### 15.2 父 Agent 委派子 Agent

```text
Parent Provider returns spawn_subagent
  -> SDK bridge
  -> spawn tool validates agentId/task
  -> spawner adds timeout and hides ChatEvents
  -> MessageBus.CallInternal registers correlation + wait edge
  -> Gateway validates owner/source/target/CallPath
  -> TaskQueue.SubmitInternal reuses or creates root execution
  -> Child Agent gets isolated subagent session
  -> Child runTurn executes
  -> completion ResolveInternal
  -> parent receives ToolResult
  -> parent Provider synthesizes final response
```

### 15.3 浏览器 Stop

```text
User clicks Stop
  -> AbortController.abort
  -> SSE reader throws AbortError
  -> server request context cancelled
  -> provider/tool context cancellation
  -> Agent defer repairs tool history
  -> server drains event channel
  -> frontend generation guard rejects late events
  -> session remains usable for next turn
```

注意：Web 直调 Agent，所以 Stop 链路不经过 TaskQueue；Channel/sub-agent 的取消才会同时涉及 Queue task context。

## 16. 并发、一致性与故障语义

### 16.1 并发边界

| 边界 | 当前机制 | 代价/限制 |
|---|---|---|
| Channel 根任务 | Queue semaphore | 只覆盖 Queue 路径 |
| 单 chat lane | FIFO queue | 保证顺序，降低同 lane 并行度 |
| 单 Agent | `turnGate` | 所有 session 串行 |
| 内部任务 | 256 slots | 满时立即失败 |
| internal RPC | 256 pending | 防无限等待，仍是进程内 |
| Web events | channel size 32 + drain | 慢消费者仍需正确取消 |
| Session DB | 每次 Get 刷新 + Flush 屏障 | 增加数据库访问 |

### 16.2 错误分层

排障时按层定位：

1. **Provider error**：HTTP、SSE parse、模型协议、限流。
2. **Tool error**：参数、sandbox、外部服务、MCP/plugin。
3. **Agent error**：ReAct 上限、历史不合法、prompt/skill。
4. **Queue error**：capacity、timeout、cancel、panic，仅 Queue 路径。
5. **Routing error**：owner、target、CallPath、wait cycle。
6. **Transport error**：浏览器断开、SSE write、Channel send。
7. **Persistence error**：Session/Store/Workspace 写入失败。

不要把所有失败都归因于“模型不稳定”。Agent Eval 的价值正是把失败归到正确层。

## 17. 测试与评测：不要混成一件事

### 17.1 当前核心测试

当前 `HEAD` tracked 的核心测试主要集中于：

- Agent 真流式 loop
- `spawn_subagent`
- MessageBus internal RPC
- Provider stream parser
- Sandbox lifecycle
- TaskQueue

它们覆盖近期高风险改造，但 config、store、session、plugin、MCP、skills 缺少专项测试。Gateway ownership、完整内部调用链、多 pod 和真实 Provider fault 也有集成测试空白。

本次文档核对期间执行：

```text
go test ./internal/... ./cmd/...
```

当前核心包测试通过。

直接执行 `go list ./...` 会被本地未跟踪的 `project-report/analysis/main.go` 阻断，因为它引用当前 `HEAD` 不存在的 `internal/eval`。这是工作树混入实验分支消费者导致的基线问题，不是核心包测试失败。

### 17.2 Eval Harness 的定位

完整 Harness 位于本地 Git ref `codex/eval-runtime-harness`，不在当前工作树。该分支包含：

- suite/case/defaults/report 类型
- strict YAML 加载
- runner 与 HTTP executor
- exact/contains/regex/JSON/tool trace/state/communication grader
- BFCL、tau-bench、SWE-bench 接入
- multi-agent team/solo baseline
- trace、usage、latency、cost 与 critical path

正确关系是：

```text
FastClaw Runtime = 被测系统
Eval Harness     = 负载生成、证据采集、评分和对比系统
```

### 17.3 当前本地 benchmark 如何解读

| 产物 | 通过情况 | Tokens | p50 latency |
|---|---:|---:|---:|
| `runtime-pilot.json` | 0/8 | 1,274,742 | 110.1s |
| `runtime-pilot-optimized.json` | 4/8 | 72,414 | 43.3s |
| `runtime-pilot-optimized-v2.json` | 8/8 | 73,729 | 46.0s |
| `runtime-smoke-optimized.json` | 1/2 | 未作为正式结论 | 未作为正式结论 |

这些未跟踪产物适合说明调优过程，不足以单独证明统计泛化性。正式报告至少还需要 commit、脏工作树状态、suite/case 版本、模型/provider 参数、环境、repetitions、seed、grader 版本、失败分母、原始 trace 与成本来源。

## 18. 金融实验资产与核心框架的关系

金融与赛事应用是 FastClaw 的验证场景，不是核心运行时本身。

完整 `finance-tools` 插件在 `codex/finance-agent-runtime` 分支，使用 Python JSON-RPC 子进程和 SQLite 保存 tenant-isolated thesis/watchlist/event state。当前工作树没有其源码，同时主干 Gateway 也尚未接入 plugin tool adapter。

`evals/finance_e2e/STAGE2-EXPERIMENT-PROTOCOL.md` 的目标是评估检索、证据分配、专家分析、综合与 telemetry，不是预测收益、执行交易或提供投资建议。协议定义了 Solo staged、Team shared retrieval、Team raw context、fixed seed、顺序随机化、case/repetition/session 隔离，以及基础设施错误、429、证据审计、成本和时长停止条件。

学习时应把金融系统看成“给运行时施加真实复杂负载的应用层”，而不是用业务结果替代运行时正确性测试。

## 19. 当前实现的主要技术债

按影响排序：

1. **多 Agent 并行度不足**：`spawn_subagent` 未进入 concurrency-safe 列表，同一 target 和 Agent gate 又重复串行。
2. **单进程内部调度**：MessageBus/TaskQueue 不跨 pod、不持久化，崩溃后 pending 调用不可恢复。
3. **HTTP 调度语义不统一**：Web/API 绕过 Queue，Queue 观测和限流不覆盖所有入口。
4. **OpenAI 路由默认未启用**：实现存在，但启动配置没有设置 `Enabled=true`。
5. **OpenAI Agent ACL 缺口**：handler 没调用 `Identity.CanAccessAgent`。
6. **统一工具策略未接线**：policy engine 不在 executor 主链。
7. **Plugin tool/hook 未装配**：adapter 存在但 Gateway 未注册。
8. **Gateway head-of-line blocking**：external/internal 共用单消费循环。
9. **错误结构化不足**：Agent 内错误常折成字符串，影响重试与自动归因。
10. **MCP HTTP 生命周期不完整**：缺 context/timeout/session/SSE 语义。
11. **UserSpace 生命周期泄漏风险**：淘汰不关闭 SandboxPool。
12. **测试分布不均**：Agent/Bus/Queue/Provider 较强，Store/Config/Plugin/MCP 较弱。
13. **实验资产污染工作树**：当前 `./...` 枚举被跨分支 `internal/eval` 引用阻断。

## 20. 推荐学习路径

### 第一阶段：单 Agent 心智模型

1. `internal/provider/provider.go`
2. `internal/agent/loop.go`
3. `internal/agent/events.go`
4. `internal/session/manager.go`
5. `internal/agent/tools/registry.go`
6. `internal/agent/sdkbridge.go`

目标：解释一轮“模型产生 tool call，工具结果如何进入下一轮模型”。

### 第二阶段：一次 Web 流

1. `web/src/app/agents/[id]/chat/page.tsx`
2. `web/src/lib/api.ts`
3. `web/src/lib/chat-stream.ts`
4. `internal/setup/handlers.go`
5. `internal/agent/loop.go`

目标：解释 `content_delta` 到 React 气泡更新，以及 Stop 如何向下传播。

### 第三阶段：多 Agent

1. `internal/agent/tools/subagent.go`
2. `internal/gateway/routing.go`
3. `internal/bus/internal.go`
4. `internal/taskqueue/queue.go`
5. `internal/gateway/gateway.go`

目标：不看文档也能画出 parent -> bus -> gateway -> queue -> child -> reply，并解释首层 internal task 何时建立 root execution、嵌套任务何时继承且免重复占槽。

### 第四阶段：控制面与扩展

1. `internal/config/config.go`
2. `internal/gateway/userspace.go`
3. `internal/store/store.go`
4. `internal/store/database.go`
5. `internal/agent/skills.go`
6. `internal/mcp/manager.go`
7. `internal/plugin/manager.go`

目标：判断一个“代码里看得见的能力”是否真的在启动链上完成装配。

### 第五阶段：测试和 Eval

1. 阅读 `internal/bus/internal_test.go` 与 `internal/taskqueue/queue_test.go`。
2. 为 owner ACL、Gateway 全链路和 Stop 竞态补测试设计。
3. 切到 Eval Harness 分支理解 suite -> executor -> grader -> report。
4. 对同一 case 比较 team 与 solo，同时看 outcome、latency、tokens、cost/success。

## 21. 关键术语速查

| 术语 | 在本项目中的准确含义 |
|---|---|
| Agent | Provider + prompt/context + tools + session/memory 的执行单元 |
| UserSpace | 按用户隔离并缓存的一整套 Agent 运行时依赖 |
| ReAct | 模型推理、工具调用、结果回填、再次推理的循环 |
| Session | 一段对话的消息与工具协议历史 |
| Memory | 跨会话长期信息文件/记录 |
| Workspace | 上传文件和工具生成物空间 |
| Skill | 以 `SKILL.md` 为核心、注入模型上下文的能力说明包 |
| MCP | 连接外部工具 server 的协议客户端 |
| Plugin | stdin/stdout JSON-RPC 子进程扩展 |
| MessageBus | 外部消息 channel 加进程内 internal RPC |
| TaskQueue | 按 lane 排队、限制 Channel 根任务并发、执行 internal task |
| Root execution ID | 让父子 Queue 任务共享一次根执行配额的标识 |
| CallPath | 当前 delegation 祖先 Agent 列表 |
| Wait graph | 检测不同执行间动态相互等待的图 |
| ChatEvent | 管理台流式展示的版本化事件 |
| Provider | OpenAI/Anthropic 等模型协议适配器 |

## 22. 最终理解检查

读完源码后，应能独立回答：

1. 为什么 Web 使用 POST fetch SSE，而不是 `EventSource`？
2. 为什么 `done` 必须晚于 `Session.Flush()`？
3. 为什么 Stop 可能破坏下一轮 tool protocol，系统如何修复？
4. 哪些入口经过 TaskQueue，哪些直调 Agent？
5. 为什么子 Agent 不能直接调用目标 `HandleMessage`？
6. `CallPath` 与 wait graph 分别防什么环？
7. 为什么内部任务不能再次占 root semaphore？
8. 当前多个 `spawn_subagent` 是否真正并行？
9. Skill、MCP 和 Plugin 的进程边界有什么不同？
10. 为什么 adapter 存在不代表功能已接线？
11. UserSpace、Store user ID 和 Agent allowlist 如何共同形成租户边界？
12. Web SSE 与 OpenAI SSE 的流语义为什么不同？
13. 当前哪些能力属于核心 `HEAD`，哪些只存在于实验分支？
14. 一次失败应如何归因到 Provider、Tool、Runtime、Transport、Store 或 Grader？

如果这些问题都能沿源码给出答案，就具备继续修改 FastClaw 核心链路的基础。

## 附录 A：高价值源码索引

| 主题 | 文件 |
|---|---|
| CLI 与 Gateway 启动 | `cmd/fastclaw/main.go` |
| Agent 主循环 | `internal/agent/loop.go` |
| Agent 流事件 | `internal/agent/events.go` |
| System prompt/context | `internal/agent/context.go` |
| Tool Registry | `internal/agent/tools/registry.go` |
| SDK bridge | `internal/agent/sdkbridge.go` |
| Sub-agent 工具 | `internal/agent/tools/subagent.go` |
| Internal RPC | `internal/bus/internal.go` |
| Message bus | `internal/bus/bus.go` |
| Gateway routing | `internal/gateway/routing.go` |
| UserSpace 装配 | `internal/gateway/userspace.go` |
| Task queue | `internal/taskqueue/queue.go` |
| Provider abstraction | `internal/provider/provider.go` |
| OpenAI adapter | `internal/provider/openai.go` |
| Anthropic adapter | `internal/provider/anthropic.go` |
| Session manager | `internal/session/manager.go` |
| SQL session adapter | `internal/session/store_adapter.go` |
| Store interface | `internal/store/store.go` |
| Database schema/migration | `internal/store/database.go` |
| Runtime config | `internal/config/config.go` |
| Startup env | `internal/config/env.go` |
| Skills loader | `internal/agent/skills.go` |
| Skill installer | `internal/skills/install.go` |
| MCP manager | `internal/mcp/manager.go` |
| Plugin manager/process | `internal/plugin/manager.go`、`internal/plugin/process.go` |
| Web chat handler | `internal/setup/handlers.go` |
| Setup server | `internal/setup/server.go` |
| OpenAI-compatible API | `internal/api/openai.go` |
| WebSocket API | `internal/api/websocket.go` |
| Frontend API/SSE parser | `web/src/lib/api.ts` |
| Frontend stream reducer | `web/src/lib/chat-stream.ts` |
| Agent chat page | `web/src/app/agents/[id]/chat/page.tsx` |

## 附录 B：文档与版本边界

- `README.md`：产品级快速说明，部分配置/存储描述落后于当前数据库主路径。
- `PROJECT-HANDOFF.md`：内部 MessageBus/TaskQueue 改造交接，适合了解近期变更。
- `FastClaw-项目面试拷打补充.md`：问题驱动的边界与面试表达，不是源码导览。
- `/Users/wangzheyu/PROJECT-HANDOFF.md`：跨分支、实验和历史问题总交接，包含多个时间点与本地资产，部分断连语义已经过时。
- 本文：以 `792417b` 当前源码为中心，将核心、实验分支与未跟踪产物分开说明。
