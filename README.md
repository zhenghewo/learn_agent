# learn_agent：Text2SQL 非线性微增量学习版

这个目录按 `PROMPTS.md` 的“概念驱动学习法”组织：

- 每个普通 Step 只讲 1 个核心概念。
- 普通 Step 都尽量独立可运行，不依赖真实数据库、真实 LLM Key、Chroma 或 MCP。
- 每个版本最后都有一个整合版，把该版本新增概念串起来。
- `step12` 是 pv0 整合版；`step16`、`step23`、`step29` 分别是 pv1、pv2、pv3 整合版。

## 目录

```text
learn_agent/
├── step00_db_seed.py                     # 基础数据库
├── step01_settings_concept.py            # Settings 配置管理
├── step02_llm_client_concept.py          # LLM Client
├── step03_sql_safety_concept.py          # SQL 安全检查
├── step04_query_executor_concept.py      # 数据库 + SQL 安全 + 执行器
├── step05_text2sql_agent_concept.py      # Text2sqlAgent + Final SQL
├── step06_graph_concept.py               # Graph 编排
├── step07_retry_concept.py               # Retry 路由
├── step08_schema_digest_concept.py       # 动态 Schema
├── step09_chatbot_memory_concept.py      # Chatbot Memory
├── step10_analyzer_report_concept.py     # Analyzer 报告
├── step11_skill_tool_concept.py          # Skill Tool
├── step12_integrated_pv0_mini.py         # pv0 整合版
├── step13_react_final_sql_concept.py     # pv1: ReAct + Final SQL
├── step14_postgres_schema_digest_concept.py # pv1: PostgreSQL schema digest
├── step15_skill_subprocess_concept.py    # pv1: skill 子进程工具
├── step16_integrated_pv1_mini.py         # pv1 整合版
├── step17_rag_router_concept.py          # pv2: SQL / KB 路由
├── step18_rag_chunk_rerank_concept.py    # pv2: chunk + rerank
├── step19_multi_query_concept.py         # pv2: Multi-Query 检索
├── step20_rag_decomposition_concept.py   # pv2: 子问题分解
├── step21_user_memory_store_concept.py   # pv2: 用户记忆存取
├── step22_memory_commit_agent_concept.py # pv2: 自动记忆归档
├── step23_integrated_pv2_mini.py         # pv2 整合版
├── step24_langchain_tool_concept.py      # pv3: 本地工具
├── step25_search_provider_chain_concept.py # pv3: 搜索 provider chain
├── step26_mcp_tool_loading_concept.py    # pv3: MCP 工具加载
├── step27_tool_orchestrator_concept.py   # pv3: 工具编排器
├── step28_tool_context_injection_concept.py # pv3: 工具上下文注入
└── step29_integrated_pv3_mini.py         # pv3 整合版
```

## 推荐运行顺序

```bash
python3 learn_agent/step00_db_seed.py
python3 learn_agent/step01_settings_concept.py
python3 learn_agent/step02_llm_client_concept.py
python3 learn_agent/step03_sql_safety_concept.py
python3 learn_agent/step04_query_executor_concept.py
python3 learn_agent/step05_text2sql_agent_concept.py
python3 learn_agent/step06_graph_concept.py
python3 learn_agent/step07_retry_concept.py
python3 learn_agent/step08_schema_digest_concept.py
python3 learn_agent/step09_chatbot_memory_concept.py
python3 learn_agent/step10_analyzer_report_concept.py
python3 learn_agent/step11_skill_tool_concept.py
python3 learn_agent/step12_integrated_pv0_mini.py
```

继续理解 pv1：

```bash
python3 learn_agent/step13_react_final_sql_concept.py
python3 learn_agent/step14_postgres_schema_digest_concept.py
python3 learn_agent/step15_skill_subprocess_concept.py
python3 learn_agent/step16_integrated_pv1_mini.py
```

继续理解 pv2：

```bash
python3 learn_agent/step17_rag_router_concept.py
python3 learn_agent/step18_rag_chunk_rerank_concept.py
python3 learn_agent/step19_multi_query_concept.py
python3 learn_agent/step20_rag_decomposition_concept.py
python3 learn_agent/step21_user_memory_store_concept.py
python3 learn_agent/step22_memory_commit_agent_concept.py
python3 learn_agent/step23_integrated_pv2_mini.py
```

继续理解 pv3：

```bash
python3 learn_agent/step24_langchain_tool_concept.py
python3 learn_agent/step25_search_provider_chain_concept.py
python3 learn_agent/step26_mcp_tool_loading_concept.py
python3 learn_agent/step27_tool_orchestrator_concept.py
python3 learn_agent/step28_tool_context_injection_concept.py
python3 learn_agent/step29_integrated_pv3_mini.py
```

## 概念到项目版本的映射

| Step | 概念 | 对应项目 |
|---|---|---|
| 00-12 | pv0 基础 Text2SQL 链路 | `text2sql_pv0` 的核心形态 |
| 13 | ReAct + `Final:` 收口 | `text2sql_pv1_0425/text2sql/text2sql_agent.py` |
| 14 | PostgreSQL schema digest / 表白名单 | `text2sql_pv1_0425/text2sql/query_executor.py`、`chatbot.py` |
| 15 | skill 子进程工具 | `text2sql_pv1_0425/text2sql/skill_runtime.py` |
| 16 | pv1 整合 | `text2sql_pv1_0425` |
| 17 | SQL / KB 路由 | `text2sql_pv2_mem/text2sql/rag_engine.py`、`graph.py` |
| 18 | RAG 切分、召回、重排 | `text2sql_pv2_mem/text2sql/rag_engine.py` |
| 19 | Multi-Query | `text2sql_pv2_mem/docs/RAG-MultiQuery.md`、`rag_engine.py` |
| 20 | 子问题分解 | `text2sql_pv2_mem/docs/RAG子问题分解.md`、`rag_engine.py` |
| 21 | 用户记忆 store | `text2sql_pv2_mem/text2sql/user_memory.py` |
| 22 | 自动记忆归档 | `text2sql_pv2_mem/text2sql/memory_commit_agent.py` |
| 23 | pv2 整合 | `text2sql_pv2_mem` |
| 24 | 本地工具 | `text2sql_pv3_tools/text2sql/tool_runtime/local_tools.py` |
| 25 | 搜索 provider chain | `text2sql_pv3_tools/text2sql/tool_runtime/web_search_providers.py` |
| 26 | MCP 工具加载 | `text2sql_pv3_tools/text2sql/tool_runtime/mcp_tools.py` |
| 27 | 工具编排器 | `text2sql_pv3_tools/text2sql/tool_runtime/orchestrator.py` |
| 28 | 工具上下文注入 | `text2sql_pv3_tools/text2sql/chatbot.py`、`graph.py` |
| 29 | pv3 整合 | `text2sql_pv3_tools` |

## Step 总览与外卖类比

| Step | 大致作用 | 外卖点单类比 | 外卖送餐类比 |
|---|---|---|---|
| step00 | 准备 demo 数据库和样例数据 | 先搭一个小餐厅，准备菜单和几份样例订单 | 先划定配送站、骑手和几个测试地址 |
| step01 | 管理配置项，比如数据库地址、重试次数 | 设置收货地址、预算、配送偏好 | 设置配送半径、超时时间、最大改派次数 |
| step02 | 封装 LLM Client，统一调用模型 | 打开外卖 App，统一通过 App 和商家沟通 | 打开骑手调度系统，统一给骑手派单 |
| step03 | 检查 SQL 是否只读、是否安全 | 确认只是在看菜单和下查询单，不允许改商家后台 | 确认配送指令只查路线，不乱改订单状态 |
| step04 | 把 SQL 安全检查和执行器组合起来 | 点单前先检查菜品合法，再把订单发给厨房 | 派单前先检查地址和路线，再交给骑手执行 |
| step05 | Text2SQL Agent：把自然语言转成 SQL | 把“我想吃不辣的面”翻译成具体菜品编号 | 把“尽快送到公司前台”翻译成配送任务单 |
| step06 | Graph 编排：串起生成、执行、分析节点 | 外卖流程从选店、下单、出餐到配送依次推进 | 配送流程从接单、取餐、导航、送达到确认完成 |
| step07 | Retry 路由：失败后重试修正 | 商家说“这个菜没了”，App 让你换个可下单的菜 | 骑手遇到封路，系统重新规划路线或改派 |
| step08 | 动态 Schema 摘要 | App 先读当前菜单，知道有哪些菜、规格和价格 | 系统先看当前路网、骑手位置和可配送区域 |
| step09 | Chatbot 多轮记忆 | 记住你上一轮说“不要香菜”，追问时继续沿用 | 记住你说“放前台”，后续同一单继续按这个交付 |
| step10 | Analyzer 报告生成和落盘 | 下单后生成一张订单小票和消费总结 | 送达后生成配送轨迹、耗时和异常记录 |
| step11 | Skill Tool：按意图调用导出工具 | 需要发票或打包清单时，叫专门的小工具处理 | 需要拍照回执或签收单时，调用专门的回执工具 |
| step12 | pv0 最小整合版 | 一个能完成点单、出餐、反馈的小型外卖闭环 | 一个能派单、取餐、送达、反馈的小型配送闭环 |
| step13 | ReAct + Final SQL：先思考，最后收口 SQL | 先比较菜品、确认口味，最后只提交一张明确订单 | 先判断路线和风险，最后只给骑手一条明确路线 |
| step14 | PostgreSQL schema digest 和表白名单 | 只展示这家店允许点的菜单，不把后厨库存表暴露出来 | 只展示可走道路和服务区域，不暴露内部调度数据 |
| step15 | Skill 子进程工具运行时 | 点单系统把“开发票”交给独立发票服务处理 | 配送系统把“生成签收单”交给独立回执服务处理 |
| step16 | pv1 整合版 | 外卖 App 升级：会确认菜单、修正错误订单、导出小票 | 配送系统升级：会校验路线、处理异常、导出配送记录 |
| step17 | RAG Router：判断走 SQL 还是知识库 | 判断你是在点当前菜品，还是问“下季度店铺活动规则” | 判断是在查当前订单位置，还是问配送规则和赔付政策 |
| step18 | RAG chunk、召回、重排 | 把厚厚的活动手册切页，先找相关页，再把最相关的排前面 | 把配送手册切成小段，先找相关规则，再按匹配度排序 |
| step19 | Multi-Query 检索 | 同时用“低脂餐”“减脂餐”“轻食”多种说法搜菜单 | 同时用“超时”“晚到”“延误”多种说法查配送规则 |
| step20 | 子问题分解 | 把“晚餐怎么点、优惠怎么用、多久送到”拆成三个问题 | 把“为什么晚、怎么补偿、多久到”拆成多个配送子问题 |
| step21 | UserMemoryStore 用户记忆 | 记住你长期偏好：少辣、不要香菜、先看套餐 | 记住你的长期收货习惯：放前台、别打电话、工作日地址 |
| step22 | MemoryCommitAgent 自动归档 | 每次点完判断哪些偏好值得长期记住 | 每次送完判断哪些收货习惯值得长期保存 |
| step23 | pv2 整合版 | 外卖 App 会查菜单、查活动手册，还记住你的口味 | 配送系统会查订单、查配送规则，还记住你的交付偏好 |
| step24 | 本地工具 web_search / local_data_analysis | App 内置“搜评价”和“算满减”的小工具 | 配送端内置“查天气”和“估算配送耗时”的小工具 |
| step25 | 搜索 provider chain | 先搜平台评价，失败再搜网页，再失败换备用搜索源 | 先查地图服务，失败再查备用地图，再失败用兜底路线 |
| step26 | MCP 工具加载 | 接入第三方配送、发票、会员积分等外部服务 | 接入第三方地图、短信、保险、签收等配送服务 |
| step27 | ToolOrchestrator 工具编排器 | 调度中心决定该叫搜索、算价、发票还是配送工具 | 调度中心决定该查路况、联系骑手、发短信还是改派 |
| step28 | 工具上下文注入 | 把工具查到的“商家今天有活动”塞回点单对话里 | 把工具查到的“前方拥堵/预计晚到”塞回配送对话里 |
| step29 | pv3 整合版 | 一个会点单、查资料、记偏好、调外部服务的完整外卖助手 | 一个会派单、查路况、记收货习惯、调外部服务的完整配送助手 |

## 每步检查

每完成一个 Step，问自己：

- [ ] 这个 Step 能跑通吗？
- [ ] 我能解释这个文件中的核心类/函数吗？
- [ ] 如果去掉这个概念，对应项目版本会少什么能力？
