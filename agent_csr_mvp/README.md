# 智能客服 Agent MVP 学习说明

这个目录是把 `learn_agent/refer/0531/智能客服系统设计.md` 落成的 MVP 版代码。  
入口文件是 `step30_csr_mvp.py`，命名成 step30 是为了接在你当前学到的 `step29_integrated_pv3_mini.py` 后面。

运行：

```bash
python3 learn_agent/agent_csr_mvp/step30_csr_mvp.py
```

## 1. 这个文件的作用

`step30_csr_mvp.py` 是一个智能客服多 Agent 的整合版 demo。

它在项目链路里的角色类似 `step29_integrated_pv3_mini.py`：

- `Chatbot` 是用户入口
- `CustomerServiceGraph` 是流程图/graph 层
- `SupervisorAgent` 是中央编排者
- `IntentRouterAgent` 负责意图路由
- `KnowledgeRagAgent` 负责知识库问答
- `TicketAgent` 负责订单查询和工单创建
- `ComplianceAgent` 负责最终回复的合规审查
- `ShortTermMemoryStore` 模拟 Redis 短期记忆
- `KnowledgeBase` 和 `TicketStore` 模拟长期记忆
- `LocalMcpToolRegistry` 模拟 MCP 工具注册和调用

## 2. 熟练程序员会先看什么

建议阅读顺序：

1. 先看 `main()`：知道 demo 会问哪些问题。
2. 再看 `Chatbot.chat()`：用户输入如何变成 `AgentState`。
3. 再看 `CustomerServiceGraph.invoke()`：短期记忆如何注入 state。
4. 再看 `SupervisorAgent.invoke()`：Supervisor 如何调度各个子 Agent。
5. 最后分别看 `IntentRouterAgent`、`KnowledgeRagAgent`、`TicketAgent`、`ComplianceAgent`。

暂时不用深究的是：关键词打分、正则提取订单号、mock 订单数据。这些只是为了让 MVP 能跑起来，真正项目里可以替换成 LLM、向量数据库、Redis、真实 MCP Server。

## 3. State 怎么流动

`AgentState` 是整条客服流程上传递的总状态。

一开始由 `Chatbot.chat()` 创建，重要字段包括：

- `messages`: 当前会话消息
- `user_id`: 用户 ID
- `session_id`: 会话 ID
- `user_text`: 本次用户问题
- `short_memory_context`: 短期记忆注入的上下文，一开始为空，graph 层填充
- `intent`: 意图路由结果，一开始为空，路由节点填充
- `sub_results`: 子 Agent 的输出结果
- `tool_records`: 工具调用记录
- `compliance_passed`: 合规是否通过
- `final_response`: 最终回复
- `trace`: 简化版链路追踪

文字流程：

```text
用户输入
-> Chatbot 创建 AgentState
-> Graph 注入短期记忆
-> Supervisor 调用 IntentRouterAgent
-> 根据 intent 分发给 KnowledgeRagAgent / TicketAgent / Compliance 分支
-> 生成 draft_response
-> ComplianceAgent 审查所有回复
-> 如果不通过，创建转人工工单
-> 写入 final_response
-> Chatbot 把本轮问答写回短期记忆
```

## 4. 对应 step29 的概念迁移

`step29` 里你学过：

- Text2SQL/RAG 路由
- memory_context 注入
- tool orchestrator
- GraphState
- Chatbot 作为入口
- `invoke()` 作为高层流程方法

这个 MVP 里对应变成：

- SQL/RAG 路由 -> 客服意图路由
- `MiniRagEngine` -> `KnowledgeRagAgent`
- `ToolOrchestrator` -> `LocalMcpToolRegistry`
- `GraphState` -> `AgentState`
- `MiniPv3Graph` -> `CustomerServiceGraph`
- `AnalyzerAgent` 输出分析 -> `SupervisorAgent` 汇总客服回复
- 工具上下文注入 -> 订单查询工具和风控检查工具

## 5. 用户点外卖的流程类比

可以把这个客服系统想成“用户点外卖的流程”：

- 用户问题 = 用户下单时写的需求
- `AgentState` = 一路流转的外卖订单
- `SupervisorAgent` = 门店店长，决定交给哪个岗位
- `IntentRouterAgent` = 前台接单员，判断是问菜单、催单，还是投诉
- `KnowledgeRagAgent` = 菜单和规则手册，回答退款、发票、账号安全等问题
- `TicketAgent` = 售后人员，查订单、建工单、继续跟进
- `ComplianceAgent` = 出餐前质检，确认回复不能泄露隐私或违规承诺
- `LocalMcpToolRegistry` = 后厨系统接口，比如查订单
- `ShortTermMemoryStore` = 当前排队小票，记住最近几轮对话
- `KnowledgeBase` / `TicketStore` = 长期保存的菜谱、规则、历史售后单

## 6. 这个 MVP 本质上在做什么

这个文件本质上是在用你已经学过的 `state + graph + tool + memory + router` 写法，实现一个可运行的智能客服 Supervisor 多 Agent 最小闭环。
