# 04 `classifier.py` 和 `bedrock_classifier.py` 拆解

源文件：

```text
python/src/agent_squad/classifiers/classifier.py
python/src/agent_squad/classifiers/bedrock_classifier.py
```

## 这个模块的作用

Classifier 的任务是：根据用户输入和历史对话，选出最适合处理这次请求的 agent。

它输出：

```text
ClassifierResult(
  selected_agent=某个 Agent 或 None,
  confidence=0 到 1 的置信度
)
```

在整个项目链路里，它处在：

```text
用户输入
-> AgentSquad.route_request
-> Classifier.classify
-> selected_agent
-> Agent.process_request
```

## `Classifier` 保存了哪些长期状态

`Classifier.__init__` 里有这些状态：

```text
self.agent_descriptions  所有 agent 的 id 和 description 拼出来的文本
self.history             历史对话文本
self.custom_variables    自定义 prompt 变量
self.prompt_template     分类 prompt 模板
self.system_prompt       替换变量后的最终 prompt
self.agents              agent_id -> Agent 的字典
```

其中最关键的是：

- `self.agents`：最后要靠它把字符串 id 找回真正的 Agent 对象。
- `self.agent_descriptions`：分类模型读它来知道有哪些候选 agent。
- `self.history`：处理 follow-up 时靠它判断是否延续上一个 agent。

## 主流程

```text
AgentSquad.add_agent(...)
-> classifier.set_agents(self.agents)
-> 用户请求进来
-> classifier.classify(input_text, chat_history)
-> set_history(chat_history)
-> update_system_prompt()
-> process_request(input_text, chat_history)
-> 返回 ClassifierResult
```

`Classifier` 本身是抽象类，真正调用模型的是子类，比如 `BedrockClassifier`。

## `set_agents` 做了什么

它把所有 agent 拼成一段描述：

```text
agent-id-1:agent description

agent-id-2:agent description
```

这段内容会进入 prompt 里的：

```text
<agents>
{{AGENT_DESCRIPTIONS}}
</agents>
```

所以 agent 的 `description` 会直接影响分类准确性。

## `set_history` 和 follow-up

`format_messages` 会把历史消息转成文本：

```text
user: ...
assistant: ...
```

分类 prompt 明确要求：如果用户输入像 “yes”、“ok”、“1”、“I want to know more” 这种 follow-up，就尽量选择上一个 agent。

这就是为什么 `AgentSquad.classify_request` 取的是：

```text
storage.fetch_all_chats(user_id, session_id)
```

而不是只取某一个 agent 的历史。分类器需要看全局上下文。

## `BedrockClassifier` 怎么拿到结构化结果

`BedrockClassifier` 用 Bedrock Converse API，并给模型配置了一个 tool：

```text
analyzePrompt
```

这个 tool 的输入 schema 要求模型返回：

```text
userinput
selected_agent
confidence
```

处理步骤：

```text
构造 user_message
-> 构造 converse_cmd，包含 system prompt 和 toolConfig
-> client.converse(...)
-> 从 response output 里找 toolUse
-> 校验 toolUse.input 是否像 ToolInput
-> get_agent_by_id(selected_agent)
-> 返回 ClassifierResult(selected_agent, confidence)
```

这里的关键不是让模型自由写一段文本，而是尽量让模型通过 toolUse 给出结构化选择。

## 数据结构怎么变化

一次分类大概是：

```text
输入：
  input_text = "Can you check the weather in Paris?"
  agents = {
    "tech-agent": Tech Agent,
    "weather-agent": Weather Agent
  }
  history = [...]

prompt 中可见：
  tech-agent: specializes in technology...
  weather-agent: specialized agent for weather...

模型 toolUse 返回：
  selected_agent = "weather-agent"
  confidence = 0.93

代码转换：
  self.agents["weather-agent"] -> Weather Agent 对象

输出：
  ClassifierResult(selected_agent=Weather Agent, confidence=0.93)
```

## 用户点外卖的流程类比

Classifier 像外卖平台的分单员：

```text
用户写：我想查巴黎天气
-> 分单员查看所有商家的经营范围
-> 分单员查看用户刚才是不是在跟某家店继续聊
-> 决定派给 Weather Agent
```

如果用户只说 “yes”，分单员不会只看这个词，而是会翻订单历史：刚才是哪家店问了一个确认问题，就继续派给那家店。

## 出 bug 先查哪里

- 总是选错 agent：先改 agent description，让边界更清楚。
- follow-up 断掉：查 `fetch_all_chats` 是否返回了历史。
- 返回了字符串但找不到 agent：查 `get_agent_by_id`，尤其是 id 是否有空格、大小写、连字符差异。
- Bedrock 返回不符合 schema：查 `is_tool_input` 和 `toolConfig`。
- 不想用 Bedrock：需要显式传入其他 classifier，否则默认 Bedrock 不可用时会报错。

## 一句话总结

Classifier 模块本质上是在把“用户这句话该谁处理”变成一个结构化的 `selected_agent` 决策。
