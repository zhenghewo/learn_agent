# 智能客服 Agent 评测系统 — 设计与实现


## 1. 为什么 Agent 需要分层评测

传统 NLP 评测（Accuracy / BLEU）无法覆盖 Agent 系统的完整行为链。Agent 评测需区分三层：

| 层级 | 英文术语 | 评测对象 | 典型指标 |
|------|----------|----------|----------|
| L1 组件级 | **Component Eval** | Intent Router、RAG、Tool Use | Routing Accuracy、Recall@K、Tool F1 |
| L2 编排级 | **Orchestration Eval** | Supervisor 路由与汇总 | Route Consistency、Info Preservation |
| L3 端到端 | **E2E / Task Eval** | 完整 `/api/chat` 链路 | **TSR** (Task Success Rate)、Latency P95 |

**拓展 — Agent 评测 vs LLM 评测：**
- **LLM Eval** 关注单轮生成质量（Perplexity、Human Preference）。
- **Agent Eval** 额外考察 **Tool Use Correctness**（函数调用参数是否正确）、**Plan Fidelity**（是否按规划执行）、**Groundedness**（RAG 回答是否 grounded 于检索文档）。
- 工业界常用框架：RAGAS（RAG 三角：Context Precision / Faithfulness / Answer Relevancy）、LangSmith Eval、HELM。

本项目的 LangGraph 流水线：

```
IntentRouter → [KnowledgeRAG | TicketHandler | ToolExecutor] → ComplianceCheck → Synthesize
```

---

## 2. 目录结构

```
python-impl/eval/
├── schemas.py              # EvalCase / EvalReport 数据模型
├── metrics.py              # 指标纯函数（F1、Recall@K、nDCG、ECE）
├── datasets/
│   ├── intent_mapping.py   # Bitext 27 intent → gold agent/tools
│   ├── loader.py           # 从 bitext/*.txt + fixtures 构建 EvalSuite
│   └── fixtures/           # compliance / tool / ticket / e2e JSON
├── evaluators/
│   ├── intent_evaluator.py
│   ├── rag_evaluator.py
│   ├── compliance_evaluator.py
│   ├── tool_evaluator.py
│   ├── ticket_evaluator.py
│   └── e2e_evaluator.py
├── runner.py               # EvalRunner 编排入口
└── report.py               # 控制台 + JSON 报告

python-impl/scripts/run_eval.py   # CLI
```

---

## 3. 核心数据模型 (`schemas.py`)

评测采用 **Case → Evaluator → ModuleMetrics → EvalReport** 四级结构。

```python
@dataclass
class IntentEvalCase:
    case_id: str
    message: str
    expected_agent: str          # knowledge_rag | ticket_handler | tool_executor
    expected_primary: str        # consultation | complaint | transaction | ...
    expected_tools: list[str]    # ["order_query", "ticket_create"]
    expected_entities: dict[str, str]

@dataclass
class RAGEvalCase:
    query: str
    gold_answer: str
    gold_source: str             # 期望命中的知识库文件名，如 track_order.txt
    gold_keywords: list[str]     # 答案关键词，用于 keyword_coverage

@dataclass
class ComplianceEvalCase:
    content: str
    should_pass: bool            # True=合规, False=应拦截
    violation_types: list[str]   # pii | forbidden_finance | overpromise

@dataclass
class ModuleMetrics:
    module: str
    total: int
    passed: int
    metrics: dict[str, float]    # 聚合指标
    details: list[dict]          # 逐条 case 结果，便于 error analysis

@dataclass
class EvalReport:
    modules: dict[str, ModuleMetrics]
    summary: dict[str, float]    # 北极星 KPI 汇总
```

**拓展 — Gold Label 设计原则：**
- **Intent Gold** 来自业务路由规则（非 LLM 标注），保证可复现。
- **RAG Gold Source** 用文件级标注（非 chunk 级），降低标注成本；生产环境可升级为 chunk ID。
- **Compliance Gold** 必须人工构造正负样本，覆盖 PII regex 与 LLM 语义违规两类。

---

## 4. 指标函数 (`metrics.py`)

指标层与 Agent 逻辑解耦，便于单元测试。

| 函数 | 用途 | Agent 场景 |
|------|------|-----------|
| `set_f1(expected, predicted)` | 集合 F1 | Tool Planning：预测工具集 vs 期望工具集 |
| `entity_f1(expected, predicted)` | 实体 F1 | Intent Router 抽取 order_id / ticket_id |
| `recall_at_k(ranked_ids, gold_id, k)` | 检索召回 | RAG 是否在前 K 条命中 gold 文档 |
| `mrr_at_k(...)` | Mean Reciprocal Rank | 正确文档排序位置 |
| `ndcg_at_k(relevances, k)` | 排序质量 | Cross-Encoder 重排效果 |
| `token_overlap_f1(ref, hyp)` | 词袋重叠 F1 | **Faithfulness 代理指标**（无 embedding 时的 groundedness 近似） |
| `calibration_ece(confidences, flags)` | 期望校准误差 | Intent confidence 是否可信 |

```python
def set_f1(expected: set[str], predicted: set[str]) -> float:
    tp = len(expected & predicted)
    _, _, f1 = precision_recall_f1(tp, len(predicted - expected), len(expected - predicted))
    return f1

def recall_at_k(ranked_ids: Sequence[str], gold_id: str, k: int) -> float:
    return 1.0 if gold_id in ranked_ids[:k] else 0.0
```

**拓展 — RAG 评测三角（RAGAS）：**
1. **Context Precision**：检索文档是否相关（→ 本项目的 Recall@K / nDCG@K）
2. **Faithfulness**：生成是否忠于 context（→ `token_overlap_f1(context, answer)`，生产可用 LLM-as-Judge）
3. **Answer Relevancy**：答案是否回应 query（→ `keyword_coverage` 或语义相似度）

---

## 5. 数据集加载 (`datasets/`)

### 5.1 Intent Gold 映射 (`intent_mapping.py`)

Bitext 27 子意图映射到 Supervisor 的三路路由：

```python
BITEXT_ROUTING_LABELS = {
    "track_order": {
        "primary": "transaction",
        "agent": "tool_executor",
        "tools": ["order_query"],
    },
    "get_refund": {
        "primary": "complaint",
        "agent": "ticket_handler",
        "tools": ["ticket_create"],
    },
    "check_refund_policy": {
        "primary": "consultation",
        "agent": "knowledge_rag",
        "tools": [],
    },
    # ... 共 27 个 intent
}
```

### 5.2 自动采样 (`loader.py`)

从 `knowledge_base/bitext/*.txt` 解析 `Question/Answer` 块，按 intent 分层采样：

```python
def load_eval_suite(*, max_intent_per_label=5, max_rag_per_source=3) -> EvalSuite:
    suite.intent_cases = load_intent_cases_from_bitext(...)  # 27 × N 条
    suite.rag_cases = load_rag_cases_from_bitext(...)
    suite.compliance_cases = load_compliance_cases(fixtures/compliance.json)
    suite.tool_cases = load_tool_cases(fixtures/tool.json)
    suite.e2e_cases = load_e2e_cases(fixtures/e2e.json)
    return suite
```

固定 JSON fixture 覆盖 **确定性场景**（订单查询、PII 泄露、工单创建），不依赖 LLM 标注。

---

## 6. 组件 Evaluator 实现

所有 Evaluator 继承 `BaseEvaluator`，实现 `async def run() -> ModuleMetrics`。

### 6.1 IntentEvaluator — Agent Routing

对应 `IntentRouterAgent.classify()`，输出结构化 JSON（primary_intent、suggested_agent、tools_to_call）。

```python
class IntentEvaluator(BaseEvaluator):
    async def run(self) -> ModuleMetrics:
        result = await self.agent.classify(case.message, case.user_id)
        agent_ok = result.suggested_agent == case.expected_agent
        tool_f1 = set_f1(set(case.expected_tools), {c["name"] for c in result.tools_to_call})
        # 聚合: agent_routing_accuracy, tool_planning_f1, entity_extraction_f1, confidence_ece
```

**关键概念 — Tool Planning：** Intent Router 不仅分类，还产出 **Function Calling Plan**（MCP tools_to_call），评测需同时考察路由 Agent 与工具规划。

### 6.2 RAGEvaluator — Retrieval + Generation

分两段评测，支持 `--rag-skip-generation` 仅测检索：

```python
class RAGEvaluator(BaseEvaluator):
    async def run(self) -> ModuleMetrics:
        rewritten = await self.agent.rewrite_query(case.query)      # Query Rewrite
        docs = await self.agent.retrieve_documents(rewritten)         # Vector + Rerank
        recall = recall_at_k([_source_id(d) for d in docs], case.gold_source, k=5)
        answer = await self.agent.generate_answer(case.query, docs)
        faith = token_overlap_f1(context_text, answer)              # Groundedness 代理
```

**拓展 — GraphRAG 评测：** 若启用 Neo4j，可在 metadata 中区分 `source_type: vector | subgraph | path`，分别统计各通道 Recall 及融合增益 Δ。

### 6.3 ComplianceEvaluator — 两阶段审查

对应 `ComplianceCheckerAgent` 的 **Rule Engine + LLM Guard** 架构：

```python
class ComplianceEvaluator(BaseEvaluator):
    async def run(self) -> ModuleMetrics:
        result = await self.agent.rule_check(case.content)   # --compliance-rule-only
        # 或 full_check(): rule → llm 级联
        predicted_block = not result.passed
        should_block = not case.should_pass
        # 计算 violation_recall, false_positive_rate, pii_detection_recall
```

**拓展 — Guardrails 设计模式：**
- **Rule-first（本项目的 rule_check）**：毫秒级、高 Recall，覆盖 PII regex 与违禁词表。
- **LLM Guard（llm_check）**：高 Precision，捕获越权承诺、歧视性内容等语义违规。
- 工业实践：**Cascade**（规则不过 → 直接拦截；规则过 → LLM 复核）平衡延迟与安全。

### 6.4 ToolEvaluator / TicketEvaluator — MCP Tool Use

```python
# ToolEvaluator: 给定 tool_calls，验证执行与回复字段
tool_results = await self.agent.run_tools(case.tool_calls, case.user_id)
answer = await self.agent.generate_answer(case.message, tool_results)
fields_ok = contains_all_fields(answer, case.expected_fields)  # 如 "ORD-20260401-001", "已发货"

# TicketEvaluator: 验证工单 CRUD 与 TK- 号回显
result_state = await self.agent.process(state)
id_ok = "TK-" in result_state["sub_results"]["ticket_handler"]
```

**关键概念 — Tool Use Eval：** 评测 **参数正确性**（schema 合规）、**执行成功率**、**NLG  grounded 于 tool result** 三维度。OpenAI Function Calling / MCP 协议使 tool eval 可自动化。

### 6.5 E2EEvaluator — 全链路 Task Success

驱动 LangGraph `CompiledStateGraph.ainvoke()`，评测端到端行为：

```python
class E2EEvaluator(BaseEvaluator):
    async def run(self) -> ModuleMetrics:
        result = await self.graph.ainvoke(initial_state)
        route_ok = result["intent"] == case.expected_agent
        kw_cov = keyword_coverage(result["final_response"], case.success_keywords)
        task_ok = kw_cov >= 0.5 and result["compliance_passed"]
        # 聚合: task_success_rate, routing_accuracy, latency_p95_ms
```

**拓展 — TSR vs FCR：**
- **TSR (Task Success Rate)**：任务是否完成（查单成功、工单创建）。
- **FCR (First Contact Resolution)**：单轮内解决，无需转人工。E2E eval 的 `success_keywords` 是 TSR 的弱监督代理。

---

## 7. 评测编排 (`runner.py`)

`EvalRunner` 统一初始化 LLM、Chroma、MCP Mock Stores，按模块调度 Evaluator：

```python
class EvalRunner:
    async def run(self, modules=["all"]) -> EvalReport:
        if "compliance" in selected:
            report.modules["compliance"] = await ComplianceEvaluator(...).run()
        if "intent" in selected:
            report.modules["intent"] = await IntentEvaluator(...).run()
        if "e2e" in selected:
            graph = create_supervisor_graph(mcp_server=..., enable_checkpointing=False)
            report.modules["e2e"] = await E2EEvaluator(graph, ...).run()
        report.summary = _build_summary(report)  # 北极星 KPI
        return report
```

北极星 KPI 映射：

| Summary Key | 来源模块 | 含义 |
|-------------|----------|------|
| `task_success_rate` | e2e | 端到端任务成功率 |
| `agent_routing_accuracy` | intent | 路由准确率 |
| `faithfulness_overlap` | rag | RAG 忠实度代理 |
| `violation_recall` | compliance | 违规检出召回 |
| `latency_p95_ms` | e2e | P95 延迟 |

---

## 8. 运行方式

```bash
cd python-impl

# 全量评测（需 LLM API Key + Chroma 索引）
python scripts/run_eval.py --output ./eval/reports/latest.json

# 仅规则引擎合规（无需 LLM）
python scripts/run_eval.py --modules compliance --compliance-rule-only

# 仅检索评测（跳过 RAG 生成，节省 Token）
python scripts/run_eval.py --modules rag --rag-skip-generation

# 指定模块 + 采样量
python scripts/run_eval.py --modules intent tool e2e --max-intent 3 --max-rag 2
```

---

## 9. 扩展方向

| 方向 | 说明 |
|------|------|
| **LLM-as-Judge** | 用强模型评 Helpfulness / Groundedness，替代 keyword_coverage |
| **RAGAS 集成** | `pip install ragas`，对 RAG 三角做标准 benchmark |
| **LangSmith Dataset** | 将 EvalCase 上传 LangSmith，支持 regression + A/B |
| **Human-in-the-Loop Eval** | 合规边界 case 人工复核，迭代 gold label |
| **Multi-turn Eval** | 扩展 E2EEvalCase 为对话脚本，测 short_term memory 指代消解 |
| **CI Gate** | `task_success_rate >= 0.75 && violation_recall >= 0.95` 作为 merge 门槛 |

---

## 10. 与系统组件对照

| Evaluator | 被测 Agent | 源码 |
|-----------|-----------|------|
| IntentEvaluator | IntentRouterAgent | `agents/intent_router.py` |
| RAGEvaluator | KnowledgeRAGAgent | `agents/knowledge_rag.py` |
| ComplianceEvaluator | ComplianceCheckerAgent | `agents/compliance_checker.py` |
| ToolEvaluator | ToolExecutorAgent | `agents/tool_executor.py` |
| TicketEvaluator | TicketHandlerAgent | `agents/ticket_handler.py` |
| E2EEvaluator | Supervisor Graph | `agents/supervisor.py` |

Supervisor 的 `route_from_intent()` 是 **Conditional Edge**（LangGraph 术语），Intent Eval 的错误会直接传导至 E2E TSR——因此 Intent + E2E 是 P0 评测优先级。
