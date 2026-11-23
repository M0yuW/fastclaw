# Presentation Q&A — Agent Runtime Project

使用方法：优先练习前 10 题。英文是可直接回答的短版本，中文是回答边界。一般先用 20–40 秒回答，再根据追问展开。以下依据现有报告和 slides，不表示新增实验或新部署状态。

## 1. What is the main contribution of this project?

The main contribution is the engineering implementation of a runtime that connects model reasoning to scheduled execution, tool use, agent coordination, and persistent application state. I also evaluate it through financial workflows and execution-mode comparisons. I am not proposing a new language model or a new financial prediction algorithm.

**中文要点：** 工程实现＋应用验证；不要宣称发明了多智能体或全新算法。

## 2. How is this different from a chatbot or a collection of scripts?

A chatbot mainly returns a response, while isolated scripts perform predefined operations. This runtime provides a shared execution layer in which the model can select tools, perform multiple steps, delegate tasks, and save application records. The contribution is the integration and control of those operations, including scheduling, scope, and traceability.

**中文要点：** 不是说 chatbot 一定不能调用工具，而是强调本项目实现的完整执行链路。

## 3. Why build a runtime when agent frameworks already exist?

Existing frameworks already provide many useful abstractions. My project is not intended to show that they are inadequate or that my system is universally better. Building the runtime allows me to implement and evaluate the specific combination of scheduling, session handling, delegation, tool integration, and research-state management used by these applications. A controlled comparison with other frameworks remains outside the current evidence.

**中文要点：** 如被问到具体框架，不凭印象声称别人不支持某项功能；本项目没有框架间性能基准。

## 4. What makes the financial analysis useful rather than just a summary?

In the Marqeta example, the answer distinguishes revenue and adjusted EBITDA growth from deteriorating GAAP profitability. It links that contrast to the difference between gross-profit growth and expense growth, and identifies specific questions for further investigation. The workflow also saves the review and keeps the thesis on hold. That makes it useful as research support, although it does not demonstrate profitable investment decisions.

**中文要点：** 有用之处是解释、风险和下一步；不能扩大为投资收益已验证。

## 5. Can you claim that the system consistently produces high-quality financial insights?

Not from the current evidence. I can show useful selected examples, checkable financial statements and calculations, and repeated execution of application workflows. But general insight quality also involves relevance, depth, and decision usefulness. Those aspects would require a broader evaluation and independent domain review. The report therefore makes a narrower claim about implemented capabilities and observed cases.

**中文要点：** 不回避局限，但也不把所有成果说成无效。客观核查能支持事实正确性，不能单独证明全面质量。

## 6. How did you evaluate the system?

I used separate layers of evidence. Deterministic tests check runtime mechanisms. Workflow checks verify tool calls and saved application state. Source and calculation checks examine selected financial claims. Local content review provides a further assessment of the answers, but it is not independent expert validation. Keeping these layers separate avoids treating successful execution as proof of a correct financial conclusion.

**中文要点：** 不声称每一条历史回答都完成了同样深度的逐结论核查；覆盖范围按相应实验说明。

## 7. Why did Team fail more checks than Solo in the all-Flash comparison?

The failed Team answers omitted required calculations or final evidence. Delegation introduces an additional synthesis step, so information returned during the workflow may not be fully retained in the final answer. The observed results show that risk, but they do not isolate every causal factor. In this comparison, Team was faster, while Solo was more complete under the strict checks.

**中文要点：** 区分直接观察“遗漏”与原因推断“交接可能带来损失”；没有消融就不要宣称已经证明唯一原因。

## 8. Why support Team if Solo passed more checks?

The runtime is designed to support different execution patterns. Team can reduce elapsed time when subtasks are sufficiently independent, while Solo can avoid some handoff overhead. The all-Flash results demonstrate this trade-off: Team was faster in all 24 pairs, but passed fewer strict checks. The appropriate choice depends on the task's completeness, latency, and cost requirements.

**中文要点：** 不为 Team 辩护成“更聪明”；选择权和可观测取舍本身是工程价值。

## 9. Are failures caused by the runtime or the model?

They can occur at different layers. A provider timeout, an invalid tool argument, a missing tool call, and an incorrect financial interpretation are different failure types. The traces and saved state help locate where a failure occurred. However, the observed location does not always establish the root cause: prompts, tool design, context, and model behavior can interact. I would use targeted tests before attributing a failure exclusively to one component.

**中文要点：** 不把所有问题都推给模型，也不把账户余额问题当成 runtime 缺陷。

## 10. What exactly does 77 out of 80 mean?

It is the number of attempts that passed the configured mechanical workflow checks in the 16-case repetition panel. All 80 attempts completed, but three failed those requirements. Two printed a tool call as text instead of actually issuing it; another omitted a corrected capex value from the saved review rationale. This is not a financial-analysis accuracy rate, because other content problems can exist even when the workflow checks pass.

**中文要点：** 这是不同于 24 对 Solo/Team 的实验。不要说“金融分析准确率 96.25%”。

## 11. Is the Marqeta case cherry-picked?

It is a selected illustrative case, and I describe it that way. It shows what the implemented workflow can produce, rather than estimating how often all future tasks will succeed. I present it alongside the broader workflow results and known failures so that the example is not mistaken for a representative quality rate.

**中文要点：** 可以合理展示成功案例，但必须明确选择性质，不能用其替代总体结果。

## 12. Did the agent calculate everything itself?

No. In the highlighted Marqeta case, a checked comparison catalog supplied the arithmetic. The model selected and interpreted those comparisons, identified opposing signals, and completed the research-record workflow. The case tests evidence interpretation and application execution, not unaided extraction and calculation from an entire filing.

**中文要点：** 预先核对的比较项属于工具/任务输入，不掩饰这一点。

## 13. Were these genuine end-to-end tests?

The financial workflow tests cover the chain from a task request through agent execution and financial tool calls to saved research records. That is the end-to-end boundary used here. Many inputs were frozen or synthetic, so those tests do not also validate live upstream retrieval. A separate live Skill example extends the chain to online market-data retrieval, but its scope is limited.

**中文要点：** 早期 SEC 模式比较与后续工具＋账本工作流不是同一个测试范围。不能把早期所有测试都说成调用了财务工具。

## 14. Why use frozen data or synthetic portfolios?

Frozen inputs make the source values and expected outcomes stable enough to inspect and repeat. Synthetic portfolios also let me construct specific conditions, such as limit violations or missing holdings. These inputs are appropriate for testing defined behaviors, but they do not fully represent the diversity or instability of live financial applications.

**中文要点：** 合成数据用于可控条件；真实资料用于应用可信度，两者互补。

## 15. Does the system support real-time analysis?

It can use Skills and tools to retrieve online data during a session, and a separate live case connected retrieval to a saved research record. However, that depends on source availability, rate limits, and response time. I would describe it as supporting on-demand online analysis, rather than claiming a continuously available real-time market system.

**中文要点：** “在线按需分析”比“实时系统”准确；没有延迟 SLA 或连续监控证据。

## 16. What happens when evidence is missing or contradictory?

For the tested critical-evidence cases, the workflow places the thesis under review, preserves its existing status and conviction, and blocks its downstream use. This separates the historical conclusion from whether it is currently safe to use. The broader idea is to avoid silently treating unresolved uncertainty as a confirmed conclusion. It does not mean that every minor disagreement must trigger a hold.

**中文要点：** “结论暂不变，但暂停用于后续决策”。关键证据规则不能被说成适用于所有金融情况的普遍准则。

## 17. How does the main agent ensure accurate delegation?

It does not guarantee accuracy simply by delegating. A useful subtask needs a clear objective, relevant context, expected output, and a defined boundary. The runtime correlates requests with returned results and records the execution, but the coordinator still has to interpret and combine the outputs. Additional evidence checks are needed when the final conclusion depends on those results.

**中文要点：** 请求关联保证“结果属于哪项委派”，不保证“子 agent 的内容必然正确”。不要把建议的任务规范说成已经全部强制实现。

## 18. What happens if the user's request is ambiguous?

The separate Python prototype allows the model to issue a structured clarification request. The runtime pauses that turn before sibling tools execute and stores the question. The user's next reply is included in the conversation so that execution can continue. The control flow is locally tested, but deciding when clarification is necessary still depends on model behavior.

**中文要点：** “系统怎么处理”先回答暂停、存储、续接；然后再讲依赖模型判断。不要只回答设计原则。

## 19. How would you test clarification behavior?

I would freeze a small panel containing genuinely ambiguous requests and sufficiently clear requests. For ambiguous tasks, I would check whether the agent asks a relevant question before consequential action. For clear tasks, I would measure unnecessary interruptions. After a predefined user reply, I would check task completion and the resulting state. Repeated runs would measure variability. This is a proposed next evaluation, not a completed result.

**中文要点：** 三项：该问时问、清晰任务不乱问、回复后能完成。问题数量少并不自动代表澄清质量高。

## 20. How does session compression work, and can it fix failed answers?

The evaluated Go implementation estimates context size at turn entry. Above its configured threshold, it first shortens older tool results while retaining recent messages. If that is insufficient, it summarizes older history. This can reduce context pressure, but summaries can also lose information. The isolated SEC sessions did not test compression as an experimental treatment, so I cannot claim that it would fix the observed answer failures.

**中文要点：** 如果被问具体参数：报告记录约 80,000-token 估计阈值、保留最近 20 条消息；这是当前报告实现，不是模型实际容量保证。

## 21. What does the load test prove?

It supports the behavior of the task queue under the tested local conditions: configured concurrency limits, per-chat ordering, and completion of synthetic tasks. It used 48 tasks across 12 chats and repeated the concurrency settings. Because it excluded model calls, database work, and external tools, it does not establish production throughput or user-facing latency under load.

**中文要点：** 不把 15 ms 人工 handler 的吞吐外推成真实金融 agent 的容量。

## 22. Can the system recover automatically after a crash?

The system persists sessions and application records, but the evaluated queue and pending request correlations are process-local. Persistence alone does not provide automatic replay or exactly-once recovery of interrupted external operations. Stronger crash recovery would require additional durable scheduling and operation-specific recovery mechanisms, which are outside the current claim.

**中文要点：** 持久化不等于任务自动恢复；不要承诺 exactly-once。

## 23. Why use Flash rather than a more powerful model?

The project focuses on runtime capabilities, so it is useful to test whether the workflow can operate with a lower-cost model. Using the same model tier in the matched Solo and Team comparison also removes the tier difference from that comparison. A stronger model might change the outcomes, but these results alone do not establish model independence or predict performance with every provider.

**中文要点：** 模型可替换是架构目标；实验效果依然依赖模型，不能说模型完全不重要。

## 24. Are repeated runs enough to establish reliability?

Repeated runs show variability on the selected cases, but they do not make those cases representative of all future tasks. Some configurations also share source material. I therefore report the observed counts and conditions rather than treating them as a population-level reliability guarantee. Broader claims would need more independent cases, predefined acceptance criteria, and appropriate uncertainty analysis.

**中文要点：** 重复次数与案例多样性不是同一回事，不把相关观测当完全独立样本。

## 25. What would you improve next?

I would prioritize the boundary between conclusions and evidence, especially checking that important claims and corrections are reflected in the saved research record. I would also evaluate the clarification prototype on the three behaviors discussed earlier. Those are focused improvements supported by the observed limitations; I would not expand the experiment scope without a specific question to answer.

**中文要点：** 与当前成果相衔接，不承诺重写系统、无限扩大实验或立刻实现分布式部署。

## Quick reference — numbers and boundaries

| Item | What to remember | What not to claim |
|---|---|---|
| Matched all-Flash comparison | 24 pairs; Solo 24/24, Team 19/24 strict passes | Team is universally better or worse |
| Mean latency | Solo 33.62 s; Team 22.42 s; about 33% lower | A general production speedup guarantee |
| Workflow repetition panel | 16 cases × 5 runs; 77/80 mechanical passes | 96.25% financial-insight accuracy |
| Critical missing evidence | 10/10 tested repetitions preserved thesis and blocked use | Every future missing-evidence case will be detected |
| Marqeta demonstration | Selected case; checked arithmetic; 5 sessions saved linked reviews and held thesis | Independent expert validation or investment performance |
| Scheduler test | 48 tasks, 12 chats, 5 repetitions per concurrency setting | Full-service load capacity |
| Clarification | Separate Python prototype; deterministic control-flow tests | Real-model clarification behavior already validated |

## Useful phrases when answering follow-ups

- **Clarify the scope:** “Do you mean the runtime execution behavior, or the quality of the financial conclusion?”
- **Separate evidence from explanation:** “What I observed was … My interpretation is …, but I have not isolated that factor experimentally.”
- **Avoid guessing:** “I have not measured that directly, so I would not want to give an unsupported number.”
- **Acknowledge a valid limitation:** “Yes, that is a limitation of the current evaluation. The narrower claim supported by the results is …”
- **Distinguish prototype from evaluated system:** “That mechanism is in the separate Python prototype; the earlier experiments evaluate the Go implementation.”
- **Return to the contribution:** “The runtime does not guarantee the model's judgment, but it makes the execution and resulting state inspectable.”

## Preparation priority

第一轮：练习第 1、4、5、6、7、9、10、13、18、24 题。第二轮：根据教授关心的方向补充架构、压缩、模型和恢复问题。不要逐字背诵整份 Q&A。

Evidence basis: `fastclaw_project_report.md`, especially its session-management discussion and sections VII-A through VII-D; `Speaker_Notes_Visual.md` for the slide-specific narrative and separate Python prototype scope. No external judge call or new paid experiment was performed to prepare this document.
