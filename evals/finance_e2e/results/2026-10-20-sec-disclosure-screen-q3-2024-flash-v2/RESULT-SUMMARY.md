# 冻结 SEC 来源的筛选→候选观点端到端回放（修订版）

本次为 **1 次历史回放**，不是实时选股、投资建议或统计可靠性估计。输入与规则见 [`sec_disclosure_screen_q3_2024_v1.json`](../../sec_disclosure_screen_q3_2024_v1.json)，原始结果、配置哈希分别见 `result.json`、`manifest.json`。修订版与首跑使用同一批冻结 SEC 原文、同一候选与同一两项阈值；修复了运营审阅日期校验，并把结构化账本证据纳入机械判分。首跑数据没有被覆盖。

## 来源与冻结数值

- [AMD Q3 2024 SEC 8-K 附件](https://www.sec.gov/Archives/edgar/data/2488/000000248824000161/q32024991.htm)，公告日期 2024-10-29，GAAP 季度营收 USD 6,819 million、同比 +18%，GAAP 毛利率 50%；Gaming 营收 USD 462 million、同比 −69%。核对位置：`GAAP Quarterly Financial Results`、`Segment Summary`。缓存原文 SHA-256：`288e1c639d72dbc0fa2e0fe1704990cf923defb0e49f8a3c39e9dc4883f7285f`。
- [Intel Q3 2024 SEC 8-K 附件](https://www.sec.gov/Archives/edgar/data/50863/000005086324000147/q324_earningsrelease.htm)，公告日期 2024-10-31，GAAP 季度营收约 USD 13.3 billion、同比 −6%，GAAP 毛利率 15.0%，重组费用约 USD 2.8 billion。核对位置：`Q3 2024 Financial Highlights`、`Q3 2024 Restructuring and Impairment Charges`。缓存原文 SHA-256：`168fed7a3314be07cb5b4e6ae7f7f1b9d89e4f67fa16d4aa2432561ca6df9283`。

核对方法：以来源锁中的 URL 和 HTML SHA-256 校验离线缓存，逐项对照上述原文表格/段落的期间、GAAP 口径、单位和数值，再用确定性规则计算筛选结果。案例规则是 GAAP 毛利率至少 40% 且营收同比不低于 0%；这是工作流演示阈值，不是 SEC 的投资结论，也不是盲法选择的样本。未输入股价、估值、分析师预测或未来收益率。离线适配器在 `screen_stocks(require_complete=false)` 调用中只提供两项规则所需的披露字段，并显式标识非实时市场数据；这不验证默认七因子筛选的完整性门槛。

## 运行与终态

Flash 隔离会话的实际轨迹包含一次 `finance-tools__screen_stocks` 和一次 `finance-tools__thesis_save`；筛选保留 AMD、拒绝 Intel。空账本最终只有一条 AMD `researching`、conviction 1 的历史初步候选观点，没有 Intel 观点、交易或实时行情调用。观点及结构化 evidence 保留了 AMD 五项原值、期间、单位、SEC URL 与哈希，并记录 Gaming 分部下滑以及估值证据缺口。历史资料日期与运营字段分离，`next_review_at` 未被错误设置为过去日期。

`result.json` 原始状态为 `mechanical_pass`，13 项机械检查均为 true；独立只读审计 `adjudicate_sec_disclosure_screen_v2.py` 为 **9/9**。模型调用 3 次，工具调用均配对，未见请求错误、终态错误、未定价或费用不确定记录。估算费用 **USD 0.0017250576**，低于本次 USD 0.01 停止线。原始 `result.json` SHA-256：`d1d8bcac96ac653e3a3b10119eadd890c442bd9646606351a15ad80cf4a9282d`。

这项证据支持：现有运行时在一个真实可核查、但历史冻结的 SEC 输入上，能完成“来源核验→确定性筛选→候选/拒绝解释→带来源的初步观点落账”。它不证明筛选阈值具有投资价值，也不证明该路径在其他公司、季度或实时条件下具有统计可靠性。旧版首跑的过去 `next_review_at` 与判分假阴性保留在旧目录，不能将两次运行混为一条观测。
