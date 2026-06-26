"""
Step 19 - Multi-Query 检索概念

新增概念：
- 多查询改写：同一个问题生成多个检索表达
- 并行/合并检索：每个改写都召回候选，再按 chunk 去重
- 价值：提高召回率，尤其是用户词和文档词不一致时

本 Step 用本地函数模拟 LLM 改写和向量检索。

运行：
    python3 learn_agent/step19_multi_query_concept.py

对应 pv2：
- text2sql_pv2_mem/text2sql/rag_engine.py 的 _multi_query_variants()
- text2sql_pv2_mem/text2sql/rag_engine.py 的 _parallel_similarity_search()
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Document:
    page_content: str
    metadata: dict[str, object] = field(default_factory=dict)


class MockRewriteModel:
    def rewrite(self, question: str) -> list[str]:
        if "低毛利" in question:
            return ["低利润订单处理规则", "折扣权限 履约成本 订单质量", "毛利率异常订单复盘"]
        return [question]


def lexical_score(query: str, doc: str) -> float:
    q_tokens = set(re.findall(r"[\u4e00-\u9fff]|\w+", query.lower()))
    d_tokens = set(re.findall(r"[\u4e00-\u9fff]|\w+", doc.lower()))
    return len(q_tokens & d_tokens) / max(1, len(q_tokens | d_tokens))


def search_one(query: str, docs: list[Document], *, k: int = 2) -> list[Document]:
    return sorted(docs, key=lambda d: lexical_score(query, d.page_content), reverse=True)[:k]


def dedupe_documents(docs: list[Document]) -> list[Document]:
    seen: set[object] = set()
    out: list[Document] = []
    for d in docs:
        key = d.metadata.get("chunk_index", d.page_content)
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def multi_query_variants(question: str, model: MockRewriteModel) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for q in [question, *model.rewrite(question)]:
        key = q.strip().lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(q)
    return merged


def multi_query_search(question: str, docs: list[Document]) -> tuple[list[str], list[Document]]:
    queries = multi_query_variants(question, MockRewriteModel())
    all_hits: list[Document] = []
    for q in queries:
        all_hits.extend(search_one(q, docs, k=2))
    return queries, dedupe_documents(all_hits)


def main() -> None:
    docs = [
        Document("订单质量规则：折扣权限异常时必须复核。", {"chunk_index": 1}),
        Document("低利润订单应评估履约成本与退货风险。", {"chunk_index": 2}),
        Document("渠道增长策略优先覆盖华东代理商。", {"chunk_index": 3}),
    ]
    queries, hits = multi_query_search("低毛利订单怎么处理？", docs)

    print("检索问题（含改写）:")
    for q in queries:
        print("-", q)

    print("\n合并去重后的候选:")
    for h in hits:
        print(h.metadata["chunk_index"], h.page_content)


if __name__ == "__main__":
    main()
