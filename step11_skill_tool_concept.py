"""
Step 11 - Skill Tool 概念

新增概念：
- SkillTool 元数据
- intent routing
- artifact_path

本 Step 只讲工具导出，不讲数据库和 Graph。

运行：
    python3 learn_agent/step11_skill_tool_concept.py

对应 pv0：
- text2sql/skill_runtime.py
- skills/my-skill/
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any


@dataclass
class SkillTool:
    intent: str
    name: str
    triggers: list[str]
    run: Callable[[dict[str, Any]], dict[str, Any]]


def export_markdown(payload: dict[str, Any]) -> dict[str, Any]:
    out = Path("learn_agent/outputs/exports/report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload["report_text"], encoding="utf-8")
    return {"ok": True, "artifact_path": str(out)}


def detect_tool(question: str, tools: list[SkillTool]) -> SkillTool | None:
    for tool in tools:
        if any(t in question for t in tool.triggers):
            return tool
    return None


def main() -> None:
    tools = [
        SkillTool(
            intent="markdown",
            name="export_markdown",
            triggers=["导出报告", "保存报告"],
            run=export_markdown,
        )
    ]

    question = "请导出报告"
    tool = detect_tool(question, tools)
    if tool:
        result = tool.run({"report_text": "# demo report\n"})
        print(tool.name, result)


if __name__ == "__main__":
    main()
