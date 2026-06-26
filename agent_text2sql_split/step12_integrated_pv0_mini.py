"""
Step 12 - 最终整合：Mini pv0

新增概念：
- 把前面分散学习的概念组合成一个最小 pv0
- 组合内容：
  Settings + LLM Client + Text2sqlAgent + QueryExecutor
  + Schema Digest + Retry Graph + Chatbot + Analyzer Report + Skill

运行：
    python3 learn_agent/step12_integrated_pv0_mini.py

对应 pv0：
- config.py
- llm_client.py
- text2sql_agent.py
- query_executor.py
- graph.py
- chatbot.py
- analyzer_agent.py
- skill_runtime.py
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, TypedDict


# 1. Settings
@dataclass
class Settings:
    max_sql_retries: int = 3
    report_dir: str = "learn_agent/outputs/final_reports"


# 2. Message / Mock LLM
@dataclass
class Message:
    role: str
    content: str


@dataclass
class Response:
    content: str


class MockChatModel:
    def invoke(self, messages: list[Message]) -> Response:
        all_text = "\n".join(m.content for m in messages)
        question = next((m.content for m in reversed(messages) if m.role == "user"), "")

        if "修正" in question and "stock" in all_text:
            return Response("Final: SELECT title, author, stock_count FROM books ORDER BY stock_count DESC LIMIT 1")

        if "库存" in question:
            # 第一轮故意错，用来演示 retry
            return Response("Final: SELECT title, stock FROM books ORDER BY stock DESC LIMIT 1")

        if "评分最高" in question or "最高" in question:
            return Response("Final: SELECT title, director, rating FROM movies ORDER BY rating DESC LIMIT 1")

        return Response("Final: SELECT title, director, rating FROM movies LIMIT 5")


def build_chat_model() -> MockChatModel:
    return MockChatModel()


# 3. Text2sqlAgent
def extract_final_sql(text: str) -> str:
    m = re.search(r"final:\s*([\s\S]+)$", text, re.IGNORECASE)
    return m.group(1).strip() if m else text.strip()


class Text2sqlAgent:
    def __init__(self):
        self.llm = build_chat_model()

    def generate(
        self,
        *,
        messages: list[Message],
        schema_text: str,
        previous_sql: str = "",
        last_error: str | None = None,
    ) -> str:
        trail = [Message("system", f"根据 schema 生成 SQL:\n{schema_text}"), *messages]
        if last_error:
            trail.append(
                Message(
                    "user",
                    f"修正 SQL。上次 SQL：{previous_sql}\n错误：{last_error}",
                )
            )
        return extract_final_sql(self.llm.invoke(trail).content)


# 4. QueryExecutor
@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    error: str | None = None


def assert_read_only_sql(sql: str) -> None:
    if not re.search(r"^\s*select\b", sql.strip(), re.IGNORECASE):
        raise ValueError("只允许 SELECT")


class QueryExecutor:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE movies (title TEXT, director TEXT, rating REAL)")
        self.conn.execute("CREATE TABLE books (title TEXT, author TEXT, stock_count INTEGER)")
        self.conn.executemany(
            "INSERT INTO movies VALUES (?, ?, ?)",
            [
                ("星际穿越", "克里斯托弗·诺兰", 9.4),
                ("教父", "弗朗西斯·福特·科波拉", 9.3),
            ],
        )
        self.conn.executemany(
            "INSERT INTO books VALUES (?, ?, ?)",
            [
                ("三体", "刘慈欣", 100),
                ("银河系漫游指南", "道格拉斯·亚当斯", 50),
            ],
        )
        self.conn.commit()

    def execute(self, sql: str) -> QueryResult:
        try:
            assert_read_only_sql(sql)
            cur = self.conn.execute(sql)
            return QueryResult([d[0] for d in cur.description], cur.fetchall())
        except Exception as e:
            return QueryResult([], [], str(e))

    def fetch_schema_digest(self) -> str:
        lines = []
        for (table,) in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            lines.append(f"表 {table}:")
            for col in self.conn.execute(f"PRAGMA table_info({table})"):
                lines.append(f"  - {col[1]} ({col[2]})")
        return "\n".join(lines)


# 5. Analyzer + Skill
@dataclass
class SkillTool:
    intent: str
    name: str
    triggers: list[str]
    run: Callable[[dict[str, Any]], dict[str, Any]]


def export_report(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["report_dir"]) / "latest_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload["report_text"], encoding="utf-8")
    return {"ok": True, "artifact_path": str(path)}


class AnalyzerAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.tools = [
            SkillTool("report", "export_report", ["导出报告", "保存报告"], export_report)
        ]

    def analyze(self, *, question: str, sql: str, result: QueryResult) -> str:
        text = (
            f"## 结论\n\n返回 {len(result.rows)} 行。\n\n"
            f"- SQL：`{sql}`\n"
            f"- 列：{result.columns}\n"
            f"- 数据：{result.rows}\n"
        )

        for tool in self.tools:
            if any(t in question for t in tool.triggers):
                r = tool.run({"report_text": text, "report_dir": self.settings.report_dir})
                text += f"\n## 导出\n\n- {tool.name}: {r['artifact_path']}\n"
        return text


# 6. Graph
class GraphState(TypedDict):
    messages: list[Message]
    schema_text: str
    sql: str
    columns: list[str]
    rows: list[tuple[Any, ...]]
    error: str | None
    retry_count: int
    analysis: str


def last_user_text(messages: list[Message]) -> str:
    return next((m.content for m in reversed(messages) if m.role == "user"), "")


class MiniGraph:
    def __init__(self, settings: Settings, executor: QueryExecutor):
        self.settings = settings
        self.executor = executor
        self.text2sql = Text2sqlAgent()
        self.analyzer = AnalyzerAgent(settings)

    def route(self, state: GraphState) -> Literal["retry", "analyze", "fail"]:
        if not state["error"]:
            return "analyze"
        if state["retry_count"] < self.settings.max_sql_retries:
            return "retry"
        return "fail"

    def invoke(self, state: GraphState) -> GraphState:
        while True:
            state["sql"] = self.text2sql.generate(
                messages=state["messages"],
                schema_text=state["schema_text"],
                previous_sql=state["sql"],
                last_error=state["error"],
            )
            result = self.executor.execute(state["sql"])
            state["columns"], state["rows"], state["error"] = (
                result.columns,
                result.rows,
                result.error,
            )

            route = self.route(state)
            if route == "retry":
                state["retry_count"] += 1
                continue

            if route == "fail":
                state["analysis"] = f"失败：{state['error']}\nSQL：{state['sql']}"
                return state

            state["analysis"] = self.analyzer.analyze(
                question=last_user_text(state["messages"]),
                sql=state["sql"],
                result=result,
            )
            state["messages"].append(Message("assistant", state["analysis"]))
            return state


# 7. Chatbot
class Chatbot:
    def __init__(self):
        self.settings = Settings()
        self.executor = QueryExecutor()
        self.schema_text = self.executor.fetch_schema_digest()
        self.graph = MiniGraph(self.settings, self.executor)
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
        }
        out = self.graph.invoke(state)
        self.messages = out["messages"]
        return out


def main() -> None:
    bot = Chatbot()
    for q in ["评分最高的电影是哪部？", "库存最多的书是哪本？请导出报告"]:
        print("\n用户：", q)
        out = bot.chat(q)
        print("SQL：", out["sql"])
        print(out["analysis"])


if __name__ == "__main__":
    main()
