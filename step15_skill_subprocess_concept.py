"""
Step 15 - Skill 子进程工具概念

新增概念：
- SKILL.md 中声明 tool intent / script / triggers
- invoke_skill_tool() 用 JSON stdin 调用脚本
- 脚本用 JSON stdout 返回 artifact_path 等结果

本 Step 只讲 skill 运行时，不讲 AnalyzerAgent 如何决定调用哪个 skill。

运行：
    python3 learn_agent/step15_skill_subprocess_concept.py

对应 pv1：
- text2sql_pv1_0425/text2sql/skill_runtime.py
- text2sql_pv1_0425/skills/my-skill/
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_TOOL_INTENT_RE = re.compile(r"^\s*-\s*intent:\s*(.+?)\s*$")
_TOOL_SCRIPT_RE = re.compile(r"^\s*script:\s*(.+?)\s*$")
_TOOL_TRIGGERS_RE = re.compile(r"^\s*triggers:\s*(.+?)\s*$")


@dataclass(frozen=True)
class SkillToolSpec:
    intent: str
    script_path: Path
    triggers: tuple[str, ...]
    name: str
    description: str


def _extract_tool_defs(skill_md_text: str) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    lines = skill_md_text.splitlines()
    i = 0
    while i < len(lines):
        m = _TOOL_INTENT_RE.match(lines[i])
        if not m:
            i += 1
            continue
        item: dict[str, Any] = {"intent": m.group(1).strip()}
        i += 1
        while i < len(lines) and not _TOOL_INTENT_RE.match(lines[i]):
            if script_m := _TOOL_SCRIPT_RE.match(lines[i]):
                item["script"] = script_m.group(1).strip()
            if triggers_m := _TOOL_TRIGGERS_RE.match(lines[i]):
                raw = triggers_m.group(1)
                item["triggers"] = [t.strip() for t in raw.split(",") if t.strip()]
            i += 1
        tools.append(item)
    return tools


def load_skill_tools(skills_root: Path) -> list[SkillToolSpec]:
    specs: list[SkillToolSpec] = []
    for skill_md in skills_root.glob("*/SKILL.md"):
        text = skill_md.read_text(encoding="utf-8")
        for item in _extract_tool_defs(text):
            script_path = (skill_md.parent / str(item.get("script", ""))).resolve()
            if not script_path.exists():
                continue
            triggers = tuple(str(t).strip().lower() for t in item.get("triggers", []))
            specs.append(
                SkillToolSpec(
                    intent=str(item["intent"]).lower(),
                    script_path=script_path,
                    triggers=triggers,
                    name=skill_md.parent.name,
                    description="demo export skill",
                )
            )
    return specs


def invoke_skill_tool(
    tool: SkillToolSpec,
    *,
    payload: dict[str, Any],
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(tool.script_path)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip()}
    try:
        return {"ok": True, "result": json.loads(proc.stdout)}
    except json.JSONDecodeError:
        return {"ok": True, "result": {"message": proc.stdout.strip()}}


def create_demo_skill(root: Path) -> None:
    skill_dir = root / "report-export"
    scripts = skill_dir / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        """
---
name: report-export
description: export markdown report
---

tools:
- intent: markdown
  script: scripts/export_markdown.py
  triggers: 导出报告, 保存报告, markdown
""".strip(),
        encoding="utf-8",
    )
    (scripts / "export_markdown.py").write_text(
        """
import json
import sys
from pathlib import Path

payload = json.loads(sys.stdin.read())
out = Path(payload["report_dir"]) / "skill_report.md"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(payload["report_text"], encoding="utf-8")
print(json.dumps({"message": "导出完成", "artifact_path": str(out)}, ensure_ascii=False))
""".strip(),
        encoding="utf-8",
    )


def main() -> None:
    root = Path("learn_agent/outputs/step15_skills")
    create_demo_skill(root)

    tools = load_skill_tools(root)
    tool = tools[0]
    result = invoke_skill_tool(
        tool,
        payload={
            "report_text": "# demo report\n\n查询返回 1 行。",
            "report_dir": "learn_agent/outputs/step15_exports",
        },
    )
    print(tool)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
