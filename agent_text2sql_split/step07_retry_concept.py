"""
Step 07 - Retry 路由概念

新增概念：
- route_after_execute()
- retry_count
- 失败后重试，成功后结束

本 Step 只讲“条件路由和重试”，不讲完整 Text2SQL。

运行：
    python3 learn_agent/step07_retry_concept.py

对应 pv0：
- text2sql/graph.py 的 route_after_execute / bump_retry
"""

from typing import Literal, TypedDict


class State(TypedDict):
    retry_count: int
    error: str | None


def route_after_execute(state: State) -> Literal["retry", "analyze", "fail"]:
    if not state["error"]:
        return "analyze"
    if state["retry_count"] < 3:
        return "retry"
    return "fail"


def main() -> None:
    state: State = {"retry_count": 0, "error": "no such column: stock"}
    while True:
        route = route_after_execute(state)
        print("route =", route, "state =", state)

        if route == "analyze":
            print("成功，进入分析")
            break

        if route == "fail":
            print("失败次数过多，结束")
            break

        state["retry_count"] += 1
        if state["retry_count"] == 2:
            state["error"] = None


if __name__ == "__main__":
    main()
