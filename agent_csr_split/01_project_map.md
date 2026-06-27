# 01 项目结构总览

## 这个项目整体负责什么

`agent-squad-main` 是一个多智能体编排框架。它不是一个单一聊天机器人，而是提供一套基础设施：

- 你可以注册多个 agent。
- 用户来了一个问题后，分类器决定哪个 agent 最适合回答。
- 被选中的 agent 处理请求。
- 存储层保存不同用户、不同会话、不同 agent 的对话历史。
- 对外统一返回 `AgentResponse`。

正常程序员看这个项目时，会先找“主入口”和“核心抽象”，而不是从 examples 或 docs 开始深挖。这里的主入口是：

```text
python/src/agent_squad/orchestrator.py
```

核心抽象是：

```text
python/src/agent_squad/agents/agent.py
python/src/agent_squad/classifiers/classifier.py
python/src/agent_squad/storage/chat_storage.py
python/src/agent_squad/types/types.py
```

## 目录怎么读

```text
agent-squad-main/
├── python/                 Python SDK 主体，当前最值得读
│   └── src/agent_squad/
│       ├── orchestrator.py 主流程入口
│       ├── agents/         各种 agent 实现
│       ├── classifiers/    分类器
│       ├── storage/        聊天历史存储
│       ├── types/          消息、配置、枚举
│       ├── utils/          tool、logger、转换工具
│       └── retrievers/     检索增强接口
├── examples/               使用示例
├── typescript/             TypeScript 版本
├── docs/                   文档站点
└── README.md               项目介绍
```

如果目标是理解 Python 项目链路，优先级是：

```text
orchestrator.py
-> agents/agent.py
-> classifiers/classifier.py
-> storage/chat_storage.py
-> storage/in_memory_chat_storage.py
-> agents/bedrock_llm_agent.py
-> utils/tool.py
-> agents/supervisor_agent.py
```

## 主流程文字图

```text
用户问题
-> AgentSquad.route_request(...)
-> storage.fetch_all_chats(...) 取所有 agent 的历史
-> classifier.classify(...) 判断 selected_agent
-> dispatch_to_agent(...) 取该 agent 自己的历史
-> selected_agent.process_request(...)
-> save_message(...) 保存用户问题
-> save_message(...) 保存 agent 回答
-> 返回 AgentResponse(metadata, output, streaming)
```

## 哪些暂时不用深究

- `.github/`：CI、发布流程，对理解运行链路帮助不大。
- `docs/`：文档站点源码，先不用读。
- `typescript/`：和 Python SDK 概念相近，但你现在先读 Python 更集中。
- 大量具体 AWS agent：比如 Lex、Bedrock Flows、Inline Agent，可以等主线清楚后再读。

## 用户点外卖的流程类比

这个项目像一个外卖平台：

```text
用户写需求
-> 平台判断这单应该给奶茶店、快餐店还是药店
-> 对应商家处理
-> 平台保存订单聊天记录
-> 用户收到出餐结果
```

`AgentSquad` 不是“厨师”，它更像“平台调度系统”。真正做菜的是各种 `Agent`。

## 这个文件本质上在做什么？

这个拆解文件本质上是在告诉你：读 Agent Squad 时要先抓住 Python SDK 的主链路，再看具体 agent 和示例。
