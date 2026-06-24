"""
Step 03 - SQL 安全检查概念

新增概念：
- 只允许 SELECT
- 拦截 DELETE / UPDATE / DROP 等危险 SQL
- 本 Step 只讲安全检查，不连接数据库

运行：
    python3 learn_agent/step03_sql_safety_concept.py

对应 pv0：
- text2sql/query_executor.py 里的 _assert_read_only_sql()
"""

import re


class UnsafeSQLError(ValueError):
    pass


SELECT_START = re.compile(r"^\s*select\b", re.IGNORECASE)
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|truncate|alter|create)\b",
    re.IGNORECASE,
)


def assert_read_only_sql(sql: str) -> None:
    sql = sql.strip()
    if not sql:
        raise UnsafeSQLError("SQL 为空")
    if not SELECT_START.search(sql):
        raise UnsafeSQLError("只允许 SELECT")
    if ";" in sql.rstrip(";").strip():
        raise UnsafeSQLError("不允许多语句")
    if FORBIDDEN.search(sql):
        raise UnsafeSQLError("包含危险关键字")


def main() -> None:
    examples = [
        "SELECT * FROM movies",
        "DELETE FROM movies",
        "SELECT * FROM movies; DROP TABLE movies",
    ]
    for sql in examples:
        try:
            assert_read_only_sql(sql)
            print("安全:", sql)
        except UnsafeSQLError as e:
            print("拦截:", sql, "原因:", e)


if __name__ == "__main__":
    main()
