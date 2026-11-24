# FastClaw Go → Python 拆分迁移 Stacked PR 审查报告

- 审查日期：2026-08-04
- 目标仓库：https://github.com/M0yuW/fastclaw-python （本地 `/Users/wangzheyu/fastclaw-python`）
- 行为参考（只读）：https://github.com/M0yuW/fastclaw/tree/m0yuw-project @ `792417b86b5c12af1b99364865217a74f4d52f38`
- 审查范围：PR #2 Provider 契约 → #3 数据/身份/Go 导入 → #4 单 Agent 运行时 → #5 多 Agent 运行时 → #6 Next.js Web 快照
- 归属方式：每条问题均用 `git log -S` 定位引入提交；基线既有问题不计入 Findings

PR → 提交映射：

| PR | 提交 |
|---|---|
| #1 main | `12cf38e` |
| #2 Provider 契约 | `052da8f` |
| #3 数据/身份/Go 导入 | `db78a13` |
| #4 单 Agent 运行时 | `877f366` |
| #5 多 Agent 运行时 | `3e62fce` |
| #6 Web 快照 | `4995dfb` |

---

## 总结

**合并建议：#2 / #3 / #4 / #5 暂不合并（存在 P0/P1 阻断项），#6 可以合并。**

| PR | 结论 |
|---|---|
| #2 Provider 契约 | 存在阻断性问题：`_raw` 别名与 Go DB blob 的 `rawAssistant` 不兼容，导致导入数据无法回放（F1，与 #4 联合成因） |
| #3 数据/身份/Go 导入 | 存在阻断性问题：密钥脱敏漏项并明文落库（F2）、`configs` 唯一键收紧导致合法 Go 数据导入失败（F4）、外键约束把 Go 允许的孤儿行变成裸 `IntegrityError`（F5）、`credential_key` 静默丢失（F2 附带）、提交后源校验无法回滚（F8） |
| #4 单 Agent 运行时 | 存在阻断性问题：历史消息 `timestamp` 反序列化失败使会话彻底不可续（F1）、`exec` 白名单可被绝对路径绕过（F3）、输出先全量缓冲后截断（F6）、忽略 SIGTERM 的子进程泄漏（F7）、重复 `tool_use` id 归一化与 `_raw` 回放不一致（F9） |
| #5 多 Agent 运行时 | 存在阻断性问题：取消一个分支会连带取消同 root 的兄弟分支（F10，Go 无此广播语义）、`batch()` 无 `return_exceptions` 导致兄弟异常无人取回（F11）、handler 注册表按 `agent_id` 单键导致跨租户覆盖（F12） |
| #6 Next.js Web 快照 | **未发现阻断性问题** |

### 已执行的验证

全部在 `/Users/wangzheyu/fastclaw-python` 实际执行：

| 命令 | 结果 |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 59 files already formatted |
| `mypy` | Success: no issues found in 48 source files |
| `pytest -q` | 36 passed |
| `pnpm --dir web install --frozen-lockfile` | exit 0 |
| `pnpm --dir web lint` | exit 0 |
| `pnpm --dir web build` | exit 0，25 routes |

**七项验证全绿——这本身就是本次审查的核心结论之一：下面的 P0 项没有任何一条能被现有测试套件捕获。**

### PR #6 快照保真性核验

逐文件核验通过：Go `792417b` 的 `web/` 共 91 个受版本控制文件，Python 侧 92 个；新增仅 `LICENSE` 与 `SOURCE.md`，缺失仅 `next-env.d.ts`（被 gitignore）；所有共有文件 SHA-256 逐一相同；未携带任何 Go Git 历史或元数据；来源标注与许可完整。CI 中 `web` job 的 pnpm 10 / node 22 / `cache-dependency-path: web/pnpm-lock.yaml` / `--frozen-lockfile` / lint / build 配置正确。

---

## Findings

按 P0 → P3 排序。每条为一个独立可行动问题。

### 索引

| 编号 | 级别 | PR | 问题 |
|---|---|---|---|
| F1 | P0 | #2 + #4 | 导入的 Go 会话无法回放，会话续聊完全失效 |
| F2 | P0 | #3 | 密钥脱敏漏项，凭据明文写入目标库且报告谎报 |
| F3 | P0 | #4 | `exec` 白名单可被任意绝对路径绕过 |
| F4 | P1 | #3 | `configs` 唯一键收紧，合法 Go 数据导入直接失败 |
| F5 | P1 | #3 | 外键约束把 Go 允许的孤儿行变成裸 `IntegrityError` |
| F6 | P1 | #4 | `exec` 输出先全量缓冲再截断，`max_output_bytes` 不防内存耗尽 |
| F7 | P1 | #4 | 忽略 SIGTERM 的子进程在超时/取消后成为孤儿进程 |
| F10 | P1 | #5 | 取消一个委派分支会连带取消同 root 的兄弟分支 |
| F8 | P2 | #3 | 提交后才做源库校验，检测到篡改已无法回滚 |
| F9 | P2 | #4 | 重复 `tool_use` id 的归一化与 `_raw` 回放不一致 |
| F11 | P2 | #5 | `batch()` 缺少 `return_exceptions`，兄弟异常无人取回 |
| F12 | P2 | #5 | handler 注册表只按 `agent_id` 索引，跨租户互相覆盖 |

---

### F1 · P0 · PR #2 + PR #4 —— 导入的 Go 会话无法回放，会话续聊完全失效

**文件与行号**

- `src/fastclaw/providers/models.py:103`（`timestamp: int = 0`）
- `src/fastclaw/providers/models.py:108`（`raw_assistant: ... = Field(default=None, alias="_raw")`）
- `src/fastclaw/agent/runner.py:212`（`ChatMessage.model_validate(message)`）

**触发条件（已实测复现，非阅读推断）**

Go 落库的 `sessions.messages` blob 由 `internal/store/store.go` 的 `SessionMessage` 序列化，用的是 camelCase + `rawAssistant` + `time.Time`（`internal/session/store_adapter.go:68-91` 写入 `Timestamp: time.Now()`）。构造真实形状的 Go DB，跑完 `import_go_database` 再用 `AgentRunner.stream` 续聊：

```
imported sessions: 1
error | ValidationError: 1 validation error for ChatMessage
timestamp
  Input should be a valid integer, unable to parse string as an integer
  [type=int_parsing, input_value='2026-01-01T00:00:00Z', input_type=str]
```

`ChatMessage` 是 `extra="forbid"`，因此 `rawAssistant` 同样触发 `extra_forbidden`（该项在单独实验中已确认）；`timestamp` 的 `int_parsing` 先行报错，所以上面只显示一条。

**实际影响**

双向断裂：

1. **读方向**：任何从 Go 迁移过来的会话，第一次续聊就在 `_history` 抛 `ValidationError`，整个 run 以 `error` 事件终止。迁移后的历史会话 100% 不可用——数据导入成功但产品功能不可用。
2. **写方向**：`_session_record`（`runner.py:239-259`）用 `model_dump(by_alias=True)` 回写，产出 `_raw` 与 `timestamp: 0`。这些行 Go 侧读回时 `rawAssistant` 为空、时间戳归零，Anthropic 的 thinking `signature` 随之丢失，破坏后续轮次的 prompt cache 与签名校验。

`docs/migration/phase-3-single-agent.md` 声称「Current Go message fields such as `content_parts`, `_raw`, metadata, origin, provider, and model are accepted and preserved for replay」，与实测结论直接矛盾——文档描述的能力并不存在。

**归属确认**：`git log -S 'alias="_raw"'` → `052da8f`（PR #2）；`git log -S 'timestamp: int = 0'`、`git log -S 'ChatMessage.model_validate'` → `877f366`（PR #4）。均非基线既有问题。

**修复方向**

`ChatMessage` 需要区分「wire/JSONL 形态」（snake_case + `_raw`）与「DB blob 形态」（camelCase + `rawAssistant` + RFC3339）两套契约：给 `raw_assistant` 加 `AliasChoices("_raw", "rawAssistant")`，`timestamp` 改为接受 `int | str | datetime` 的 union 并用 `field_validator(mode="before")` 归一化，或在 importer 落库时就把 blob 规范化成 Python 侧唯一形态。同时把回写序列化方向与 Go 读取端对齐（决定其中一种为权威格式，另一种做转换），并给「真实 Go blob → 导入 → 续聊 → Go 读回」加端到端回归测试。

---

### F2 · P0 · PR #3 —— 密钥脱敏漏项，凭据明文写入目标库且报告谎报

**文件与行号**

- `src/fastclaw/migration/importer.py:51-65`（`_SECRET_KEYS` 固定精确匹配集合）
- `src/fastclaw/migration/importer.py:342-362`（`_redact_value`，仅 `key.lower() in _SECRET_KEYS` 才置空）

**触发条件（已实测）**

Go `configs.data` 中放入 `clientSecret` / `refreshToken` / `privateKey` / `authToken` / `apiKey` 五个字段后执行导入：只有 `apiKey` 被置空，其余四个**原文写入目标库**，而报告里 `redacted_secrets=1`。原因是集合做的是精确名匹配，`clientsecret`、`refreshtoken`、`privatekey`、`authtoken` 都不在 `_SECRET_KEYS` 里（集合里只有裸 `token` 和裸 `secret`）。

同时 Go `configs.credential_key`（`store.go:204-207` 的 `CredentialKey`）在目标 schema 中没有对应列，导入过程**静默丢弃**，既不落库也不在报告中提示。

**实际影响**

迁移的核心承诺之一是「配置凭据不得泄漏到报告、日志或目标库」，这里三处同时失守：明文入库、报告数字失真（运维据此认为已脱敏）、外部凭据引用键丢失（迁移后相关 config 无法解析凭据，功能性损坏）。目标库的备份、只读副本、日志导出都会带上这些明文。

**归属确认**：`git log -S '_SECRET_KEYS'` → `db78a13`（PR #3）。

**修复方向**

`_redact_value` 改为子串/正则匹配（`secret|token|password|key|credential|passphrase` 词根，配合白名单排除 `key_prefix`、`publicKey` 之类误伤项），并对 value 形态做兜底（长随机串、`sk-` 前缀等）。报告的 `redacted_secrets` 必须由实际置空次数产生且与逐字段清单一起输出。`credential_key` 要么在目标 schema 补列，要么在报告里显式列为「已知丢弃字段」并给出 P0 级警告。

---

### F3 · P0 · PR #4 —— `exec` 白名单可被任意绝对路径绕过

**文件与行号**：`src/fastclaw/tools/builtin.py:77`

```python
if Path(argv[0]).name not in self._allowed_commands:
    return ToolResult(content="executable is denied by policy", is_error=True)
```

**触发条件（已实测）**

白名单为 `{"echo"}` 时，模型传 `argv = ["$TMPDIR/echo", ...]`，其中 `$TMPDIR/echo` 是一个内容为 `#!/bin/sh\nid` 的可执行脚本。`Path(...).name == "echo"` 通过校验，`create_subprocess_exec` 随后执行了 `id`。任何模型可写目录（workspace 本身、`/tmp`、`ReadFileTool` 根目录）下放一个同名文件即可执行任意代码。

**实际影响**

允许列表是这个工具唯一的安全边界，而它只比较 basename。结合同一 agent 可写文件的能力，等价于任意命令执行——完整逃逸出 exec 策略。

**归属确认**：`git log -S 'allowed_commands'` → `877f366`（PR #4），Python 侧新写代码。Go 的 `internal/agent/tools/exec.go:30-36,105-120` 不采用「basename 匹配 + 直接 exec 任意路径」的组合，因此这是迁移引入的弱化，不是基线问题。

**修复方向**

拒绝任何包含路径分隔符的 `argv[0]`；把允许列表解析为**绝对路径白名单**（启动时用受控 `PATH` 解析一次并缓存 realpath），执行前对 realpath 做等值比对，并显式传入受控 `env`（至少固定 `PATH`），避免通过 `PATH` 与相对路径两条通道绕过。

---

### F4 · P1 · PR #3 —— `configs` 唯一键收紧，合法 Go 数据导入直接失败

**文件与行号**：`src/fastclaw/storage/models.py:119`

```python
__table_args__ = (UniqueConstraint("kind", "user_id", "agent_id", "name"),)
```

**触发条件（已实测）**

Go 的唯一键是 `UNIQUE (kind, scope, scope_id, name)`（`internal/store/database.go` DDL），`scope ∈ {system, user, agent, skill}`。Python 侧丢掉了 `scope` 维度，把 `scope_id` 拆成 `user_id` / `agent_id`（`importer.py:330-339` 的 `_config_user_id` / `_config_agent_id`：`scope != "user"` 时 `user_id` 为空串）。于是 Go 中完全合法的两行——`(kind='provider', scope='system', scope_id='', name='anthropic')` 与 `(kind='provider', scope='user', scope_id='', name='anthropic')`——映射到同一个 `(kind, '', '', name)`，导入中止：

```
UNIQUE constraint failed: configs.kind, configs.user_id, configs.agent_id, configs.name
```

**实际影响**

带 system 级与 user 级同名配置的真实 Go 库无法完成迁移，且失败点在事务中段、报错是裸 SQLite 约束文本，运维无法据此定位是哪一行、更无法判断该不该跳过。这是「迁移工具对合法源数据拒收」，不是数据脏。

**归属确认**：`git log -S 'UniqueConstraint("kind"'` → `db78a13`（PR #3）。

**修复方向**

在目标 schema 中保留 `scope` 列并把唯一键还原为 `(kind, scope, scope_id, name)`（`user_id` / `agent_id` 作为派生索引列或视图），或在唯一键中显式纳入 scope 判别。无论哪种，导入前都应做一次冲突预检，把冲突行以「源主键 + 冲突原因」清单形式报出，而不是让 SQLite 约束在写入中途炸开。

---

### F5 · P1 · PR #3 —— 外键约束把 Go 允许的孤儿行变成裸 `IntegrityError`

**文件与行号**

- `src/fastclaw/storage/models.py:86-91`（`sessions.user_id` / `agent_id` FK）
- `src/fastclaw/storage/models.py:137`（`cron_jobs.agent_id` FK）
- `src/fastclaw/storage/models.py:63-68`（`apikey_agents` 双 FK）
- `src/fastclaw/storage/database.py:31-40`（`PRAGMA foreign_keys=ON`）
- `src/fastclaw/migration/importer.py:56-60` 附近的 `sqlite_integrity_errors` 检查

**触发条件（已实测）**

Go schema **没有外键**，`DeleteAgent`（`internal/store/database.go:891-920`）是应用层级联，因此实际生产库里存在指向已删除 agent/user 的 `sessions`、`cron_jobs`、`apikey_agents` 行是常态。导入这类库时得到：

```
IntegrityError: FOREIGN KEY constraint failed
```

PR #3 明显预期用 `PRAGMA foreign_key_check` / `sqlite_integrity_errors` 给出友好诊断，但因为 `foreign_keys=ON` 在写入时就已生效，异常在到达那段检查之前先抛出，友好路径永远走不到。

**实际影响**

任何有历史删除记录的真实 Go 库都会在导入中途失败，错误信息不含表名、不含行标识，运维既不知道坏了几行也不知道怎么清。原本设计的诊断能力实际不可达。

**归属确认**：`git log -S 'ForeignKey("agents.id"'` → `db78a13`（PR #3）。

**修复方向**

导入流程改为「先在源侧做引用完整性预扫描 → 输出孤儿行清单 → 按显式策略（跳过并计数 / 中止 / 补建占位父行）处理 → 再写入」。同时把 `IntegrityError` 捕获点前移，转换为带表名与主键的结构化错误。若要保留 FK，`--allow-orphans` 之类的显式开关比中途炸更合适。

---

### F6 · P1 · PR #4 —— `exec` 输出先全量缓冲再截断，`max_output_bytes` 不防内存耗尽

**文件与行号**：`src/fastclaw/tools/builtin.py:86`、`92`

```python
stdout, stderr = await process.communicate()          # 86：无上限缓冲
...
output = raw_output[: self._max_output_bytes].decode(errors="replace")   # 92：事后才截断
```

**触发条件（已实测）**

允许列表中任一命令产出远超 `max_output_bytes`（默认 1 MB）的输出（`yes`、`cat` 大文件、构建工具刷日志）时，`communicate()` 会把全部字节读进内存，截断发生在**读完之后**。

**实际影响**

`max_output_bytes` 给出的是「返回给模型的内容有上限」的假象，而非资源上限。单次工具调用即可把进程内存拉到与子进程输出同量级，多 agent 并发时可导致宿主 OOM。这是一个可由模型侧输入触发的资源耗尽路径。

**归属确认**：与 F3 同属 `877f366`（PR #4）新写的 `ExecTool`。

**修复方向**

改为增量读取 `process.stdout` / `stderr`，累计字节达到上限即停止读取、置 `truncated=True` 并终止子进程；不要依赖事后切片。

---

### F7 · P1 · PR #4 —— 忽略 SIGTERM 的子进程在超时/取消后成为孤儿进程

**文件与行号**：`src/fastclaw/tools/builtin.py:87-90`

```python
except BaseException:
    process.terminate()      # 仅 SIGTERM
    await process.wait()     # 无超时，无 SIGKILL 升级
    raise
```

**触发条件（已实测）**

子进程安装 `trap '' TERM`（或以任何方式忽略 SIGTERM）后触发取消/超时：`terminate()` 无效，`await process.wait()` 无限期挂住。实测中该子进程在超时后作为孤儿进程存活。对照组（正常响应 SIGTERM 的子进程）能被正确回收，说明问题只在忽略信号这一分支。

**实际影响**

两重后果：取消语义被破坏（取消调用本身挂在 `wait()` 上，无法及时返回），以及进程泄漏（残留子进程继续占 CPU / 文件句柄 / 网络连接，长时间运行的服务会累积）。要求的「取消时工具进程必须立即关闭」在此路径上不成立。

**归属确认**：`877f366`（PR #4）。

**修复方向**

`terminate()` 后带超时等待（如 `with anyio.fail_after(grace)`），超时则 `process.kill()` 再 `wait()`；并把子进程放进独立进程组（`start_new_session=True`），用 `os.killpg` 终止整棵进程树，避免子进程自己 fork 的孙进程逃逸。

---

### F10 · P1 · PR #5 —— 取消一个委派分支会连带取消同 root 的兄弟分支

**文件与行号**

- `src/fastclaw/orchestration/bus.py:109-112`
- `src/fastclaw/orchestration/queue.py:116-125`（`cancel_root` 遍历取消所有同 root 作业）

```python
try:
    return await asyncio.shield(future)
except asyncio.CancelledError:
    await self._queue.cancel_root(context.root_execution_id)   # 过度广播
    raise
```

**触发条件（已实测）**

同一 `root_execution_id` 下并发两个委派 A、B；只取消 A 的等待。`cancel_root` 把该 root 下**所有**作业的 future 与 execution 一并取消，B 随之被取消——尽管没有任何人要求取消 B。

**实际影响**

单个子任务的超时/放弃会摧毁整个 root 下的并行工作，包括其他分支已经跑到一半的结果。这是取消语义错误，直接对应「取消一个 root 不应错误取消其他共享工作」这条要求。

对照 Go：`internal/taskqueue/queue.go:270-335` 用 `sync.Once` 的 `finishTask` 加 **per-task** 的 `context.AfterFunc(requestCtx, baseCancel)`，**没有任何按 root 的取消广播**。Python 侧的 root 级广播是迁移过程中新引入的语义，不是对 Go 行为的翻译。

**归属确认**：`git log -S 'cancel_root'` → `3e62fce`（PR #5）。

**修复方向**

改为 per-task 取消：`shield` 外层捕获取消时只取消**本次** submit 出来的那一个作业（把 job 句柄回传给调用方），并用引用计数处理去重共享的 future——只有全部等待者都取消时才真正取消底层执行。如确实需要 root 级取消（比如整个 run 被中止），应作为独立的显式 API，由 run 的拥有者调用，而不是任一等待者取消时的副作用。

---

### F8 · P2 · PR #3 —— 提交后才做源库校验，检测到篡改已无法回滚

**文件与行号**：`src/fastclaw/migration/importer.py:155-157`

```python
if _sha256_file(source) != before_sha:
    raise RuntimeError("source database changed during target commit")
return report
```

**触发条件**

导入过程中源 Go DB 被并发写入（Go 服务未停机就执行迁移，属最可能的现实场景）。此时目标事务**已经提交**，这行校验只是在事后抛异常。

**实际影响**

目标库留下一份基于「读取期间发生变化的源」的部分/不一致快照，而调用方只收到一个 `RuntimeError`，无法区分「什么都没写」和「写了但可能不一致」。SHA-256 钉定本意是保证快照一致性，实际退化为一个事后告警。注意源库确实是以 `mode=ro` 打开的（已核验），因此这不是写坏源库的问题，而是目标库一致性无法保证的问题。

**归属确认**：`git log -S '"source database changed during target commit"'` → `db78a13`（PR #3）。

**修复方向**

把源校验移到目标事务 **commit 之前**，校验失败即回滚；或在导入开始时对源文件做快照拷贝（含 `-wal` / `-shm`）后再读取快照。若保留事后校验，异常信息必须明确告知「目标库已提交且可能不一致，需要丢弃重来」。

---

### F9 · P2 · PR #4 —— 重复 `tool_use` id 的归一化与 `_raw` 回放不一致，产生失配的 `tool_result`

**文件与行号**：`src/fastclaw/agent/runner.py:215-226`（`_normalize_live_calls`），与 `runner.py:239-259` 的 `_raw` 原样回写共同构成

**触发条件（已实测）**

Anthropic 流中出现两个相同 `id`（如 `"dup"`）的 `tool_use` 块时，`_normalize_live_calls` 把第二个重命名为 `"tool-live-0-1"`，但 assistant 的 `_raw` 是**逐字节原样保留并回放**的，里面仍是两个 `id: "dup"`。结果下一轮请求中：`_raw` 内有 `dup` / `dup` 两个 `tool_use`，而 tool 结果消息用的是 `dup` 与 `tool-live-0-1`——出现一个无法匹配任何 `tool_use` 的 `tool_result`，同时有一个 `tool_use` 没有对应结果。

**实际影响**

Anthropic 侧对 `tool_use` / `tool_result` 配对有严格要求，这种历史会导致后续轮次 400 或模型行为错乱。触发条件依赖 provider 返回重复 id（少见但并非不可能，尤其在流式分片重组出错时），故定 P2 而非 P1；一旦发生，该会话此后不可恢复。

**归属确认**：`877f366`（PR #4）新增的归一化逻辑。

**修复方向**

归一化必须与 `_raw` 同步：要么在重命名 tool call 时同步改写 `_raw` 中对应块的 `id`，要么在检测到重复 id 时放弃复用 `_raw`（回退为按 `content_parts` 重建 assistant 消息），并记录一条可观测的告警。二者不可只做其一。

---

### F11 · P2 · PR #5 —— `batch()` 缺少 `return_exceptions`，兄弟异常无人取回

**文件与行号**：`src/fastclaw/orchestration/bus.py:120-124`

```python
return tuple(
    await asyncio.gather(
        *(self.request(context, item.agent_id, item.task) for item in requests)
    )
)
```

**触发条件（已实测）**

`batch()` 中任一委派抛异常：`gather` 立即以该异常返回（fail-fast），其余仍在运行的 `request` 协程既不被取消也不被 await。它们后续抛出的异常无人取回，产生 `Task exception was never retrieved`；成功的兄弟结果同样被丢弃。

**实际影响**

批量委派的失败处理不可用——调用方只能看到第一个异常，无法知道其余分支的成败，也无法回收它们的结果；同时污染日志并留下悬挂任务。与 F10 叠加时后果更重：一个失败既触发 root 广播取消，又让兄弟异常散落。

**归属确认**：`3e62fce`（PR #5）。

**修复方向**

`gather(..., return_exceptions=True)`，然后按位置把每个结果分类为成功值或异常，聚合成结构化的批量结果返回给调用方；若语义上确实要 fail-fast，则必须在退出前显式取消并 await 其余任务。

---

### F12 · P2 · PR #5 —— handler 注册表只按 `agent_id` 索引，跨租户互相覆盖

**文件与行号**：`src/fastclaw/orchestration/bus.py:56`、`66`（`self._handlers[agent_id]`）

**触发条件**

`register(user_id=..., agent_id=..., handler=...)` 接收 `user_id`，但注册表的键只有 `agent_id`。两个租户注册同名 agent_id（如都叫 `researcher`）时，后注册者覆盖先注册者。此后 tenant A 的委派会命中 tenant B 注册的 handler。

需要说明的是：队列侧的 target key 是 `(user_id, target_agent_id)`（`bus.py:100`），跨租户校验（`CrossTenantError`）也确实存在并生效——所以这不是任意越权读取，而是**同名 agent 的 handler 实现被跨租户串用**。因此定 P2 而非 P0；但在多租户部署下这是真实的租户隔离缺口，且现有测试用的都是唯一 agent_id，永远命中不到。

去重键 `(root_execution_id, target_agent_id, task)`（`bus.py:103`）同样不含 `user_id`；由于 `root_execution_id` 实践中唯一，暂未构成可复现的跨租户串用，但它是同一处设计不一致的延伸，建议一并修正。

**归属确认**：`git log -S 'self._handlers[agent_id]'` → `3e62fce`（PR #5）。

**修复方向**

`_handlers` 改为以 `(user_id, agent_id)` 为键，与队列 target key 保持一致；重复注册应显式报错而非静默覆盖。去重键补上 `user_id`。

---

## 未确认风险

以下项因缺少真实生产数据、外部凭据或线上服务，本次**未能验证**，不作为 finding，但建议合并前补齐：

1. **`chat()` 与耗尽 `stream()` 的结果等价性**、以及 usage / cache token 累加的数值正确性。本次只用 MockTransport 构造了受控 SSE 序列；真实 Anthropic / OpenAI 兼容端点在分片边界、`cache_creation_input_tokens` / `cache_read_input_tokens` 上报时机、以及中途 HTTP 5xx 的表现上可能与构造流不同。EOF / 畸形 SSE / 主动关闭是否会被误判为成功，需要用真实 provider 的异常响应验证。

2. **Go 旧版（legacy）schema 的字段映射。** 本次基于 `792417b` 的当前 DDL 构造源库。importer 中针对更早 Go schema 的兼容分支（列缺失、`scope` 语义变更前的数据）没有真实旧库可测，映射正确性未确认。

3. **bcrypt / SHA-256 API key / API-key→Agent ACL 的跨语言兼容性。** 已核验 `internal/users/apikey.go:49-78` 的算法形状与 Python 侧一致，但没有真实 Go 生成的 hash 与 key 做端到端登录/鉴权验证。Go 侧生成、Python 侧校验的实测缺失。

4. **`busy_timeout` 在高并发下的实际效果。** WAL 与 `foreign_keys` 已确认在每条连接上生效（通过 engine `connect` 事件核验），但 `busy_timeout=5000` 是否足以覆盖真实并发写入场景，需要压测。

5. **等待图环检测在高并发下的竞态。** 已验证 call-path 环、以及 call_path 不一致时 wait-graph 仍能识别环（对应现有测试 `test_wait_graph_rejects_a_cycle_even_with_inconsistent_call_paths`），但没有做高并发随机化压测来排查假阳性/假阴性与 `_add_wait` / `_remove_wait` 之间的竞态窗口。

6. **`shutdown` 在并发 submit / execute / cancel 三方交织下的恰好一次语义。** 现有测试 `test_shutdown_completes_waiters_once_and_is_idempotent` 只覆盖了串行的幂等调用。

7. **`spawn_subagent` 的身份伪造面。** 已确认身份来自 `contextvars` 中的 `ExecutionContext` 而非模型参数这一设计，但没有完整枚举工具入参 schema 来证明模型无法通过任何字段影响 `user_id`。需要逐个工具定义审一遍。

8. **`WebFetchTool` 的 SSRF（`src/fastclaw/tools/builtin.py:119-131`）。** 只校验 scheme ∈ {http, https}，没有主机/IP 过滤（169.254.169.254、127.0.0.1、内网段）、没有重定向限制。这确实是可被模型触发的内网探测面。**放在这里而不是 Findings，是因为 Go 的 `internal/agent/tools/web_fetch.go` 同样没有主机过滤——按「不报基线既有问题」的要求，这不算迁移引入的回归。** 需要指出的是它是 PR #4 新写的代码，等于把同一风险重新实现了一遍；是否作为独立安全项处理，取决于对基线风险的处置计划，本报告不替这个决定下结论。

### 已撤销的疑虑

- 早前一项关于「CI 的 Python 3.14 矩阵可能因缺少 wheel 而失败」的疑虑**已被证伪并撤销**——`uv pip install -e ".[dev]"` 在 3.14 下退出码 0，安装成功。故该项不出现在 Findings 中。

