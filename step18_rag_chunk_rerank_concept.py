"""
Step 18 - RAG Chunk + Rerank 概念

新增概念：
- chunk：把长文档切成适合向量检索的小片段
- similarity_search：先粗召回候选片段
- rerank：再按问题相关性重排，保留 top_n

本 Step 使用词法相似度模拟 embedding 和 reranker，不依赖 Chroma/API。

运行：
    python3 learn_agent/step18_rag_chunk_rerank_concept.py

对应 pv2：
- text2sql_pv2_mem/text2sql/rag_engine.py 的 split_text()/rerank_documents()
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Document:
    page_content: str
    metadata: dict[str, object] = field(default_factory=dict)


def split_sentences(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"(?<=[。！？!?；;.\n])\s*", text) if p.strip()]


def split_text(text: str, *, chunk_size: int = 80, overlap: int = 12) -> list[str]:
    """先切句，再打包成 chunk；overlap 用上个 chunk 的尾巴衔接上下文。"""
    chunks: list[str] = []
    current = ""
    for sent in split_sentences(text):
        candidate = f"{current}{sent}" if current else sent
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        tail = current[-overlap:] if overlap and current else ""
        current = f"{tail}{sent}"
    if current:
        chunks.append(current)
    return chunks


def lexical_score(query: str, doc: str) -> float:
    q_tokens = set(re.findall(r"[\u4e00-\u9fff]|\w+", query.lower()))
    d_tokens = set(re.findall(r"[\u4e00-\u9fff]|\w+", doc.lower()))
    if not q_tokens or not d_tokens:
        return 0.0
    return len(q_tokens & d_tokens) / len(q_tokens | d_tokens)


def similarity_search(query: str, docs: list[Document], *, k: int) -> list[Document]:
    ranked = sorted(docs, key=lambda d: lexical_score(query, d.page_content), reverse=True)
    return ranked[:k]


def rerank_documents(query: str, docs: list[Document], *, top_n: int) -> list[Document]:
    ranked = []
    for d in docs:
        score = lexical_score(query, d.page_content)
        ranked.append(Document(d.page_content, {**d.metadata, "rerank_score": round(score, 4)}))
    ranked.sort(key=lambda d: float(d.metadata["rerank_score"]), reverse=True)
    return ranked[:top_n]


def main() -> None:
    text = (
        "2026 年渠道策略强调区域代理分层运营。"
        "低毛利订单需要先核对折扣权限，再评估履约成本。"
        "新品组合应优先进入华东和华南重点客户。"
        "售后响应时间会影响复购率。"
    )
    chunks = split_text(text, chunk_size=45, overlap=6)
    docs = [Document(c, {"chunk_index": i}) for i, c in enumerate(chunks)]

    query = "低毛利订单应该怎么处理"
    candidates = similarity_search(query, docs, k=4)
    ranked = rerank_documents(query, candidates, top_n=2)

    print("chunks:")
    for d in docs:
        print(d.metadata["chunk_index"], d.page_content)

    print("\nrerank top:")
    for d in ranked:
        print(d.metadata, d.page_content)


if __name__ == "__main__":
    main()
