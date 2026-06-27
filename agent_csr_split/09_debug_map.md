# 09 排错地图和复习清单

## 一句话总图

```text
AgentSquad 负责调度
Classifier 负责选人
Agent 负责干活
Storage 负责记忆
Tool 负责外部能力
SupervisorAgent 负责团队协作
```

## 常见问题先查哪里

### 1. 用户问题路由错了

优先查：

```text
agent.description
Classifier.set_agents
Classifier.prompt_template
BedrockClassifier.process_request
```

思路：

```text
分类器只知道你告诉它的 agent 描述。
如果两个 agent 描述边界模糊，它就容易分错。
```

### 2. 分类器返回了 no agent

优先查：

```text
AgentSquadConfig.USE_DEFAULT_AGENT_IF_NONE_IDENTIFIED
AgentSquad.default_agent
AgentSquadConfig.NO_SELECTED_AGENT_MESSAGE
Classifier.get_agent_by_id
```

尤其注意 agent id：

```text
"Tech Agent" -> "tech-agent"
```

模型如果返回 `"Tech Agent"` 而不是 `"tech-agent"`，可能找不到对象。

### 3. 多轮对话衔接不上

优先查：

```text
storage.save_chat_message
storage.fetch_all_chats
storage.fetch_chat
agent.save_chat
MAX_MESSAGE_PAIRS_PER_AGENT
```

判断关键：

```text
分类器需要 fetch_all_chats
具体 agent 需要 fetch_chat
```

一个负责路由上下文，一个负责回答上下文。

### 4. 程序重启后历史消失

优先查：

```text
是否使用 InMemoryChatStorage
```

`InMemoryChatStorage` 只保存在 Python 对象内。要跨重启保存，需要 DynamoDB 或 SQL storage。

### 5. 流式输出能显示，但没有进历史

优先查：

```text
AgentStreamResponse.final_message
AgentSquad.agent_process_request
BedrockLLMAgent.handle_streaming_response
OpenAIAgent.handle_streaming_response
```

流式 token 只是过程，保存历史要靠最后的完整 `final_message`。

### 6. 工具没有被调用

优先查：

```text
agent.tool_config
AgentTool.description
AgentTool.properties
system_prompt
toolMaxRecursions
```

模型要知道：

- 有哪些工具。
- 工具能做什么。
- 参数怎么填。
- 什么时候必须用工具。

### 7. 工具调用了但结果格式报错

优先查：

```text
utils/tool.py AgentToolResult
to_bedrock_format
to_anthropic_format
自定义 useToolHandler
ConversationMessage.content
```

不同平台工具结果格式不同。Bedrock 通常是 `toolResult`，Anthropic 通常是 `tool_result`。

### 8. Supervisor 找不到团队成员

优先查：

```text
SupervisorAgent.send_messages
message["recipient"]
agent.name
```

`recipient` 要和 `agent.name` 匹配，不是和 `agent.id` 匹配。

### 9. 自定义 agent 接不进框架

优先查：

```text
是否继承 Agent
是否实现 async process_request
返回值是否是 ConversationMessage 或 AsyncIterable
options.name / options.description 是否正确
```

最小合同是：

```python
async def process_request(
    self,
    input_text,
    user_id,
    session_id,
    chat_history,
    additional_params=None,
):
    ...
```

## 文件一句话复习

```text
orchestrator.py
  多 agent 总调度入口。

types/types.py
  定义消息、角色、配置、模型常量。

agents/agent.py
  定义所有 agent 必须遵守的统一接口。

classifiers/classifier.py
  把 agent 描述和历史拼进 prompt，抽象出分类流程。

classifiers/bedrock_classifier.py
  用 Bedrock toolUse 得到 selected_agent 和 confidence。

storage/chat_storage.py
  定义聊天历史存取接口。

storage/in_memory_chat_storage.py
  用字典按 user/session/agent 保存临时历史。

agents/bedrock_llm_agent.py
  调 Bedrock Converse API，支持 streaming、retriever、tool calling。

utils/tool.py
  把 Python 函数包装成不同模型平台可调用的 tool。

agents/supervisor_agent.py
  让 lead agent 把团队 agent 当工具并行调度。
```

## 复习问题

1. `AgentSquad.route_request` 和 `Agent.process_request` 哪个层级更高？
2. 为什么 classifier 要读 `fetch_all_chats`，但 selected agent 只读 `fetch_chat`？
3. `ConversationMessage.content` 为什么设计成 list，而不是字符串？
4. `InMemoryChatStorage` 为什么不是跨会话持久化记忆？
5. streaming 响应为什么需要 `final_message`？
6. `AgentTool` 如何从函数签名推断参数 schema？
7. `SupervisorAgent` 的 `send_messages` 为什么要匹配 `agent.name`？
8. 如果自定义 agent 返回普通 dict，会在哪里出问题？

## 用户点外卖的流程总复盘

```text
用户下单
-> AgentSquad 平台接单
-> Classifier 分单员判断该给哪家店
-> Storage 翻订单历史
-> Agent 商家处理订单
-> Tool 后厨设备提供外部能力
-> Storage 保存订单沟通记录
-> AgentResponse 把餐品和小票交给用户
```

如果订单复杂：

```text
SupervisorAgent 店长
-> 同时问多个岗位
-> 收齐结果
-> 给用户一个完整答复
```

## 一句话总结

这份排错地图本质上是在帮你把 Agent Squad 的“路由、执行、记忆、工具、团队协作”五个关键边界记牢。
