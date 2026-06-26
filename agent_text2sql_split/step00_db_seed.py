"""
Step 00 - 基础数据库

新增概念：
- sqlite3.connect(":memory:")：创建内存临时数据库
- CREATE TABLE：创建表
- INSERT：插入演示数据
- SELECT：查询数据

运行：
    python3 learn_agent/step00_db_seed.py

对应 pv0：
- pg_init/、测试数据
"""

import sqlite3


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


def main() -> None:
    conn = create_demo_db()
    rows = conn.execute(
        "SELECT title, director, rating FROM movies ORDER BY rating DESC"
    ).fetchall()
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
