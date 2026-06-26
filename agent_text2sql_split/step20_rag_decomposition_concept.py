"""
Step 20 - RAG 子问题分解概念

新增概念：
- decompose：把复杂问题拆成多个可独立检索的子问题
- retrieve_and_answer_sub：每个子问题各自检索和生成子答案
- synthesize：最后综合子答案回答原问题

本 Step 用本地知识片段模拟 RAG，不依赖 LLM/API。

运行：
    python3 learn_agent/step20_rag_decomposition_concept.py

对应 pv2：
- text2sql_pv2_mem/text2sql/rag_engine.py 的 _ask_with_decomposition()
- text2sql_pv2_mem/docs/RAG子问题分解.md
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SubAnswer:
    sub_question: str
    retrieval_queries: list[str]
    answer: str


class MiniKnowledgeBase:
    def __init__(self) -> None:
        self.docs = {
            "渠道": "2027 年渠道增长优先做区域代理分层、重点客户联合拜访。",
            "低毛利": "低毛利订单要先核对折扣权限，再评估履约成本和退货风险。",
            "新品": "新品组合优先进入华东和华南重点客户，先小批量试点。",
        }

    def search(self, query: str) -> str:
        for key, text in self.docs.items():
            if key in query:
                return text
        return "未检索到直接证据。"


def decompose(question: str) -> list[str]:
    if "同时" in question or "以及" in question:
        return [
            "2027 年渠道增长策略是什么？",
            "低毛利订单应该怎么处理？",
            "新品组合应该怎么落地？",
        ]
    return [question]


def retrieve_and_answer_sub(kb: MiniKnowledgeBase, sub_question: str) -> SubAnswer:
    evidence = kb.search(sub_question)
    answer = f"依据：{evidence}"
    return SubAnswer(sub_question, [sub_question], answer)


def synthesize(question: str, sub_answers: list[SubAnswer]) -> str:
    lines = [f"原问题：{question}", "", "综合回答："]
    for item in sub_answers:
        lines.append(f"- {item.sub_question} {item.answer}")
    return "\n".join(lines)


def main() -> None:
    question = "2027 年渠道增长策略、低毛利订单以及新品组合怎么处理？"
    kb = MiniKnowledgeBase()
    subs = decompose(question)
    answers = [retrieve_and_answer_sub(kb, sq) for sq in subs]

    print("子问题:")
    for sq in subs:
        print("-", sq)

    print("\n最终综合:")
    print(synthesize(question, answers))


if __name__ == "__main__":
    main()
