"""
Step 17 - RAG Router 概念

新增概念：
- route(question)：把问题分到 SQL 路径或知识库路径
- 年份阈值：未来经营/策略问题优先走 kb
- LLM 分类兜底：无法用规则判断时，让模型返回 {"route":"sql|kb"}

本 Step 只讲“路由”，不讲向量检索和数据库执行。

运行：
    python3 learn_agent/step17_rag_router_concept.py

对应 pv2：
- text2sql_pv2_mem/text2sql/rag_engine.py 的 RagEngine.route()
- text2sql_pv2_mem/text2sql/graph.py 的 route_query()
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Response:
    content: str


class MockRouterModel:
    def invoke(self, messages: list[str]) -> Response:
        question = messages[-1]
        kb_words = ["策略", "规划", "复盘", "培训", "打法", "政策"]
        route = "kb" if any(w in question for w in kb_words) else "sql"
        return Response(f'{{"route":"{route}"}}')


@dataclass
class RagSettings:
    rag_enabled: bool = True
    rag_router_year_threshold: int = 2026


class RagRouter:
    def __init__(self, settings: RagSettings, model: MockRouterModel):
        self.settings = settings
        self.model = model

    def route(self, question: str) -> str:
        if not self.settings.rag_enabled:
            return "sql"

        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", question)]
        if years and max(years) >= self.settings.rag_router_year_threshold:
            return "kb"

        resp = self.model.invoke([f"用户问题：{question}"])
        raw = resp.content.replace(" ", "").lower()
        return "kb" if '"route":"kb"' in raw else "sql"


def main() -> None:
    router = RagRouter(RagSettings(), MockRouterModel())
    questions = [
        "统计 2024 年订单总额最高的客户",
        "2027 年渠道增长策略是什么？",
        "销售团队培训材料里建议怎么处理低毛利订单？",
    ]
    for q in questions:
        print(q, "=>", router.route(q))


if __name__ == "__main__":
    main()
