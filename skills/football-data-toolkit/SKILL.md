---
name: football-data-toolkit
description: Go Runtime 的受控通用足球数据工具包；TheSportsDB 确认比赛身份，ESPN 仅补充详情，赔率独立降级。
license: Apache-2.0
env:
  - name: ODDS_API_KEY
    description: The Odds API 密钥，仅由 Runtime 从环境变量注入；未配置时返回结构化 unavailable。
    required: false
---

# 通用足球比赛数据工具包（Go Runtime）

所有脚本位于 `scripts/`。事实查询必须先确认赛事、赛季、日期和对阵；不得用模型记忆补造实时事实。

## 数据源策略

- TheSportsDB 是赛程、结果、积分榜和比赛身份的主来源。
- ESPN 只补充详情、场地、近期 form、H2H 和事件。403、超时、空数据、畸形 JSON、结构变化或赛事/球队/日期不一致时，保留主来源结果并显式降级。
- The Odds API 与体彩是独立赔率来源，不得修改主比赛身份。Odds API 不可用或无覆盖时查询体彩；两者都失败时返回 `odds unavailable`。
- 每个来源输出 `source`、`status`、`as_of`，失败时只输出脱敏的 `error_code` 和 `safe_reason`。
- 禁止把 URL、ESPN slug、TheSportsDB league ID、Odds API sport key 或 `apiKey` 作为模型参数。

## 超时约定

所有 HTTP 请求走 `scripts/common/http_fetch.py`，不再直接用 `urllib.request.urlopen`。
原因：`urlopen` 的 `timeout` 是**按地址**计的，`getaddrinfo` 返回几个地址就乘几倍。
`www.thesportsdb.com` 解析出 3 个 Cloudflare anycast 地址，其中一个在部分网络上丢弃
SYN，实测一次「25 秒」的请求耗时 51.7 秒，而服务器本身 0.2 秒就应答——耗时 100% 在
connect。`http_fetch` 给每个地址一个 4 秒的首轮预算，并让声明的 timeout 成为整次调用
（含重试）的真实上限。

- 每次 HTTP 调用上限：TheSportsDB / 体彩 / Odds API 20 秒，ESPN 15 秒。
- 脚本级最坏情况是调用次数 × 上限：`thesportsdb_data.py` 与 `odds_data.py` 各两次调用。
- 只允许 https，只跟随同 host 跳转；跨 host 跳转按 `http` 错误拒绝。
- 传输层失败被归为 `timeout` / `connect` / `http` / `too_large` / `malformed` 五类，
  各脚本再映射到自己的 `error_code`。「没拿到应答」映射为 `unavailable`，
  「拿到了但不可用」映射为 `rejected`。
- 测试：`cd scripts && python3 -m unittest common.test_http_fetch -v`（仅标准库，
  用本地 TLS 服务器和黑洞地址，不访问真实数据源）。

## 命令

- `python3 scripts/thesportsdb_data.py --competition "瑞典超" --schedule --date 2026-08-10`
- `python3 scripts/thesportsdb_data.py --competition "英超" --standings --season 2026-2027`
- `python3 scripts/espn_data.py --list-competitions`
- `python3 scripts/espn_data.py --competition "瑞典超" --schedule --date 2026-08-10`
- `python3 scripts/espn_data.py --competition "FIFA World Cup" --summary --event 760496`
- `python3 scripts/odds_data.py --competition "瑞典超" --regions eu --markets h2h,totals --odds-format decimal`
- `python3 scripts/odds_data.py --competition "FIFA World Cup" --commence-from 2026-06-01T00:00:00Z --commence-to 2026-08-01T00:00:00Z`
- `python3 scripts/sporttery_data.py --match "IK Sirius" "IF Brommapojkarna"`

`odds_data.py` 先查询实时 sports catalog，再确认受审 `sport_key`。`ODDS_API_KEY` 只从环境变量读取，不进入输出、日志、数据库或异常。无 key、无覆盖或失败时，调用方应查询体彩当前赛事；禁止回退到模型记忆或猜测 sport key。

`thesportsdb_data.py` 是 Go Runtime 通用团队的比赛身份、赛程、赛果和积分榜主来源。
`espn_data.py` 只补充 ESPN 详情；`odds_data.py` 与体彩提供独立赔率证据。旧的
`match_data.py` 世界杯命令仅保留来源兼容，不用于通用赛事流程。
