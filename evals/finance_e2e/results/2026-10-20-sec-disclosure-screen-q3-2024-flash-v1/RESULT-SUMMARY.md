# 一次真实 SEC 来源的筛选→候选观点端到端实验

## 案例边界

这是 **1 次历史回放**，不是实时选股，也不是投资建议。输入为项目中已按 SHA-256 锁定的两份 SEC 8-K 财报附件：

- [AMD 2024 年第三季度业绩公告](https://www.sec.gov/Archives/edgar/data/2488/000000248824000161/q32024991.htm)：GAAP 营收 USD 6,819 million、同比增长 18%、GAAP 毛利率 50%；Gaming 营收 USD 462 million、同比下降 69%。原文位置为 “GAAP Quarterly Financial Results” 与 “Segment Summary”。原始 HTML SHA-256：`288e1c639d72dbc0fa2e0fe1704990cf923defb0e49f8a3c39e9dc4883f7285f`。
- [Intel 2024 年第三季度业绩公告](https://www.sec.gov/Archives/edgar/data/50863/000005086324000147/q324_earningsrelease.htm)：GAAP 营收约 USD 13.3 billion、同比下降 6%、GAAP 毛利率 15.0%；另披露约 USD 2.8 billion 重组费用。原文位置为 “Q3 2024 Financial Highlights” 与 “Q3 2024 Restructuring and Impairment Charges”。原始 HTML SHA-256：`168fed7a3314be07cb5b4e6ae7f7f1b9d89e4f67fa16d4aa2432561ca6df9283`。

预先写定的**案例筛选规则**（不是 SEC 本身给出的结论）：同一 Q3 2024 期间，GAAP 毛利率至少 40%，且营收同比不低于 0%。股价、估值、分析师目标价和预期回报不在输入范围内。该阈值是用于演示工作流的研究规则，选取这两个公司和阈值并非盲法或代表性抽样。

`sec_disclosure_screen_q3_2024_v1.json` 冻结了原值、规则、链接、原文定位和哈希；离线适配脚本每次读取来源锁并校验本地 SEC HTML 哈希，再执行两项确定性条件。调用的仍是运行时 `finance-tools__screen_stocks`，但设置 `require_complete=false`，因为通用七因子筛选所需的股价/估值/分析师指标根本不属于本案例；工具回包明确标记 `offline_frozen_adapter=true`、`not_live_market_data=true`。不能把它写成实时行情筛选或通用七因子筛选已经通过验证。

## 原始运行及复核

- 使用隔离网关会话和空财务账本，仅运行一次 Flash。模型工具轨迹为 **1 次真实 `screen_stocks` 调用 + 1 次 `thesis_save` 调用**；无交易、无实时市场数据调用。工具保留 AMD、以两项条件均不满足拒绝 Intel。账本只新增 AMD 的 `researching`、低 conviction、标有 `HISTORICAL PRELIMINARY` 的观点；Intel 没有观点记录。
- AMD 持久化 evidence 中有营收 6819、营收同比 18%、GAAP 毛利率 50%、Gaming 营收 462、Gaming 同比 −69%，每条均保留期间、单位、SEC URL 和完整 SHA-256。最终答复说明了 Intel 的拒绝理由、AMD Gaming 风险及估值/价格数据缺口。所示数值和筛选算式与上述 SEC 原文一致。
- 原始 `result.json` 的 `status=needs_review`：唯一失败项 `reported_values_and_risk` 只在 `thesis` 正文中找 `462` 和 `69%`；模型把这两个数保存在结构化 `evidence` 与 `assumptions`，并在最终答复复述。**原始结果不改写。** 后置只读脚本 `adjudicate_sec_disclosure_screen_v1.py` 检查持久化证据、单位、来源、工具和终态，8/8 项通过，明确将此项识别为正文限定检查造成的假阴性；这不是第二次模型运行。
- 请求错误、费用不确定、未定价调用均为 0；估算费用 **USD 0.0016445576**，低于 USD 0.01 停止线。原始 `result.json` SHA-256：`f2fa73c508e757fbe754597eb4c564c3c47546562e24199d7d6080eb1b6615ef`。`manifest.json` 保存输入、脚本、插件、网关及配置快照哈希。

## 能支持及不能支持的结论

本次证明了：在一个**真实、可回溯但历史冻结**的 SEC 输入上，现有 runtime 能完成“来源校验→确定性筛选工具→agent 解释保留/拒绝→带来源的初步观点落账”的单次端到端路径。它不证明该阈值有投资价值、不证明观点能预测回报，也不证明在新公司、新时期或实时数据上具有统计意义的可靠性。

还有两个应保留的工程限定：第一，`require_complete=false` 是为了使用不同于默认七因子的、仅依赖已披露字段的演示规则，不能把它当作默认完整性保护的成功案例。第二，agent 在历史回放账本里填写了过去的 `next_review_at=2024-10-31`；用于真实调度前，应把“数据截至日”和“下一次实际审阅时间”分开处理。本次没有静默修改该终态。
