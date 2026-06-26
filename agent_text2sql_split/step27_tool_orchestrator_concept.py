"""
Step 27 - ToolOrchestrator 概念

新增概念：
- list_tools：列出可用工具
- select_tool：让 LLM/规则选择一个工具与参数
- execute_tool：执行工具
- validate_result：判断工具输出是否足够支撑用户目标
- retry：校验不通过时可带失败原因再选一次

本 Step 用规则模拟 LLM 决策和校验。

运行：
    python3 learn_agent/step27_tool_orchestrator_concept.py

对应 pv3：
- text2sql_pv3_tools/text2sql/tool_runtime/orchestrator.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolDescriptor:
    name: str
    description: str
    source: str


@dataclass
class ToolDecision:
    tool_name: str
    arguments: dict[str, Any]
    rationale: str = ""


@dataclass
class ToolValidation:
    satisfied: bool
    reason: str
    suggest_retry: bool = False


@dataclass
class ToolRunRecord:
    user_goal: str
    tools_listed: list[ToolDescriptor] = field(default_factory=list)
    decision: ToolDecision | None = None
    tool_output: str = ""
    tool_error: str | None = None
    validation: ToolValidation | None = None
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class SimpleTool:
    name: str
    description: str
    func: Callable[[dict[str, Any]], str]

    def invoke(self, arguments: dict[str, Any]) -> str:
        return self.func(arguments)


def web_search_tool(args: dict[str, Any]) -> str:
    query = str(args.get("query") or "")
    if "失败" in query:
        return "联网搜索失败：后端不可用"
    return "1. 低毛利订单处理规则\n   先复核折扣权限，再评估履约成本。"


def local_analysis_tool(args: dict[str, Any]) -> str:
    data = json.loads(str(args["data_json"]))
    return f"本地分析完成：行数={len(data.get('rows', []))}"


class ToolOrchestrator:
    def __init__(self, tools: list[SimpleTool], *, max_attempts: int = 2):
        self._tools = {t.name: t for t in tools}
        self.max_attempts = max_attempts

    def list_tools(self) -> list[ToolDescriptor]:
        return [ToolDescriptor(t.name, t.description, "local") for t in self._tools.values()]

    def select_tool(self, user_goal: str, *, extra_context: str = "") -> ToolDecision:
        if "联网" in user_goal or "最新" in user_goal or "搜索" in user_goal:
            return ToolDecision("web_search", {"query": user_goal, "max_results": 3}, "需要外部信息")
        if "表格" in user_goal or "分析" in user_goal:
            return ToolDecision(
                "local_data_analysis",
                {"data_json": json.dumps({"columns": ["x"], "rows": [[1], [2], [3]]})},
                "本地数据足够",
            )
        return ToolDecision("none", {}, "无需工具")

    def execute_tool(self, decision: ToolDecision) -> tuple[str, str | None]:
        if decision.tool_name == "none":
            return "", None
        tool = self._tools.get(decision.tool_name)
        if not tool:
            return "", f"未知工具：{decision.tool_name}"
        try:
            return tool.invoke(decision.arguments), None
        except Exception as e:
            return "", f"{type(e).__name__}: {e}"

    def validate_result(self, user_goal: str, decision: ToolDecision, output: str, error: str | None) -> ToolValidation:
        if decision.tool_name == "none":
            return ToolValidation(True, "无需工具")
        if error or not output.strip() or output.startswith("联网搜索失败"):
            return ToolValidation(False, "工具失败或输出为空", suggest_retry=False)
        return ToolValidation(True, "工具输出可用")

    def run(self, user_goal: str) -> ToolRunRecord:
        record = ToolRunRecord(user_goal=user_goal, tools_listed=self.list_tools())
        if not record.tools_listed:
            record.skipped = True
            record.skip_reason = "无可用工具"
            return record

        for _ in range(self.max_attempts):
            decision = self.select_tool(user_goal)
            record.decision = decision
            if decision.tool_name == "none":
                record.skipped = True
                record.skip_reason = decision.rationale
                record.validation = ToolValidation(True, decision.rationale)
                return record
            output, error = self.execute_tool(decision)
            record.tool_output, record.tool_error = output, error
            record.validation = self.validate_result(user_goal, decision, output, error)
            if record.validation.satisfied:
                return record
            if not record.validation.suggest_retry:
                return record
        return record


def main() -> None:
    orchestrator = ToolOrchestrator(
        [
            SimpleTool("web_search", "联网搜索", web_search_tool),
            SimpleTool("local_data_analysis", "本地表格分析", local_analysis_tool),
        ]
    )
    for goal in ["搜索低毛利订单最新处理规则", "分析这张表格", "普通 SQL 查询"]:
        record = orchestrator.run(goal)
        print("\n目标:", goal)
        print(record)


if __name__ == "__main__":
    main()
