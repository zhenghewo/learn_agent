"""
Step 08 - 动态 Schema 概念

新增概念：
- 从数据库读取表结构
- 生成 schema digest 文本
- table_filter：只暴露指定表

运行：
    python3 learn_agent/step08_schema_digest_concept.py

对应 pv0：
- QueryExecutor.fetch_schema_digest()
"""

import sqlite3


def create_demo_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE movies (title TEXT, rating REAL)")
    conn.execute("CREATE TABLE books (title TEXT, stock_count INTEGER)")
    return conn


def fetch_schema_digest(conn: sqlite3.Connection, table_filter: list[str] | None = None) -> str:
    tables = [
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    ]
    if table_filter:
        tables = [t for t in tables if t in table_filter]

    lines: list[str] = []
    for table in tables:
        lines.append(f"表 {table}:")
        for col in conn.execute(f"PRAGMA table_info({table})"):
            lines.append(f"  - {col[1]} ({col[2]})")
    return "\n".join(lines)


def main() -> None:
    conn = create_demo_db()
    print("全部 schema:")
    print(fetch_schema_digest(conn))
    print("\n只看 books:")
    print(fetch_schema_digest(conn, ["books"]))


if __name__ == "__main__":
    main()
