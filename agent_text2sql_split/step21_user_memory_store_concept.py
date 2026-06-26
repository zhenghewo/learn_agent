"""
Step 21 - UserMemoryStore 概念

新增概念：
- MEMORY.md：长期自述/稳定设定
- L1 情景记忆：用户发生过的具体事件
- L2 程序性记忆：用户稳定偏好、习惯、规则
- build_prompt_block()：把检索到的记忆拼成给模型看的上下文块

本 Step 用内存列表模拟向量检索，不依赖 Chroma/MemPalace。

运行：
    python3 learn_agent/step21_user_memory_store_concept.py

对应 pv2：
- text2sql_pv2_mem/text2sql/user_memory.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


Layer = str


@dataclass
class MemoryHit:
    memory_id: str
    user_id: str
    layer: Layer
    content: str
    time: str
    tags: list[str] = field(default_factory=list)
    similarity: float | None = None


def lexical_similarity(query: str, text: str) -> float:
    q = set(re.findall(r"[\u4e00-\u9fff]|\w+", query.lower()))
    t = set(re.findall(r"[\u4e00-\u9fff]|\w+", text.lower()))
    return len(q & t) / max(1, len(q | t))


class UserMemoryStore:
    def __init__(self, *, user_id: str, memory_md_path: Path):
        self.user_id = user_id
        self.memory_md_path = memory_md_path
        self._items: list[MemoryHit] = []

    def read_memory_md(self) -> str:
        if not self.memory_md_path.exists():
            return ""
        return self.memory_md_path.read_text(encoding="utf-8").strip()

    def upsert_vector_memory(
        self,
        *,
        layer: Layer,
        content: str,
        tags: list[str],
        memory_id: str,
    ) -> str:
        now = datetime.now().isoformat(timespec="seconds")
        self._items = [m for m in self._items if m.memory_id != memory_id]
        self._items.append(MemoryHit(memory_id, self.user_id, layer, content, now, tags))
        return memory_id

    def search_vector_memories(self, query: str, *, layer: Layer, n_results: int) -> list[MemoryHit]:
        hits = [m for m in self._items if m.layer == layer]
        ranked: list[MemoryHit] = []
        for h in hits:
            ranked.append(
                MemoryHit(
                    h.memory_id,
                    h.user_id,
                    h.layer,
                    h.content,
                    h.time,
                    h.tags,
                    lexical_similarity(query, h.content),
                )
            )
        ranked.sort(key=lambda h: h.similarity or 0.0, reverse=True)
        return ranked[:n_results]

    def build_prompt_block(self, query: str, *, l1_k: int = 2, l2_k: int = 2) -> str:
        parts: list[str] = []
        md = self.read_memory_md()
        if md:
            parts.append("### MEMORY.md（用户长期设定）\n" + md)

        for layer, title, k in [
            ("L1", "### L1 情景记忆（检索）", l1_k),
            ("L2", "### L2 程序性记忆（检索）", l2_k),
        ]:
            hits = self.search_vector_memories(query, layer=layer, n_results=k)
            if hits:
                lines = [
                    f"- [{h.layer}] {h.content}（tags={','.join(h.tags)}, sim={h.similarity:.3f}）"
                    for h in hits
                ]
                parts.append(title + "\n" + "\n".join(lines))

        if not parts:
            return ""
        return "以下为辅助记忆；数据类问题仍以数据库和知识库证据为准。\n\n" + "\n\n".join(parts)


def main() -> None:
    md = Path("learn_agent/outputs/step21_MEMORY.md")
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("- 用户希望数据报告先给结论，再列依据。", encoding="utf-8")

    store = UserMemoryStore(user_id="u1", memory_md_path=md)
    store.upsert_vector_memory(
        layer="L1",
        content="用户在上周复盘过低毛利订单，重点关注折扣权限。",
        tags=["work", "order"],
        memory_id="mem_l1",
    )
    store.upsert_vector_memory(
        layer="L2",
        content="用户偏好先看汇总结论，再看明细表。",
        tags=["habit", "report"],
        memory_id="mem_l2",
    )

    print(store.build_prompt_block("低毛利订单报告怎么写？"))


if __name__ == "__main__":
    main()
