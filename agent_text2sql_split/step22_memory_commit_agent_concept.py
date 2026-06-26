"""
Step 22 - MemoryCommitAgent 概念

新增概念：
- 自动归档：每轮结束后判断哪些内容值得写入长期记忆
- L1/L2 分层：事件写 L1，稳定偏好/规则写 L2
- normalize_commit_items()：过滤非法 JSON、层级、空内容、过多条目

本 Step 只讲“如何决定写什么记忆”，不讲向量库写入。

运行：
    python3 learn_agent/step22_memory_commit_agent_concept.py

对应 pv2：
- text2sql_pv2_mem/text2sql/memory_commit_agent.py
- text2sql_pv2_mem/text2sql/graph.py 的 commit_memory()
"""

from __future__ import annotations

import json
import re
from typing import Any


_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def parse_json_blob(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if m := _JSON_FENCE.search(text):
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def normalize_commit_items(data: dict[str, Any] | None, *, max_items: int) -> list[dict[str, Any]]:
    if max_items <= 0 or not data or not isinstance(data.get("items"), list):
        return []

    out: list[dict[str, Any]] = []
    for item in data["items"]:
        if not isinstance(item, dict):
            continue
        layer = str(item.get("layer", "")).upper()
        if layer not in ("L1", "L2"):
            continue
        content = str(item.get("content", "")).strip()
        if len(content) < 4:
            continue
        tags_raw = item.get("tags") or ["general"]
        tags = [str(t).strip().lower() for t in tags_raw if str(t).strip()][:5]
        out.append(
            {
                "layer": layer,
                "content": content[:2000],
                "tags": tags or ["general"],
                "event_time": item.get("event_time"),
            }
        )
        if len(out) >= max_items:
            break
    return out


class MockCommitModel:
    def invoke(self, user_text: str, assistant_text: str) -> str:
        if "以后" in user_text and "先给结论" in user_text:
            return json.dumps(
                {
                    "items": [
                        {
                            "layer": "L2",
                            "content": "用户希望数据分析报告以后先给结论，再展开依据。",
                            "tags": ["habit", "report"],
                        }
                    ]
                },
                ensure_ascii=False,
            )
        return '{"items":[]}'


class MemoryCommitAgent:
    def __init__(self, model: MockCommitModel, *, max_items: int = 3):
        self.model = model
        self.max_items = max_items

    def propose_items(self, *, user_text: str, assistant_text: str) -> list[dict[str, Any]]:
        raw = self.model.invoke(user_text, assistant_text)
        return normalize_commit_items(parse_json_blob(raw), max_items=self.max_items)


def main() -> None:
    agent = MemoryCommitAgent(MockCommitModel())
    items = agent.propose_items(
        user_text="以后帮我做数据分析时，先给结论，再给依据。",
        assistant_text="好的，我会按这个结构组织报告。",
    )
    print(json.dumps(items, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
