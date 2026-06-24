"""
Step 06 - Graph 编排概念

新增概念：
- GraphState：流程状态
- node：节点函数
- invoke：按顺序执行节点

本 Step 不关心真实数据库和真实 LLM，只讲“流程编排”。

运行：
    python3 learn_agent/step06_graph_concept.py

对应 pv0：
- text2sql/graph.py
"""

from typing import TypedDict


class GraphState(TypedDict):
    question: str
    sql: str
    result: str
    answer: str


def generate_sql(state: GraphState) -> dict:
    print("[node] generate_sql")
    return {"sql": "SELECT title FROM movies LIMIT 1"}


def execute_sql(state: GraphState) -> dict:
    print("[node] execute_sql")
    return {"result": "[('星际穿越',)]"}


def analyze(state: GraphState) -> dict:
    print("[node] analyze")
    return {"answer": f"根据 {state['sql']} 查到：{state['result']}"}


def invoke(state: GraphState) -> GraphState:
    for node in [generate_sql, execute_sql, analyze]:
        state.update(node(state))
    return state


def main() -> None:
    state: GraphState = {"question": "查电影", "sql": "", "result": "", "answer": ""}
    out = invoke(state)
    print(out["answer"])


if __name__ == "__main__":
    main()
