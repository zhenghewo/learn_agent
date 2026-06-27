# 08 examples 怎么读

示例目录：`learn_agent/refer/0607/agent-squad-main/examples`

## 示例的作用

`examples/` 不是框架核心，但它告诉你 SDK 在真实应用里怎么串起来。

读示例时不要先纠结 AWS 账号、环境变量、UI 框架。先看共同套路：

```text
创建 AgentSquad
-> 创建 classifier 或使用默认 classifier
-> 创建多个 agent
-> orchestrator.add_agent(...)
-> 调 route_request 或 agent_process_request
-> 根据 streaming 处理输出
```

## `examples/python-demo/main.py`

这是最适合作为入门的 CLI 示例。

主流程：

```text
创建 AgentSquad
-> 创建 Tech Agent
-> 创建 Weather Agent
-> Weather Agent 配 tool_config
-> weather_agent.set_system_prompt(...)
-> add_agent
-> while True 读取用户输入
-> asyncio.run(handle_request(...))
```

它展示了两件重要事情：

1. 普通 LLM agent 怎么注册。
2. 带工具的 weather agent 怎么注册。

Weather tool 有两种接法：

- 用 `AgentTools` 自动处理。
- 用自定义 `useToolHandler` 手动处理 Bedrock 或 Anthropic 的工具格式。

正常程序员会重点看：

```text
tool_config = {
  "tool": ...,
  "toolMaxRecursions": 5,
  "useToolHandler": ...
}
```

这说明工具调用不是魔法，而是 agent 配置的一部分。

## `examples/python-demo/tools/weather_tool.py`

这个文件展示了一个工具怎么被包装。

主流程：

```text
fetch_weather_data(latitude, longitude)
-> requests.get(open-meteo)
-> 返回 JSON 字符串

AgentTool(name="Weather_Tool", func=fetch_weather_data)
-> AgentTools([...])
```

Bedrock 自定义 handler 的流程：

```text
遍历 response.content
-> 找 toolUse
-> 取 latitude / longitude
-> 调 fetch_weather_data
-> 包成 toolResult
-> 返回 ConversationMessage(role="user", content=tool_results)
```

这个例子很适合对照 `utils/tool.py` 读。

## `examples/fast-api-streaming/main.py`

这个示例展示如何把 Agent Squad 接到 FastAPI。

主流程：

```text
app = FastAPI()
-> setup_orchestrator()
-> POST /stream_chat/
-> response_generator(...)
-> orchestrator.route_request(query, user_id, session_id, None, True)
-> async for chunk in response.output
-> yield chunk.text
```

关键点是 `route_request` 的最后一个参数：

```text
stream_response=True
```

这样 `AgentSquad` 会把流式输出交给 API 层，由 FastAPI 的 `StreamingResponse` 往外发。

## `examples/supervisor-mode/main.py`

这个示例展示 SupervisorAgent。

它创建了很多团队成员：

```text
TechAgent
SalesAgent
Claim Agent
WeatherAgent
HealthAgent
TravelAgent
AirlinesBot
```

然后创建：

```text
lead_agent
supervisor = SupervisorAgent(
  lead_agent=lead_agent,
  team=[...],
  storage=DynamoDbChatStorage(...),
  extra_tools=AgentTools([...])
)
```

最关键的是它没有让 classifier 自动选择 supervisor，而是手动构造：

```python
ClassifierResult(selected_agent=supervisor, confidence=1.0)
```

然后直接调用：

```python
orchestrator.agent_process_request(...)
```

这说明 `agent_process_request` 可以绕过分类器，直接把请求交给指定 agent。

## `examples/text-2-structured-output`

这个示例展示如何自定义一个 agent。

`ProductSearchAgent` 继承 `Agent`，自己实现：

```text
process_request
```

它不是直接返回普通自然语言，而是要求模型输出 JSON，再用：

```text
json.loads(llm_response)
```

解析结构化结果。

这个示例最适合学习“如何自己写一个 agent”：

```text
继承 Agent
-> 定义 Options
-> 初始化模型 client 和 prompt
-> 实现 process_request
-> 返回 ConversationMessage
```

## `examples/bedrock-prompt-routing/main.py`

这个示例把 `BedrockClassifier` 的 `model_id` 配成 Bedrock Prompt Router ARN。

它说明 classifier 不一定只能用普通模型 ID，也可以接路由能力。

阅读时重点看：

```text
classifier=BedrockClassifier(BedrockClassifierOptions(model_id=...))
```

## 用户点外卖的流程类比

examples 像外卖平台给商家的开店样板：

```text
python-demo = 一个命令行点单台
fast-api-streaming = 一个 Web 外卖窗口
supervisor-mode = 一家有店长和多个岗位的大店
text-2-structured-output = 专门把订单整理成结构化小票的店
weather_tool = 后厨查天气设备
```

你不需要一开始把每家店都跑起来。先看它们共同使用 `AgentSquad` 的方式，就能抓住框架用法。

## 运行提醒

这些示例大多依赖 AWS Bedrock、DynamoDB、Lex、环境变量或 OpenAI/Anthropic key。当前拆解只做静态阅读，没有实际调用云服务运行。

如果后面要本地最小化跑通，可以先写一个假的 `Classifier` 和假的 `Agent`，绕开云服务，把 `AgentSquad` 主流程跑起来。

## 一句话总结

`examples/` 本质上是在展示 Agent Squad 的几种接法：CLI、FastAPI 流式接口、Supervisor 团队协调、自定义结构化输出 agent。
