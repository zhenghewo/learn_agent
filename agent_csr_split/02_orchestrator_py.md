# 02 `orchestrator.py` 拆解

源文件：`learn_agent/refer/0607/agent-squad-main/python/src/agent_squad/orchestrator.py`

## 这个文件的作用

`orchestrator.py` 定义了 `AgentSquad`，它是 Python SDK 的高层入口。外部代码通常这样用它：

```python
orchestrator = AgentSquad(...)
orchestrator.add_agent(tech_agent)
response = await orchestrator.route_request(user_input, user_id, session_id)
```

它负责的不是“亲自回答问题”，而是：

- 管理 agent 列表。
- 调用 classifier 判断选哪个 agent。
- 把请求派发给被选中的 agent。
- 保存用户消息和 assistant 消息。
- 组装统一的 `AgentResponse`。

## `__init__` 初始化了什么

`AgentSquad.__init__` 里的长期状态很重要：

```text
self.config          全局配置，比如是否打印日志、历史长度上限
self.storage         聊天历史存储，默认 InMemoryChatStorage
self.logger          日志工具
self.agents          已注册 agent 字典，key 是 agent.id
self.classifier      分类器，默认尝试用 BedrockClassifier
self.execution_times 记录分类、处理等耗时
self.default_agent   分类失败时可使用的默认 agent
```

这些都是对象级长期状态。也就是说，只要这个 `AgentSquad` 对象还活着，它们就还在。

如果用默认 `InMemoryChatStorage`，聊天历史也是“对象生命周期内有效”。程序重启后就没了。要跨进程、跨重启保存，需要用 DynamoDB 或 SQL 这类 storage。

## 输入和输出

最重要的方法是：

```python
await orchestrator.route_request(
    user_input,
    user_id,
    session_id,
    additional_params=None,
    stream_response=False,
)
```

输入：

- `user_input`：用户这次说的话。
- `user_id`：哪个用户。
- `session_id`：哪个会话。
- `additional_params`：额外参数，会传给 agent。
- `stream_response`：是否把流式 agent 的输出作为 async generator 返回。

输出：

```text
AgentResponse(
  metadata=AgentProcessingResult(...),
  output=ConversationMessage 或 async generator,
  streaming=True/False
)
```

## 主流程按程序员阅读顺序拆

### 1. `add_agent`

```text
add_agent(agent)
-> 检查 agent.id 是否重复
-> 放进 self.agents
-> classifier.set_agents(self.agents)
```

这里有一个关键点：注册 agent 不只是放进字典，还要同步给分类器。分类器需要知道“有哪些店可以接单”。

### 2. `route_request`

这是最外层入口：

```text
清空 execution_times
-> classify_request(...)
-> 如果没选中 agent，返回无法处理的消息
-> agent_process_request(...)
-> finally 打印耗时
```

它像外卖平台收到订单后的总入口。

### 3. `classify_request`

```text
storage.fetch_all_chats(user_id, session_id)
-> classifier.classify(user_input, chat_history)
-> 如果没选中，且配置允许默认 agent，就 get_fallback_result
-> 返回 ClassifierResult
```

这里取的是“所有 agent 的历史”，因为分类器要判断这句话是不是之前某个 agent 对话的 follow-up。

### 4. `agent_process_request`

这是派单后处理的核心：

```text
如果 classifier_result.selected_agent 存在
-> dispatch_to_agent(...)
-> create_metadata(...)
-> save_message(用户消息)
-> 如果 agent 支持 streaming：
     stream_response=True  时，把流式 chunk 交给调用者，并在 final_message 出现后保存
     stream_response=False 时，内部消费完整流，拿到 final_message 后保存
-> 如果 agent 非 streaming：
     直接保存 ConversationMessage
-> 返回 AgentResponse
```

注意这里会先保存用户消息，再保存 assistant 消息。这样存储层能形成一对一对的聊天记录。

### 5. `dispatch_to_agent`

```text
selected_agent = classifier_result.selected_agent
agent_chat_history = storage.fetch_chat(user_id, session_id, selected_agent.id)
response = selected_agent.process_request(
    user_input,
    user_id,
    session_id,
    agent_chat_history,
    additional_params,
)
```

这里取的是“被选中 agent 自己的历史”，因为真正回答时不一定需要看到所有 agent 的历史。

## 数据怎么变化

这里没有一个叫 `GraphState` 的总状态，但有三类状态：

```text
AgentSquad 对象状态：
  self.agents / self.classifier / self.storage / self.config

一次请求的临时状态：
  user_input / classifier_result / agent_response / metadata / final_response

存储里的长期聊天状态：
  user_id + session_id + agent_id -> messages
```

一次请求大概这样变化：

```text
user_input = "What is AWS Lambda?"
classifier_result.selected_agent = Tech Agent
agent_chat_history = Tech Agent 之前的对话
agent_response = Tech Agent 生成的回答
metadata.agent_name = "Tech Agent"
storage 保存 user message
storage 保存 assistant message
return AgentResponse
```

## `invoke / run / execute / generate / analyze` 层级对应

这个项目里核心方法名是：

```text
route_request        最高层，对外入口
classify_request     中间层，负责选 agent
agent_process_request 中间层，负责派发和保存
dispatch_to_agent    更低层，只管调用 selected_agent
process_request      agent 统一接口，具体 agent 真正干活
```

多个类都有 `process_request`，原因是它是“统一合同”。`AgentSquad` 不需要知道 Bedrock、OpenAI、Lambda 的内部差异，只要它们都实现：

```python
async def process_request(...)
```

就能被统一调度。

## 用户点外卖的流程类比

```text
用户下单
-> 平台总调度 AgentSquad 收到订单
-> 分单员 Classifier 判断该给哪家店
-> 平台取出这家店和用户之前的聊天记录
-> 商家 Agent 开始做餐
-> 平台保存“用户下单内容”
-> 平台保存“商家出餐结果”
-> 用户收到餐和订单信息
```

`stream_response=True` 就像后厨边做边把进度递出来；但平台要等最后的完整餐品 `final_message` 出来后，才能把完整结果记入订单历史。

## 出 bug 先查哪里

- 分类错 agent：先查 `classify_request`、classifier prompt、agent description。
- 没有选中 agent：查 `NO_SELECTED_AGENT_MESSAGE`、`USE_DEFAULT_AGENT_IF_NONE_IDENTIFIED`、`default_agent`。
- 历史没保存：查 `agent.save_chat`、`save_message`、storage 实现。
- 流式响应没进入历史：查 `AgentStreamResponse.final_message` 是否最终出现。
- metadata 不对：查 `create_metadata`。

## 一句话总结

`orchestrator.py` 本质上是在做多 agent 系统的总调度：分类、派发、保存历史、统一返回结果。
