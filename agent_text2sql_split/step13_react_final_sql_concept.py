"""
Step 13 - ReAct Final SQL 概念

新增概念：
- ReAct 输出格式：Thought / Action / Observation / Final
- _extract_final_sql()：只把 Final: 后面的内容当最终 SQL
- max_react_steps：模型没给 Final 时，继续追问一轮

本 Step 只讲“如何让模型思考多轮但最终收口成 SQL”，不讲数据库执行。

运行：
    python3 learn_agent/step13_react_final_sql_concept.py

对应 pv1：
- text2sql_pv1_0425/text2sql/text2sql_agent.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Response:
    content: str


_SQL_BLOCK = re.compile(r"```(?:sql)?\s*([\s\S]*?)```", re.IGNORECASE)

_REACT_OBSERVATION = (
    "Observation（系统）：上一轮没有 Final:。"
    "请继续 ReAct；若已确定查询，下一轮必须输出 Final: <SQL>。"
)


def _extract_sql(text: str) -> str:
    """兼容旧模型：如果没有 Final，但有 ```sql```，就提取代码块。"""
    m = _SQL_BLOCK.search(text.strip())
    return m.group(1).strip() if m else text.strip()


def _extract_final_sql(text: str) -> str | None:
    """从最后一个 Final: 后面解析最终 SQL。"""
    lower = text.lower()
    idx = lower.rfind("final:")
    if idx == -1:
        return None
    sql = text[idx + len("final:") :].strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```\s*$", "", sql).strip()
    return sql or None


def _resolve_sql_output(text: str) -> str:
    """优先 Final:；没有 Final 时才降级兼容旧格式。"""
    return _extract_final_sql(text) or _extract_sql(text)


class MockReActModel:
    def invoke(self, messages: list[Message]) -> Response:
        all_text = "\n".join(m.content for m in messages)
        if "上一轮没有 Final" in all_text:
            return Response(
                "Thought: 已确认表和字段。\n"
                "Action: 构造只读查询。\n"
                "Observation: SQL 以 SELECT 开头。\n"
                "Final: SELECT customer_name, total_amount FROM orders "
                "ORDER BY total_amount DESC LIMIT 1"
            )
        return Response(
            "Thought: 用户想找销售额最高的客户。\n"
            "Action: 先识别 orders 表。\n"
            "Observation: 需要继续确认排序字段。"
        )


class Text2sqlAgent:
    def __init__(self, model: MockReActModel, *, max_react_steps: int = 3):
        self._llm = model
        self._max_react_steps = max(1, max_react_steps)

    def generate(self, *, messages: list[Message], schema_text: str) -> str:
        trail = [Message("system", f"根据 schema 生成 PostgreSQL SELECT:\n{schema_text}")]
        trail.extend(messages)

        last_raw = ""
        for step in range(self._max_react_steps):
            resp = self._llm.invoke(trail)
            last_raw = resp.content
            sql = _extract_final_sql(last_raw)
            if sql:
                return sql

            if step < self._max_react_steps - 1:
                trail.append(Message("assistant", last_raw))
                trail.append(Message("user", _REACT_OBSERVATION))

        return _resolve_sql_output(last_raw)


def main() -> None:
    agent = Text2sqlAgent(MockReActModel())
    sql = agent.generate(
        messages=[Message("user", "销售额最高的客户是谁？")],
        schema_text="表 orders: customer_name, total_amount",
    )
    print("最终 SQL:")
    print(sql)

    fallback = _resolve_sql_output("```sql\nSELECT * FROM orders LIMIT 3\n```")
    print("\n兼容旧格式:")
    print(fallback)


if __name__ == "__main__":
    main()
