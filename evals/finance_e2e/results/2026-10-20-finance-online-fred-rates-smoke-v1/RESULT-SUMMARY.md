# 在线金融数据冒烟测试（2026-10-20）

## 部署修复

18953 Go Gateway 使用的主配置数据库中，`finance-tools` 的 `finskillsPath`、`serenitySkillPath`、`stateDbPath` 仍指向迁移前的 `/Users/wangzheyu/`。修改前分别备份主配置库和财务账本至 `/private/tmp/fastclaw-finance-config-before-online-smoke-20261020.db`、`/private/tmp/fastclaw-finance-ledger-before-online-smoke-20261020.db`。本次只更新该插件的四个配置值：三个路径指向当前 `/Users/m0yuw/` 下的资源，并将 `pythonBin` 指向项目内隔离虚拟环境。兼容入口位于 `tools/live-finskills/`，调用已安装的全局金融 skill 原脚本，不修改其内容。US/CN 六个入口均存在，`yfinance`、`akshare`、`numpy`、`scipy`、`requests` 均可导入。

主服务经 LaunchAgent 重启后，18953 Gateway 与其 `finance-tools` Python 子进程持续运行，启动日志显示插件 `started`。本次没有创建或修改观点、告警或持仓账本记录。

## 在线调用与结果

1. 美股 AMD 的 `stock_snapshot(history,5d)` 确实执行了真实 Yahoo 取数脚本，但上游返回 `Too Many Requests. Rate limited.`。结果保留于相邻目录 `2026-10-20-finance-online-smoke-v1/result.json`，状态 `needs_review`，不能算取数成功。
2. A 股 600519 的 `stock_snapshot(basic)` 通过插件发起，45 秒内未完成，上游超时。该尝试只作为诊断，不计入成功案例。
3. 已安装的 SEC skill 直接在线查询 AMD 最近两份 10-Q，获得 2026-08-05 的 accession `0000002488-26-000123` 和 2026-05-06 的 accession `0000002488-26-000076`，含原始 filing URL。这验证了 skill 的动态公开资料入口，但不是通过 `finance-tools` 原生工具调用，也不是 Agent 全流程。
4. 使用已部署的 `finance-tools` 插件执行一次 `macro_snapshot(US,rates)`，经 FRED 在线 CSV 接口获取 `FEDFUNDS` 月度序列。2026-10-20T15:31:56Z 工具回包，最近一条记录日期为 **2026-09-01、数值 3.75%**；来源标注为 `FRED` 和 `finskills`，非评测 fixture，缓存未命中，带 `as_of` 与 `stale_after`。7/7 冒烟断言通过，完整原始回包在 `result.json`。该数值和月度口径可在 [FRED 官方序列页](https://fred.stlouisfed.org/series/FEDFUNDS) 独立核对。

首次 FRED 回包实际来自 FRED，却被插件标成 `yfinance`。已修复项目源代码和本机部署副本的 US macro 来源映射，并在修复后重跑、重新启动 18953。插件单元测试 20/20 通过。首次错误回包未写入最终成功结果。

## 结论边界

本次证明本地部署可以通过金融插件从在线公开源获取带日期、数值和来源标识的宏观数据，也证明全局 SEC skill 可在线列出最新可用文件。它**不证明** Yahoo 行情和 AKShare 在此网络环境中可用，不证明逐笔实时行情，也没有运行“Agent 推理→观点落账”的完整在线工作流。FRED 是按月发布的序列；`as_of` 是工具取回时间，不是数据观察日期。完整端到端实时分析需要另设任务，并对源站限流、超时及数据时效继续控制。
