"""
Step 23 - pv2 整合版：Mini Text2SQL + RAG + Memory

整合概念：
- pv1 的 SQL 生成、执行、分析、自愈
- step17 RAG Router：SQL / KB 双路径
- step18-20 RAG：检索、重排、Multi-Query、子问题分解
- step21-22 UserMemoryStore + MemoryCommitAgent

运行：
    python3 learn_agent/step23_integrated_pv2_mini.py

对应 pv2：
- text2sql_pv2_mem/text2sql/graph.py
- text2sql_pv2_mem/text2sql/rag_engine.py
- text2sql_pv2_mem/text2sql/user_memory.py
- text2sql_pv2_mem/text2sql/memory_commit_agent.py
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict


@dataclass
class Settings:
    max_sql_retries: int = 2
    rag_enabled: bool = True
    rag_router_year_threshold: int = 2026
    rag_multi_query_enabled: bool = True
    rag_decomposition_enabled: bool = True
    memory_auto_commit_enabled: bool = True


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
        self.conn.execute("CREATE TABLE orders (customer TEXT, total_amount REAL, year INTEGER)")
        self.conn.executemany(
            "INSERT INTO orders VALUES (?, ?, ?)",
            [("云杉科技", 9800, 2025), ("北辰零售", 5200, 2025)],
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
        return "表 orders:\n  - customer (TEXT)\n  - total_amount (REAL)\n  - year (INTEGER)"


class Text2sqlAgent:
    def generate(
        self,
        *,
        messages: list[Message],
        schema_text: str,
        previous_sql: str = "",
        last_error: str | None = None,
        memory_context: str = "",
    ) -> str:
        if last_error:
            return "SELECT customer, total_amount FROM orders ORDER BY total_amount DESC LIMIT 1"
        return "SELECT customer, amount FROM orders ORDER BY amount DESC LIMIT 1"


class AnalyzerAgent:
    def analyze(
        self,
        *,
        user_question: str,
        sql: str,
        columns: list[str],
        rows: list[tuple[Any, ...]],
        memory_context: str = "",
    ) -> str:
        pref = "（已按你的偏好：先给结论，再列依据）\n" if "先给结论" in memory_context else ""
        return f"{pref}## 结论\n返回 {len(rows)} 行：{rows}\n\n## 依据\nSQL：`{sql}`\n列：{columns}"


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
            Document("2027 年渠道增长优先区域代理分层和重点客户联合拜访。", {"source": "strategy.txt"}),
            Document("低毛利订单要核对折扣权限，并评估履约成本和退货风险。", {"source": "quality.txt"}),
            Document("新品组合优先进入华东和华南重点客户。", {"source": "product.txt"}),
        ]

    def route(self, question: str) -> str:
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", question)]
        if years and max(years) >= self.settings.rag_router_year_threshold:
            return "kb"
        if any(w in question for w in ["策略", "规划", "低毛利", "新品"]):
            return "kb"
        return "sql"

    def _queries(self, question: str) -> list[str]:
        if not self.settings.rag_multi_query_enabled:
            return [question]
        extras = []
        if "低毛利" in question:
            extras.append("订单质量 折扣权限 履约成本")
        if "渠道" in question:
            extras.append("渠道增长 区域代理 重点客户")
        return list(dict.fromkeys([question, *extras]))

    def _decompose(self, question: str) -> list[str]:
        if not self.settings.rag_decomposition_enabled:
            return [question]
        if "以及" in question or "和" in question:
            return ["2027 年渠道增长策略是什么？", "低毛利订单怎么处理？"]
        return [question]

    def _score(self, query: str, doc: Document) -> int:
        return sum(1 for ch in set(query) if ch in doc.page_content)

    def ask(self, question: str, *, memory_context: str = "") -> RagResult:
        subs = self._decompose(question)
        all_queries: list[str] = []
        chosen: list[Document] = []
        answer_lines: list[str] = []
        for sub in subs:
            queries = self._queries(sub)
            all_queries.extend(queries)
            ranked = sorted(self.docs, key=lambda d: max(self._score(q, d) for q in queries), reverse=True)
            top = ranked[0]
            chosen.append(top)
            answer_lines.append(f"- {sub} {top.page_content}")
        if "先给结论" in memory_context:
            answer_lines.insert(0, "结论先行：下面按你的偏好先汇总关键处理建议。")
        return RagResult("\n".join(answer_lines), chosen, all_queries, subs)


@dataclass
class MemoryHit:
    layer: str
    content: str
    tags: list[str]


class UserMemoryStore:
    def __init__(self) -> None:
        self.memory_md = "- 用户希望数据报告先给结论，再列依据。"
        self.items: list[MemoryHit] = [
            MemoryHit("L2", "用户偏好先给结论，再给依据。", ["habit", "report"])
        ]

    def build_prompt_block(self, query: str) -> str:
        lines = ["### MEMORY.md（用户长期设定）", self.memory_md]
        for item in self.items:
            lines.append(f"- [{item.layer}] {item.content}（tags={','.join(item.tags)}）")
        return "\n".join(lines)

    def upsert_vector_memory(self, *, layer: str, content: str, tags: list[str]) -> str:
        self.items.append(MemoryHit(layer, content, tags))
        return f"mem_{len(self.items)}"


class MemoryCommitAgent:
    def propose_items(self, *, user_text: str, assistant_text: str, route: str, sql_excerpt: str = "") -> list[dict[str, Any]]:
        if "以后" in user_text and "先给结论" in user_text:
            return [{"layer": "L2", "content": "用户希望以后回答先给结论。", "tags": ["habit"]}]
        return []


class GraphState(TypedDict):
    messages: list[Message]
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


class MiniPv2Graph:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.qe = QueryExecutor()
        self.text2sql = Text2sqlAgent()
        self.analyzer = AnalyzerAgent()
        self.rag = MiniRagEngine(settings)
        self.memory_store = UserMemoryStore()
        self.committer = MemoryCommitAgent()

    def invoke(self, state: GraphState) -> GraphState:
        uq = last_user_text(state["messages"])
        state["memory_context"] = self.memory_store.build_prompt_block(uq)
        state["route"] = self.rag.route(uq)

        if state["route"] == "kb":
            result = self.rag.ask(uq, memory_context=state["memory_context"])
            state["analysis"] = result.answer
            state["rag_context"] = [str(d.metadata.get("source")) for d in result.contexts]
            state["rag_retrieval_queries"] = result.retrieval_queries
            state["rag_sub_questions"] = result.sub_questions
            state["messages"].append(Message("assistant", result.answer))
        else:
            while True:
                state["sql"] = self.text2sql.generate(
                    messages=state["messages"],
                    schema_text=state["schema_text"],
                    previous_sql=state["sql"],
                    last_error=state["error"],
                    memory_context=state["memory_context"],
                )
                res = self.qe.execute(state["sql"])
                state["columns"], state["rows"], state["error"] = res.columns, res.rows, res.error
                if not state["error"]:
                    state["analysis"] = self.analyzer.analyze(
                        user_question=uq,
                        sql=state["sql"],
                        columns=state["columns"],
                        rows=state["rows"],
                        memory_context=state["memory_context"],
                    )
                    state["messages"].append(Message("assistant", state["analysis"]))
                    break
                if state["retry_count"] >= self.settings.max_sql_retries:
                    state["analysis"] = f"SQL 失败：{state['error']}"
                    break
                state["retry_count"] += 1

        writes: list[dict[str, Any]] = []
        if self.settings.memory_auto_commit_enabled:
            for item in self.committer.propose_items(
                user_text=uq,
                assistant_text=state["analysis"],
                route=state["route"],
                sql_excerpt=state["sql"],
            ):
                memory_id = self.memory_store.upsert_vector_memory(
                    layer=item["layer"], content=item["content"], tags=item["tags"]
                )
                writes.append({"memory_id": memory_id, **item})
        state["memory_writes"] = writes
        return state


class Chatbot:
    def __init__(self) -> None:
        self.graph = MiniPv2Graph(Settings())
        self.schema_text = self.graph.qe.fetch_schema_digest()
        self.messages: list[Message] = []

    def chat(self, text: str) -> GraphState:
        self.messages.append(Message("user", text))
        state: GraphState = {
            "messages": self.messages.copy(),
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
        self.messages = out["messages"]
        return out


def main() -> None:
    bot = Chatbot()
    for q in [
        "订单总额最高的客户是谁？",
        "2027 年渠道增长策略以及低毛利订单怎么处理？",
        "订单总额最高的客户是谁？以后回答先给结论，好吗？",
    ]:
        print("\n用户：", q)
        out = bot.chat(q)
        print("route:", out["route"])
        if out["sql"]:
            print("sql:", out["sql"], "retry:", out["retry_count"])
        if out["rag_retrieval_queries"]:
            print("retrieval_queries:", out["rag_retrieval_queries"])
        if out["memory_writes"]:
            print("memory_writes:", json.dumps(out["memory_writes"], ensure_ascii=False))
        print(out["analysis"])


if __name__ == "__main__":
    main()
