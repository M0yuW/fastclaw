# 交接文档：为 Go Runtime 补上后端工具策略（feat/enforce-agent-tool-policy）

日期：2026-08-11（2026-08-12 补记合并与 PR）
分支：`feat/enforce-agent-tool-policy`
远端：已推到 `origin`（`git@github.com:M0yuW/fastclaw.git`）
PR：**https://github.com/M0yuW/fastclaw/pull/5 → `m0yuw-project`，OPEN / MERGEABLE / CLEAN，待合入**
状态：**代码全部完成、已合上游、已推送、PR 已开；唯一未做的是把配置写进线上数据库**（项目已停，见 §5）

原本基于 `m0yuw-project` = `792417b`，但目标分支在开发期间前进了 8 个提交到 `99993bb`
（一个大的 eval harness）。已把上游合进本分支（`2a76cfa`），三处冲突手工解决，见 §2.5。
**本文中所有行号均为合并后（`2a76cfa`）的值。**

---

## 1. 要解决的问题

通用足球总控 agent（`agt_3b64820e301b55be2096`）从不调用 `spawn_subagent`，
自己把活干了。

根因不是"模型不听话"，而是**后端没有任何工具策略强制**：

- `policy.CheckTool()` 全仓零调用方
- `rc.PolicyPreset` 被解析出来，但没人读
- 根本不存在 `delegate-only` 预设

也就是说 SOUL 里"必须调用专家"这句话只是**建议**。提示词是建议，
只有后端拒绝才是约束。这是本分支的全部立论。

---

## 2. 五个提交做了什么

```
29c33b9  feat(policy): enforce per-agent tool policy at definition and execution
52fc862  feat(tools): add structured ledger tools and allow them under delegate-only
f308a20  fix(skills): bound football HTTP calls to their stated timeout
5d320ae  feat(scripts): lock the football coordinator to delegate-only
ccffd2c  docs: hand off the agent tool policy work
2a76cfa  Merge m0yuw-project into feat/enforce-agent-tool-policy
```

### 2.1 `29c33b9` — 双闸门强制

从 `codex/finance-e2e-study` 回合并策略预设与 hook 时序修复。

关键设计：**一个 per-turn `turnRegistry`，喂两个闸门**

- `turnRegistry.Definitions()` → 模型看不见被禁的工具
- 同一个 `turnRegistry` 传给 `executeToolsConcurrently` → 伪造的调用也执行不了，
  报 "unknown tool"

代码位置：`internal/agent/loop.go:688`
（`a.filterByPolicy(toolRegistryFromContext(ctx, a.registry))`，合并后的形态见 §2.5）。

**时序坑（务必保留）**：`Registry.Filter` 是浅拷贝 + 新 `tools` map，
保留闭包和运行期接线，但**不会观察后续的 setter 调用**。所以必须在
per-turn 接线（`bindSession`，`loop.go:605`）**之后**再 filter（`loop.go:688`）。
顺序颠倒会得到一个没接 session 的 registry。

`CheckTool` 语义：deny 优先（`"*"` 匹配全部）→ 若 `len(Allow) > 0` 则名字必须在里面
→ 否则不限制。

### 2.2 `52fc862` — 结构化账本工具

新增 `internal/agent/tools/ledger.go`（`ledger_append` / `ledger_report`），
并把它们加进 `DelegateOnlyPolicy` 的 Allow 列表。

**为什么必须先有这个**：总控被锁成 delegate-only 之后就没有 `write_file` 和
`exec` 了。如果不给它结构化记账，它写不了账本；为了写账本又得把
通用工具面还给它，那这个预设就白锁了。理由写在 `defaults.go` 的注释里：
读写"自己的结论记录"是编排，不是取证，所以不破坏"每条事实都来自专家"这条不变量。

**为什么不是"用 write_file 写 JSON"**：自由格式的写法每次都会给同一个
subject 追加一行新记录。把唯一键存进文件本身，第二次写入在构造上就是更新。

- 唯一键默认 `["subject","date"]`，可由调用方指定；键存在文件里
- 拒绝改键（已有行的身份会变）
- 每个"解析后的路径"一把 mutex（`sync.Map`），8 路并发追加不丢行（有测试）
- 三路存储开关，镜像 `write_file`：`workspaceStore`（云、按 session）→
  `sandbox.Executor`（容器）→ 宿主机 `userRoot`
- 只接受工作区**相对**路径；拒绝绝对路径、`..`、身份文件（SOUL.md 等）、`skills/`
- 能读老的裸 JSON 数组（provisioning 脚本 seed 的就是 `[]`），其他内容大声报错

测试：`ledger_test.go` 14 个、`ledger_storage_test.go` 5 个、
`policy_contract_test.go` 里有 `TestDelegateOnlyLedgerRoundTrips`
（在 delegate-only 下真的 append + report 一遍）。

### 2.3 `f308a20` — 足球 Skill 的 HTTP 超时

**这是本分支里最容易被误判的一个 bug，测量数据都在。**

`urllib.request.urlopen(url, timeout=N)` 的 timeout 是**按连接尝试**计的，
不是按调用。`socket.create_connection` 会把 `getaddrinfo` 返回的每个地址
都走一遍，每个都花满 timeout。

实测：

| 观察 | 数值 |
|---|---|
| 一次成功的 `timeout=25` 请求 | **51.7 秒** |
| 一次 `timeout=90` 的请求 | **151 秒** |
| DNS | 0.0086 秒（不是 DNS） |
| 同进程连续两次同 URL | 0.98s 然后 60.92s（不是常规限流） |
| 三个 anycast IP 单独探测（8s 预算） | `172.67.72.25` 0.20s / **`104.26.11.201` 超时** / `104.26.10.201` 0.21s |
| 三次调用的阶段拆解 | `connect=150.22 / 0.20 / 75.22`，`tls≈0.44`，`first_byte≈0.2-0.4`，`body=0.00`，全部 HTTP 200 |
| 机制验证 | 3 个黑洞地址 × `timeout=3` = **9.01 秒** |

结论：`www.thesportsdb.com` 解析出 3 个 Cloudflare anycast 地址，
其中一个在本网络丢弃 SYN；**耗时 100% 在 connect**，服务器本身 0.2 秒就应答。
解析顺序在不同进程间会变，所以症状是间歇性的——这正是它一直没被定位的原因。

对 agent 的实际伤害：工具调用看起来卡死一分半，模型于是得出"主数据源不可用"
的结论，而数据源其实好得很，只是排在一条死路后面。

修复：新增 `skills/football-data-toolkit/scripts/common/http_fetch.py`

- 一个地址一个地址地试，首轮每个地址 4 秒预算（`FAST_CONNECT_TIMEOUT`）
- 整次调用（含重试）共享**一个** deadline，声明的 timeout 是真上限
- 只有 `kind == "connect"` 且剩余 ≥ 1 秒时才走第二轮慢速 pass，
  所以"网络慢但活着"仍然能成
- 只允许 https；只跟随同 host 跳转，跨 host 跳转按 `http` 错误拒绝
  （防止 provider 端改动把已审的请求引到未审的 host）
- 传输失败归为五类：`timeout` / `connect` / `http` / `too_large` / `malformed`

**效果**：代表性请求 51.7s → 五次连续运行 9.15 / 1.03 / 12.97 / 4.98 / 8.96 秒。
死路还在走，只是变便宜了。

五个脚本全部迁移完：

| 脚本 | 地址数 | 迁移前 | 现在 |
|---|---|---|---|
| `thesportsdb_data.py` | 3 | 25s × 3 | `REQUEST_TIMEOUT = 20.0` |
| `odds_data.py` | 4（最坏） | 25s × 4 | `20.0`，用 `fetch_json_with_headers` 取配额头 |
| `espn_data.py` | 2 | 25s × 2 | `15.0`（`--match`/`--form`/`--discipline` 会连发多次） |
| `sporttery_data.py` | 2 | 30s × 2 | `20.0` |
| `match_data.py` | 3 | 25s × 3 | `20.0` |

`espn_data.py` 的 403→curl 回退也一并处理：加了 `--connect-timeout 4`
配合 `--max-time`，让 curl 有同样的死路行为；同时把 403 的识别从
`urllib.error.HTTPError.code` 换成 `FetchError.kind == "http" and status == 403`，
其他失败保持各自的分类。

**新增 `fetch_json_with_headers`** 是因为 `odds_data.py` 要读
`x-requests-remaining` 之类的配额头；返回的 header 名统一小写，
这样查表不依赖 provider 的大小写习惯（有测试）。

错误码映射刻意保持了各脚本原有的 `unavailable` / `rejected` 语义：
**"没拿到应答" → `unavailable`**（数据源没答，赛事本身没问题），
**"拿到了但用不了" → `rejected`**。`thesportsdb_data.py` 的 `fetch()` 是靠
code 里含不含 `"request"` 来分流的，新 code 是照着这个挑的，别乱改名。

测试：`skills/football-data-toolkit/scripts/common/test_http_fetch.py`，
13 个，**纯标准库 unittest**（本机没有 pytest，全仓也没有既存 Python 测试）。

```bash
cd skills/football-data-toolkit/scripts && python3 -m unittest common.test_http_fetch -v
# Ran 13 tests in 20.997s / OK
```

不碰任何真实数据源：成功路径用本地自签 TLS 服务器（`openssl` 现生证书，
`setUpClass` 里 monkeypatch `ssl.create_default_context` 信任它，
`tearDownClass` 还原）；死路路径用 `10.255.255.1`（不可路由的 RFC1918，
**丢 SYN 而不是回 RST**——已单独验证：1s 预算耗 1.00s，3s 预算耗 3.00s。
如果它是快速拒绝，那把 per-address 预算删掉测试也会过，测试就没意义了）。

`TestDeadRouteHandling` 通过替换 `http_fetch._addresses` 来构造地址列表，
钉住三条性质：活地址排在两个死地址后面仍然很快到达、全死时总预算是真上限、
第一个死地址不吃掉整个预算。

**注意**：测试 harness 在 `setUpClass` 里全局替换了 `ssl.create_default_context`，
而 `http_fetch._one_attempt` 调的就是这个符号。以后加测试如果要 patch
`socket.getaddrinfo`，记得还原。

### 2.4 `5d320ae` — 把总控锁上

`scripts/create_general_football_team.py`：

- `AgentSpec` 新增 `policy_preset` 字段
- 新增 `_defaults(spec)`，只给总控写 `"policy": "delegate-only"`；
  六个专家**故意**不写（它们才是取证的）。空串和不存在语义相同，
  所以选择不写而不是写空串
- 改写 SOUL 第 5 条

**SOUL 那处改动是必须的，不然锁上就崩**：原文写的是绝对路径
`~/.fastclaw/workspaces/{COORDINATOR_ID}/football/ledger.json`，
但 `ledger_append` 只接受工作区相对路径，绝对路径直接拒。
锁上之后模型第一次写账本就会被拒。现在写的是 `football/ledger.json`，
并明确固定键 `["competition","season","date","match"]`，同时提到 `ledger_report`。

另加了一节"工具边界"，告诉总控它能碰什么、不能碰什么，以及
**工具被拒时应该说缺什么，而不是改写请求去绕开**。限制可见时模型的行为明显更好。

### 2.5 `2a76cfa` — 合上游，三处冲突

`m0yuw-project` 在本分支开发期间前进了 8 个提交（`792417b` → `99993bb`），
加了一个大的 eval harness（`internal/eval/`、`internal/evaltenant/`、
`internal/taskqueue/`、`internal/setup/` 等）。`merge-base` 仍是 `792417b`，
三个文件冲突——因为**目标分支独立实现了同一个特性**。

**`internal/policy/defaults.go`（最重要的一处）**：目标分支自己也加了
`NoToolsPolicy()` 和 `DelegateOnlyPolicy()`，两个 `LoadPreset` 分支一模一样，
但它的 Allow 列表只有 `spawn_subagent`：

```go
Description: "Allows only spawn_subagent",
Tools: ToolsPolicy{Allow: []string{"spawn_subagent"}},
```

**保留我们三个名字的版本**（`spawn_subagent`、`ledger_append`、`ledger_report`）。
理由就是 §2.2：delegate-only 的总控没有 `write_file` 和 `exec`，
没有账本工具它就记不了账，为了记账又得把通用工具面要回去，那预设就白锁了。
**以后再遇到这个冲突，不要取上游的单工具版本**——没有本文上下文的人很容易
"顺手解决"成那样，然后总控第一次写账本就挂。

**`internal/agent/loop.go`**：两边都要。上游给 eval harness 加了
`ContextWithToolRegistry`（`internal/agent/tool_context.go`），让一次请求可以
带自己的 registry 而不污染 agent 共享的那一份。合并后的形态是**先取 request-scoped
registry，没有就退回 agent 自己的，然后再按 policy 收窄**：

```go
turnRegistry := a.filterByPolicy(toolRegistryFromContext(ctx, a.registry))
```

为此把 filter 逻辑抽成 `filterByPolicy(base *tools.Registry)`（`loop.go:409` 附近），
`allowedRegistry()` 变成 `a.filterByPolicy(a.registry)` 的薄封装，
两条路径共用一个 filter。上游的 identity contract 校验、usage trace
（`RecordModelCall`）、`UpdateConfig` 里的 `SetRequiredIdentityFiles` /
`SetToolGuidance` 全部保留，我们的 `agent tool policy loaded` 日志也保留。

**`internal/agent/tools/registry.go`**：合并两份 `NewEmptyRegistry` 注释；
`Filter` 的注释取我们的版本，因为它记着那条迫使 filter 必须在 `bindSession`
之后构建的 snapshot 语义（§2.1 的时序坑）。`registerBuiltins` 里的
`RegisterLedger(r)` 未被冲突波及。

**合并带来的一个好消息**：上游的 `internal/evaltenant/tenant.go:106` 已经在给它的
benchmark coordinator 写 `policy = "delegate-only"`，所以这个预设合并后立刻有了
第二个消费方。它的 `internal/eval/multiagent_test.go:112` 断言的是 request-scoped
registry（只有 `spawn_subagent` 一个工具），不受我们放宽 Allow 列表的影响。

---

## 3. 必须保留的设计约束

这几条是用户明确纠正过的，不要回退：

1. **总控的正确流程是"每个专家一个批量任务"**：把完整的、已规范化的比赛列表
   一次交给五个核心专家中的每一个，然后把融合后的概率交给 EV 专家。
   **不是每场比赛一个 sub-agent。** 模型自己事后提的"一场一个 sub-agent"是错的。
2. **根因是后端缺强制，不是模型不听话。** SOUL 本身已经写对了。
3. 步骤顺序：账本工具（`52fc862`）必须先落地，再锁总控（`5d320ae`）。
   顺序反了总控写不了账本。

---

## 4. 验证记录

Go 侧（合并后重跑，全部干净）：

```bash
gofmt -l <改动的文件>          # 无输出
go build ./cmd/... ./internal/...   # 无输出
go vet   ./cmd/... ./internal/...   # 无输出
go test  ./cmd/... ./internal/...   # 全 ok
go test -race -count=1 ./internal/agent/... ./internal/policy/...
#   agent 1.900s / tools 1.955s / policy 1.320s  全 ok
go test -count=1 ./internal/eval/... ./internal/evaltenant/... ./internal/api/...
#   eval 3.473s / evaltenant 0.378s / api 0.692s  全 ok（上游新增的包）
```

- 19/19 ledger 测试通过（含并发）
- 4/4 delegate-only 契约测试通过
- 2 个新 policy 预设测试通过

**注意构建范围**：`internal/eval` 现在存在了（上游加的），但
`project-report/analysis/main.go` 对不上它的 API（`MultiAgentBaselineSoloTwoPass`、
`SourceSHA256`、`ForbiddenOutputValues` 都不存在），所以**构建范围照旧**限定在
`./cmd/... ./internal/...`，不能 `./...`。

**`gofmt` 的既存噪声**：`internal/policy/policy.go`、`sdkbridge.go`、
`registry.go`、`web_fetch.go` 在 baseline 就是未格式化的。已核实过
（`git show HEAD:... | gofmt -l` 报，`git diff --stat HEAD --` 空），
不是本分支弄的，刻意没动。

Python 侧：

```bash
cd skills/football-data-toolkit/scripts
python3 -m unittest common.test_http_fetch -v   # 13 tests OK
```

五个脚本的真实冒烟测试（都成功）：

| 脚本 | 耗时 |
|---|---|
| `thesportsdb_data.py --schedule` | 1.17s |
| `espn_data.py --schedule` | 1.62s |
| `match_data.py --schedule` | 8.96s（走到了死路，但便宜） |
| `sporttery_data.py --list-worldcup` | 0.17s |
| `odds_data.py`（无 key）| 0.06s，正确返回 `odds_key_missing` / `unavailable` |

`~/.fastclaw/skills/football-data-toolkit/` 的部署副本已同步，
`diff -rq --exclude=__pycache__` 报 IN SYNC，且在部署位置也跑过 13 个测试和一次真实请求。

`scripts/create_general_football_team.py` 无法在本机直接 `--dry-run`：
它用了 `from datetime import UTC`（需要 3.11），而本机 `python3` 是 3.9.6。
用 `/tmp/check_provision.py` 绕过该 import 验证了新逻辑：
总控 `policy=delegate-only`、六个专家无 `policy` 键、SOUL 里已无绝对路径、
`ledger_append`/`ledger_report` 都在。**要真跑这个脚本需要 Python ≥ 3.11。**

---

## 5. 唯一剩下的事：写进线上数据库

代码全齐了，但**线上库还没锁**。已确认：

```sql
select count(*) from configs where data like '%"policy"%';   -- 0
```

总控当前的 `agents.defaults` 行：

```
id       = sc_general_football_0
scope_id = agt_3b64820e301b55be2096
data     = {"model":"deepseek/deepseek-v4-pro","maxTokens":8192,
            "temperature":0.4,"maxToolIterations":60}
```

需要变成加上 `"policy": "delegate-only"`。同时 `agent_files` 里那份 `SOUL.md`
还是**旧的绝对路径版本**，必须一起换成 `5d320ae` 里的新文案，
否则模型第一次写账本就会被 `ledger_append` 拒。

两条路：

- **A 不可行（已核实）**：重跑 `scripts/create_general_football_team.py` **没用**。
  `provision()` 在 `create_general_football_team.py:306-313` 处，若七个 agent 的
  id 和 name 都已存在就直接 `return {"status": "existing"}`，
  **早于任何 `configs` / `agent_files` 写入**。也就是说它只负责首次建团，
  不负责更新既有行。（脚本里那份新 SOUL 和 `_defaults()` 的价值在于：
  以后重建团队、或换机器部署时是对的。）
- **B（唯一可行）**：Runtime 停着的时候手工改两行。先备份
  `~/.fastclaw/fastclaw.db`，然后：
  1. `configs` 里 `id = 'sc_general_football_0'` 那行的 `data` JSON 加上
     `"policy": "delegate-only"`；
  2. `agent_files` 里 `agent_id = 'agt_3b64820e301b55be2096'` 且
     `filename = 'SOUL.md'` 的 `content` 换成 `5d320ae` 里的新文案
     （从 `scripts/create_general_football_team.py` 的 `AGENTS[0].soul` 取，
     注意里面的 `{DATA_ID}` 等占位符是 f-string，要取插值后的结果）。

  如果嫌手写 SQL 麻烦，也可以给 provisioning 脚本加一个 `--update-existing`
  分支，让它在 "existing" 时改为更新这两张表——这是比手工 SQL 更好的长期做法，
  但本次没做。

**必须在 Runtime 停止时做**，改完重启，然后验证：启动日志应该出现
`agent tool policy loaded`（`loop.go:239-245`，preset 非空才打），
并且总控在被要求做分析时应该真的发出 `spawn_subagent`。

---

## 6. 已知遗留 / 下一步

按优先级：

1. **合入 PR #5**（https://github.com/M0yuW/fastclaw/pull/5 → `m0yuw-project`）。
   状态 OPEN / MERGEABLE / CLEAN，29 文件 / +4962 −27，冲突已在 `2a76cfa` 解决完，
   剩下的只是点合并。合之前**请核对 §2.5 的第一条**：
   `DelegateOnlyPolicy` 的 Allow 列表必须是三个名字。
2. **锁线上库**（§5），这是唯一的功能性缺口。
3. **provisioning 脚本只能建团、不能更新**（见 §5 的 A）。给它加一个
   `--update-existing` 分支是本分支最自然的下一步收尾。
4. **契约测试还不完整**：现有测试覆盖了"delegate-only 下工具面只有三个"
   和"账本能来回跑"，但没有一个端到端测试证明"总控在真实一轮里确实发出了
   `spawn_subagent`"。原计划的第 5 步只算部分完成。上游新增的
   `internal/gateway/subagent_integration_test.go` 和 `internal/eval/` harness
   现在都在树里了，写这个测试比之前容易。

其他：

- `~/.fastclaw/skills/` 的部署副本是**手工 `cp` 同步**的。以后改仓库里的
  Skill 记得再同步一次，或者干脆做个同步脚本。
- 未提交、且按之前的约定**不要提交**的东西：
  `runtime-benchmark-tenant.json`（含 API key）、`plugins/finance-tools/__pycache__/`、
  `project-report/`、`FastClaw-项目面试拷打补充.md`、
  `scripts/com.fastclaw.go.local.plist` 及若干 `runtime-*.json`。
  本次只提交了 `skills/football-data-toolkit/` 和
  `scripts/create_general_football_team.py`，提交前扫过没有字面 key。
- `PROJECT-HANDOFF.md` 里有真实凭据（网关登录口令、`ODDS_API_KEY`），
  不要在输出里回显。

---

## 7. 关键文件索引

| 文件 | 作用 |
|---|---|
| `internal/agent/loop.go:688` | per-turn `turnRegistry`，双闸门的源头 |
| `internal/agent/loop.go:409` | `filterByPolicy`，两条路径共用的 filter |
| `internal/agent/loop.go:605` | `bindSession`，**必须在 filter 之前** |
| `internal/agent/loop.go:239` | 从 `rc.PolicyPreset` 造 engine + 日志 |
| `internal/agent/loop.go:1213` | `UpdateConfig` 时重建 engine |
| `internal/agent/tool_context.go` | 上游加的 request-scoped registry（eval harness 路径） |
| `internal/policy/defaults.go:78` | `DelegateOnlyPolicy()`，含为何放行账本工具的理由 |
| `internal/agent/tools/ledger.go:86` | `RegisterLedger`；账本工具三路存储 + per-path 互斥 |
| `internal/agent/tools/file.go` | 存储路由的模板（照它写的） |
| `internal/agent/policy_contract_test.go` | delegate-only 契约测试（工具面 + 账本往返） |
| `internal/evaltenant/tenant.go:106` | 上游的第二个 `delegate-only` 消费方 |
| `internal/gateway/userspace.go:312` | agent-scope `agents.defaults` 覆盖 `PolicyPreset` |
| `internal/config/config.go:331` | `AgentDefaults.PolicyPreset`，JSON 键是 `"policy"` |
| `skills/football-data-toolkit/scripts/common/http_fetch.py` | 有界 HTTP，模块 docstring 里记着实测数据 |
| `skills/football-data-toolkit/scripts/common/test_http_fetch.py` | 13 个标准库测试，含死路用例 |
| `skills/football-data-toolkit/SKILL.md` | 新增"超时约定"一节 |
| `scripts/create_general_football_team.py` | 团队 provisioning + `_defaults()` + 新 SOUL |
