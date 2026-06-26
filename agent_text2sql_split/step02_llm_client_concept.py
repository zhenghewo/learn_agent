"""
Step 02 - LLM Client 概念

新增概念：
- build_chat_model()
- model.invoke(messages)
- 用 MockChatModel 模拟真实大模型

本 Step 只讲“如何封装模型调用”，不讲 SQL 执行。

运行：
    python3 learn_agent/step02_llm_client_concept.py

对应 pv0：
- text2sql/llm_client.py
"""

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
            return Response("SELECT title, rating FROM movies ORDER BY rating DESC LIMIT 1")
        return Response("SELECT title FROM movies LIMIT 5")


def build_chat_model() -> MockChatModel:
    return MockChatModel()


def main() -> None:
    model = build_chat_model()
    response = model.invoke(
        [
            Message("system", "你是 Text2SQL 助手"),
            Message("user", "评分最高的电影是哪部？"),
        ]
    )
    print(response.content)


if __name__ == "__main__":
    main()
