# Oral Presentation Script — An Auditable Agent Runtime

配套：Agent_Runtime_Project_Overview_Updated.pptx，10 页。

英文为可直接练习的口头稿；中文提示和方括号动作不朗读。建议先计时练习一遍，目标约 10 分钟，实际取决于语速和指图停顿。不要把每个数字都念出来。Q&A 另见同目录 Presentation_QA_EN_ZH.md。

## Slide 1 — Introduction | 0:00–0:35

Good morning, Professor Fong. Today I would like to present my project on an auditable agent runtime.

The project focuses on the software layer around a language model: how it executes tasks, uses tools, coordinates agents, and saves the results in an application.

I will first introduce the system design, then show its financial research applications, and finally discuss the evaluation results and remaining limitations.

**中文提示：** 开场先明确项目是 runtime，不是新模型，也不是金融预测模型。如果在下午汇报，将 Good morning 改为 Good afternoon。

## Slide 2 — Why a Runtime? | 0:35–1:25

A language model can produce a convincing answer, but an application usually needs more than an answer.

For example, reviewing a company's earnings may require retrieving disclosures, checking calculations, comparing conflicting evidence, and updating a research record. These steps need to happen in the right order, under the correct user context, and with records that we can inspect afterwards.

This is the problem my project addresses. The runtime connects model reasoning to controlled execution and persistent application state.

Financial research is a useful application for testing this design because dates, accounting definitions, evidence, and saved decisions all matter. However, completing a workflow and producing a correct financial conclusion are different things, so I evaluate them separately.

**中文提示：** 核心句：“模型给出答案”不等于“应用完成工作”。

## Slide 3 — System Architecture | 1:25–2:35

[Point from the left-hand input toward the Gateway, then to the lower supporting components.]

This diagram shows the main execution path. A request enters through a web interface or an API. The system resolves the user and agent scope before starting the task.

Inside the Gateway, the message bus connects requests and responses. The task queue controls when work can run, and keeps tasks within the same chat in order.

The agent loop then prepares the conversation, calls the model, and executes the tools requested by the model. Tool results return to the loop, which can continue until it produces a response or reaches an execution limit.

The supporting components connect the loop to model providers, tools, and persistent records. Sessions preserve conversation history, while traces help us inspect individual calls and outcomes.

The evaluated implementation uses a single Gateway process. Its scheduling state is process-local. Therefore, I am not claiming distributed scheduling or automatic recovery of every interrupted external action.

**中文提示：** 沿着箭头讲，不逐个念模块。图是逻辑架构；身份检查不是独立部署的服务。最后一句说明边界即可，不必反复强调。

## Slide 4 — Core Engineering Mechanisms | 2:35–3:40

There are four main engineering mechanisms.

First, scheduling controls concurrent work and preserves ordering within each chat. Timeouts and cancellation help bound execution.

Second, session management maintains a usable conversation history. It repairs tool-call history and reduces long histories through pruning and summarization. This helps manage limited context, although a summary can still lose details.

Third, tools run within a resolved user and agent scope. Tool filtering and separate plugin processes provide execution boundaries. They are useful controls, but they are not a complete security guarantee.

Fourth, the runtime records calls and outcomes. When something goes wrong, we can inspect whether the problem occurred in the provider request, the tool invocation, the agent handoff, or the saved application state.

Together, these mechanisms make the execution easier to control and investigate. They do not guarantee that every model judgment is correct.

**中文提示：** 四个关键词：调度、会话、工具边界、追踪。不要把“可审计”说成“自动保证正确”。

## Slide 5 — Solo and Team Execution | 3:40–4:30

[Point to the serial path, then the fork-and-join path.]

The same runtime supports both Solo and Team execution.

In Solo mode, one agent carries out the stages in sequence. This keeps the analysis within one execution path.

In Team mode, a coordinator delegates focused subtasks to specialists and combines their results. Independent subtasks can run in parallel, which may reduce elapsed time.

However, delegation also introduces handoffs. Evidence or calculations can be lost when specialist outputs are combined.

So the objective is not to prove that more agents are always better. It is to support both modes and make their trade-offs visible, so the application can choose an appropriate execution pattern.

**中文提示：** 三个 specialist 只是示意，不代表系统固定只能有三个。

## Slide 6 — Financial Workflows | 4:30–5:35

[Point to the four input families, then follow the common path to saved records.]

Following your suggestion to explore more business and financial applications, I expanded the evaluation to four workflow families.

The first reviews earnings disclosures and updates a research view. The second screens companies against criteria and creates candidate research records. The third diagnoses risks in supplied portfolio holdings. The fourth handles conflicting or missing evidence.

For the conflict workflow, the default is to preserve the existing thesis but block its use in later decisions until the issue is reviewed.

These workflows go beyond generating text. They use financial tools and save application records, including reviews, thesis updates, and alerts.

Most tests use frozen disclosures or synthetic inputs so that the expected behavior can be checked. There is also a separate live-data Skill example, but that single example does not establish continuous availability of external data sources.

**中文提示：** 四类应用共享工具和状态链路；不要说所有案例都用实时真实行情。

## Slide 7 — A Concrete Example: Earnings Quality | 5:35–7:00

This Marqeta example illustrates the kind of useful analysis the workflow can produce.

The task compares selected earnings disclosures for the second and third quarters of 2025. Revenue increased, and company-defined adjusted EBITDA also increased. However, the GAAP operating loss and net loss became larger.

[Point to the table, then compare the two bars on the right.]

The useful observation is that business growth and improving accounting profitability are not the same thing.

The comparison also provides a specific explanation. Gross profit increased by about 10.50 million dollars, but operating expenses increased by about 11.64 million. The difference explains the approximately 1.14 million deterioration in the operating result.

The arithmetic came from a checked comparison catalog. The model's role was to select and interpret the evidence, recognize the opposing signals, and identify what needed further investigation, such as expense drivers and the reconciliation between accounting measures.

All five sessions saved linked reviews, acknowledged the alerts, and kept the thesis held and blocked from subsequent use.

This is a selected example of useful, evidence-linked analysis. It is not proof that the system always produces high-quality investment insights, and it has not been independently validated by financial experts.

**中文提示：** 价值是“识别相反信号＋定量解释＋明确待查事项＋保存研究状态”，不是简单复述收入增长。承认计算来自已核对目录，不说模型自行完成全部原始财报分析。

## Slide 8 — Evaluation Results | 7:00–8:20

[Point first to the time chart, then to the completion chart.]

I separate the evaluation into three types of evidence.

First, the model-matched comparison uses Flash for both Solo and Team. Across 24 paired observations, Team was faster in every pair. Mean latency was about 22 seconds for Team and 34 seconds for Solo, or roughly one-third lower for Team.

However, Solo passed all 24 strict checks, while Team passed 19. The Team failures involved missing calculations or final evidence. This shows a speed and completeness trade-off, rather than a general superiority of Team execution.

Second, a separate financial workflow panel recorded 77 passes on workflow checks out of 80 attempts. These checks concern tool use and required application outcomes. They should not be interpreted as 77 fully correct financial analyses.

Third, a scheduler-only load test checked ordering and concurrency limits using 48 synthetic tasks across 12 chats. All tasks completed within the configured scheduling constraints in the tested runs.

These experiments provide different kinds of evidence. They should not be combined into a single overall reliability score, and the scheduler test is not a production capacity benchmark.

**中文提示：** 24 对比较、80 次工作流、调度测试是不同实验。不要合并分母，也不要把严格通过率当作金融洞察质量分数。

## Slide 9 — Clarification within a conversation | 8:20–9:15

[Read the dialogue from top to bottom.]

This example shows how the runtime handles an unclear request. The user asks to compare the latest results, but has not specified the company or the periods. The agent asks a focused question.

The runtime saves that question and pauses the turn before executing the other tools in the response. When the user replies with Marqeta and the two quarters, the next turn uses the conversation history to continue the original task.

This is a conversational pause. It does not keep a worker waiting, and it does not undo earlier actions. The dialogue on this slide illustrates the interaction rather than reporting a recorded test.

**中文提示：** 沿着四行对话讲清“缺信息、提问、补充、继续”。不区分实现语言，也不把示意对话当成实验结果。

## Slide 10 — Conclusion | 9:15–10:00

To conclude, the contribution is an auditable runtime that connects model reasoning with controlled execution and persistent application state.

The financial workflows demonstrate applications beyond a standalone chatbot response. The experiments show that the system can execute these workflows and expose useful trade-offs, while the case study illustrates a useful form of evidence-linked financial analysis.

My claim is therefore practical and bounded: the project provides an implemented runtime, working application workflows, and inspectable evaluation evidence. It does not establish universal analytical reliability or investment performance.

I would welcome your feedback on whether the engineering work and application evidence are sufficient for the project report, and which aspect would benefit most from further clarification.

Thank you. I am happy to take your questions.

**中文提示：** 收束到工程成果和应用证据，不在结尾临时承诺再做大规模实验。

## Rehearsal checklist

- 先完整计时一次，按自己的语速调整；不要为了赶时间加速念限制条件。
- 第 3、5、6 页用手势或光标指图；图中细节留给提问。
- 第 7 页可停顿，让听众看出“增长指标改善，但 GAAP 亏损扩大”的对比。
- 记住三组数字：24/24 对 19/24；33.62 秒对 22.42 秒；77/80 是机械通过。
- 时间不足时缩短第 4 页机制细节和第 6 页应用描述，保留第 7 页案例与第 8 页证据边界。
- 不背诵每句话；每页记住一个结论和一个过渡。

## Evidence basis

Prepared against the existing visual deck and current `fastclaw_project_report.md`, especially the architecture/session sections and evaluation sections VII-A through VII-D. No new experiment was run for this script. The Python clarification status follows the separate prototype description in the accompanying slide notes; it is not presented as a newly verified deployment status.
