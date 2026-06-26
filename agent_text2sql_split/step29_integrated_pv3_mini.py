"""
Step 29 - pv3 整合版：Mini Text2SQL + RAG + Memory + Tools

整合概念：
- pv2 的 SQL/RAG/Memory 双路径
- step24 本地工具：web_search / local_data_analysis
- step25 搜索 provider chain
- step26 MCP 工具加载形态
- step27 ToolOrchestrator：选择、执行、校验
- step28 工具上下文注入 + memory_query

运行：
    python3 learn_agent/step29_integrated_pv3_mini.py

对应 pv3：
- text2sql_pv3_tools/text2sql/tool_runtime/
- text2sql_pv3_tools/text2sql/chatbot.py
- text2sql_pv3_tools/text2sql/graph.py
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, TypedDict


@dataclass
class Settings:
    max_sql_retries: int = 2
    rag_router_year_threshold: int = 2026
    tools_enabled: bool = True
    tools_max_attempts: int = 2


@dataclass
class Message:
    role: str
    content: str


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    error: str | None = None


class QueryExecutor:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE sales (region TEXT, revenue REAL, profit REAL)")
        self.conn.executemany(
            "INSERT INTO sales VALUES (?, ?, ?)",
            [("华东", 1000, 120), ("华南", 800, 90), ("华北", 500, 30)],
        )
        self.conn.commit()

    def execute(self, sql: str) -> QueryResult:
        try:
            if not sql.strip().lower().startswith("select"):
                raise ValueError("仅允许 SELECT")
            cur = self.conn.execute(sql)
            return QueryResult([d[0] for d in cur.description], cur.fetchall())
        except Exception as e:
            return QueryResult([], [], str(e))

    def fetch_schema_digest(self) -> str:
        return "表 sales:\n  - region (TEXT)\n  - revenue (REAL)\n  - profit (REAL)"


class Text2sqlAgent:
    def generate(self, *, messages: list[Message], last_error: str | None = None, **_: Any) -> str:
        question = "\n".join(m.content for m in messages if m.role == "user")
        if "利润" in question:
            return "SELECT region, profit FROM sales ORDER BY profit DESC LIMIT 3"
        return "SELECT region, revenue FROM sales ORDER BY revenue DESC LIMIT 3"


class AnalyzerAgent:
    def analyze(self, *, user_question: str, sql: str, columns: list[str], rows: list[tuple[Any, ...]], memory_context: str = "") -> str:
        return f"## 结论\n返回 {len(rows)} 行：{rows}\n\n## 依据\nSQL：`{sql}`\n列：{columns}"


@dataclass
class Document:
    page_content: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class RagResult:
    answer: str
    contexts: list[Document]
    retrieval_queries: list[str]
    sub_questions: list[str]


class MiniRagEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.docs = [
            Document("低毛利订单处理：先复核折扣权限，再评估履约成本。", {"source": "playbook.txt"}),
            Document("2027 年渠道策略：区域代理分层，重点客户联合拜访。", {"source": "strategy.txt"}),
        ]

    def route(self, question: str) -> str:
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", question)]
        if years and max(years) >= self.settings.rag_router_year_threshold:
            return "kb"
        if "低毛利" in question or "策略" in question or "工具调用补充上下文" in question:
            return "kb"
        return "sql"

    def ask(self, question: str, *, memory_context: str = "") -> RagResult:
        queries = [question]
        scored = sorted(self.docs, key=lambda d: sum(1 for ch in set(question) if ch in d.page_content), reverse=True)
        top = scored[0]
        answer = f"## 结论\n{top.page_content}\n\n## 依据\n来自 {top.metadata['source']}"
        if "工具调用补充上下文" in question:
            answer += "\n\n## 工具补充\n已结合工具搜索结果校正回答。"
        return RagResult(answer, [top], queries, [question])


class UserMemoryStore:
    def build_prompt_block(self, query: str) -> str:
        return "### L2 程序性记忆（检索）\n- 用户偏好先给结论，再列依据。"


class MemoryCommitAgent:
    def propose_items(self, **_: Any) -> list[dict[str, Any]]:
        return []


@dataclass
class SimpleTool:
    name: str
    description: str
    func: Callable[[dict[str, Any]], str]

    def invoke(self, args: dict[str, Any]) -> str:
        return self.func(args)


@dataclass
class ToolDescriptor:
    name: str
    description: str
    source: str


@dataclass
class ToolDecision:
    tool_name: str
    arguments: dict[str, Any]
    rationale: str = ""


@dataclass
class ToolValidation:
    satisfied: bool
    reason: str
    suggest_retry: bool = False


@dataclass
class ToolRunRecord:
    user_goal: str
    tools_listed: list[ToolDescriptor] = field(default_factory=list)
    runtime_notes: list[str] = field(default_factory=list)
    decision: ToolDecision | None = None
    tool_output: str = ""
    tool_error: str | None = None
    validation: ToolValidation | None = None
    skipped: bool = False
    skip_reason: str = ""


def web_search_impl(args: dict[str, Any]) -> str:
    query = str(args.get("query") or "")
    if not query.strip():
        return "错误：query 不能为空"
    return "1. 订单质量规则\n   低毛利订单应复核折扣权限，并评估履约成本。\n   https://example.com/order-quality"


def local_analysis_impl(args: dict[str, Any]) -> str:
    data = json.loads(str(args.get("data_json") or "{}"))
    return f"本地数据分析：行数={len(data.get('rows', []))}"


class ToolOrchestrator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.tools = {
            "web_search": SimpleTool("web_search", "联网搜索", web_search_impl),
            "local_data_analysis": SimpleTool("local_data_analysis", "本地表格统计分析", local_analysis_impl),
        }
        self.runtime_notes = ["MCP 未配置：本 demo 只加载本地工具。"]

    def list_tools(self) -> list[ToolDescriptor]:
        return [ToolDescriptor(t.name, t.description, "local") for t in self.tools.values()]

    def select_tool(self, user_goal: str) -> ToolDecision:
        if any(w in user_goal for w in ["最新", "联网", "资料", "搜索"]):
            return ToolDecision("web_search", {"query": user_goal, "max_results": 3}, "需要外部资料")
        if "本地分析" in user_goal:
            payload = {"columns": ["profit"], "rows": [[120], [90], [30]]}
            return ToolDecision("local_data_analysis", {"data_json": json.dumps(payload)}, "可用本地表格工具")
        return ToolDecision("none", {}, "无需工具")

    def run(self, user_goal: str) -> ToolRunRecord:
        record = ToolRunRecord(user_goal=user_goal, tools_listed=self.list_tools(), runtime_notes=self.runtime_notes)
        decision = self.select_tool(user_goal)
        record.decision = decision
        if decision.tool_name == "none":
            record.skipped = True
            record.skip_reason = decision.rationale
            record.validation = ToolValidation(True, decision.rationale)
            return record
        try:
            record.tool_output = self.tools[decision.tool_name].invoke(decision.arguments)
        except Exception as e:
            record.tool_error = f"{type(e).__name__}: {e}"
        ok = bool(record.tool_output.strip()) and not record.tool_output.startswith(("错误：", "联网搜索失败"))
        record.validation = ToolValidation(ok, "工具输出可用" if ok else "工具失败")
        return record


def tool_output_usable(record: ToolRunRecord) -> bool:
    return bool(
        not record.skipped
        and not record.tool_error
        and record.tool_output.strip()
        and not record.tool_output.startswith(("错误：", "联网搜索失败", "未检索到"))
        and (record.validation is None or record.validation.satisfied)
    )


def build_tool_context_block(record: ToolRunRecord, *, max_chars: int = 500) -> str:
    if not tool_output_usable(record):
        return ""
    body = record.tool_output.strip()
    if len(body) > max_chars:
        body = body[:max_chars] + "\n...（工具输出已截断）"
    return "【工具调用补充上下文】\n" + body


class GraphState(TypedDict):
    messages: list[Message]
    memory_query: str
    schema_text: str
    sql: str
    columns: list[str]
    rows: list[tuple[Any, ...]]
    error: str | None
    retry_count: int
    analysis: str
    route: str
    rag_context: list[str]
    rag_retrieval_queries: list[str]
    rag_sub_questions: list[str]
    memory_context: str
    memory_writes: list[dict[str, Any]]


def last_user_text(messages: list[Message]) -> str:
    return next((m.content for m in reversed(messages) if m.role == "user"), "")


class MiniPv3Graph:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.qe = QueryExecutor()
        self.text2sql = Text2sqlAgent()
        self.analyzer = AnalyzerAgent()
        self.rag = MiniRagEngine(settings)
        self.memory = UserMemoryStore()

    def invoke(self, state: GraphState) -> GraphState:
        uq = last_user_text(state["messages"])
        state["memory_context"] = self.memory.build_prompt_block(state.get("memory_query") or uq)
        state["route"] = self.rag.route(uq)
        if state["route"] == "kb":
            result = self.rag.ask(uq, memory_context=state["memory_context"])
            state["analysis"] = result.answer
            state["rag_context"] = [str(d.metadata.get("source")) for d in result.contexts]
            state["rag_retrieval_queries"] = result.retrieval_queries
            state["rag_sub_questions"] = result.sub_questions
            return state

        state["sql"] = self.text2sql.generate(messages=state["messages"])
        res = self.qe.execute(state["sql"])
        state["columns"], state["rows"], state["error"] = res.columns, res.rows, res.error
        state["analysis"] = self.analyzer.analyze(
            user_question=uq,
            sql=state["sql"],
            columns=state["columns"],
            rows=state["rows"],
            memory_context=state["memory_context"],
        )
        return state


class Chatbot:
    def __init__(self) -> None:
        self.settings = Settings()
        self.tools = ToolOrchestrator(self.settings)
        self.graph = MiniPv3Graph(self.settings)
        self.schema_text = self.graph.qe.fetch_schema_digest()
        self.messages: list[Message] = []

    def chat(self, user_text: str, *, memory_query: str | None = None) -> GraphState:
        self.messages.append(Message("user", user_text))
        state: GraphState = {
            "messages": self.messages.copy(),
            "memory_query": memory_query or user_text,
            "schema_text": self.schema_text,
            "sql": "",
            "columns": [],
            "rows": [],
            "error": None,
            "retry_count": 0,
            "analysis": "",
            "route": "",
            "rag_context": [],
            "rag_retrieval_queries": [],
            "rag_sub_questions": [],
            "memory_context": "",
            "memory_writes": [],
        }
        out = self.graph.invoke(state)
        self.messages = [*self.messages, Message("assistant", out["analysis"])]
        return out

    def chat_with_tools(self, user_text: str) -> tuple[ToolRunRecord, GraphState]:
        record = self.tools.run(user_text) if self.settings.tools_enabled else ToolRunRecord(user_text, skipped=True)
        block = build_tool_context_block(record)
        enriched = f"{user_text}\n\n{block}" if block else user_text
        return record, self.chat(enriched, memory_query=user_text)


def main() -> None:
    bot = Chatbot()
    for q in [
        "各区域收入排名是什么？",
        "结合最新资料，低毛利订单怎么处理？",
        "做一个本地分析：利润分布如何？",
    ]:
        print("\n用户：", q)
        tool_record, out = bot.chat_with_tools(q)
        if tool_record.decision:
            print("tool:", tool_record.decision.tool_name, "| usable:", tool_output_usable(tool_record))
        print("route:", out["route"])
        if out["sql"]:
            print("sql:", out["sql"])
        if out["rag_context"]:
            print("rag_context:", out["rag_context"])
        print(out["analysis"])


if __name__ == "__main__":
    main()
