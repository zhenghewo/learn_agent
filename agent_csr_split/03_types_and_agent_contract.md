# 03 `types.py` 和 `agents/agent.py` 拆解

源文件：

```text
python/src/agent_squad/types/types.py
python/src/agent_squad/agents/agent.py
```

## 这两个文件的作用

这两个文件是项目的“通用语言”。

`types.py` 定义消息、角色、配置、模型常量。

`agents/agent.py` 定义所有 agent 必须遵守的接口，也定义统一响应结构。

正常程序员读多 agent 框架时，会优先看这里，因为它回答一个问题：不同 agent 之间到底靠什么格式沟通？

## `types.py` 里最重要的数据结构

### `ParticipantRole`

```text
USER      "user"
ASSISTANT "assistant"
```

它规定一条消息是谁说的。

### `ConversationMessage`

它是一条对话消息：

```text
role    user 或 assistant
content list[Any]
```

常见形状：

```python
ConversationMessage(
    role="user",
    content=[{"text": "What is AWS Lambda?"}]
)
```

注意：`content` 是 list，不是单纯字符串。因为 Bedrock、tool call、reasoning content 都可能塞进不同块。

### `TimestampedMessage`

它继承 `ConversationMessage`，多了：

```text
timestamp 毫秒时间戳
```

存储层内部需要排序，所以会用带时间戳的消息；对外返回时常常再去掉 timestamp。

### `AgentSquadConfig`

这是 `AgentSquad` 的全局配置：

```text
LOG_AGENT_CHAT
LOG_CLASSIFIER_CHAT
LOG_CLASSIFIER_OUTPUT
LOG_EXECUTION_TIMES
MAX_RETRIES
USE_DEFAULT_AGENT_IF_NONE_IDENTIFIED
NO_SELECTED_AGENT_MESSAGE
MAX_MESSAGE_PAIRS_PER_AGENT
```

其中最容易影响控制流的是：

- `USE_DEFAULT_AGENT_IF_NONE_IDENTIFIED`
- `NO_SELECTED_AGENT_MESSAGE`
- `MAX_MESSAGE_PAIRS_PER_AGENT`

## `agent.py` 里的核心结构

### `AgentOptions`

每个 agent 初始化时的基础配置：

```text
name
description
save_chat
callbacks
LOG_AGENT_DEBUG_TRACE
```

`name` 和 `description` 不只是展示文本，它们会影响分类器选 agent。description 写得太模糊，分类就容易错。

### `Agent`

所有 agent 的抽象父类。

`__init__` 做了几件事：

```text
self.name = options.name
self.id = generate_key_from_name(options.name)
self.description = options.description
self.save_chat = options.save_chat
self.callbacks = options.callbacks 或默认 AgentCallbacks
self.log_debug_trace = options.LOG_AGENT_DEBUG_TRACE
```

`self.id` 是从名字生成的，比如：

```text
"Tech Agent" -> "tech-agent"
```

这个 id 后面会用在：

- `self.agents` 字典 key
- storage 的 key
- classifier 选择 agent

### `process_request`

这是所有具体 agent 必须实现的方法：

```python
async def process_request(
    self,
    input_text,
    user_id,
    session_id,
    chat_history,
    additional_params=None,
)
```

输入：

- `input_text`：这次用户说的话。
- `user_id`：用户标识。
- `session_id`：会话标识。
- `chat_history`：这个 agent 过去的聊天历史。
- `additional_params`：外部传进来的附加参数。

输出：

- 非流式：`ConversationMessage`
- 流式：`AsyncIterable[AgentStreamResponse]`

### `AgentResponse`

`AgentSquad.route_request` 最终返回的统一包装：

```text
metadata  AgentProcessingResult
output    真正回答，可能是 ConversationMessage，也可能是流
streaming bool
```

### `AgentStreamResponse`

流式响应里的每个 chunk：

```text
text           当前 token 文本
thinking       当前 thinking 文本
final_message  完整消息，通常在最后一个 chunk 出现
final_thinking 完整 thinking
```

对存储来说，最关键的是 `final_message`。没有它，流式回答可能无法被完整保存。

## 长期状态和临时数据

长期状态：

```text
Agent.name
Agent.id
Agent.description
Agent.save_chat
Agent.callbacks
```

每次请求临时创建：

```text
input_text
chat_history
ConversationMessage(user input)
AgentStreamResponse chunk
AgentResponse
```

这和你之前学的“对象长期状态 vs 函数临时变量”是一类问题：`self.xxx` 往往跟对象生命周期绑定，方法里的普通变量通常只活在本次调用里。

## 用户点外卖的流程类比

`ConversationMessage` 像订单沟通记录：

```text
role = 谁说的
content = 说了什么，或附带了什么工具结果
```

`AgentOptions` 像商家入驻资料：

```text
name = 店名
description = 店铺经营范围
save_chat = 是否保存订单聊天记录
callbacks = 每个节点触发的通知
```

`process_request` 像所有商家都必须提供的接单接口。奶茶店、药店、快餐店内部做法不同，但平台只要求它们都能“接单并返回结果”。

## 出 bug 先查哪里

- agent 选不到：看 `Agent.id` 是否和 classifier 返回一致。
- agent description 不生效：看 `add_agent` 后是否调用了 `classifier.set_agents`。
- streaming 无法保存：看最后有没有 `AgentStreamResponse(final_message=...)`。
- 回答格式怪：看具体 agent 返回的是不是 `ConversationMessage`。

## 一句话总结

`types.py` 和 `agent.py` 本质上是在定义整个多 agent 系统的共同数据格式和统一接单合同。
