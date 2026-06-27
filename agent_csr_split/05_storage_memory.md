# 05 `storage` 聊天历史拆解

源文件：

```text
python/src/agent_squad/storage/chat_storage.py
python/src/agent_squad/storage/in_memory_chat_storage.py
python/src/agent_squad/storage/dynamodb_chat_storage.py
python/src/agent_squad/storage/sql_chat_storage.py
```

## 这个模块的作用

Storage 负责保存和读取聊天历史。它让系统支持多轮对话。

在主流程里，它被用在两个地方：

```text
分类前：
  fetch_all_chats(user_id, session_id)
  让 classifier 看所有 agent 历史

派发前：
  fetch_chat(user_id, session_id, selected_agent.id)
  让被选中的 agent 看自己的历史

回答后：
  save_chat_message(...) 保存 user 和 assistant 消息
```

## `ChatStorage` 是抽象接口

它规定所有存储实现都要提供：

```text
save_chat_message
save_chat_messages
fetch_chat
fetch_all_chats
```

还提供两个通用辅助方法：

```text
is_same_role_as_last_message
trim_conversation
```

### `trim_conversation`

它会限制历史长度，而且会尽量保留成对消息：

```text
user -> assistant
user -> assistant
```

如果最大条数是奇数，会减成偶数，避免只留下半轮对话。

## `InMemoryChatStorage` 保存了什么长期状态

`__init__` 里最重要的是：

```text
self.conversations = defaultdict(list)
```

key 的生成规则是：

```text
user_id#session_id#agent_id
```

所以同一个用户、同一个会话，和不同 agent 的聊天历史是分开的。

例如：

```text
user123#session456#tech-agent
user123#session456#weather-agent
```

这点很重要：Weather Agent 不会默认拿到 Tech Agent 的内部历史。只有 classifier 的 `fetch_all_chats` 会把所有 agent 历史拿出来用于判断路由。

## `save_chat_message` 流程

```text
生成 key
-> 找到 conversation list
-> 如果新消息 role 和最后一条一样，就不保存
-> ConversationMessage 转成 TimestampedMessage
-> append
-> trim_conversation
-> 存回 self.conversations
-> 去掉 timestamp 后返回
```

为什么要避免连续同 role？

因为正常对话应该是：

```text
user
assistant
user
assistant
```

如果连续两个 user 或连续两个 assistant，很多 LLM API 的消息格式会出问题，或让历史变得混乱。

## `fetch_chat` 和 `fetch_all_chats`

`fetch_chat`：

```text
只取某个 agent 的历史
```

`fetch_all_chats`：

```text
遍历当前 user_id + session_id 下所有 agent 的历史
按 timestamp 排序
assistant 消息前面加上 [agent_id]
返回给 classifier
```

assistant 前面加 `[agent_id]` 是为了让 classifier 知道上一轮是谁回答的，方便处理 follow-up。

## 内存状态 vs 持久化状态

这里非常适合区分三种状态：

```text
函数临时变量：
  key / conversation / timestamped_message
  本次方法调用结束后就没了

对象长期状态：
  InMemoryChatStorage.conversations
  只要这个 Python 对象还在，历史就在

跨进程持久化状态：
  DynamoDB / SQL
  程序重启后还可以取回
```

默认 `InMemoryChatStorage` 不是数据库。它适合 demo 和测试，不适合真实线上长期记忆。

## 用户点外卖的流程类比

Storage 像外卖平台的订单历史系统：

```text
user_id = 用户账号
session_id = 本次点单会话
agent_id = 哪家店
ConversationMessage = 一条订单沟通记录
TimestampedMessage = 带时间的订单沟通记录
```

`fetch_chat` 像只翻“用户和这家店”的聊天记录。

`fetch_all_chats` 像平台客服翻“用户本次会话里和所有店的沟通记录”，判断用户现在这句是不是延续刚才的话题。

## 出 bug 先查哪里

- 历史没了：确认是不是默认 `InMemoryChatStorage`，程序重启后会丢。
- 多个 agent 历史串了：查 key 是否包含 `agent_id`。
- follow-up 分类失败：查 `fetch_all_chats` 返回的 assistant 消息是否带 `[agent_id]`。
- 历史太长或太短：查 `MAX_MESSAGE_PAIRS_PER_AGENT` 和 `trim_conversation`。
- 连续消息没保存：查 `is_same_role_as_last_message`。

## 一句话总结

Storage 模块本质上是在按 `user_id + session_id + agent_id` 管理多轮对话历史，让分类和回答都能带上下文。
