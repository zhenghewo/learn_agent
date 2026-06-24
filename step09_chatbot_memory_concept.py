"""
Step 09 - Chatbot Memory 概念

新增概念：
- Chatbot.chat()
- thread_id
- messages 历史

本 Step 只讲多轮记忆，不讲 SQL。

运行：
    python3 learn_agent/step09_chatbot_memory_concept.py

对应 pv0：
- text2sql/chatbot.py
"""

from dataclasses import dataclass


@dataclass
class Message:
    role: str
    content: str


class Chatbot:
    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.memory: dict[str, list[Message]] = {}

    def chat(self, text: str) -> str:
        messages = self.memory.setdefault(self.thread_id, [])
        messages.append(Message("user", text))

        answer = f"这是第 {len([m for m in messages if m.role == 'user'])} 个用户问题：{text}"
        messages.append(Message("assistant", answer))
        return answer


def main() -> None:
    bot = Chatbot(thread_id="demo")
    print(bot.chat("我想查电影"))
    print(bot.chat("评分最高的是哪部？"))

    print("\n历史消息:")
    for m in bot.memory["demo"]:
        print(m.role, ":", m.content)


if __name__ == "__main__":
    main()
