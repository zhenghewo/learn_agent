"""
Step 14 - PostgreSQL Schema Digest 概念

新增概念：
- information_schema.columns：从 PostgreSQL 元数据里读取表和字段
- schema_allow_tables：只把允许的表暴露给模型
- schema digest：把真实 schema 压缩成 LLM 易读文本

本 Step 只讲 schema 摘要，不讲 SQL 生成和执行。

运行：
    python3 learn_agent/step14_postgres_schema_digest_concept.py

对应 pv1：
- text2sql_pv1_0425/text2sql/query_executor.py 的 fetch_schema_digest()
- text2sql_pv1_0425/text2sql/chatbot.py 的 refresh_schema()
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ColumnInfo:
    table_name: str
    column_name: str
    data_type: str


class MockPostgresCatalog:
    """用内存列表模拟 information_schema.columns。"""

    def __init__(self) -> None:
        self.columns = [
            ColumnInfo("customers", "customer_id", "integer"),
            ColumnInfo("customers", "customer_name", "text"),
            ColumnInfo("customers", "region", "text"),
            ColumnInfo("orders", "order_id", "integer"),
            ColumnInfo("orders", "customer_id", "integer"),
            ColumnInfo("orders", "total_amount", "numeric"),
            ColumnInfo("orders", "order_date", "date"),
            ColumnInfo("audit_log", "raw_payload", "jsonb"),
        ]

    def list_columns(self, table_filter: list[str] | None = None) -> list[ColumnInfo]:
        allowed = set(table_filter or [])
        rows = [c for c in self.columns if not allowed or c.table_name in allowed]
        return sorted(rows, key=lambda c: (c.table_name, c.column_name))


def parse_allow_tables(value: str) -> list[str] | None:
    names = [item.strip() for item in value.split(",") if item.strip()]
    return names or None


def fetch_schema_digest(
    catalog: MockPostgresCatalog,
    *,
    schema_allow_tables: str = "",
) -> str:
    table_filter = parse_allow_tables(schema_allow_tables)
    rows = catalog.list_columns(table_filter=table_filter)
    if not rows:
        return "(public 下无表或无可读列)"

    lines: list[str] = []
    current_table = ""
    for col in rows:
        if col.table_name != current_table:
            current_table = col.table_name
            lines.append(f"\n表 {current_table}:")
        lines.append(f"  - {col.column_name} ({col.data_type})")
    return "\n".join(lines).strip()


def main() -> None:
    catalog = MockPostgresCatalog()

    print("全部 schema:")
    print(fetch_schema_digest(catalog))

    print("\n只暴露业务表:")
    print(fetch_schema_digest(catalog, schema_allow_tables="customers, orders"))


if __name__ == "__main__":
    main()
