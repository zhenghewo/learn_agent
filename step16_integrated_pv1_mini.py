"""
Step 16 - pv1 整合版：Mini Text2SQL pv1

整合概念：
- step13 ReAct + Final SQL 收口
- step14 PostgreSQL 风格 schema digest 与表白名单
- step15 Skill 子进程导出
- step12 已掌握的 Settings / QueryExecutor / Retry Graph / Analyzer / Chatbot

运行：
    python3 learn_agent/step16_integrated_pv1_mini.py

对应 pv1：
- text2sql_pv1_0425/text2sql/config.py
- text2sql_pv1_0425/text2sql/text2sql_agent.py
- text2sql_pv1_0425/text2sql/query_executor.py
- text2sql_pv1_0425/text2sql/graph.py
- text2sql_pv1_0425/text2sql/analyzer_agent.py
- text2sql_pv1_0425/text2sql/skill_runtime.py
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict


@dataclass
class Settings:
    max_sql_retries: int = 3
    schema_allow_tables: str = "customers,orders"
    report_dir: str = "learn_agent/outputs/pv1_reports"


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Response:
    content: str


def extract_final_sql(text: str) -> str | None:
    idx = text.lower().rfind("final:")
    if idx == -1:
        return None
    sql = text[idx + len("final:") :].strip()
    return sql or None


class MockPv1Model:
    """模拟 pv1 的 ReAct 模型：先思考，必要时根据错误修正 SQL。"""

    def invoke(self, messages: list[Message]) -> Response:
        all_text = "\n".join(m.content for m in messages)
        if "no such column" in all_text and "amount" in all_text:
            return Response(
                "Thought: amount 字段不存在，应改用 schema 里的 total_amount。\n"
                "Action: 修正字段名。\n"
                "Observation: SELECT 只读。\n"
                "Final: SELECT c.customer_name, SUM(o.total_amount) AS revenue "
                "FROM orders o JOIN customers c ON c.customer_id = o.customer_id "
                "GROUP BY c.customer_name ORDER BY revenue DESC LIMIT 1"
            )
        if "上一轮没有 Final" in all_text:
            return Response(
                "Thought: 需要 customers 和 orders join。\n"
                "Action: 生成聚合 SQL，但字段名先写错以演示自愈。\n"
                "Observation: 等待执行器验证。\n"
                "Final: SELECT c.customer_name, SUM(o.amount) AS revenue "
                "FROM orders o JOIN customers c ON c.customer_id = o.customer_id "
                "GROUP BY c.customer_name ORDER BY revenue DESC LIMIT 1"
            )
        return Response(
            "Thought: 用户要找销售额最高的客户。\n"
            "Action: 识别 customers/orders 表。\n"
            "Observation: 还没有输出最终 SQL。"
        )


class Text2sqlAgent:
    def __init__(self, model: MockPv1Model, *, max_react_steps: int = 3):
        self._llm = model
        self._max_react_steps = max_react_steps

    def generate(
        self,
        *,
        messages: list[Message],
        schema_text: str,
        previous_sql: str = "",
        last_error: str | None = None,
    ) -> str:
        trail = [Message("system", f"根据 schema 生成 PostgreSQL SELECT:\n{schema_text}")]
        trail.extend(messages)
        if last_error:
            trail.append(
                Message(
                    "user",
                    f"上一次 SQL 执行失败。\n错误信息：{last_error}\n上次 SQL：{previous_sql}",
                )
            )

        last_raw = ""
        for step in range(self._max_react_steps):
            last_raw = self._llm.invoke(trail).content
            if sql := extract_final_sql(last_raw):
                return sql
            if step < self._max_react_steps - 1:
                trail.append(Message("assistant", last_raw))
                trail.append(Message("user", "Observation（系统）：上一轮没有 Final:，请继续。"))
        return last_raw.strip()


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    error: str | None = None


def assert_read_only_sql(sql: str) -> None:
    if not re.search(r"^\s*select\b", sql.strip(), re.IGNORECASE):
        raise ValueError("仅允许 SELECT")
    if ";" in sql.rstrip(";").strip():
        raise ValueError("不允许多语句")


class QueryExecutor:
    def __init__(self, settings: Settings):
        self._settings = settings
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE customers (customer_id INTEGER, customer_name TEXT, region TEXT)")
        self.conn.execute(
            "CREATE TABLE orders (order_id INTEGER, customer_id INTEGER, total_amount REAL, order_date TEXT)"
        )
        self.conn.executemany(
            "INSERT INTO customers VALUES (?, ?, ?)",
            [(1, "云杉科技", "华东"), (2, "北辰零售", "华北")],
        )
        self.conn.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?)",
            [(101, 1, 9800.0, "2026-04-01"), (102, 2, 5200.0, "2026-04-02")],
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
        allowed = {t.strip() for t in self._settings.schema_allow_tables.split(",") if t.strip()}
        lines: list[str] = []
        for (table,) in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            if allowed and table not in allowed:
                continue
            lines.append(f"\n表 {table}:")
            for col in self.conn.execute(f"PRAGMA table_info({table})"):
                lines.append(f"  - {col[1]} ({col[2]})")
        return "\n".join(lines).strip()


@dataclass(frozen=True)
class SkillToolSpec:
    intent: str
    script_path: Path
    triggers: tuple[str, ...]


def ensure_export_skill() -> SkillToolSpec:
    script = Path("learn_agent/outputs/pv1_skill/export_markdown.py")
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        """
import json
import sys
from pathlib import Path

payload = json.loads(sys.stdin.read())
out = Path(payload["report_dir"]) / "latest_pv1_report.md"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(payload["report_text"], encoding="utf-8")
print(json.dumps({"message": "导出完成", "artifact_path": str(out)}, ensure_ascii=False))
""".strip(),
        encoding="utf-8",
    )
    return SkillToolSpec("markdown", script.resolve(), ("导出", "保存", "markdown"))


class AnalyzerAgent:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._skill = ensure_export_skill()

    def analyze(self, *, question: str, sql: str, result: QueryResult) -> str:
        report = (
            "## 结论\n\n"
            f"查询返回 {len(result.rows)} 行，结果为：{result.rows}\n\n"
            f"- SQL：`{sql}`\n"
            f"- 列：{result.columns}\n"
        )
        if any(t in question for t in self._skill.triggers):
            proc = subprocess.run(
                [sys.executable, str(self._skill.script_path)],
                input=json.dumps(
                    {"report_text": report, "report_dir": self._settings.report_dir},
                    ensure_ascii=False,
                ),
                text=True,
                capture_output=True,
                check=False,
            )
            data = json.loads(proc.stdout)
            report += f"\n## 导出\n\n- {data['message']}：`{data['artifact_path']}`\n"
        return report


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


class MiniPv1Graph:
    def __init__(self, settings: Settings, executor: QueryExecutor):
        self._settings = settings
        self._executor = executor
        self._text2sql = Text2sqlAgent(MockPv1Model())
        self._analyzer = AnalyzerAgent(settings)

    def route_after_execute(self, state: GraphState) -> Literal["retry", "analyze", "fail"]:
        if not state["error"]:
            return "analyze"
        if state["retry_count"] < self._settings.max_sql_retries:
            return "retry"
        return "fail"

    def invoke(self, state: GraphState) -> GraphState:
        while True:
            state["sql"] = self._text2sql.generate(
                messages=state["messages"],
                schema_text=state["schema_text"],
                previous_sql=state["sql"],
                last_error=state["error"],
            )
            result = self._executor.execute(state["sql"])
            state["columns"], state["rows"], state["error"] = result.columns, result.rows, result.error

            route = self.route_after_execute(state)
            if route == "retry":
                state["retry_count"] += 1
                continue
            if route == "fail":
                state["analysis"] = f"失败：{state['error']}\nSQL：{state['sql']}"
                return state
            state["analysis"] = self._analyzer.analyze(
                question=last_user_text(state["messages"]),
                sql=state["sql"],
                result=result,
            )
            state["messages"].append(Message("assistant", state["analysis"]))
            return state


class Chatbot:
    def __init__(self) -> None:
        self.settings = Settings()
        self.executor = QueryExecutor(self.settings)
        self.schema_text = self.executor.fetch_schema_digest()
        self.graph = MiniPv1Graph(self.settings, self.executor)
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
    print("Schema digest:")
    print(bot.schema_text)

    out = bot.chat("销售额最高的客户是谁？请导出报告")
    print("\n最终 SQL:")
    print(out["sql"])
    print("\n分析:")
    print(out["analysis"])
    print("retry_count =", out["retry_count"])


if __name__ == "__main__":
    main()
