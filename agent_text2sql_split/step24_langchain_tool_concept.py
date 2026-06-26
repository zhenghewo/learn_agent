"""
Step 24 - LangChain Tool 本地工具概念

新增概念：
- tool：把普通函数包装成可被 Agent/编排器调用的工具
- web_search / local_data_analysis：pv3 默认注册的两个本地工具
- 参数校验：工具入口要把空 query、非法 JSON 等错误转成可读文本

本 Step 不依赖 langchain_core，使用小 dataclass 模拟 @tool 的核心形态。

运行：
    python3 learn_agent/step24_langchain_tool_concept.py

对应 pv3：
- text2sql_pv3_tools/text2sql/tool_runtime/local_tools.py
- text2sql_pv3_tools/text2sql/tool_runtime/data_analysis.py
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class SimpleTool:
    name: str
    description: str
    func: Callable[..., str]

    def invoke(self, arguments: dict[str, Any]) -> str:
        return self.func(**arguments)


def simple_tool(func: Callable[..., str]) -> SimpleTool:
    return SimpleTool(
        name=func.__name__,
        description=(func.__doc__ or "").strip(),
        func=func,
    )


@simple_tool
def web_search(query: str, max_results: int = 5) -> str:
    """执行联网搜索并返回整理后的文本结果。"""
    if not query.strip():
        return "错误：query 不能为空"
    limit = max(1, min(int(max_results), 10))
    demo_results = [
        ("订单质量白皮书", "低毛利订单需要复核折扣权限。"),
        ("渠道策略简报", "区域代理分层能提升重点客户覆盖。"),
    ]
    lines = []
    for i, (title, body) in enumerate(demo_results[:limit], 1):
        lines.append(f"{i}. {title}\n   {body}\n   https://example.com/{i}")
    return "\n\n".join(lines)


def run_table_analysis(data_json: str, question: str = "") -> str:
    payload = json.loads(data_json)
    columns = [str(c) for c in payload.get("columns", [])]
    rows = payload.get("rows", [])
    numeric: dict[str, list[float]] = {}
    for idx, col in enumerate(columns):
        nums = [float(r[idx]) for r in rows if isinstance(r, list) and idx < len(r) and isinstance(r[idx], (int, float))]
        if nums:
            numeric[col] = nums

    parts = ["## 数据分析报告", f"- 行数：{len(rows)}", f"- 分析要求：{question or '无'}"]
    for col, nums in numeric.items():
        parts.append(f"- {col}: min={min(nums):.2f}, max={max(nums):.2f}, mean={statistics.fmean(nums):.2f}")
    return "\n".join(parts)


@simple_tool
def local_data_analysis(data_json: str, question: str = "") -> str:
    """对 JSON 表格做本地统计分析。data_json 格式：{"columns":["col"],"rows":[[1]]}。"""
    try:
        return run_table_analysis(data_json, question)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return f"错误：{e}"


def main() -> None:
    tools = [web_search, local_data_analysis]
    for t in tools:
        print(f"{t.name}: {t.description}")

    print("\n搜索工具输出:")
    print(web_search.invoke({"query": "低毛利订单", "max_results": 2}))

    print("\n本地分析工具输出:")
    print(
        local_data_analysis.invoke(
            {
                "data_json": json.dumps({"columns": ["revenue"], "rows": [[100], [180], [220]]}),
                "question": "看一下收入范围",
            }
        )
    )


if __name__ == "__main__":
    main()
