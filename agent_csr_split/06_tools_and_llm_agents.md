# 06 LLM Agent 和 Tool Calling 拆解

源文件：

```text
python/src/agent_squad/agents/bedrock_llm_agent.py
python/src/agent_squad/agents/openai_agent.py
python/src/agent_squad/agents/anthropic_agent.py
python/src/agent_squad/utils/tool.py
python/src/agent_squad/agents/chain_agent.py
python/src/agent_squad/agents/lambda_agent.py
python/src/agent_squad/agents/comprehend_filter_agent.py
```

## 这个模块群的作用

`Agent` 是统一接口，具体 agent 才是真正做事的地方。

最典型的是 `BedrockLLMAgent`：

```text
接收用户输入
-> 拼 system prompt
-> 拼历史消息
-> 调 Bedrock Converse API
-> 如果模型要求调用工具，就执行工具
-> 把工具结果塞回对话
-> 再问模型
-> 返回最终 ConversationMessage 或流式 chunk
```

## `BedrockLLMAgentOptions` 里有什么

常见配置：

```text
model_id
region
streaming
inference_config
guardrail_config
retriever
tool_config
custom_system_prompt
client
additional_model_request_fields
```

这些多数会进入 `self.xxx`，成为 agent 的长期配置。

特别重要的几个：

- `streaming`：控制是否流式输出。
- `retriever`：如果有，会先检索上下文，再追加到 system prompt。
- `tool_config`：如果有，模型可以使用工具。
- `custom_system_prompt`：覆盖默认角色说明。

## `BedrockLLMAgent.process_request` 主流程

```text
callbacks.on_agent_start
-> _prepare_conversation(input_text, chat_history)
-> _prepare_system_prompt(input_text)
-> _build_conversation_command(conversation, system_prompt)
-> _process_with_strategy(streaming, command, conversation, tracking_info)
```

这里的 `conversation` 是本次临时构造的消息列表：

```text
历史消息
-> 追加当前 user message
```

它不是长期状态，长期历史仍然由 storage 保存。

## 非流式回答流程

```text
_handle_single_response_loop
-> handle_single_response
-> client.converse(...)
-> 得到 llm_response
-> 如果 llm_response 里有 toolUse：
     _process_tool_block
     conversation.append(tool_response)
     command["messages"] = conversation_to_dict(conversation)
     继续循环
-> 没有 toolUse：
     返回最终 ConversationMessage
```

`max_recursions` 是为了防止模型无限要求调用工具。

## 流式回答流程

```text
_handle_streaming
-> handle_streaming_response
-> client.converse_stream(...)
-> 每个 text delta yield AgentStreamResponse(text=...)
-> 最后 yield AgentStreamResponse(final_message=...)
-> 如果 final_message 里有 toolUse，继续工具循环
```

对外部调用者来说，流式返回是一个 async generator。

对 `AgentSquad` 来说，最重要的是最后能不能拿到 `final_message`，因为保存历史要靠完整消息。

## `AgentTool` 是什么

`utils/tool.py` 里的 `AgentTool` 把一个 Python 函数包装成模型可调用的工具。

初始化时它会保存：

```text
name
description 或 func docstring
properties 参数 schema
required 必填参数
func 被包装后的函数
```

如果没手动传 `properties`，它会尝试从函数签名和 type hints 提取参数。

例如一个天气函数：

```python
async def fetch_weather_data(latitude: str, longitude: str):
    ...
```

会被包装成一个工具，让模型知道它需要 `latitude` 和 `longitude`。

## `AgentTools.tool_handler` 做什么

它负责执行模型请求的工具：

```text
遍历 response.content
-> 找 toolUse block
-> 取 tool name / tool id / input
-> callbacks.on_tool_start
-> _process_tool(tool_name, input_data)
-> callbacks.on_tool_end
-> 包装成 toolResult
-> 返回一条 user role 的工具结果消息
```

为什么工具结果要变成 `user` 消息？

因为从模型对话格式看，模型说“我要调用工具”，外部系统执行后，要把“工具执行结果”作为下一条消息喂回模型。

## `OpenAIAgent` 和 `AnthropicAgent`

它们和 `BedrockLLMAgent` 的主思想一致：

```text
准备 system prompt
-> 组合历史消息和用户输入
-> 调对应模型 API
-> 返回 ConversationMessage 或 AgentStreamResponse
```

差异主要是：

- API 请求格式不同。
- tool schema 格式不同。
- streaming chunk 格式不同。

所以项目把共同接口放在 `Agent`，把平台差异留在具体 agent 类里。

## 其他 agent 先知道什么

### `ChainAgent`

它把多个 agent 串成流水线：

```text
agent1 输出
-> 作为 agent2 输入
-> 作为 agent3 输入
```

中间 agent 不能返回 streaming，因为下一步需要完整文本。

### `LambdaAgent`

它把请求转成 JSON payload，调用 AWS Lambda，再把 Lambda 响应解码成 `ConversationMessage`。

### `ComprehendFilterAgent`

它更像内容过滤器：

```text
检测情绪 / PII / 毒性内容
-> 有问题返回 None
-> 没问题把原输入包装成 ConversationMessage
```

## 用户点外卖的流程类比

`BedrockLLMAgent` 像一家能接复杂订单的商家：

```text
收到订单
-> 看用户历史口味
-> 看店铺工作守则 system prompt
-> 如果需要查库存或开设备，就调用 Tool
-> 把工具结果拿回来继续处理
-> 最后出餐
```

Tool 像后厨设备或外部系统：

```text
Weather_Tool = 查天气设备
Product search = 查商品库存系统
Lambda = 外包给另一个厨房窗口
```

## 出 bug 先查哪里

- 模型不调用工具：查 `tool_config` 格式、tool description、system prompt。
- 工具参数为空：查 `AgentTool` 的 `properties` 和函数 type hints。
- 工具循环停不下来：查 `toolMaxRecursions`。
- streaming 有输出但历史没保存：查最后是否 yield `final_message`。
- Bedrock 请求报格式错：查 `conversation_to_dict` 和 `content` 结构。
- OpenAI agent 初始化失败：查是否传了 `api_key`。

## 一句话总结

LLM Agent 和 Tool 模块本质上是在把“统一的 agent 接单接口”连接到具体模型 API、工具调用和流式输出机制上。
