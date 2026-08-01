# 金融多 Agent Runtime 评测 — 第一轮代码与实验审查报告

| 项目 | 值 |
|---|---|
| 报告日期 | **2026-08-01**（本地 UTC+8；对应 2026-07-31T18:38Z） |
| 审查对象 | FastClaw 金融多 Agent Runtime 评测 |
| 仓库 | `/Users/wangzheyu/fastclaw` |
| 分支 | `codex/finance-agent-runtime` |
| HEAD | `351ee422f25ef86fc3c0159f7894739be95ac1a6` |
| 基线分支 | `m0yuw-project` |
| 工作区状态 | 17 个 modified + 16 个 untracked（审查期间未做任何修改） |
| 审查依据 | `CLAUDE-REVIEW-PROMPT-finance-runtime.md` Prompt 1（只审查，不修改） |
| 审查方法 | 全量源码阅读 + 一次性 Go probe 测试（已删除）+ 从原始 JSON 独立重算 + 三路并行独立审计交叉验证 |
| 平台验证 | `go build ./...` 干净；`go test -count=1 ./...` 退出 0；`go test -race ./internal/agent ./internal/store ./internal/agent/tools` 全部 ok；`python3 -m unittest test_plugin` 10 tests OK |
| 未执行 | 任何真实 gateway / 网络 integration 测试；任何金融实验重跑 |
| 安全约束遵守 | 未读取、未回显 `runtime-benchmark-tenant.json` 中的 API key；未 commit、未 push；未修改任何仓库文件 |

---

## 1. 结论

**代码：修复后可合并。实验结论与 project-report：当前不可对外发布。**

三条独立复算路径（本人的 Go probe、指标/grader 专项审计、从 JSON 的独立数值重算）互相印证出同一个核心问题：**已发布的两个正式实验的 Team 分数，都无法用磁盘上现有的 rubric 复现**；而造成 runtime-r1 那一处 baseline 失败的不是报告所称的 "lexical false negative"，而是一个 grounding 假阳性 bug。此外，并发改动引入了一条会杀死整个 gateway 进程的路径，SQLite 修复没有覆盖真正触发 `SQLITE_BUSY` 的事务形状。

生产 runtime 的核心并发正确性（结果回填、tool_use ID 对齐、取消语义、去重、mutex 保护）经实测是正确的——这部分声称成立。

### 阻塞合并的最小集

`C1`、`C2`、`C4`、`C3`、`H1`、`H2`、`H3`、`H4`、`H5`、`H6`、`H7`。其中只有 `C3` 需要在修好 `C1`/`C2` 之后**重跑一次金融实验**才能报出可信数字。

---

## 2. 十条声称的裁定

| # | 声称 | 裁定 | 依据 |
|---|---|---|---|
| 1 | `solo_two_pass` 是与 Team 接近的两阶段 compute-matched baseline | **成立** | session 共享链已证；r1 真实数据 pass-1 prompt 638–668 token → pass-2 1345–1786 token |
| 2 | `forbidden_output_values` + grounding，违规使 Team 和 baseline outcome 失败 | **部分成立** | 确实双侧 gate，但存在 C1 假阳性；且 H6 只统计 team |
| 3 | 空输出即使 executor 返回 nil error 也作为 baseline error，不进入成功率分母 | **成立** | `runner.go:216-226` + `multiagent.go:599-602`，有测试覆盖 |
| 4 | 报告/compare 增加 compute-matched gain、grounding、分 baseline token/cost/latency | **部分成立** | 字段齐全且成本对账精确，但存在 H6、H7、H9、M5、M9 |
| 5 | 6 个固定时点金融案例 + 3 个真实 Flash specialist | **成立（但需限定）** | specialist 是真 runtime agent；evidence 是 `SOUL.md` 里的 FIN-01..06 字面查表，非检索 |
| 6 | distinct target 的 `spawn_subagent` 可并发；同 target 重复调用仍串行 | **成立** | 实测混合批 + `uniqueSubAgentTargets` 四种畸形输入全部 fail-safe |
| 7 | 修复 tool hook latency 起始时间丢失 | **部分成立** | 索引对齐正确，但时间语义仍错（M1：duration 是批级墙钟） |
| 8 | SQLite 默认启用 WAL、foreign_keys、busy_timeout(5000)，并验证并发 writer 会等待 | **部分成立** | H2 路径子串误判、H3 自定义 DSN 无 WAL、H4 事务形状未覆盖 |
| 9 | required identity file 读取保留底层 store error | **部分成立** | 两条路径都能到调用方；残留 M7（FS 兜底吞错、`ErrNotFound` 消息错） |
| 10 | 真实实验记录 coordinator/sub-agent token、成本、延迟分解 | **成立** | 成本对账到 1.4e-17 |

---

## 3. Findings

按 Critical / High / Medium / Low 排序。每条包含：文件与行号、触发场景、实际后果、为什么现有测试没挡住、最小修复建议。

### CRITICAL

#### C1 · forbidden-assertion 的否定判定被一个引号字符击穿，并且已经污染了已发布结果
**类别：代码 bug**

**位置**：`internal/eval/multiagent.go:1205-1215`（`equalWords`）、`:1217-1248`（`hasNegationScope`）、`:1156-1162`（`trimMatchPunctuation`）、`:1250+`（`normalizeMatchText`）

`equalWords` 与 `hasNegationScope` 直接比较归一化后的原始 token，从不调用 `trimMatchPunctuation`；而 `normalizeMatchText` 的 replacer 不含 `“ ” ‘ ’`，`trimMatchPunctuation` 的 trim 集合 `` ."'[]{}|,;!? `` 也不含弯引号。

**触发场景**（`finance-runtime-formal-r1.json`，`earnings-catalyst-review` / `solo_open_book` 的真实输出，逐字）：

```
... and explicitly states “no trade is authorized”.
```

分词后否定 token 是 `“no` 而不是 `no`，`hasNegationScope` 返回 false，`containsForbiddenAssertion(output, "trade is authorized")` 返回 **true**。

同一缺陷反向也成立——`The desk confirms: "trade is authorized".` 会**漏检**（直引号与短语首 token 粘连）。第二类触发是 markdown 表格行：`|` 既不是 clause 分隔符也不被归一化，`none`/`excluded` 不在否定词表内，因此 `finance-workflow-formal-r3.json` 中

```
| **trade authorized** | — | none | explicitly excluded | rsk-121 |
```

同样误报。clause 级证据：

```
runtime r1 solo_open_book: clause#5  neg=true  " no trade is authorized"
                           clause#21 neg=false "explicitly states “no trade is authorized"
workflow r3 team:          clause#33 neg=true  " no trade authorized"
                           clause#46 neg=false "| **trade authorized** | — | none | explicitly excluded | rsk-121 |"
```

**实际后果**：该 attempt 的三个 FIN-01 milestone 全部通过（rubric widening 前后都通过），`multiAgentOutcomePass`（`:1093-1103`）**仅**因这个假阳性判它失败。这一次翻转是 `multi_agent_solo_open_book_success_rate = 0.8333` 的唯一来源，进而决定了 `multi_agent_fair_collaboration_gain = 0.0`。修掉引号后 solo_open_book 是 6/6；在 r1 当时实际生效的 rubric 下（team 5/6），fair gain 应为 **−16.7pp，而不是 0.0**。`evals/finance-runtime-formal-r1.md` §3.4 把这次失败归因为 `conviction moves from 3 to 4` 的措辞差异，是错的——那个 alternative 当时已经存在（详见 H8）。

**为什么现有测试没挡住**：`internal/eval/multiagent_test.go:201-226` 的 `TestContainsForbiddenAssertionIgnoresNegatedOrUncertainMentions` 只使用无引号散文（`"No refund is authorized until…"`），没有任何 case 把短语放进引号、括号或表格单元格。

**最小修复**：在 `equalWords` 和 `hasNegationScope` 内部对 token 调用 `trimMatchPunctuation`；把 `“ ” ‘ ’` 加入 `trimMatchPunctuation` 的 trim 集合与 `normalizeMatchText` 的 replacer；`|` 同时应作为 clause 分隔符加入 `forbiddenMatchClauses`。已实测：该修改后 r1 真实输出不再产生 violation，且直引号包裹的真实断言仍能被正确检出。

---

#### C2 · milestone grader 完全没有否定/方向感知，断言了相反决策的答案照样 outcome pass
**类别：指标口径 bug**

**位置**：`internal/eval/multiagent.go:879`（`containsAllFold`）、`:1093-1103`（`multiAgentOutcomePass`）、`:603`（每个 baseline 的判定点）、`internal/eval/runner.go:365-369`（`MATeamOutcomeSuccessRate`）

`containsAllFold` 只做归一化子串存在性判定。`multiAgentOutcomePass` = 全部 milestone 通过 AND 无 forbidden assertion，而这是**每个** baseline 以及 `MATeamOutcomeSuccessRate` 的通过标准，因此也是 fair gain 与 compute-matched gain 的标准。

**触发场景**（实测，FIN-01）：

```
FIL-101 shows 18 percent growth and 220 basis points. THS-111: the catalyst is
not confirmed but the invalidation is not observed. We refuse the positive upgrade
review: do NOT move conviction from 3 to 4, do NOT write expected_version 4. No trade.
```

三个 milestone 全过、无 forbidden 命中 → **outcome pass**。FIN-06 用一段平铺直叙否认 contradiction / needs_review / clarification 的文本同样通过。

方向盲同样实测成立（`containsAllFold` 是 per-value 的无序子串匹配）：

| Case | milestone | 应失败的文本 | 实测 |
|---|---|---|---|
| FIN-06 | `filing-claim [FIL-601, 8 billion, 5 billion yuan]` | `capex guidance was RAISED from 5 billion to 8 billion yuan` | pass |
| FIN-02 | `primary-evidence` | `customer C-17 (31 percent of revenue) has RENEWED its contract` | pass |
| FIN-05 | `stress` | `drawdown of 17 percent is comfortably inside the 10 percent risk limit` | pass |

**实际后果**：headline 的 fair gain 与 compute-matched gain 衡量的是"要求的 token 是否出现"，不是"决策是否正确"。注意 `containsAllInOrderFold` 确实对 `conviction from 3 to 4`、`reduced from 8 billion to 5 billion` 有方向敏感性（实测反转文本不匹配），但它只 gate `ma_contribution`，不进入 `multiAgentOutcomePass`。

**为什么现有测试没挡住**：所有测试断言的都是"正确输出通过 / 无关输出失败"，没有一个喂入"词法完整但语义反转"的答案。

**最小修复**：对 milestone value 复用 `hasNegationScope`，要求至少一次非否定的 clause 内出现；或为每个 case 强制配置编码反向决策的 `forbidden_output_values`（`not moving conviction`、`raised from 5 billion to 8 billion` 等）。

---

#### C3 · rubric 在两次正式运行之后被放宽，两个已发布的 Team 分数都无法从磁盘文件复现
**类别：实验设计限制 + 文档事实错误**

**位置**：`evals/multiagent-finance-runtime.yaml`（**完全未纳入版本控制，无 git history**）、`evals/multiagent-finance-workflow.yaml`（工作区已改）、`evals/finance-workflow-formal-r3.md:31`、`evals/finance-runtime-formal-r1.md:135`

用当前 YAML 对已存储的原始输出重新评分（我的 Go probe 与独立 Python 复算端口结果一致）：

```
finance-runtime-formal-r1.json
  FLIP portfolio-concentration-response  team  stored=false  regraded=true
  regraded: solo_open_book 5/6  solo_two_pass 6/6  team 6/6  oracle_team 5/6
  发布值:   solo_open_book 5/6  solo_two_pass 6/6  team 5/6  oracle_team 5/6

finance-workflow-formal-r3.json
  FLIP earnings-catalyst-review          team  stored=true   regraded=false
  FLIP contradictory-primary-evidence    team  stored=true   regraded=false
  regraded: solo_closed_book 0/18  solo_open_book 14/18  team 12/18  oracle_team 14/18
  发布值:   team 14/18
```

即 `multi_agent_compute_matched_gain` 从已发布的 `-0.1667` 移动到 `0.0`。

**时间戳锁定了改动**：JSON 为 12:38 / 14:09 / 14:32，两个 YAML 均为 14:36，runtime 报告 14:38。

**污染范围量化**：`evals/multiagent-finance-workflow.yaml` 在 HEAD 上 `||` alternative 数为 **0**；工作区版本新增了 `solo_two_pass` baseline、全部 pricing、全部 `forbidden_output_values` 和全部 `||`。runtime YAML 携带 23 个额外 milestone alternative、38 个非标准 alternative；其中 35 个在 formal-r1 之前的模型输出里逐字出现过，33 个来自 11:42 / 11:56 的 workflow pilot。**alternatives 是读了模型输出之后写的。**

Leave-one-alternative-out 分析：23 个 milestone alternative 中有 5 个对 formal-r1 的 pass/fail 是 load-bearing。剥离全部 `||` 后同一批输出得分：

| rubric | team | open_book | two_pass | oracle |
|---|---:|---:|---:|---:|
| 当前磁盘 YAML | 6/6 | 5/6 | 6/6 | 5/6 |
| 报告发布值 | 5/6 | 5/6 | 6/6 | 5/6 |
| canonical only（剥离全部 `||`） | 3/6 | 3/6 | 5/6 | 4/6 |

r3 同样：当前 workflow YAML 下 team 12/18（两个 attempt 触发了新加的 forbidden value），HEAD 下 team 10/18、open 9/18、oracle 11/18。

**实际后果**：`evals/finance-workflow-formal-r3.md:31` 声称词表 "frozen before this formal run" —— 对磁盘上的文件不成立。`evals/finance-runtime-formal-r1.md:135` 承认了扩充，但 JSON 与所有派生表格都是扩充前产生的，而 md 把 5/6 表述为 "the reproducible machine-scored result"，任何运行已提交套件的人都无法复现该值。formal-r1 是 **fitted score，不是 validation score**。

**为什么现有测试没挡住**：没有任何机制把 rubric 内容 hash 进 report envelope，也没有 CI 检查 eval YAML 是否被 git 跟踪。

**最小修复**：把两个 YAML 纳入 git；在 report envelope 中记录 rubric 文件的 sha256；在把任一数字当作 validation 分数之前，用冻结的 rubric 重跑。

---

#### C4 · 会 panic 的 tool 现在会杀死整个 gateway 进程
**类别：代码 bug（并发改动引入的可用性回归）**

**位置**：`open-agent-sdk-go@v0.1.0/tools/executor.go:84-93`（`runConcurrent` 的 goroutine）、`:96-167`（`runSingle`）——两处都没有 `recover()`；FastClaw 侧入口是 `internal/agent/sdkbridge.go:56-63`（`toolAdapter.Call`）

**触发场景**：任何 tool 函数 panic（nil map 写入、plugin adapter 里的越界、JSON 断言失败）。实测（注入一个会 panic 的 `read_file`）：

```
panic: probe: tool panic
  agent.(*toolAdapter).Call             sdkbridge.go:63
  tools.(*Executor).runSingle           executor.go:148
  tools.(*Executor).runConcurrent.func1 executor.go:88
created by tools.runConcurrent in goroutine 56
```

**实际后果**：并发化之前，panic 沿调用方 goroutine 展开，`internal/taskqueue/queue.go:305,351` 的 `recover()` 能把它限制在单个 turn 内。现在它起源于 SDK 拥有的子 goroutine，FastClaw 调用栈上**没有任何** `recover()` 能看到它——进程死亡，同时带走所有其他用户的 in-flight turn。这是并发改动引入的新回归，不是既有问题。

**为什么现有测试没挡住**：没有任何测试注册会 panic 的 tool；而且在修复落地前也无法在进程内测试，因为 panic 会杀死 test binary。

**最小修复**：在 FastClaw 自己拥有的 `toolAdapter.Call`（`sdkbridge.go:56`）内 `defer recover()`，返回 `IsError: true` 的 `ToolResult` 并记录 `debug.Stack()`：

```go
func (t *toolAdapter) Call(...) (result *sdktypes.ToolResult, err error) {
    defer func() {
        if r := recover(); r != nil {
            slog.Error("tool panicked", "tool", t.name, "panic", r, "stack", string(debug.Stack()))
            result = &sdktypes.ToolResult{IsError: true, Error: fmt.Sprintf("tool %s panicked: %v", t.name, r)}
            err = nil
        }
    }()
    ...
}
```

### HIGH

#### H1 · 重复或空的 `tool_call` ID 会把一个 tool 的结果静默复制给另一个
**类别：代码 bug**

**位置**：`internal/agent/sdkbridge.go:176-182`

```go
byID := make(map[string]sdktools.ToolCallResponse, len(responses))
for _, resp := range responses {
    byID[resp.ToolUseID] = resp   // last write wins
}
```

**触发场景**：provider（或 `internal/provider` 的 streaming-delta 重组 bug）发出两个共享同一 ID 的 tool call，或发出空 ID。实测：两个 ID 均为 `"dup"`（args 分别 `path=a`、`path=b`）的调用都拿到 `content-of-b`；ID 为 `""` 时同样。

**实际后果**：模型被告知 tool A 返回了 tool B 的输出——在金融工作流里就是一个 sub-agent 的研究被归属到另一个 sub-agent 身上，完全静默，无 error、无日志。另外两个 `tool_result` 携带同一 ID，Anthropic 会以重复 `tool_use_id` 返回 400。

**为什么现有测试没挡住**：`internal/agent/sdkbridge_test.go:56` 用 `"call-" + rune('1'+index)` 生成唯一 ID，从不触发碰撞（顺带：该生成器在 index > 8 时会产出 `':'`，无害但脆弱）。

**最小修复**：检测碰撞并记录 error；配合 consume-once 语义（查完 `delete(byID, tc.ID)`），使第二次重复 ID 得到显式的 "no response" 失败结果而非拷贝。

---

#### H2 · `sqliteDSNWithBusyTimeout` 对整条 DSN 做子串匹配，包含文件系统路径
**类别：代码 bug**

**位置**：`internal/store/database.go:43-52`

```go
if strings.Contains(strings.ToLower(dsn), "busy_timeout") { return dsn }
```

**触发场景 A**：数据目录路径中含该字符串。端到端实测 `NewDBStore("sqlite", "file:/…/busy_timeout/x.db?…")` 得到 `PRAGMA busy_timeout = 0`。任何部署（`busy_timeout` 调试目录、同名 tenant、eval fixture 路径）会静默拿到零超时——正是这次修复要解决的故障，且出现在最不会去看的配置里。

**触发场景 B**：百分号编码绕过 guard。`_pragma=busy%5Ftimeout(1)` 会导致追加第二个 `busy_timeout(5000)`；modernc 会把 `busy_timeout` 排到 pragma 序列最前（`sqlite@v1.48.2/sqlite.go:136-215`），重复项被应用两次且优先级未定义。

**触发场景 C**：`NewDBStore` 用 `dialect == "sqlite"` 精确判定，而 `driverName`（`database.go:54`）对未知 dialect 透传——传 `"SQLite"` 会拿到 sqlite driver 但完全没有 busy_timeout。

**实际后果**：`SQLITE_BUSY` 在这三种配置下完全未被缓解。

**为什么现有测试没挡住**：`internal/store/database_integration_test.go:147-177` 的 `TestDefaultSQLitePragmas` 只走 `New(nil, t.TempDir())` 的默认 DSN 路径；`sqliteDSNWithBusyTimeout` 本身没有任何单元测试。

**最小修复**：解析 query string 而不是扫全串——

```go
func sqliteDSNWithBusyTimeout(dsn string) string {
    query := ""
    if i := strings.IndexByte(dsn, '?'); i >= 0 { query = dsn[i+1:] }
    for _, kv := range strings.Split(query, "&") {
        if v, ok := strings.CutPrefix(kv, "_pragma="); ok {
            if decoded, err := url.QueryUnescape(v); err == nil &&
                strings.HasPrefix(strings.ToLower(decoded), "busy_timeout") {
                return dsn
            }
        }
    }
    ...
}
```

并在 `NewDBStore` 顶部一次性归一化 dialect（`strings.ToLower(strings.TrimSpace(dialect))`）。

---

#### H3 · WAL 与 foreign_keys 只通过 factory 的默认 DSN 字面量生效
**类别：代码 bug**

**位置**：`internal/store/factory.go:20-26`（只在 `cfg.Type == StorageSQLite && dsn == ""` 时拼出带 `_pragma=journal_mode(WAL)` 的 DSN）；`internal/gateway/gateway.go:140-144` 与 `cmd/fastclaw/cmd_admin.go:31-35` 把 `env.Storage.DSN` 原样透传

**触发场景**：任何显式配置了 `storage.dsn` 的安装。实测矩阵：

```
file:<tmp>/p1.db?_pragma=busy_timeout(5000)                            journal=delete busy=5000 fk=0
<tmp>/p2.db?_pragma=busy_timeout(5000)                                 journal=delete busy=5000 fk=0
file:<tmp>/p3.db?cache=shared&_pragma=busy_timeout(5000)               journal=delete busy=5000 fk=0
file:<tmp>/p4.db?_pragma=journal_mode(WAL)&_pragma=busy_timeout(5000)  journal=wal    busy=5000 fk=0
file:<tmp>/p5.db?_journal=WAL&_fk=1&_pragma=busy_timeout(5000)         journal=delete busy=5000 fk=0
```

**实际后果**：自定义 DSN 的安装只拿到 busy_timeout，journal 仍是 `delete`——恰好是产生 `SQLITE_BUSY` 的配置。

**顺带确认的两点**（都对本次改动的收益评估有影响）：

1. 改动前的默认 `?_journal=WAL&_fk=1` 是**完全惰性**的。实测打开 `file:…?_journal=WAL&_fk=1` 报告 `journal_mode="delete" foreign_keys=0 busy_timeout=0`。modernc 的 `applyQueryParams` 只认 `_pragma`、`_time_format`、`_time_integer_format`、`_timezone`、`_txlock`、`_inttotime`、`_texttotime`，未知 key 静默忽略。**即此前所有安装的 WAL 与 FK 都是关的。**
2. `foreign_keys(1)` 当前行为上是 no-op：`migrationSQL()`（`database.go:409-521`）没有声明任何 `FOREIGN KEY` / `REFERENCES`，删除走手工级联（`:614` `DeleteUser`、`:907` `DeleteAgent`）。因此不存在"新约束拒写"或"级联语义变化"的兼容风险，但这个 pragma 除了未来防御外也不带来任何收益。

**为什么现有测试没挡住**：同 H2——只测了默认 DSN 路径。

**最小修复**：把 journal_mode 与 foreign_keys 的注入移入 `sqliteDSNWithBusyTimeout` 同一处，对所有 sqlite DSN 补齐。

---

#### H4 · WAL + busy_timeout(5000) 不能修复 store 实际的事务形状
**类别：代码 bug**

**位置**：`internal/store/database.go:33`（`SetMaxOpenConns(25)`）、`:614`（`DeleteUser`）、`:907`（`DeleteAgent`）

**触发场景**：`DeleteUser` 开的是 deferred 事务（modernc 在未设 `_txlock` 时发裸 `begin`，见 `sqlite@v1.48.2/tx.go:23-24`），先 `SELECT id FROM agents WHERE user_id = ?` 取读快照，再执行写。若期间另一条连接提交，读→写升级失败为 `SQLITE_BUSY_SNAPSHOT`(517)，**`busy_timeout` 对此不会等待**，driver 立即返回，唯一补救是重试。

两次独立实测：

- 孤立 probe：deferred tx → `SELECT COUNT(*)` → 并发 commit → `DELETE`，在 `busy_timeout=5000` 下 **11µs** 就报 `database is locked (517)`。
- 真实 probe：12 个 goroutine 走公开 `Store` API（`SaveSession` / `SaveAgentFile` / `DeleteUser`）打 `New(nil, dir)`，每轮 1–4 次 `DeleteUser` 失败（517 与 5 混合），跨轮不确定。

**实际后果**：本次改动**减少但没有消除**报告中所称已修复的症状。

**为什么现有测试没挡住**：没有任何测试通过 `Store` 接口驱动并发写。`TestIntegrationSQLiteBusyWriterWaits` 用的是两条裸 `INSERT`，没有读后写升级——恰好是 `busy_timeout` 唯一能处理的形状。（该测试自身的设计缺陷见第 6 节第 12 项。）

**最小修复**：sqlite DSN 追加 `_txlock=immediate`，使 `begin immediate` 前置获取写锁，让 `busy_timeout` 覆盖等待。实测：加 `_txlock=immediate` 后真实 probe **3 轮全部 0 错误**，而当前 deferred 配置对照为 2 / 0 / 1 错误。该方案优于 `SetMaxOpenConns(1)`，因为它在 WAL 下保留读并发。注意同库 `internal/store/fts.go:30` 已有 `SetMaxOpenConns(1)` + `// SQLite single-writer` 的先例——若改用该方案需同步修改 H4 相关测试（见第 6 节）。

---

#### H5 · sub-agent parent-turn 去重只在 eval 路径安装，而 tool 描述向模型承诺复用
**类别：代码 bug / 契约不一致**

**位置**：`internal/api/openai.go:174-176`（`agentCtx = tools.ContextWithSubAgentDedup(agentCtx)` 只在 `req.FastClaw.Eval` 为真时执行；grep 确认这是唯一非测试调用点）vs `internal/agent/tools/subagent.go:52`

tool 描述对模型宣称：

> Call each target agent at most once per parent turn; repeated calls reuse the first result.

**触发场景**：生产环境的任何路径——IM channel、cron、web chat、任何非 eval 的 API 请求——都没有这张 dedup map，`makeSubAgentTool` 无条件落到 `spawnSubAgent`。

**实际后果**：并发改动让问题更具体。`uniqueSubAgentTargets` 把重复 target 标为 unsafe → 串行执行，于是同一 agent 的两次调用现在**连续真跑两次**，各付全额 LLM 成本，各自改写该 agent 的 session，第二次还看得到第一次写入的状态。成本与延迟静默翻倍。

**为什么现有测试没挡住**：`internal/agent/tools/subagent_test.go:51` 显式调用了 `ContextWithSubAgentDedup`，测的是机制而非生产接线；`sdkbridge_test.go` 用的 fake tool 完全绕过 dedup 路径。

**最小修复**：在每个 agent turn 都安装 dedup context——自然缝隙是 `internal/agent/loop.go` 构建 turn context 处，或 `internal/gateway` 派发到 `Run` 处，使所有 channel 一致。若 eval-only 是刻意的评分需要，则必须修改 tool 描述，停止承诺复用。

---

#### H6 · grounding accuracy 只统计 team attempt，而 grounding 决定每个 baseline 的通过
**类别：指标口径 bug**

**位置**：`internal/eval/runner.go:201-202`（累加位于 `attempt.MultiAgent` 块内，而该块只由 team 分支填充）、`internal/eval/multiagent.go:962-974`（只从 `gradeMultiAgentAttempt` 到达，唯一调用点 `:527`）、`internal/eval/multiagent.go:603`（baseline 的 grounding 失败被静默折进 `baselineResult.Passed`）、`internal/eval/report.go:129-139`（打印时无 scope 限定词）

**实际后果**：r1 报告 `multi_agent_grounding_accuracy = 1.000, violations 0/28`，而恰恰是一次 grounding violation（C1 的假阳性）判负了 solo_open_book。按 mode 从存储输出重算：

| 范围 | 检查数 | violation | accuracy |
|---|---:|---:|---:|
| team（报告口径） | 28 | 0 | 100.00% |
| solo_open_book | 28 | 1 | 96.43% |
| 全部 24 个 baseline 输出 | 112 | 1 | 99.11% |

**为什么现有测试没挡住**：没有测试断言 grounding 计数覆盖非 team baseline。

**最小修复**：按 baseline 累加独立计数器并分 mode 打印；或最低限度把报告行标签改为 `MA grounding (team attempts only)`。

---

#### H7 · `MACollaborationGain` 混用了两种通过标准
**类别：指标口径 bug**

**位置**：`internal/eval/runner.go:343`（`MATeamSuccessRate = maTeamPassed / MAAttempts`，其中 `maTeamPassed` 是 milestone + delegation + contribution + efficiency + fault + grounding 的严格全 AND，见 `multiagent.go:536-539`）、`:371`（从中减去 outcome-only 的 `MASoloSuccessRate`）、`:365-369`（同口径字段 `MATeamOutcomeSuccessRate` 已存在，却只被 fair / compute-matched gain 使用）

**实际后果**（`finance-workflow-formal-r3.json` 实测）：`team_success_rate 0.7222`（严格）vs `team_outcome_success_rate 0.7778`（outcome）。`collaboration_gain = 0.7222` 是对 `solo_closed_book 0.0` 算出的，因此比另两个 gain 的口径**低 5.6pp**。

另有一个独立问题：closed-book solo 得 0/18，是因为它无法知道 milestone 所要求的 evidence ID（`FIL-101` 等）。这个 gain 衡量的是 **evidence 可得性，不是协作**。

**为什么现有测试没挡住**：没有测试断言三个 gain 使用同一分子口径。

**最小修复**：用 `MATeamOutcomeSuccessRate` 计算 `MACollaborationGain`；在 `report.go:79-90` 把 closed-book gain 明确标注为 evidence-access delta。

---

#### H8 · 报告 §3.4 的三条失败归因，两条是错的，且其中一条的"修复"无效
**类别：文档事实错误（带指标后果）**

**位置**：`evals/finance-runtime-formal-r1.md:129-133`

| 归因 | 报告说法 | 实测裁定 |
|---|---|---|
| 1 | solo_open_book 写 `conviction moves from 3 to 4`，rubric 要 `conviction from 3 to 4` | **错**。同一输出还含 `moves conviction from 3 to 4`，子串本就存在，milestone 在 widening 前即通过。真实原因是 **C1** |
| 2 | Oracle Team 写 `exceeds`，rubric 要 `crosses` | **错**。`crosses` **在**输出中（`crosses the invalidation threshold`）。真正缺失的是 `above 25 percent`——模型写的是 `more than 25 %`。widening 加的 `exceeding 25 percent` 与 `crosses \|\| exceeds` 都不匹配 `more than`。实测：oracle_team FIN-02 在**当前** YAML 下**仍然失败** |
| 3 | Team 写 `re-running` / `re-run`，rubric 要 `rerun` / `re-check` / `recheck` | **正确**，widening 确实修好了 |

**实际后果**：§3.4 的结论 "under manual semantic adjudication each mode passed all six cases"（`:133`）建立在两个错误根因上；且用于填坑的 calibration 留了一个 case 仍然失败。

同类问题在 §5.3（`:224`）：对 r2 那次失败的归因同样是 rubric 版本问题——14:20 的 `/tmp/fastclaw-finance-team.yaml` 快照缺 `24-hour concurrence window`；当前 YAML 下 r2 team 是 6/6。报告称其"added to the frozen semantic alternatives"，而它在 md 写作前就已加入 runtime YAML，因此 "frozen" 在 r1 与 r3 两处都不准确。

**最小修复**：见第 8 节的替换措辞。

---

#### H9 · `total_tokens` 重复计入 37,248 个 cache-read token，"3.97×" 与"便宜 54.4%"是缓存记账产物
**类别：指标口径 bug + 对外表述问题**

**位置**：`evals/finance-runtime-formal-r1.md:141-164`（§4.1）；根因是 `total = prompt + completion` 且 `cache_read ⊆ prompt`

实测：全实验 `cache_read_tokens = 37,248`，`cache_creation_tokens = 0`。Team 的 prompt 有 **62.9%** 是 cache read，solo_open_book 只有 26.1%。cache read 确实按配置折扣计价（Pro 0.003625 vs input 0.435 = 0.83%；Flash 2.0%），但也确实被计入 `total_tokens`。

按可计费 input + completion 重算：

| 比较 | 报告值 | 可计费口径 |
|---|---:|---:|
| tokens team / open_book | 3.971× | **1.994×** |
| tokens team / two_pass | 1.294× | **0.593×** |

cache read 按全价 input 计费的敏感性分析：

| 比较 | 报告值 | 全价口径 |
|---|---:|---:|
| cost team / open_book | 1.410× | **2.169×** |
| cost team / two_pass | 0.456×（−54.4%） | **0.733×（−26.7%）** |

md 与 report JSON 均未披露这一点。

**附带的因果表述错误**：§4.1 把 team vs two_pass 的节省归因于"assigning evidence retrieval to the cheaper Flash specialists"。实测 $0.010354 的节省中 **92.1%** 来自 Pro completion token 从 18,092 降到 7,128（−60.6%），Flash specialist 只贡献 $0.001363 的 team 成本。机制是"coordinator 少写了昂贵的 Pro 输出"，而且 two_pass 本身要输出两份完整答案。

---

#### H10 · 无界子序列匹配器支撑着 100% contribution utilization，而测试名声称了一个实现里不存在的界
**类别：代码 bug + 测试命名错误**

**位置**：`internal/eval/multiagent.go:1140-1155`（`wordsAppearInOrder` 只在匹配时前进，从不重置，没有窗口）、`internal/eval/multiagent_test.go:33-52`（`TestContainsAllInOrderFoldAllowsBoundedParaphraseGaps`）

**触发场景**：实测 FIN-01 governance 的 contribution value 列表能在**每个 token 之间插入 400 个填充词**的文本上匹配。真实存储输出中有 28 个 contribution value 只通过子序列而非子串成立，实测最大单 gap：

- **97 token**：`contradictory-primary-evidence` 的 `reduced from 8 billion to 5 billion yuan`，跨一段散文加一张 markdown evidence 表
- **112 token**：`duplicate-event-alert` 的 `duplicate_count to 2`

另一实测反例：`staged plan was rejected… rebalance nothing… below 45 percent` 也能通过。

**实际后果**：改为连续匹配后 contribution utilization 是 **17/18 = 94.4%**，不是报告的 100.0%。而 `TestContainsAllInOrderFoldAllowsBoundedParaphraseGaps` 只断言三个正例和一次反转，**从不断言任何界**——测试名声称了一个实现没有的性质。

**最小修复**：重命名测试，或加最大 gap 参数。实测约 8 token 的窗口能接纳真实数据里所有合法改写，同时拒绝 97 / 112 token 的跨段匹配。

### MEDIUM

#### M1 · `AfterToolCall` 的 duration 现在是整批的墙钟，不是单 tool 的
**类别：代码 bug**（声称 7 只部分成立）

**位置**：`internal/agent/loop.go:793-806`（所有 `BeforeToolCall` hook 在 `:812` 调用 `executeToolsConcurrently` **之前**就全部打完）、`internal/agent/hooks.go:92`（`time.Since(hc.StartTime)`）、`internal/agent/sdkbridge.go:166`（`costTracker.AddToolDuration` 记录同一个批级 duration）、`internal/plugin/hook_adapter.go:114-153`（`buildHookFireParams` 从不转发 `StartTime`，plugin hook 根本算不出 duration）

**触发场景**：任何有 ≥2 个 tool call 的 turn。

**实际后果**：批内每个 tool 都被报成整批耗时；并发化后这是批内 **max**，方向上恰好掩盖慢 tool。延迟遥测与任何基于它的成本/时长归属都是错的。

**最小修复**：在真正开始执行的地方记录 per-tool 起点——在 `toolAdapter.Call` 顶部取 `time.Now()`，通过 `toolCallResult` 新增 `Duration` 字段回传给 `AfterToolCall` hook（考虑到现有 `LoggingHook` 的覆写行为，这是风险最低的变体）。

---

#### M2 · milestone 与 contribution 两个 grader 对同一个 value 字符串会给出相反结论
**类别：代码 bug**

**位置**：`internal/eval/multiagent.go:879`（`containsAllFold` 要求连续子串）vs `:895`（`containsAllInOrderFold` 允许任意 gap）

**触发场景**（r1 FIN-05 team 真实输出）：value `rerun || re-check || recheck` —— milestone **fail**、contribution **pass**。原因是 `re-check` 归一化成两个 token `re check`，跨 4 个中间词在 `re running concentration and stress check` 上子序列命中。

**实际后果**：该 attempt 记录里同一条 rubric value 同时是 `ma_contribution: passed` 和 `ma_milestone: failed`。

**最小修复**：两处统一用同一 matcher；或对源自连字符单词的多 token alternative 要求相邻。

---

#### M3 · delegation precision 的分母未去重，而分子去重
**类别：指标口径 bug**

**位置**：`internal/eval/multiagent.go:846`（`metrics.TotalDelegations = len(delegations)`）vs `:863`（`valid` 是 `map[string]bool`，`:864` 取 `len`）

**触发场景**：同一 target 被调用两次且两次都有效时，precision 会 < 1。

**实际后果**：r1 / r2 因 18/18 恰好一对一而不可见；一旦出现重复调用，precision 会被低估，且与 `project-report/fastclaw_project_report.md:392-396` 所述的 "unique valid delegated set D" 定义矛盾。

---

#### M4 · `compare.go:124-125` 把同一个 delta 赋给两个字段
**类别：代码 bug（既有，非本轮引入）**

**位置**：`internal/eval/compare.go:124-125`

```go
MAFaultInjectionPoints:   percentagePointDelta(faultObservationRate(baseline.Metrics), faultObservationRate(candidate.Metrics)),
MAFaultObservationPoints: percentagePointDelta(faultObservationRate(baseline.Metrics), faultObservationRate(candidate.Metrics)),
```

**实际后果**：fault injection 的比较列永远等于 observation 列。

---

#### M5 · `computeMatchedGainAvailable` 的兜底会让"故意无效"的 gain 复活
**类别：代码 bug**

**位置**：`internal/eval/compare.go:332-353`（`MAComputeMatchedGainValid` 为 false 时退化为 `MASoloTwoPassEvaluated > 0 && team.Evaluated > 0`）、`:296-304`（打印点）

**触发场景**：旧报告（`finance-workflow-*.json`，pre-two-pass）因 `multi_agent_compute_matched_gain_valid: null` 与 `multi_agent_solo_two_pass_evaluated: null` 而正确显示 n/a——这部分没问题。风险在于计数存在但 gain 确实缺失的报告（例如部分运行时刻意留 false），兜底会把存储的 0 当成有意义的 0，印成真实 pp delta。

**最小修复**：以报告 `version` 字段判定，而不是用可重算的计数反推 validity。

---

#### M6 · `solo_two_pass` 只对 pass-2 文本评分
**类别：代码 bug（公平性残留）**

**位置**：`internal/eval/multiagent.go:622`（`combinedResponse = finalResponse`，丢弃 pass-1 的 `Output` / `Trace`）、`:645`（只有 pass-2 文本进入 `multiAgentOutcomePass`）、`:753-758`（synthesis prompt 说 "Using the analysis from the previous pass" 且刻意不重发 evidence packet）

**先证伪一个假设**：**"pass 2 看不到 pass 1"是错的**。两次 `Execute` 复用同一 `ExecutionRequest`（`:560-566` 建，`:607-646` 复用）→ 同一 `SessionKey` → `x-fastclaw-session-key`（`internal/eval/http_executor.go:125-127`）→ `bus.InboundMessage.ChatID`（`internal/api/openai.go:112,145-151`）→ 同一 `session.Session`（`internal/agent/loop.go:553,617,632-634`；`internal/session/manager.go:111-149`），全链无 eval 专用 session 重置。r1 真实数据佐证：pass-1 prompt token 638–668，pass-2 1345–1786，六个 case 全部如此（pass 2 携带了 pass 1 的约 1100 token 输出）。**该 baseline 是合法的 compute-matched control。**

**残留风险**：若 pass 2 概括而非重述，evidence ID / 数字覆盖会丢失，即使分析本身正确。

**最小修复**：对 `analysisResponse.Output + "\n" + finalResponse.Output` 评分；或在 synthesis prompt 中要求最终答案自包含。

**测试缺口**：`internal/eval/multiagent_test.go:691-758` 的 `TestMultiAgentRunnerAccountsEveryBaselineCostBucket` 漏了 `solo_two_pass`，且其 fake executor 无状态——session 传递一旦回归，没有任何测试能发现。

---

#### M7 · `loadFileWithError` 在有 FS 兜底文件时吞掉 store error，fresh install 又报错误的消息
**类别：代码 bug**

**位置**：`internal/agent/context.go:357-374`

```go
if cb.store != nil {
    data, err := cb.store.GetWorkspaceFile(...)
    if err == nil && len(data) > 0 { return ..., nil }
    storeErr = err
}
if cb.home != "" {
    if data, err := os.ReadFile(...); err == nil && len(data) > 0 { return ..., nil }  // storeErr 被丢弃
}
return "", storeErr
```

**触发场景 A**：store 报 `database is locked`，但存在陈旧的本地 `SOUL.md`。agent 以陈旧身份启动，store 故障被完全丢弃——prompt 里的身份与 DB 中的身份静默分叉。

**触发场景 B**：`MemoryStoreAdapter.GetWorkspaceFile` 委托到 `GetAgentFile`，后者对缺行返回 `ErrNotFound`（`internal/store/database.go:1058` 的 `scanErr(err)`）。因此配了 `requiredIdentityFiles` 的**全新** store-backed 安装、且无 FS 文件时，会得到 `load required identity file SOUL.md: ... not found`，而不是本意的 `required identity file SOUL.md is missing or empty`——`context.go:100` 的那条分支只在 `store == nil` 时可达。两种情况下 turn 都会被拒（`loop.go:574-580` 返回错误并 `events.fail`），但运维看到的是可操作性更差的那条消息。

**为什么现有测试没挡住**：`TestContextBuilderPreservesRequiredIdentityStoreError` 用 `countingIdentityStore{err: errors.New("database is locked")}` 且 `home: ""`，FS 兜底从不存在、`ErrNotFound` 从不返回。该测试断言消息**不**含 "missing or empty"，恰好把上述行为固化了下来。

**最小修复**：`if errors.Is(err, store.ErrNotFound) { err = nil }` 把"不存在"与"传输故障"区分开；FS 兜底成功但 `storeErr != nil` 时至少 warn 一条日志。

---

#### M8 · `BuildSystemPrompt` 丢弃身份契约错误
**类别：代码 bug（当前无非测试调用方）**

**位置**：`internal/agent/context.go:112`

```go
identityRevision, _ := cb.ValidateRequiredIdentityFiles()
```

grep 确认目前无非测试调用方（`loop.go:586` 走的是低层 `buildSystemPrompt(identityRevision)`，且在 `:574-580` 已检查过错误）。但任何未来调用导出的 `BuildSystemPrompt` 的代码会拿到空身份且无任何信号。

**最小修复**：改签名为 `(string, error)`，或重命名以显式表明它吞错。

---

#### M9 · per-success 成本用严格分母，而紧挨着的成功率是 outcome 分母
**类别：指标口径 bug**

**位置**：`internal/eval/runner.go:348-352`（用 `maTeamPassed`，严格全 grader AND）；`internal/eval/report.go:139-`（`MA usage:` 行紧邻显示 outcome rate 的 `MA fair baselines:` 行）

**实际后果**：r3 实测 `0.02731626 / 13 = 0.0021013`，而 team baseline 报的是 14 次 outcome pass。r1 因两者都是 5 而不可见。

**最小修复**：择一分母并在报告标签中写明。

---

#### M10 · `ModelUsageCollector.Sequence` 现在是完成顺序，不是调用顺序
**类别：代码 bug（并发改动带来的行为变化）**

**位置**：`internal/agent/usage_trace.go:101-104`（`call.Sequence = len(collector.calls) + 1`，在 mutex 下）

**触发场景**：两个并发 sub-agent 各自发起 model call。

**实际后果**：`Sequence` 不再反映模型请求工作的顺序，任何从 `Sequence` 重建时间线的 eval 报告会以非确定顺序交错 sub-agent，同一输入的两次运行产出不同排序，削弱 `internal/eval/compare.go` 的跨运行可比性。

**最小修复**：在调用**开始**处用 `atomic.AddInt64` 赋序；或保留完成计数器同时附加 parent tool-call index / `CallPath` + per-path 计数器，供消费方确定性排序。

---

#### M11 · 报错的 baseline 仍然贡献 token 与成本
**类别：指标口径（疑似刻意，但未文档化）**

**位置**：`internal/eval/runner.go:225-232`（`TotalTokens` 与 `EstimatedCostUSD` 的累加在 `baseline.Error == ""` 的 guard 之外）、`internal/eval/report.go:177-189`（在成本旁打印 `valid %d | errors %d` 但无说明）

**实际后果**：超时的 baseline 会抬高其成本桶，同时被排除在 `Evaluated` 之外。所有已存报告 `errored: 0`，因此未被触发。

---

### LOW

| # | 位置 | 问题 | 状态 |
|---|---|---|---|
| **L1** | `multiagent.go:1310-1312` + `:1148` | 二次去复数：`normalizeMatchText` 去尾 `s`（len>3）后 `trimMatchPunctuation` 又去一次 → `cross`→`cros`→`cro`、`class`→`clas`→`cla`。实测 `containsAllInOrderFold("cro border", ["cross border"])` 为 true 而 `containsAllFold` 为 false。扫描两个 YAML 全部 22 个多 token value：**当前 0 个受影响**（`crosses`→`crosse`、`basis`→`basi` 在第二遍下稳定） | 潜伏。修复：`trimMatchPunctuation` 去掉去复数逻辑 |
| **L2** | `multiagent.go:1157-1159` | 朴素去复数碰撞：`basis`→`basi`、`gross`→`gros`、`status`→`statu`、`thesis`→`thesi`、`analysis`→`analysi`。实测 milestone value `status invalidated` 被拼写错误 `statu invalidated` 满足 | 实践中无害（`asset`/`assets` 归并是本意），记录备查 |
| **L3** | `multiagent.go:1240-1244`、`:1195` | `hasNegationScope` 把 `may` / `might` / `could` / `possible` / `possibly` 当否定，±5 词内抑制真实 violation。实测 `"Returns are guaranteed, which may reassure the desk."` 与 `"The filing overrides the transcript, so we could act."` 均不报警。另 `forbiddenMatchClauses` 按 `" and "` 切分会缩短 clause。扫描 154 条真实输出：两者各 **0 次**出现 | 潜伏。修复：把 hedge 移到独立的 uncertainty 列表，要求 hedge 出现在短语**之前**而非 ±5 窗口内任意位置 |
| **L4** | `sdkbridge.go:88-94` | `IsConcurrencySafe` 对非字符串 `agentId` 取 `""`。实测若 `targets[""]=true` 会判为并发安全 | 当前不可达（`uniqueSubAgentTargets:244` 跳过空 ID；畸形 JSON / 空 / 缺失 / 非字符串全部产出 `map[]`）。修复：`agentID, ok := input["agentId"].(string); if !ok \|\| agentID == "" { return false }` |
| **L5** | `sdkbridge.go:154` vs `:234` | 同一批 arguments 被解析两次且依据不同：`uniqueSubAgentTargets` 用原始 JSON 字符串，`IsConcurrencySafe` 用反序列化后的 map | 当前一致。修复：在 `executeToolsConcurrently` 里解析一次并向下传递 |
| **L6** | `internal/store/factory.go` / 运维 | WAL 现在真正生效，产生 `-wal` / `-shm` sidecar。实测 `New(nil, home)` 生成 `fastclaw.db`、`fastclaw.db-shm`、`fastclaw.db-wal`。只复制 `fastclaw.db` 的备份或容器卷流程现在会抓到陈旧数据库 | **真实运维语义变化**（改动前 `_journal=WAL` 被忽略，journal 实为 `delete`）。需写入部署文档；无代码修复 |
| **L7** | `internal/agent/loop.go:820-839` | padding 块不可达——`sdkbridge.go:176-230` 保证 `len(results) == len(toolCalls)` 恒成立 | 建议改为断言 + 日志，并在 `:842` 加注释说明该不变量，因为它是一次重构就会破的 |
| **L8** | SDK `executor.go:78` / `internal/bus/internal.go:117-123` | SDK 的并发组无上限（无 semaphore）；宽 fan-out 下会撞上 `ErrInternalBackpressure`（cap 100） | 未在现有实验触发 |

---

## 4. 分类汇总（Prompt 1 第 4 项要求）

| 类别 | Findings |
|---|---|
| **代码 bug** | C1, C4, H1, H2, H3, H4, H5, H10, M1, M2, M4, M5, M6, M7, M8, M10, L1–L8 |
| **指标口径 bug** | C2, H6, H7, M3, M9, M11 |
| **实验设计限制** | C3（rubric 未版本化 + calibration leakage）；6 case × 1 rep 无统计功效；静态 evidence（`SOUL.md` 字面查表）；跨运行墙钟不可比 |
| **文档表述问题** | H8, H9（表述部分）；`finance-runtime-formal-r1.md` §3.4 / §4.1 / §5.3；`finance-workflow-formal-r3.md:31`；project-report 全部条目（第 8 节） |

---

## 5. 经验证正确的关键路径（Prompt 1 第 5 项要求）

### 并发结果回填
**安全，但依据不显然，值得加注释固化。** SDK `RunTools`（`open-agent-sdk-go@v0.1.0/tools/executor.go:42-78`）确实重排：它把所有 concurrency-safe 调用划入一个 slice 先跑，再追加 sequential 结果。实测混合批 `[write, read, write, list]` 的返回顺序是 `[read, list, write, write]`。

误归属被 `internal/agent/sdkbridge.go:176-230` 阻止——它按 `ToolUseID` 重键进一个以 `toolCalls` 为索引的 slice，而不是按位置 zip。实测 2 safe + 2 unsafe 的混合批，结果 ID 按原序 `c1,c2,c3,c4` 回填。因此 `loop.go:842` 的 `toolCallStarted[idx]` / `resp.ToolCalls[idx]` 索引对齐正确、无越界风险。**声称 7 的对齐部分成立**（时间语义本身见 M1）。

这份安全性完全依赖 `byID` 重键，建议在 `loop.go:842` 加注释说明该不变量。

### 缺失响应补位
`sdkbridge.go:183-190` 合成显式失败 `tool_result`，孤立 `tool_use` ID 不会到达 provider 触发 400。

### `uniqueSubAgentTargets` 失败安全
`sdkbridge.go:234-254`：畸形 JSON、空、缺失、非字符串 `agentId` 四种形态全部产出 `map[]`；重复 target 映射为 `false`。四种情况都路由到串行执行。重复 target 另受 taskqueue ChatKey `"subagent:" + ownerUserID + ":" + targetAgentID`（`internal/gateway/routing.go:122`）下游序列化。**声称 6 成立。**

### 取消语义
中途 cancel 时 3/3 个 `tool_use` ID 都返回 `context canceled` 错误结果，无孤立、无挂起。（**行为记录，非缺陷**：预先取消的 context **不**短路，tool 仍会执行并返回 `ok`——这可能不是期望行为，值得显式固定语义。）

### 部分失败与未知 tool
返回 `("partial output", err)` 的 tool 正确同时暴露部分文本与错误（含 "try a different approach" 后缀），不影响兄弟调用。未知 tool 返回 `IsError` 结果（`Unknown tool: does_not_exist`）并保留 ID，不会丢弃该调用。

### `spawn_subagent` 本体并发安全
`internal/agent/tools/subagent.go`：`subAgentCallCounter` 用 `atomic.AddUint64`（`:121`）；`subAgentDedup.call`（`:89-113`）持 `d.mu` 保护 map 并通过 `done` channel 发布、带 `ctx.Done()` 逃逸；`spawnSubAgent` 每次调用建全新 `bus.InboundMessage`，唯一 `callID` 与 ChatID。无共享可变状态，`-race` 干净。

`gatewaySubAgentSpawner.SpawnSubAgent`（`routing.go:381-409`）具备 call-path 环检测、每次调用 10 分钟超时、`ContextWithoutChatEvents` 使 sub-agent 输出不泄漏到 parent 流。背压非阻塞并返回 `ErrInternalBackpressure`。

`ModelUsageCollector`（`usage_trace.go:38,101-112`）与 `MemMeter`（`internal/usage/usage.go:84`）均 mutex 保护，并发 `RecordModelCall` 无竞争。

### turn 级序列化未受影响
`turnGate`（`loop.go:270`，cap 1）仍按 agent 串行化 turn；并发只发生在 turn 内部，因此 turn 内 session append 顺序不受影响。

### 身份契约错误在两条路径都到达调用方
`loop.go:574-580` 返回错误并调用 `events.fail`；streaming 路径经 `error` event → `reader.SetErr`。**声称 9 在"保留底层 error"这一点上成立**（残留问题见 M7）。

### 成本对账精确
r1 四个 baseline 成本桶之和 `0.0390194716` = `multi_agent_total_estimated_cost_usd`（Δ = 1.4e-17）；`coordinator 0.007304723 + subagent 0.001363494 = team 0.008668217` 精确相等；role 划分正确——6 次 team attempt 对应 12 次 Pro coordinator 调用 + 18 次 Flash subagent 调用；`pricing_coverage = 1.0` over 54 calls；`solo_two_pass` 与 `oracle_team` 都经 `multiagent.go:513` 计入。**声称 4 与 10 的成本部分成立。**

按 baseline 独立重算并与 report JSON 逐字符对账通过：

| mode | passed | tokens | cost USD | mean latency |
|---|---:|---:|---:|---:|
| solo_open_book | 5/6 | 10,301 | 0.00614801 | 18,047.6 ms |
| solo_two_pass | 6/6 | 31,604 | 0.01902258 | 54,988.9 ms |
| team | 5/6 | 40,905 | 0.00866822 | 28,674.0 ms |
| oracle_team | 5/6 | 9,383 | 0.00518066 | 15,415.7 ms |

（注意 role 分解里的 latency 是 `Σ latency / MAAttempts`，即 per-attempt 求和，不是 per-call 均值。）

### 空输出与错误剔除
`runner.go:216-226` 递增 `Errored` 并跳过 `Evaluated` / `Passed` / latency；空输出在 `multiagent.go:599-602` 转为 error。有 `TestMultiAgentRunnerIsolatesBaselineTimeouts`（`:525`）与 `TestMultiAgentRunnerTreatsEmptyBaselineOutputAsError`（`:588`）覆盖。所有已存报告 `errored: 0`。**声称 3 成立。**

### Valid 标记
`runner.go:374-389` 仅在双侧 `Evaluated > 0` 时置位 `MAFairCollaborationValid` / `MAComputeMatchedGainValid`。数据佐证：pre-two-pass 报告的 `compute_matched_gain_valid: null`、`finance-runtime-pilot.json` 的 `collaboration_gain_valid: false` 而 fair / compute 为 true。`report.go:231-243` 正确渲染 `n/a`。（仅 compare 侧兜底可疑，见 M5。）

### grounding 计数有界
`multiagent.go:962-967` 每个配置 value 最多计一次 violation，因此 per-attempt violations ≤ assertions，`MAGroundingAccuracy ∈ [0,1]`，跨 repetition 与 baseline 无重复计数。从全部存储输出独立重算与 r1 报告值一致。

### `solo_two_pass` 确实共享第一遍上下文
完整证据链与 token 佐证见 M6。**该 baseline 合法，声称 1 成立。**

### contribution grader 的方向敏感性
`containsAllInOrderFold` 正确拒绝 `reduced from 5 billion to 8 billion`（对 FIN-06 value）与 `conviction from 4 to 3`（对 FIN-01 value）；`<25%` / `>25%` 归一化为不同的 `below` / `above` token，不交叉匹配；`PE of 14` ≡ `PE 14` 经停用词移除，符合设计。

### 贪心子序列无回溯不产生假阴性
leftmost-greedy 对子序列包含是可证最优的。实测 `[a b c]` vs `a x a b c`、`a b x a b c`、`[a b a c]` vs `a b b a c` 全部正确为 true。缺少回溯**不**造成假阴性。

### 并行性数字算术正确
从 r2 的 `cases[].attempts[].model_calls[].latency_ms` 按 role 分组独立重算：

```
mean wall (attempts[].latency_ms) = 34,465.2 ms
mean serial_CF (Σcoord + Σsub)    = 37,986.3 ms
mean floor (Σcoord + max sub)     = 34,331.1 ms
saved = CF - wall                 =  3,521.1 ms
avoided specialist wait           =  3,655.2 ms
聚合节省 = 9.2695%（per-case mean 9.330%, sd 1.934, t-CI [7.30, 11.36], bootstrap [7.81, 10.79]）
specialist 等待消除 = 57.07% ；wall - floor = 134.1 ms
```

两个 artifact 的 SHA-256 与 md 逐字一致（`fa18d56e…d25d53`、`c7f9b994…35182f`）。运行时间线 formal-r1 13:57:48–14:09:32、par-r1 14:20:51–14:24:57、par-r2 14:29:17–14:32:44。逐个核对 md 中每个数字对全部五个 runtime JSON 与两个 pilot：**没有任何数字来自被污染的 par-r1 或任何 pilot**；§3–4 来自 formal-r1，§5.2–5.3 来自 par-r2，"21.10 s" 是 formal-r1 的 `metrics.multi_agent_coordinator_model_latency_ms`。

两点重要限定：该公式**只存在于 md 散文里，Go 代码中没有实现**；且 coordinator 占 r2 墙钟 **91.6%**，完美三路 specialist 并行的结构上限是 **9.62%**——实现已到可达天花板。调度开销可测且非零（serialized formal-r1 为 +1,142 ms/attempt，parallel r2 为 +134 ms），计回则为 11.9–12.1%。

### Postgres 与内存库未受影响
pragma 注入以 `dialect == "sqlite"` 为门（`database.go:26`）；`:memory:` 与 `file::memory:?cache=shared` 都正确追加 pragma。

### 历史 Table VII 全部对账通过
12 行数据与 `finance-runtime-pilot.json` / pilot-optimized-v2 对账一致：tokens 1274742→73729、calls 194→53、p50 110066.128→46021.91 ms、p95 201590.843→60037.384 ms、precision 0.42028985→1.0、contrib 0.17241379→1.0、milestone 0.16666→1.0、coordination 0.38212526→1.0、cost $0.019598938、team $0.013750972、solo $0.005847966、coordinator $0.009910576、subagent $0.003840396、per-success $0.0017188715。

---

## 6. 建议新增的测试（Prompt 1 第 6 项要求：优先行为测试与并发测试）

### 并发 / 行为（无需真实网络）

| # | 测试 | `-race` | 对应 finding |
|---|---|---|---|
| 1 | 混合 safe/unsafe 批的结果与 `toolCalls` 索引对齐 —— **价值最高**，守护 C1/H1 依赖的不变量 | 否 | C4 前置 |
| 2 | 重复 `tool_use` ID 不产生结果复制 | 否 | H1 |
| 3 | 空 `tool_use` ID 被显式处理 | 否 | H1 |
| 4 | panic 的 tool 返回错误结果、进程存活（须在 recover 修复后才能写） | 否 | C4 |
| 5 | 未知 tool 名返回带 ID 的错误结果而非丢弃调用 | 否 | 已手工验证 |
| 6 | 中途 `ctx` 取消仍答复每个 `tool_use` ID | **是** | 已手工验证 |
| 7 | 预先取消的 `ctx` 语义显式固定（当前**不**短路，tool 仍执行） | 否 | 行为记录 |
| 8 | `uniqueSubAgentTargets` 对畸形 / 空 / 重复 / 非字符串 args 的表驱动测试 | 否 | L4, L5 |
| 9 | 并发 tool 共享 registry 无竞争（8 路并行） | **是** | — |
| 10 | hook `StartTime` 是 per-tool 而非批级 | 否 | M1 |

### Store

| # | 测试 | `-race` | 对应 finding |
|---|---|---|---|
| 11 | `sqliteDSNWithBusyTimeout` 九例矩阵：路径含 `busy_timeout`、百分号编码、已有 query、已有 busy_timeout、`:memory:`、`file::memory:?cache=shared`、大小写 dialect、无 query、自定义 DSN | 否 | H2 |
| 12 | 12 goroutine 走公开 `Store` API（含 `DeleteUser`）无 `SQLITE_BUSY` —— **这是真正复现 H4 的测试** | **是** | H4 |
| 13 | 自定义 DSN 也得到 `journal_mode=wal` 与 `foreign_keys=1` | 否 | H3 |

#### 12b · 重写 `TestIntegrationSQLiteBusyWriterWaits`，必须加对照臂

**位置**：`internal/store/database_integration_test.go:105-145`

现测试用单个 pooled `*sql.DB` 的两条裸 `INSERT`。实测其对照组（`busy_timeout(0)`）确实会失败：

```
busy_timeout=0
second writer result WITHOUT busy_timeout: database is locked (5) (SQLITE_BUSY)
```

因此它不是字面上的空测试——但它失败的原因是附带的：`SetMaxOpenConns(25)` 让第二个 writer 拿到了另一条连接。一旦为 H4 改成 `SetMaxOpenConns(1)`，第二个 `Exec` 会阻塞在连接池而非 SQLite，测试将**以完全错误的理由通过**，同时对 `busy_timeout` 一无所断言。它也从不驱动生产真正会崩的读后写升级（H4），且不走 `New`，因此抓不到 H2。

建议设计（已构建并运行验证）：

```go
// 两个独立的 *sql.DB（不是一个池），_txlock=immediate 使 holder 确定性拿到写锁，
// hold 时长远小于 5s 超时但远大于调度噪声。
open := func(bt string) *sql.DB {
    d, _ := sql.Open("sqlite", dsn+"&_pragma=busy_timeout("+bt+")&_txlock=immediate")
    d.SetMaxOpenConns(1)   // 把争用压到 SQLite 而不是连接池
    return d
}
run := func(bt string, hold time.Duration) error { /* holder Begin+Insert; waiter goroutine Begin+Insert; sleep(hold); holder.Commit(); 返回 waiter 结果 */ }

errZero := run("0", 300*time.Millisecond)     // 对照：必须失败
errFive := run("5000", 300*time.Millisecond)  // 处理：必须成功
if errZero == nil { t.Error("对照臂未失败：该测试无法检出 busy_timeout 缺失") }
if errFive != nil { t.Errorf("处理臂失败：%v", errFive) }
```

实测：

```
busy_timeout(0),    300ms hold -> database is locked (5) (SQLITE_BUSY)
busy_timeout(5000), 300ms hold -> <nil>
```

**对照臂是关键增量**：它证明该测试有能力检出修复的缺失，而现行测试并未确立这一点。

### Grader / 指标

| # | 测试 | 对应 finding |
|---|---|---|
| 14 | forbidden assertion 在弯引号、直引号、括号、markdown 表格单元格中的行为 | C1 |
| 15 | 词法完整但语义反转的输出**必须**判失败（每个 case 一条） | C2 |
| 16 | milestone 与 contribution 对同一 value 字符串结论一致 | M2 |
| 17 | `containsAllInOrderFold` 的 gap 上界（真实数据的 97 / 112 token 跨段必须拒绝） | H10 |
| 18 | 分 baseline 的 grounding 计数出现在指标里 | H6 |
| 19 | `MACollaborationGain` 与 fair / compute gain 同口径 | H7 |
| 20 | rubric hash 写入 report envelope，且用同一 hash 重跑得到同一分数 | C3 |
| 21 | 重复 target 时 delegation precision 分母去重 | M3 |
| 22 | `solo_two_pass` 出现在成本桶归属测试里 | M6 |
| 23 | 旧报告（缺 Valid 字段）在 compare 中显示 n/a，不被兜底复活 | M5 |

### 必须走真实 gateway integration

| # | 测试 | 对应 finding |
|---|---|---|
| 24 | 生产（非 eval）turn 中同 target 的两次 `spawn_subagent` 只执行一次 —— 单元测试抓不到 eval-only 接线 | H5 |
| 25 | 并发下 sub-agent trace 归属与 `Sequence` 的确定性 | M10 |
| 26 | 宽 fan-out 下的 internal-bus 背压（`ErrInternalBackpressure`，cap 100） | L8 |

---

## 7. 可安全使用 vs 当前不能声称的结论（Prompt 1 第 7 项要求）

### 7.1 可安全使用（简历 / 论文）

1. 构建并插桩了 coordinator–specialist agent runtime，具备 request-scoped delegation、并发 sub-agent 执行、按调用的 token / 成本 / 延迟归属。
2. 该 6-case 受控套件上 delegation 完全精确：18/18 次 `spawn_subagent` 命中 3 个预期 target，全部在 `round: 1`，零意外 target、零重复 target，formal-r1 与 par-r2 一致。
3. distinct specialist 并发执行，同 target 重复调用保持串行；within-run 墙钟落在 model-call floor 之上 134 ms。
4. 并发把 within-run serial counterfactual 降低 **9.3%**（per-case mean 9.33%，95% CI [7.30%, 11.36%]；计回实测调度开销为约 12%），而结构上限是 **9.62%**（coordinator 占 91.6% 墙钟）——实现已到可达极限。
5. store 级并发控制是必需的：par-r1 把 DB 争用以 `IDENTITY.md missing/empty`、`missing SOUL.md` 的形式暴露给模型，其 incomplete-screening case 升级到 3 轮 7 次 spawn。该争用已被诊断（并部分修复，见 H4）。
6. 完整的 token / 成本 / 延迟分解，100% pricing coverage，成本账本对账到 1e-17。
7. 成本与延迟差异在 6 对配对 case 上统计显著：team 比 one-pass open-book 慢 1.59×（+10.63 s，95% CI [+4.49, +16.76]，paired t p=0.0067，Wilcoxon p=0.0312）、贵 1.41×（p=0.0185）；比 two-pass 快 0.52×（−26.31 s，p=0.0049）、便宜 0.46×（p=0.0014）——**须同时给出 H9 的缓存记账说明**。case-bootstrap 比值 CI：latency 1.589× [1.342, 2.071] 与 0.521× [0.429, 0.636]；cost 1.410× [1.198, 1.764] 与 0.456× [0.380, 0.551]；tokens 3.971× [3.537, 4.610] 与 1.294× [1.157, 1.460]。
8. 建成了评测 harness 本身：四条匹配 baseline（含 compute-matched 与 oracle 控制）、forbidden-assertion grounding 检查、可对账的成本账本。

**可直接使用的简历措辞**：

> Built and instrumented a coordinator–specialist agent runtime with request-scoped delegation, concurrent sub-agent execution, and per-call token/cost/latency attribution; measured 100% delegation precision/recall on a 6-case controlled suite, diagnosed and fixed SQLite contention exposed by concurrent sessions, and quantified a 9–12% within-run latency reduction against a 9.6% structural ceiling. Also built the evaluation harness itself: four matched baselines including compute-matched and oracle controls, forbidden-assertion grounding checks, and a cost ledger reconciling to 1e-17.

### 7.2 当前不能声称

1. **任何方向的决策质量结论。** 6 case × 1 rep 下 exact McNemar 的最小可达 p 是 0.0312，而三个实际比较全为 **p = 1.0000**（team vs open_book 1-vs-1 discordant；team vs two_pass 0-vs-1；team vs oracle 1-vs-1）。"fair gain 0.0 pp" **不是**等价性证据。Wilson 95%：6/6 [61.0, 100.0]、5/6 [43.6, 97.0]；Clopper-Pearson 95%：6/6 [54.1, 100.0]、5/6 [35.9, 99.6]（宽 63.7 pp）。
2. **formal-r1 作为 validation 分数。** rubric 未版本化，38 个 alternative 中 35 个晚于 pilot 输出，发布的 5/6 在磁盘文件下不复现，canonical-only 评分是 3/6。它是一个 **fitted score**。
3. **任何检索、抽取鲁棒性、point-in-time 或无 look-ahead 的能力。** `~/.fastclaw/fastclaw.db` 的 `agent_files` 表中，`finance-source` 的 `SOUL.md` 就是一张 FIN-01..FIN-06 字面查表，带 `NO_MATCHING_EVIDENCE` 兜底和 "You have no tools. Do not use outside knowledge." 的指令。
4. **把 solo baseline 描述为信息可得性对照。** `multiAgentEvidencePacket` 让 open_book、two_pass、oracle_team 收到**同一批** evidence 字符串（前两者是匿名 `evidence-1..3`，oracle 是带标签的 `agentID (role)`）。任务本质是 paraphrase-and-preserve，因此诚实的问题只是"routing 是否降低了保真度"，不是"协作是否发现了更多"。
5. **预测精度、选股 alpha、回测收益、可比 benchmark 分数。**（md 已如此声明，保留。）
6. **"grounding accuracy 100%" 作为系统属性。** 它是单一 baseline 上的 28 次配置化子串检查，且有已知假阳性模式（C1）。
7. **r3 的 "+72.2 percentage points over closed-book"。** 那衡量的是 evidence 可得性（H7）。
8. **"3.97× tokens" / "便宜 54.4%" 不加缓存记账说明**（H9）。

---

## 8. Project Report 专项（Prompt 1 第 8 项要求）

`project-report/` 整体 untracked。产物时间线是本节所有问题的根因：

| 文件 | mtime |
|---|---|
| `fastclaw_project_report.md` | 07-31 11:03:48 |
| `build_report.py` | 07-31 11:03:48 |
| `FastClaw_Project_Report_Zheyu_Wang.docx` | 07-31 11:04:05 |
| `FastClaw_Project_Report_Zheyu_Wang.pdf` | 07-31 11:04:18 |
| `finance-runtime-pilot*.json` | 07-31 12:38 |
| `finance-runtime-formal-r1.json` | 07-31 14:09 |
| `finance-runtime-parallel-team-r2.json` | 07-31 14:32 |
| 两个 YAML | 07-31 14:36 |
| `evals/finance-runtime-formal-r1.md` | 07-31 14:38 |

**报告的全部四个产物都早于它本应描述的实验。** 因此报告不是"部分过期"，而是完全先于本轮金融 runtime 实验。

### 8.1 事实错误清单

| # | 位置 | 问题 | 证据 |
|---|---|---|---|
| F1 | `.md` 与 DOCX 全文 | `solo_two_pass`、`two-pass`、`compute-matched`、`grounding`、`WAL`、`busy_timeout`、`SQLITE`、`9.3%` 的出现次数**均为 0** | 全文 grep |
| F2 | `.md:413` | 称 "72 case–mode executions" | formal-r1 实际是 24 次 baseline execution / 54 次 model call |
| F3 | `.md:388` | 把 outcome success 定义为 "milestone-only" | `MATeamSuccessRate` 走全部 grader（runner.go:343） |
| F4 | `.md:392-396` | delegation precision 分母写作 "unique valid delegated set D" | 实现分母 `TotalDelegations` **未**去重（multiagent.go:846） |
| F5 | `.md:377-382` | baseline 定义表遗漏 `solo_two_pass` | YAML `baselines:` 四项 |
| F6 | 覆盖率 25.7 / 78.2 / 75.3 | 与 HEAD 一致，但当前 dirty tree 实为 26.3 / 78.6 / 76.5 | 本地重测 |
| F7 | `assets/multiagent_sequence.png` | 图示串行 delegation，与已落地的并发实现矛盾 | 目视 |
| F8 | `artifact.md` 全文 | 仅列 2 个 pilot JSON；覆盖率 25.7%；称 8 页（实际 PDF 19 页）；称表格浅灰底纹（`build_report.py` 用 NAVY + 白字） | 逐项比对 |

### 8.2 过期段落清单（含替换意图）

| # | 位置 | 现文 | 替换意图 |
|---|---|---|---|
| S1 | `.md:526`（PDF p15） | "Four-mode repeated finance score \| Not yet reported" | 已有一次四 baseline 真实运行；须改为"已运行 1 rep，不支持统计结论"，并同时修 `build_report.py` 中对应表 |
| S2 | `.md:533` | RQ2 表述 | 纳入 compute-matched baseline |
| S3 | `.md:539` | RQ5 表述 | 纳入并发与 store 争用发现 |
| S4 | `.md:541-547` | §VII-F | 纳入 grounding、并发、SQLITE_BUSY 故障发现与修复 |
| S5 | `.md:607` / `.md:617` | Limitations / Future Work | 纳入 rubric calibration leakage、缓存 token 记账、n=6 的统计功效 |
| S6 | `evals/finance-workflow-formal-r3.md:31` | — | 与 r1 分表分口径，禁止直接比较 total tokens 与 attempt latency |
| S7 | `evals/finance-runtime-formal-r1.md` §3.2 / §3.4 / §4.1 / §5.3 | 见 C1 / C3 / H8 / H9 | 修完 C1/C2 后重跑并重写 |

**8-case 两 baseline 历史结果与 6-case 四 baseline 金融结果必须分表、分口径**（Prompt 4 第 5 项），当前 `.md` 未做此隔离。

### 8.3 重新生成 DOCX/PDF 前的阻塞项

| # | 阻塞项 | 位置 |
|---|---|---|
| B1 | `python-docx` 与 `PIL` 在本机不可用，`build_report.py` 无法执行 | 环境 |
| B2 | `TEMPLATE_PATH` 指向仓库外 `/Users/wangzheyu/Downloads/ieee_financial_analysis_assistant_verified.docx`（sha256 `1a49827…5fdc`），不可复现 | `build_report.py:～30` |
| B3 | 无 PDF 生成步骤，且本机无 `soffice` / `libreoffice`；PDF 只能手工产出 → 必然漂移 | `build_report.py` 全文 |
| B4 | Table VII 数据**硬编码**，改 Markdown 不会改 DOCX | `build_report.py:736-785` |
| B5 | figure caption 硬编码 | `build_report.py:849-853` |
| B6 | table 计数器硬编码 | `build_report.py:856`、`:889-891` |
| B7 | 仅 macOS 字体路径，非 mac 机器构建结果不同 | `build_report.py:40-52` |
| B8 | `project-report/` 全部 untracked，产物无版本锚点 | git |

**引用**：逐条核验，全部真实存在且与相邻论点匹配，无虚构文献、无伪 IEEE 发表信息。唯一问题是**编号不连续**——首次出现顺序为 [10]@:115、[11]@:253、[12]@:473，均早于 [9]@:585。

**视觉 QA**：渲染 PDF 第 1 / 14 / 15 页目视检查，无裁切、重叠、表格断行、孤行或 caption 问题。字体、页眉页脚、参考文献悬挂缩进正常。视觉不是阻塞项；**内容过期才是**。

**修复顺序约束**（Prompt 5 第 10 项）：先改 Markdown 与 `build_report.py`，再重新生成，再目视检查；**不得手改生成产物**。

---

## 9. 交付状态与约束遵守

### 9.1 本轮已执行的验证

| 命令 | 结果 |
|---|---|
| `go build ./...` | 通过 |
| `go test -count=1 ./...` | exit 0 |
| `go test -race ./internal/agent ./internal/store ./internal/agent/tools` | 全部 ok |
| `python3 -m unittest test_plugin`（finance plugin） | 10 tests OK |
| `git status --short` | 33 条（17 M + 16 ??），与本轮开始时快照一致 |
| `jq` 独立重算 formal-r1 / par-r2 / workflow-r3 的成功率、成本、延迟、并行度 | 见 §3 各 finding |
| 本地探针（已删除）：SDK 混合批次序、DSN 重写矩阵、busy_timeout 对照臂、rubric canonical-only 重评分 | 见 §3 |

### 9.2 未执行

- 任何真实 gateway / 网络 integration 测试。
- 任何金融实验重跑（C3 需要，但必须先修 C1/C2）。
- `build_report.py`（B1 环境缺依赖）。
- 未读取、未回显 `runtime-benchmark-tenant.json` 中的任何凭据。

### 9.3 约束遵守确认

| 约束 | 状态 |
|---|---|
| 第一轮只审查，不修改代码 | 遵守 —— 唯一写入的文件是本审查文档（用户明确要求） |
| 不输出或提交 `runtime-benchmark-tenant.json` 的 API key | 遵守 —— 该文件从未被读取 |
| 不 commit、不 push | 遵守 |
| 探针文件清理 | 遵守 —— 全部删除，worktree 已回到起始状态 |

### 9.4 建议的最小阻塞修复集

按依赖顺序：

1. **C1** grounding 假阳性（`normalizeMatchText` 未处理弯引号 / 竖线）——修完才能重跑。
2. **C2** 语义反转输出仍可通过词法 grader。
3. **C4** tool panic 杀进程（生产可用性，与实验无关，可并行修）。
4. **C3** rubric 未版本化 + 事后校准 —— 冻结 rubric、写入 hash、**在 C1/C2 修完后重跑金融实验**，重跑前的分数不得引用。
5. **H1–H7**：结果按 ID 回填的边界、DSN 重写误判、pragma 未生效、`_txlock=immediate`、`spawn_subagent` 去重只在 eval 生效（与工具描述承诺矛盾）、grounding 仅 team、`MACollaborationGain` 混口径。

**只有 C3 需要重跑真实金融实验**，其余均为代码 / 指标口径修复。project-report 的 DOCX/PDF 重新生成应在 C1–C3 修复并重跑之后进行，否则会再次固化一份过期产物。

---

*报告结束。以上全部 finding 均给出文件与行号；第一轮未修改任何被审查文件，未提交、未推送。*







