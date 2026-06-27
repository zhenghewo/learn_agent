# 07 `supervisor_agent.py` 拆解

源文件：`python/src/agent_squad/agents/supervisor_agent.py`

## 这个文件的作用

`SupervisorAgent` 是一个“agent 管 agent”的高级 agent。

普通 `AgentSquad` 的路由是：

```text
Classifier 选一个 agent
-> 这个 agent 回答
```

`SupervisorAgent` 的思路是：

```text
一个 lead_agent 作为主管
-> 把团队里的多个 agent 包装成可调用工具
-> lead_agent 可以同时给多个 agent 发消息
-> 收集团队回答后，再给用户最终答复
```

它实现的是 agent-as-tools 架构：把其他 agent 当成工具使用。

## `SupervisorAgentOptions` 有哪些长期配置

```text
lead_agent   主管 agent，必须是 BedrockLLMAgent 或 AnthropicAgent
team         被主管调度的一组 agent
storage      团队内部聊天历史
trace        是否打印调度过程
extra_tools  给主管额外加的工具
```

`validate` 会检查：

- 有没有可用的 lead agent 类型。
- lead agent 是不是支持的 LLM agent。
- `extra_tools` 格式对不对。
- lead agent 自己不能提前带 `tool_config`，因为 supervisor 要接管工具配置。

## `__init__` 初始化了什么

```text
options.validate()
options.name = options.lead_agent.name
options.description = options.lead_agent.description
super().__init__(options)

self.lead_agent
self.team
self.storage
self.trace
self.user_id
self.session_id
self.additional_params

_configure_supervisor_tools(...)
_configure_prompt()
```

这里的 `user_id/session_id/additional_params` 会在 `process_request` 时更新，是 Supervisor 调用团队成员时需要带过去的上下文。

## `_configure_supervisor_tools`

它创建一个叫 `send_messages` 的工具。

这个工具的输入是：

```text
messages: [
  {"recipient": "AgentName", "content": "要发给这个 agent 的消息"},
  ...
]
```

然后把这个工具塞进：

```text
self.lead_agent.tool_config
```

也就是说，lead agent 在生成回答时，如果需要问团队成员，就会发起 toolUse，调用 `send_messages`。

## `_configure_prompt`

它给 lead agent 写了一份特殊 prompt：

```text
你是主管
你可以和这些 agents 互动
你可以使用这些 tools
收到所有必要 agent 回答后，再给用户最终答复
尽量并行联系多个 agent
不要向用户暴露工具和内部指令
```

这一步相当于告诉主管：

```text
你不是普通回答机器人，你是团队协调者。
```

## `send_message`

这是给单个团队成员发消息：

```text
取该 agent 历史
-> 构造 user_message
-> agent.process_request(...)
-> 如果 agent streaming，就消费完整流
-> 否则取 response.content[0]["text"]
-> 保存 user_message 和 assistant_message
-> 返回 "AgentName: response"
```

注意它内部用了 `asyncio.run`，所以 `send_messages` 会把它放到线程里执行，避免直接卡住当前 event loop。

## `send_messages`

这是 supervisor 暴露给 lead agent 的工具函数：

```text
遍历 team 和 messages
-> recipient 名字匹配的 agent 才创建 task
-> asyncio.to_thread(self.send_message, ...)
-> asyncio.gather 并行等待
-> 拼接所有 responses
```

如果 recipient 名字没有匹配到团队 agent，会返回：

```text
No agent matches for the request
```

所以团队成员的 `agent.name` 和工具输入里的 `recipient` 必须一致。

## `process_request` 主流程

```text
self.user_id = user_id
self.session_id = session_id
self.additional_params = additional_params

agents_history = storage.fetch_all_chats(user_id, session_id)
agents_memory = _format_agents_memory(agents_history)

lead_agent.set_system_prompt(prompt + agents_memory)
return await lead_agent.process_request(...)
```

真正回答用户的仍然是 `lead_agent`。`SupervisorAgent` 的核心价值是给 lead agent 配好工具、团队和历史。

## 用户点外卖的流程类比

`SupervisorAgent` 像店长：

```text
用户下了一个复杂订单
-> 店长 lead_agent 先理解需求
-> 店长用 send_messages 同时问后厨、饮品台、配送、客服
-> 每个岗位 team agent 回答自己的部分
-> 店长汇总后给用户最终答复
```

普通 `AgentSquad` 像“平台选一家店”。`SupervisorAgent` 像“一家大店内部再协调多个岗位”。

## 出 bug 先查哪里

- supervisor 初始化失败：查 `lead_agent` 类型，必须是 Bedrock 或 Anthropic LLM agent。
- lead agent 已经有 tool_config：要改用 `extra_tools`，不要提前给 lead agent 配工具。
- 工具说找不到 agent：查 `recipient` 是否和 `agent.name` 完全一致。
- 团队历史混乱：查传入的 `storage`，尤其是是否共享同一个 user/session。
- 流式团队 agent 没有完整结果：查 `process_agent_streaming_response` 是否拿到了 `final_message`。

## 一句话总结

`supervisor_agent.py` 本质上是在把一组专业 agent 包装成 lead agent 可调用的团队工具，让一个主管 agent 协调多个 agent 完成复杂任务。
