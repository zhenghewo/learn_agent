"""
Step 04 - QueryExecutor 概念

新增概念：
- QueryExecutor：专门执行 SQL
- QueryResult：结构化返回 columns / rows / error
- 本 Step 组合了 Step00 的数据库 + Step03 的安全检查

运行：
    python3 learn_agent/step04_query_executor_concept.py

对应 pv0：
- text2sql/query_executor.py
"""

from dataclasses import dataclass
from typing import Any
import re
import sqlite3


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    error: str | None = None


def create_demo_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE movies (title TEXT, director TEXT, rating REAL)")
    conn.executemany(
        "INSERT INTO movies VALUES (?, ?, ?)",
        [
            ("星际穿越", "克里斯托弗·诺兰", 9.4),
            ("教父", "弗朗西斯·福特·科波拉", 9.3),
        ],
    )
    conn.commit()
    return conn


def assert_read_only_sql(sql: str) -> None:
    if not re.search(r"^\s*select\b", sql.strip(), re.IGNORECASE):
        raise ValueError("只允许 SELECT")


class QueryExecutor:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def execute(self, sql: str) -> QueryResult:
        try:
            assert_read_only_sql(sql)
            cur = self.conn.execute(sql)
            return QueryResult(
                columns=[d[0] for d in cur.description],
                rows=cur.fetchall(),
            )
        except Exception as e:
            return QueryResult(columns=[], rows=[], error=str(e))


def main() -> None:
    executor = QueryExecutor(create_demo_db())
    result = executor.execute("SELECT title, rating FROM movies ORDER BY rating DESC")
    print(result)


if __name__ == "__main__":
    main()
