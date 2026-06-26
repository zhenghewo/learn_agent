"""
Step 25 - Search Provider Chain 概念

新增概念：
- provider=auto：按优先级尝试多个搜索后端
- provider 固定值：只使用指定后端
- run_web_search()：成功返回 (来源, 结果)，全部失败返回错误列表

本 Step 使用 mock provider，不发真实网络请求。

运行：
    python3 learn_agent/step25_search_provider_chain_concept.py

对应 pv3：
- text2sql_pv3_tools/text2sql/tool_runtime/web_search_providers.py
"""

from __future__ import annotations

from typing import Callable


SearchFn = Callable[[str, int], list[str]]


def search_bocha(query: str, limit: int) -> list[str]:
    if "无 key" in query:
        raise RuntimeError("未配置 BOCHA_API_KEY")
    return [f"博查结果 {i}: {query}" for i in range(1, limit + 1)]


def search_searxng(query: str, limit: int) -> list[str]:
    raise RuntimeError("SearXNG 未启动或未启用 JSON")


def search_duckduckgo(query: str, limit: int) -> list[str]:
    return [f"DuckDuckGo 结果 {i}: {query}" for i in range(1, limit + 1)]


def build_search_chain(provider: str) -> list[tuple[str, SearchFn]]:
    mode = provider.strip().lower() or "auto"
    if mode == "bocha":
        return [("博查", search_bocha)]
    if mode == "searxng":
        return [("SearXNG", search_searxng)]
    if mode == "duckduckgo":
        return [("DuckDuckGo", search_duckduckgo)]
    return [("博查", search_bocha), ("SearXNG", search_searxng), ("DuckDuckGo", search_duckduckgo)]


def run_web_search(query: str, limit: int, *, provider: str = "auto") -> tuple[str | None, list[str]]:
    errors: list[str] = []
    for name, fn in build_search_chain(provider):
        try:
            lines = fn(query, limit)
            if lines:
                return name, lines
            errors.append(f"{name}: 无结果")
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {e}")
    return None, errors


def main() -> None:
    for provider, query in [("auto", "低毛利订单"), ("auto", "无 key 低毛利订单"), ("searxng", "渠道策略")]:
        source, payload = run_web_search(query, 2, provider=provider)
        print(f"\nprovider={provider}, source={source}")
        for line in payload:
            print("-", line)


if __name__ == "__main__":
    main()
