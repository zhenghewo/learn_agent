"""
Step 28 - Tool Context Injection 概念

新增概念：
- tool_output_usable()：只有可信工具输出才注入主流程
- build_tool_context_block()：把工具结果变成用户问题的补充上下文
- memory_query：工具上下文很长时，记忆检索仍用原始用户问题，避免 embedding 超长/跑偏

本 Step 只讲工具输出如何进入 Chatbot，不讲工具如何选择。

运行：
    python3 learn_agent/step28_tool_context_injection_concept.py

对应 pv3：
- text2sql_pv3_tools/text2sql/tool_runtime/orchestrator.py
- text2sql_pv3_tools/text2sql/chatbot.py 的 chat(memory_query=...)
- text2sql_pv3_tools/text2sql/graph.py 的 memory_query
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolValidation:
    satisfied: bool
    reason: str
    suggest_retry: bool = False


@dataclass
class ToolRunRecord:
    tool_output: str = ""
    tool_error: str | None = None
    validation: ToolValidation | None = None
    skipped: bool = False
    skip_reason: str = ""


_TOOL_FAIL_PREFIXES = ("错误：", "联网搜索失败", "未检索到")


def tool_output_usable(record: ToolRunRecord) -> bool:
    if record.skipped or record.tool_error:
        return False
    output = record.tool_output.strip()
    if not output:
        return False
    if output.startswith(_TOOL_FAIL_PREFIXES):
        return False
    if record.validation and not record.validation.satisfied:
        return False
    return True


def build_tool_context_block(record: ToolRunRecord, *, max_chars: int = 160) -> str:
    if not tool_output_usable(record):
        return ""
    body = record.tool_output.strip()
    if len(body) > max_chars:
        body = body[:max_chars] + "\n...（工具输出已截断）"
    return "【工具调用补充上下文】\n" + body


class Chatbot:
    def chat(self, user_text: str, *, memory_query: str | None = None) -> dict[str, str]:
        """memory_query 默认等于 user_text；工具注入后可单独传原始问题。"""
        return {
            "sent_to_graph": user_text,
            "used_for_memory_search": memory_query or user_text,
        }


def main() -> None:
    original_question = "结合最新资料，低毛利订单怎么处理？"
    record = ToolRunRecord(
        tool_output="1. 订单质量规则：先复核折扣权限，再评估履约成本和退货风险。",
        validation=ToolValidation(True, "足够支撑回答"),
    )
    block = build_tool_context_block(record)

    user_text = f"{original_question}\n\n{block}" if block else original_question
    out = Chatbot().chat(user_text, memory_query=original_question)

    print("主流程收到:")
    print(out["sent_to_graph"])
    print("\n记忆检索使用:")
    print(out["used_for_memory_search"])


if __name__ == "__main__":
    main()
