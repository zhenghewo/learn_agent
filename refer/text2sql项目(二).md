## 项目代码


### llm_client
```python
from langchain_openai import ChatOpenAI

from text2sql.config import Settings, get_settings, resolve_llm_base_url


def build_chat_model(settings: Settings | None = None) -> ChatOpenAI:
    """基于 LangChain OpenAI 兼容客户端，支持豆包 / DeepSeek / 千问等网关。"""
    s = settings or get_settings()
    base_url = resolve_llm_base_url(s)
    return ChatOpenAI(
        model=s.llm_model,
        api_key=s.llm_api_key or "not-set",
        base_url=base_url,
        temperature=0.1,
        timeout=120,
    )
```


### query_executor
```python
import re
from dataclasses import dataclass
from typing import Any

import psycopg2
import psycopg2.extras

from text2sql.config import Settings, get_settings


class UnsafeSQLError(ValueError):
    """Raised when SQL fails static safety checks."""


_SELECT_START = re.compile(r"^\s*select\b", re.IGNORECASE | re.DOTALL)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|truncate|alter|create|grant|revoke|copy\s+from|;\s*select)\b",
    re.IGNORECASE,
)


def _assert_read_only_sql(sql: str) -> None:
    s = sql.strip()
    if not s:
        raise UnsafeSQLError("SQL 为空")
    if not _SELECT_START.search(s):
        raise UnsafeSQLError("仅允许以 SELECT 开头的只读查询")
    if ";" in s.rstrip(";").strip():
        raise UnsafeSQLError("不允许多条语句或分号拼接")
    if _FORBIDDEN.search(s):
        raise UnsafeSQLError("检测到可能的数据变更或危险关键字")


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    error: str | None = None


class QueryExecutor:
    """连接 PostgreSQL 执行只读 SQL。"""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()

    def execute(self, sql: str) -> QueryResult:
        _assert_read_only_sql(sql)
        try:
            conn = psycopg2.connect(
                self._settings.database_url,
                connect_timeout=self._settings.sql_timeout_seconds,
            )
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(f"SET statement_timeout = {self._settings.sql_timeout_seconds * 1000}")
                    cur.execute(sql)
                    rows = cur.fetchall()
                    cols = [d[0] for d in cur.description] if cur.description else []
                    tuples = [tuple(r[c] for c in cols) for r in rows]
                    return QueryResult(columns=cols, rows=tuples, error=None)
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001 — 执行层统一转为可展示错误
            return QueryResult(columns=[], rows=[], error=str(e))

    def fetch_schema_digest(self, table_filter: list[str] | None = None) -> str:
        """拉取 public 模式下表与列信息，供 Text2SQL 作为上下文。"""
        filter_clause = ""
        params: list[Any] = []
        if table_filter:
            filter_clause = " AND c.table_name = ANY(%s)"
            params.append(table_filter)
        sql = f"""
        SELECT c.table_name, c.column_name, c.data_type
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
        {filter_clause}
        ORDER BY c.table_name, c.ordinal_position
        """
        r = self.execute(sql)
        if r.error:
            return f"(无法读取 schema: {r.error})"
        lines: list[str] = []
        current = ""
        for row in r.rows:
            t, col, dtype = row[0], row[1], row[2]
            if t != current:
                current = t
                lines.append(f"\n表 {t}:")
            lines.append(f"  - {col} ({dtype})")
        return "\n".join(lines) if lines else "(public 下无表或无可读列)"
```

### text2sql_agent
```python
import re
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from text2sql.llm_client import build_chat_model


_SQL_BLOCK = re.compile(r"```(?:sql)?\s*([\s\S]*?)```", re.IGNORECASE)


def _extract_sql(text: str) -> str:
    text = text.strip()
    m = _SQL_BLOCK.search(text)
    if m:
        return m.group(1).strip()
    return text


class Text2sqlAgent:
    """根据自然语言与上下文生成只读 SQL，并在失败时结合错误信息修正。"""

    SYSTEM = """你是 PostgreSQL SQL 专家。根据「数据库 schema」「对话历史」和「当前用户意图」生成**恰好一条**只读 SELECT 语句。

硬性规则：
1. 只输出一条 SQL；不要 Markdown；不要分号分隔的多条语句。
2. 必须以 SELECT 开头；禁止 INSERT/UPDATE/DELETE/DDL/事务控制。
3. 若信息不足，做保守、可执行的查询（例如 LIMIT）。
4. 若用户追问指代前文，结合对话历史消歧。"""

    def __init__(self, model: Any | None = None):
        self._llm = model or build_chat_model()

    def generate(
        self,
        *,
        messages: list[BaseMessage],
        schema_text: str,
        previous_sql: str = "",
        last_error: str | None = None,
    ) -> str:
        extra: list[BaseMessage] = []
        if last_error:
            extra.append(
                HumanMessage(
                    content=(
                        f"上一次生成的 SQL 执行失败。\n错误信息：{last_error}\n"
                        f"上次 SQL：\n{previous_sql}\n\n请修正为一条可执行的 SELECT，只输出 SQL。"
                    )
                )
            )
        prompt: list[BaseMessage] = [
            SystemMessage(
                content=f"{self.SYSTEM}\n\n当前数据库 schema 摘要：\n{schema_text}"
            ),
            *messages,
            *extra,
        ]
        resp = self._llm.invoke(prompt)
        raw = resp.content if hasattr(resp, "content") else str(resp)
        return _extract_sql(str(raw)).strip()


def last_user_text(messages: list[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            c = m.content
            return c if isinstance(c, str) else str(c)
    return ""
```

#


### langgraph
```python
from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from text2sql.analyzer_agent import AnalyzerAgent
from text2sql.config import Settings, get_settings
from text2sql.query_executor import QueryExecutor
from text2sql.text2sql_agent import Text2sqlAgent, last_user_text


class GraphState(TypedDict):
    """LangGraph 状态：多轮对话 + SQL 执行 + 分析。"""

    messages: Annotated[list[BaseMessage], add_messages]
    schema_text: str
    sql: str
    columns: list[str]
    rows: list[tuple[Any, ...]]
    error: str | None
    retry_count: int
    analysis: str


def build_text2sql_graph(
    settings: Settings | None = None,
    *,
    query_executor: QueryExecutor | None = None,
    text2sql: Text2sqlAgent | None = None,
    analyzer: AnalyzerAgent | None = None,
):
    s = settings or get_settings()
    qe = query_executor or QueryExecutor(s)
    gen = text2sql or Text2sqlAgent()
    ana = analyzer or AnalyzerAgent()

    def generate_sql(state: GraphState) -> dict[str, Any]:
        sql = gen.generate(
            messages=state["messages"],
            schema_text=state.get("schema_text") or "(无 schema)",
            previous_sql=state.get("sql") or "",
            last_error=state.get("error"),
        )
        return {"sql": sql}

    def execute_sql(state: GraphState) -> dict[str, Any]:
        res = qe.execute(state["sql"])
        if res.error:
            return {
                "columns": [],
                "rows": [],
                "error": res.error,
            }
        return {
            "columns": res.columns,
            "rows": res.rows,
            "error": None,
        }

    def route_after_execute(state: GraphState) -> Literal["retry", "analyze", "fail"]:
        if not state.get("error"):
            return "analyze"
        if state.get("retry_count", 0) < s.max_sql_retries:
            return "retry"
        return "fail"

    def bump_retry(state: GraphState) -> dict[str, Any]:
        return {"retry_count": state.get("retry_count", 0) + 1}

    def run_analyze(state: GraphState) -> dict[str, Any]:
        uq = last_user_text(state["messages"])
        text = ana.analyze(
            user_question=uq,
            sql=state["sql"],
            columns=state["columns"],
            rows=state["rows"],
        )
        return {
            "analysis": text,
            "messages": [AIMessage(content=text)],
        }

    def run_fail(state: GraphState) -> dict[str, Any]:
        err = state.get("error") or "未知错误"
        n = state.get("retry_count", 0)
        text = (
            f"SQL 执行仍失败（已达最大重试次数 {s.max_sql_retries} 次）。\n\n"
            f"最后错误：{err}\n\n"
            f"已尝试的 SQL：\n```sql\n{state.get('sql', '')}\n```"
        )
        return {
            "analysis": text,
            "messages": [AIMessage(content=text)],
        }

    g = StateGraph(GraphState)
    g.add_node("generate_sql", generate_sql)
    g.add_node("execute_sql", execute_sql)
    g.add_node("bump_retry", bump_retry)
    g.add_node("analyze", run_analyze)
    g.add_node("fail", run_fail)

    g.add_edge(START, "generate_sql")
    g.add_edge("generate_sql", "execute_sql")
    g.add_conditional_edges(
        "execute_sql",
        route_after_execute,
        {
            "retry": "bump_retry",
            "analyze": "analyze",
            "fail": "fail",
        },
    )
    g.add_edge("bump_retry", "generate_sql")
    g.add_edge("analyze", END)
    g.add_edge("fail", END)

    return g
```

### analyzer_agent
```python
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from text2sql.llm_client import build_chat_model


class AnalyzerAgent:
    """对查询结果生成中文分析报告。"""

    SYSTEM = """你是数据分析助手。根据用户问题、执行的 SQL 与查询结果，写一份**专业、简洁**的中文分析报告。

要求：
- 用 Markdown 小标题与列表，先给结论再给依据。
- 若结果为空，说明可能原因与下一步建议。
- 不要编造数据中不存在的数字；统计量请基于给定结果。
- 篇幅适中，避免空话。"""

    def __init__(self, model: Any | None = None):
        self._llm = model or build_chat_model()

    def analyze(
        self,
        *,
        user_question: str,
        sql: str,
        columns: list[str],
        rows: list[tuple[Any, ...]],
        max_rows_in_prompt: int = 50,
    ) -> str:
        preview = rows[:max_rows_in_prompt]
        body = (
            f"用户问题：{user_question}\n\n"
            f"执行的 SQL：\n{sql}\n\n"
            f"列：{columns}\n"
            f"行（最多展示 {max_rows_in_prompt} 行）：\n{preview}"
        )
        if len(rows) > max_rows_in_prompt:
            body += f"\n… 共 {len(rows)} 行，其余已省略。"
        msgs = [
            SystemMessage(content=self.SYSTEM),
            HumanMessage(content=body),
        ]
        resp = self._llm.invoke(msgs)
        return str(resp.content if hasattr(resp, "content") else resp).strip()
```

### config
```python
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


Provider = Literal["doubao", "deepseek", "qwen", "openai"]


# 常见 OpenAI 兼容网关默认地址（可通过环境变量覆盖）
_DEFAULT_BASE_URLS: dict[str, str] = {
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai": "https://api.openai.com/v1",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql://user:pass@localhost:5432/dbname",
        description="PostgreSQL 连接串",
    )

    llm_provider: Provider = Field(default="deepseek", description="doubao | deepseek | qwen | openai")
    llm_api_key: str = Field(default="", description="LLM API Key")
    llm_base_url: str | None = Field(default=None, description="覆盖默认网关")
    llm_model: str = Field(default="deepseek-chat", description="模型名")

    max_sql_retries: int = Field(default=3, ge=1, le=10)
    sql_timeout_seconds: int = Field(default=60, ge=1)

    # 可选：限制只暴露这些表给模型（逗号分隔）；空表示从库中拉取 public 表清单
    schema_allow_tables: str = Field(default="", description="e.g. orders,users")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def resolve_llm_base_url(settings: Settings) -> str:
    if settings.llm_base_url:
        return settings.llm_base_url
    return _DEFAULT_BASE_URLS.get(settings.llm_provider, _DEFAULT_BASE_URLS["openai"])
```

### chatbot
```python
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from text2sql.config import Settings, get_settings
from text2sql.graph import GraphState, build_text2sql_graph
from text2sql.query_executor import QueryExecutor


class Chatbot:
    """多轮对话客户端：维护 thread、schema 缓存，调用 LangGraph。"""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        thread_id: str = "default",
        query_executor: QueryExecutor | None = None,
    ):
        self._settings = settings or get_settings()
        self._qe = query_executor or QueryExecutor(self._settings)
        self._thread_id = thread_id
        self._schema_text: str | None = None
        workflow = build_text2sql_graph(self._settings, query_executor=self._qe)
        self._app = workflow.compile(checkpointer=MemorySaver())

    def refresh_schema(self) -> str:
        allow = self._settings.schema_allow_tables
        tables = [t.strip() for t in allow.split(",") if t.strip()] if allow else None
        self._schema_text = self._qe.fetch_schema_digest(table_filter=tables)
        return self._schema_text

    @property
    def schema_text(self) -> str:
        if self._schema_text is None:
            self.refresh_schema()
        assert self._schema_text is not None
        return self._schema_text

    def chat(self, user_text: str) -> dict[str, Any]:
        """处理一轮用户输入，返回完整状态片段（含 analysis、sql、error 等）。"""
        init: GraphState = {
            "messages": [HumanMessage(content=user_text)],
            "schema_text": self.schema_text,
            "sql": "",
            "columns": [],
            "rows": [],
            "error": None,
            "retry_count": 0,
            "analysis": "",
        }
        cfg: dict[str, Any] = {"configurable": {"thread_id": self._thread_id}}
        # 合并 checkpoint：新输入用 add_messages 追加
        out = self._app.invoke(init, cfg)
        return out
```

### chat_demo
```python
#!/usr/bin/env python3
"""
功能演示：通过 Chatbot 客户端与数据库对话（需已配置数据库与 LLM）。

环境变量示例：
  export DATABASE_URL='postgresql://...'
  export LLM_API_KEY='...'
  export LLM_PROVIDER=deepseek
  export LLM_MODEL=deepseek-chat

用法：
  python scripts/functional_chat_demo.py              # 进入实时交互（默认）
  python scripts/functional_chat_demo.py -i           # 同上，显式指定交互
  python scripts/functional_chat_demo.py "问题一" "问题二"  # 非交互，按顺序批量提问
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 保证从项目根目录可导入 text2sql
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import readline  # noqa: F401 — 启用行编辑与历史（Unix/macOS 常见）
except ImportError:
    pass

from text2sql.chatbot import Chatbot  # noqa: E402


def _print_turn_header(turn: int) -> None:
    print(f"\n{'=' * 12} 第 {turn} 轮 {'=' * 12}", flush=True)


def _print_assistant(out: dict, *, show_json: bool) -> None:
    print("\n助手：\n", out.get("analysis", ""), "\n", sep="", flush=True)
    if show_json:
        payload = {
            "sql": out.get("sql"),
            "columns": out.get("columns"),
            "row_count": len(out.get("rows") or []),
            "error": out.get("error"),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


def run_interactive(bot: Chatbot, *, show_json: bool) -> int:
    print(
        "已进入实时问答。输入问题后回车发送；空行忽略。\n"
        "退出：quit / exit / q 或 Ctrl+D\n",
        file=sys.stderr,
        flush=True,
    )
    turn = 0
    while True:
        try:
            line = input("你> ").strip()
        except EOFError:
            print("\n再见。", file=sys.stderr, flush=True)
            return 0
        except KeyboardInterrupt:
            print("\n再见。", file=sys.stderr, flush=True)
            return 0

        if not line:
            continue
        low = line.lower()
        if low in ("quit", "exit", "q"):
            print("再见。", file=sys.stderr, flush=True)
            return 0

        turn += 1
        _print_turn_header(turn)
        print(f"用户：{line}\n", flush=True)
        out = bot.chat(line)
        _print_assistant(out, show_json=show_json)


def run_batch(bot: Chatbot, questions: list[str], *, show_json: bool) -> int:
    for i, q in enumerate(questions):
        _print_turn_header(i + 1)
        print(f"用户：{q}\n", flush=True)
        out = bot.chat(q)
        _print_assistant(out, show_json=show_json)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Text2SQL Chatbot：实时交互或批量提问",
        epilog="使用 -i / --interactive 时始终进入交互，不会执行命令行中的问题。",
    )
    p.add_argument(
        "questions",
        nargs="*",
        help="非交互模式下依次提问；不传则进入实时交互",
    )
    p.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="强制进入实时交互（与默认无参数行为一致）",
    )
    p.add_argument(
        "--thread",
        default="demo-thread",
        help="会话 thread_id，多轮需相同",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="每轮额外输出 sql / 列 / 行数等 JSON",
    )
    args = p.parse_args()

    use_interactive = args.interactive or not args.questions

    print("正在拉取 schema …", file=sys.stderr, flush=True)
    bot = Chatbot(thread_id=args.thread)
    bot.refresh_schema()

    if use_interactive:
        return run_interactive(bot, show_json=args.json)
    return run_batch(bot, list(args.questions), show_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
```