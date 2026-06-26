"""
Step 26 - MCP Tool Loading 概念

新增概念：
- MCP server config：stdio command 或 SSE/HTTP URL
- diagnose_mcp_config()：工具未加载时给出可读原因
- load_mcp_tools()：连接成功后把远程工具变成可调用工具列表

本 Step 使用 mock MCP client，不连接真实 MCP 服务。

运行：
    python3 learn_agent/step26_mcp_tool_loading_concept.py

对应 pv3：
- text2sql_pv3_tools/text2sql/tool_runtime/mcp_tools.py
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Any


@dataclass
class Settings:
    tools_mcp_enabled: bool = True
    mcp_data_analysis_url: str = ""
    mcp_data_analysis_command: str = ""
    mcp_data_analysis_server_name: str = "data_analysis"
    mcp_data_analysis_transport: str = "sse"
    mcp_data_analysis_tool_name: str = ""


@dataclass
class McpTool:
    name: str
    description: str

    def invoke(self, arguments: dict[str, Any]) -> str:
        return f"{self.name} 收到参数：{arguments}"


@dataclass
class McpLoadResult:
    tools: list[McpTool]
    ok: bool
    message: str


def mcp_server_config(settings: Settings) -> dict[str, dict[str, Any]] | None:
    name = settings.mcp_data_analysis_server_name.strip() or "data_analysis"
    if settings.mcp_data_analysis_command.strip():
        parts = shlex.split(settings.mcp_data_analysis_command)
        return {name: {"command": parts[0], "args": parts[1:], "transport": "stdio"}}
    if settings.mcp_data_analysis_url.strip():
        return {name: {"url": settings.mcp_data_analysis_url, "transport": settings.mcp_data_analysis_transport}}
    return None


def diagnose_mcp_config(settings: Settings) -> str:
    if not settings.tools_mcp_enabled:
        return "TOOLS_MCP_ENABLED=false，已跳过 MCP 工具注册。"
    if not settings.mcp_data_analysis_command and not settings.mcp_data_analysis_url:
        return "未配置 MCP：请设置 MCP_DATA_ANALYSIS_URL 或 MCP_DATA_ANALYSIS_COMMAND。"
    if settings.mcp_data_analysis_command:
        return f"将使用 stdio MCP：{settings.mcp_data_analysis_command}"
    return f"将连接 SSE MCP：{settings.mcp_data_analysis_url}"


def load_mcp_tools(settings: Settings) -> McpLoadResult:
    cfg = mcp_server_config(settings)
    if not settings.tools_mcp_enabled or not cfg:
        return McpLoadResult([], False, diagnose_mcp_config(settings))

    tools = [
        McpTool("remote_profile_table", "远程分析客户画像表"),
        McpTool("remote_forecast", "远程生成预测摘要"),
    ]
    wanted = settings.mcp_data_analysis_tool_name.strip()
    if wanted:
        tools = [t for t in tools if t.name == wanted]
    if not tools:
        return McpLoadResult([], False, "MCP 已连接但未返回匹配工具。")
    return McpLoadResult(tools, True, f"已加载 MCP 工具 {len(tools)} 个")


def main() -> None:
    cases = [
        Settings(),
        Settings(mcp_data_analysis_command="python -m fake_server"),
        Settings(mcp_data_analysis_url="http://127.0.0.1:8000/sse", mcp_data_analysis_tool_name="remote_forecast"),
    ]
    for s in cases:
        print("\n诊断:", diagnose_mcp_config(s))
        print("config:", mcp_server_config(s))
        print("load:", load_mcp_tools(s))


if __name__ == "__main__":
    main()
