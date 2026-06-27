# Agent Squad 拆解入口

来源项目：`learn_agent/refer/0607/agent-squad-main`

解释模板：`learn_agent/PYTHON_FILE_EXPLAIN_PROMPT.md`

这组文件按“初学者但想培养程序员阅读习惯”的顺序拆解 Agent Squad。重点放在 Python SDK 主线，因为这个项目虽然同时有 TypeScript、docs、examples、CI，但最适合你当前学习路线的是：

```text
用户输入
-> AgentSquad.route_request
-> Classifier 判断该交给哪个 Agent
-> 被选中的 Agent.process_request
-> ChatStorage 保存用户消息和助手消息
-> AgentResponse 返回给外部调用者
```

## 建议阅读顺序

1. `01_project_map.md`：先看项目地图，知道哪些目录重要。
2. `02_orchestrator_py.md`：看主流程入口 `AgentSquad`。
3. `03_types_and_agent_contract.md`：看消息、配置、Agent 抽象接口。
4. `04_classifier_flow.md`：看分类器如何选 agent。
5. `05_storage_memory.md`：看聊天历史怎么存、怎么取。
6. `06_tools_and_llm_agents.md`：看 LLM agent 和 tool-calling 循环。
7. `07_supervisor_agent.md`：看 SupervisorAgent 如何把多个 agent 当工具协调。
8. `08_examples_reading.md`：看示例项目怎么把 SDK 串起来。
9. `09_debug_map.md`：最后用它当排错地图。

## 一个总类比：用户点外卖的流程

- 用户输入 = 用户下单时写的需求
- `AgentSquad` = 外卖平台的总调度系统
- `Classifier` = 分单员，判断这个订单该给哪家店/哪个专员
- `Agent` = 真正处理订单的商家、客服、骑手或专业窗口
- `ConversationMessage` = 一条聊天记录或订单备注
- `ChatStorage` = 订单历史系统
- `AgentResponse` = 最终出餐结果加上订单元信息
- `streaming` = 后厨边做边从窗口递出进度
- `Tool` = 商家调用的后厨设备或外部系统，比如查天气、查商品
- `SupervisorAgent` = 店长，自己不一定做每个细活，但会同时派给多个岗位

## 这个项目本质上在做什么？

Agent Squad 本质上是在做一个“多 agent 路由器”：它先判断用户请求应该交给哪个专长 agent，再把上下文和用户输入交给该 agent 处理，并把对话历史保存起来，方便后续多轮对话继续衔接。
