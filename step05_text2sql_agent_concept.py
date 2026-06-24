"""
Step 05 - Text2sqlAgent 概念

新增概念：
- Text2sqlAgent：专门负责“问题 -> SQL”
- Final: 输出协议
- extract_final_sql()：从模型输出中提取 SQL

本 Step 只讲 Agent 生成 SQL，不执行 SQL。

运行：
    python3 learn_agent/step05_text2sql_agent_concept.py

对应 pv0：
- text2sql/text2sql_agent.py
"""

import re
from dataclasses import dataclass


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Response:
    content: str


class MockChatModel:
    def invoke(self, messages: list[Message]) -> Response:
        question = messages[-1].content
        if "评分最高" in question:
            return Response(
                "Thought: 需要按 rating 降序排序。\n"
                "Final: SELECT title, rating FROM movies ORDER BY rating DESC LIMIT 1"
            )
        return Response("Final: SELECT title FROM movies LIMIT 5")


def extract_final_sql(text: str) -> str:
    match = re.search(r"final:\s*([\s\S]+)$", text, re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()


class Text2sqlAgent:
    def __init__(self):
        self.model = MockChatModel()

    def generate(self, question: str, schema_text: str) -> str:
        response = self.model.invoke(
            [
                Message("system", f"根据 schema 生成 SQL:\n{schema_text}"),
                Message("user", question),
            ]
        )
        print("模型原始输出:")
        print(response.content)
        return extract_final_sql(response.content)


def main() -> None:
    agent = Text2sqlAgent()
    sql = agent.generate("评分最高的电影是哪部？", "movies(title, rating)")
    print("提取 SQL:", sql)


if __name__ == "__main__":
    main()
