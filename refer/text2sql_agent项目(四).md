

## 依赖库
pip3 install langchain-chroma langchain-openai pypdf reportlab

# Text2SQL + RAG 运行流程图

![目录](./flow_db_rag.png)
```mermaid
flowchart TD
    A[用户提问\nscripts/functional_chat_demo.py] --> B[Chatbot.chat]
    B --> C[LangGraph: route_query]

    C --> D{RAG 可用?}
    D -- 否 --> E[route = sql\n记录 rag_error]
    D -- 是 --> F[RagEngine.route]

    F --> G{是否命中 KB 规则?}
    G -- 是 --> H[route = kb]
    G -- 否 --> E

    %% RAG 分支
    H --> I[answer_with_rag]
    I --> J[ensure_index]
    J --> K{索引存在且有数据?}
    K -- 否 --> L[load_kb_documents\n读取 txt/pdf]
    L --> M[split_documents\nfixed/sentence/paragraph/semantic]
    M --> N[Chroma.from_documents\n写入向量库]
    K -- 是 --> O[打开现有向量库]
    N --> O
    O --> P[similarity_search\n向量召回 top_k]
    P --> Q[rerank_documents\n重排 top_n]
    Q --> R[LLM 基于上下文生成答案]
    R --> S[返回 analysis + rag_context]

    %% SQL 分支
    E --> T[generate_sql\nText2SQL Agent]
    T --> U[execute_sql\nQueryExecutor]
    U --> V{执行成功?}
    V -- 否 且未达重试上限 --> W[bump_retry]
    W --> T
    V -- 否 且达到重试上限 --> X[fail]
    V -- 是 --> Y[analyze\nAnalyzer Agent]

    %% 数据库节点
    U --> DB[(PostgreSQL)]
    DB --> U

    X --> Z[返回失败说明]
    Y --> AA[返回分析结果]
```

## 补充说明

- `route=kb` 时走 RAG 路径，不会执行 SQL。
- `route=sql` 时走数据库路径：生成 SQL -> 执行 SQL -> 成功分析或失败重试。
- RAG 检索目录默认是 `outputs/rag_store/<rag_chunk_method>`。
- 若 RAG 初始化失败，会自动回退 SQL，并在状态中携带 `rag_error` 便于排查。

## 代码

### graph
```python
from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from text2sql.analyzer_agent import AnalyzerAgent
from text2sql.config import Settings, get_settings
from text2sql.query_executor import QueryExecutor
from text2sql.rag_engine import RagEngine
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
    route: str
    rag_context: list[str]
    rag_error: str | None


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
    rag: RagEngine | None = None
    rag_init_error: str | None = None
    if s.rag_enabled:
        try:
            rag = RagEngine(s)
        except Exception as e:
            rag = None
            rag_init_error = f"{type(e).__name__}: {e}"

    def route_query(state: GraphState) -> dict[str, Any]:
        if rag is None:
            return {"route": "sql", "rag_error": rag_init_error}
        uq = last_user_text(state["messages"])
        route = rag.route(uq)
        return {"route": route, "rag_error": None}

    def route_after_classifier(state: GraphState) -> Literal["rag", "sql"]:
        return "rag" if state.get("route") == "kb" else "sql"

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

    def answer_with_rag(state: GraphState) -> dict[str, Any]:
        if rag is None:
            detail = state.get("rag_error") or "unknown initialization error"
            return {
                "analysis": (
                    "当前环境 RAG 不可用，已回退为 SQL 模式。\n"
                    f"具体原因：{detail}"
                ),
                "sql": "",
                "columns": [],
                "rows": [],
                "error": f"RAG unavailable: {detail}",
                "rag_context": [],
                "messages": [AIMessage(content="当前环境 RAG 不可用，已回退为 SQL 模式。")],
            }
        uq = last_user_text(state["messages"])
        result = rag.ask(uq)
        contexts = [
            f"{d.metadata.get('source', 'unknown')} | score={d.metadata.get('rerank_score', 'n/a')}"
            for d in result.contexts
        ]
        return {
            "analysis": result.answer,
            "sql": "",
            "columns": [],
            "rows": [],
            "error": None,
            "rag_context": contexts,
            "rag_error": None,
            "messages": [AIMessage(content=result.answer)],
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
        rag_error = state.get("rag_error")
        if rag_error:
            text = (
                "提示：当前会话未启用 RAG，已自动回退 SQL 路径。\n"
                f"RAG 初始化错误：{rag_error}\n\n{text}"
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
    g.add_node("route_query", route_query)
    g.add_node("answer_with_rag", answer_with_rag)
    g.add_node("generate_sql", generate_sql)
    g.add_node("execute_sql", execute_sql)
    g.add_node("bump_retry", bump_retry)
    g.add_node("analyze", run_analyze)
    g.add_node("fail", run_fail)

    g.add_edge(START, "route_query")
    g.add_conditional_edges(
        "route_query",
        route_after_classifier,
        {
            "rag": "answer_with_rag",
            "sql": "generate_sql",
        },
    )
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
    g.add_edge("answer_with_rag", END)
    g.add_edge("analyze", END)
    g.add_edge("fail", END)

    return g

```

### rag_engine
```python
from __future__ import annotations

import json
import re
import shutil
from urllib import error as urlerror
from urllib import parse, request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from typing import cast

from text2sql.config import Settings, get_settings
from text2sql.llm_client import build_chat_model

ChunkMethod = Literal["fixed", "sentence", "paragraph", "semantic"]

try:
    from langchain_chroma import Chroma
except Exception:  # pragma: no cover
    Chroma = None  # type: ignore[assignment]

try:
    from langchain_openai import OpenAIEmbeddings
except Exception:  # pragma: no cover
    OpenAIEmbeddings = None  # type: ignore[assignment]

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore[assignment]

class ApiReranker:
    """OpenAI 兼容 rerank 客户端（优先调用 /rerank）。"""

    # 初始化 rerank 客户端配置（模型、网关地址、鉴权）。
    def __init__(self, *, model: str, base_url: str | None, api_key: str | None):
        self._model = model
        self._base_url = (base_url or "").rstrip("/")
        self._api_key = api_key or ""

    # 计算查询与候选文档的重排分数，失败时降级为词法打分。
    def predict(self, pairs: list[list[str]]) -> list[float]:
        if not pairs:
            return []
        query = pairs[0][0]
        docs = [p[1] for p in pairs]
        if not self._base_url:
            return [_lexical_score(query, doc) for doc in docs]
        try:
            return self._predict_via_api(query=query, docs=docs)
        except Exception:
            # 接口失败时兜底，保证业务不中断
            return [_lexical_score(query, doc) for doc in docs]

    # 通过兼容接口调用 /rerank 并解析返回分数。
    def _predict_via_api(self, *, query: str, docs: list[str]) -> list[float]:
        endpoint = f"{self._base_url}/rerank"
        body = json.dumps(
            {
                "model": self._model,
                "query": query,
                "documents": docs,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        req = request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
        except urlerror.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"rerank 接口错误: {e.code} {detail}") from e
        data = json.loads(raw)
        return _extract_rerank_scores(data, doc_count=len(docs))


class LengthSafeEmbeddings:
    """为有严格 token 限制的 Embedding API 提供长度保护。"""

    # 初始化带长度保护的 embedding 包装器。
    def __init__(self, backend: Any, *, max_chars: int = 380):
        self._backend = backend
        self._max_chars = max(64, max_chars)

    # 对文档列表先做截断保护，再批量计算向量。
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        safe_texts = [_truncate_for_embedding(t, max_chars=self._max_chars) for t in texts]
        return self._backend.embed_documents(safe_texts)

    # 对查询文本先做截断保护，再计算向量。
    def embed_query(self, text: str) -> list[float]:
        safe_text = _truncate_for_embedding(text, max_chars=self._max_chars)
        return self._backend.embed_query(safe_text)


@dataclass(frozen=True)
class RagResult:
    answer: str
    route: str
    contexts: list[Document]


class RagEngine:
    _ROUTER_SYSTEM = """你是查询路由器，只返回 JSON。
任务：把用户问题路由到 "sql" 或 "kb"。

规则：
1) 若问题明确要求数据库实时统计、订单明细、按字段筛选，优先 "sql"；
2) 若问题是政策、复盘、规划、培训、年度报告、未来年份(>=2026)经营结论，优先 "kb"；
3) 输出格式必须是 {"route":"sql"} 或 {"route":"kb"}。"""

    _QA_SYSTEM = """你是企业经营知识库问答助手。请基于给定检索片段回答：
- 先给简明结论，再给依据；
- 若证据不足要明确说明；
- 禁止编造不存在的事实。"""

    # 初始化 RAG 引擎及其 embedding、rerank 等核心组件。
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._llm = build_chat_model(self._settings)
        self._kb_dir = self._resolve_path(self._settings.rag_kb_dir)
        self._store_dir = self._resolve_path(self._settings.rag_store_dir)
        self._require_rag_deps()
        embedding_api_key = (
            self._settings.rag_embedding_api_key or self._settings.llm_api_key or "not-set"
        )
        embedding_base_url = self._settings.rag_embedding_base_url or self._settings.llm_base_url
        self._embedding_max_chars = min(380, max(64, self._settings.rag_chunk_size))
        raw_embeddings = OpenAIEmbeddings(
            model=self._settings.rag_embedding_model,
            api_key=embedding_api_key,
            base_url=_join_openai_base_url(embedding_base_url),
            request_timeout=self._settings.rag_embedding_timeout_seconds,
            max_retries=self._settings.rag_embedding_max_retries,
            chunk_size=self._settings.rag_embedding_batch_size,
        )
        self._embeddings = LengthSafeEmbeddings(
            raw_embeddings,
            max_chars=self._embedding_max_chars,
        )
        self._reranker = ApiReranker(
            model=self._settings.rag_rerank_model,
            base_url=self._settings.rag_rerank_base_url or self._settings.llm_base_url,
            api_key=self._settings.rag_rerank_api_key or self._settings.llm_api_key,
        )

    # 校验 RAG 运行所需第三方依赖是否可用。
    @staticmethod
    def _require_rag_deps() -> None:
        if not all([Chroma, OpenAIEmbeddings, PdfReader]):
            raise RuntimeError(
                "RAG 依赖未安装，请先安装: langchain-chroma, langchain-openai, pypdf"
            )

    # 将配置中的相对/绝对路径统一解析为绝对路径。
    @staticmethod
    def _resolve_path(path: str) -> Path:
        p = Path(path).expanduser()
        if p.is_absolute():
            return p
        return (Path(__file__).resolve().parents[1] / p).resolve()

    # 按切分策略构建或复用向量索引。
    def ensure_index(self, *, method: ChunkMethod | None = None, force_rebuild: bool = False) -> None:
        split_method = method or self._settings.rag_chunk_method
        index_dir = self._store_dir / split_method
        if force_rebuild and index_dir.exists():
            shutil.rmtree(index_dir, ignore_errors=True)
        if index_dir.exists() and self._index_has_data(split_method):
            return
        docs = self.load_kb_documents()
        chunks = split_documents(
            docs,
            method=split_method,
            chunk_size=self._settings.rag_chunk_size,
            overlap=self._settings.rag_chunk_overlap,
            embeddings=self._embeddings,
            embedding_max_chars=self._embedding_max_chars,
        )
        if not chunks:
            raise RuntimeError(
                "知识库切分后无可用 chunk，请检查 RAG_KB_DIR 下是否有非空 txt/pdf 文档"
            )
        self._precheck_embedding_api()
        index_dir.mkdir(parents=True, exist_ok=True)
        cast(Any, Chroma).from_documents(
            documents=chunks,
            embedding=self._embeddings,
            persist_directory=str(index_dir),
        )

    # 暴露 embedding 对象供外部复用。
    @property
    def embeddings(self) -> Any:
        return self._embeddings

    # 获取对应切分策略的向量库句柄（必要时先建索引）。
    def _get_store(self, *, method: ChunkMethod | None = None) -> Any:
        split_method = method or self._settings.rag_chunk_method
        self.ensure_index(method=split_method)
        return cast(Any, Chroma)(
            persist_directory=str(self._store_dir / split_method),
            embedding_function=self._embeddings,
        )

    # 检查某个索引目录是否存在且包含有效向量数据。
    def _index_has_data(self, method: ChunkMethod) -> bool:
        index_dir = self._store_dir / method
        if not index_dir.exists():
            return False
        try:
            store = cast(Any, Chroma)(
                persist_directory=str(index_dir),
                embedding_function=self._embeddings,
            )
            collection = getattr(store, "_collection", None)
            if collection is None:
                return False
            count = int(collection.count())
            return count > 0
        except Exception:
            return False

    # 将用户问题路由到 SQL 或知识库问答链路。
    def route(self, question: str) -> str:
        if not self._settings.rag_enabled:
            return "sql"
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", question)]
        if years and max(years) >= self._settings.rag_router_year_threshold:
            return "kb"
        resp = self._llm.invoke(
            [
                SystemMessage(content=self._ROUTER_SYSTEM),
                HumanMessage(content=f"用户问题：{question}"),
            ]
        )
        raw = str(resp.content if hasattr(resp, "content") else resp)
        if '"route":"kb"' in raw.replace(" ", "").lower():
            return "kb"
        return "sql"

    # 预检查 embedding 接口连通性，提前暴露配置问题。
    def _precheck_embedding_api(self) -> None:
        try:
            self._embeddings.embed_query("ping")
        except Exception as e:
            raise RuntimeError(
                "Embedding API 连通性检查失败，请检查网络/网关地址/超时设置。"
                f" base_url={self._settings.rag_embedding_base_url or self._settings.llm_base_url},"
                f" timeout={self._settings.rag_embedding_timeout_seconds}s,"
                f" retries={self._settings.rag_embedding_max_retries},"
                f" batch={self._settings.rag_embedding_batch_size}. 详细错误: {e}"
            ) from e

    # 执行知识库检索、重排并生成最终回答。
    def ask(self, question: str) -> RagResult:
        store = self._get_store()
        candidates = store.similarity_search(question, k=self._settings.rag_top_k)
        ranked = rerank_documents(
            query=question,
            docs=candidates,
            reranker=self._reranker,
            top_n=self._settings.rag_top_n,
        )
        context_text = "\n\n".join(
            f"[片段{i + 1}] {d.page_content}" for i, d in enumerate(ranked)
        )
        prompt = f"用户问题：{question}\n\n检索上下文：\n{context_text}"
        resp = self._llm.invoke(
            [
                SystemMessage(content=self._QA_SYSTEM),
                HumanMessage(content=prompt),
            ]
        )
        answer = str(resp.content if hasattr(resp, "content") else resp).strip()
        return RagResult(answer=answer, route="kb", contexts=ranked)

    # 扫描知识库目录并加载 txt/pdf 文档内容。
    def load_kb_documents(self) -> list[Document]:
        docs: list[Document] = []
        if not self._kb_dir.exists():
            return docs
        for p in sorted(self._kb_dir.glob("**/*")):
            if p.suffix.lower() not in {".txt", ".pdf"} or not p.is_file():
                continue
            text = self._read_text_file(p) if p.suffix.lower() == ".txt" else self._read_pdf(p)
            if not text.strip():
                continue
            docs.append(
                Document(
                    page_content=text,
                    metadata={"source": str(p), "file_type": p.suffix.lower()},
                )
            )
        return docs

    # 读取 UTF-8 文本文件内容。
    @staticmethod
    def _read_text_file(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    # 读取 PDF 每页文本并合并为单一字符串。
    @staticmethod
    def _read_pdf(path: Path) -> str:
        reader = cast(Any, PdfReader)(str(path))
        texts: list[str] = []
        for page in reader.pages:
            texts.append(page.extract_text() or "")
        return "\n".join(texts)


# 将文档集合按指定策略切分为可入库的 chunk 文档。
def split_documents(
    docs: list[Document],
    *,
    method: ChunkMethod,
    chunk_size: int,
    overlap: int,
    embeddings: Any,
    embedding_max_chars: int | None = None,
) -> list[Document]:
    chunked: list[Document] = []
    for doc in docs:
        text = doc.page_content.strip()
        if not text:
            continue
        parts = split_text(
            text=text,
            method=method,
            chunk_size=chunk_size,
            overlap=overlap,
            embeddings=embeddings,
        )
        safe_parts = _split_for_embedding_limit(
            parts,
            max_chars=embedding_max_chars or chunk_size,
            overlap=min(overlap, max(0, (embedding_max_chars or chunk_size) // 8)),
        )
        for idx, part in enumerate(safe_parts):
            chunked.append(
                Document(
                    page_content=part,
                    metadata={**doc.metadata, "chunk_method": method, "chunk_index": idx},
                )
            )
    return chunked


# 根据切分方法分发到具体的文本切分实现。
def split_text(
    *,
    text: str,
    method: ChunkMethod,
    chunk_size: int,
    overlap: int,
    embeddings: Any,
) -> list[str]:
    if method == "fixed":
        return _fixed_chunks(text, chunk_size=chunk_size, overlap=overlap)
    if method == "sentence":
        return _sentence_chunks(text, chunk_size=chunk_size, overlap=overlap)
    if method == "paragraph":
        return _paragraph_chunks(text, chunk_size=chunk_size, overlap=overlap)
    return _semantic_chunks(text, chunk_size=chunk_size, overlap=overlap, embeddings=embeddings)


# 按固定窗口大小与重叠比例进行字符级切分。
def _fixed_chunks(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    out: list[str] = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(text), step):
        seg = text[i : i + chunk_size].strip()
        if seg:
            out.append(seg)
    return out


# 基于中英文标点与换行进行句子切分。
def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;.\n])\s*", text)
    return [p.strip() for p in parts if p.strip()]


# 先切句再按目标窗口打包为 chunk。
def _sentence_chunks(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    sentences = _split_sentences(text)
    return _pack_units(sentences, chunk_size=chunk_size, overlap=overlap)


# 先按段落切分再按目标窗口打包为 chunk。
def _paragraph_chunks(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return _pack_units(paragraphs, chunk_size=chunk_size, overlap=overlap)


# 将语义单元按 chunk_size 合并并处理 overlap 衔接。
def _pack_units(units: list[str], *, chunk_size: int, overlap: int) -> list[str]:
    out: list[str] = []
    cur = ""
    for unit in units:
        candidate = f"{cur}\n{unit}".strip() if cur else unit
        if len(candidate) <= chunk_size:
            cur = candidate
            continue
        if cur:
            out.append(cur)
        if overlap > 0 and out:
            tail = out[-1][-overlap:]
            cur = f"{tail}\n{unit}".strip()
        else:
            cur = unit
    if cur:
        out.append(cur)
    return out


# 利用相邻句 embedding 相似度做语义分组后再打包。
def _semantic_chunks(
    text: str,
    *,
    chunk_size: int,
    overlap: int,
    embeddings: Any,
) -> list[str]:
    sentences = _split_sentences(text)
    if len(sentences) <= 2:
        return _sentence_chunks(text, chunk_size=chunk_size, overlap=overlap)
    vecs = embeddings.embed_documents(sentences)
    sims: list[float] = []
    for i in range(len(vecs) - 1):
        a, b = vecs[i], vecs[i + 1]
        denom = (_norm(a) * _norm(b)) or 1e-9
        sims.append(_dot(a, b) / denom)
    threshold = sorted(sims)[max(0, int(len(sims) * 0.25) - 1)] if sims else 0.6
    groups: list[list[str]] = [[sentences[0]]]
    for i in range(1, len(sentences)):
        sim = sims[i - 1] if i - 1 < len(sims) else 1.0
        if sim < threshold:
            groups.append([sentences[i]])
        else:
            groups[-1].append(sentences[i])
    units = [" ".join(g).strip() for g in groups if g]
    return _pack_units(units, chunk_size=chunk_size, overlap=overlap)


# 对召回文档进行重排并返回 top_n 结果。
def rerank_documents(
    *,
    query: str,
    docs: list[Document],
    reranker: CrossEncoder,
    top_n: int,
) -> list[Document]:
    if not docs:
        return []
    pairs = [[query, d.page_content] for d in docs]
    scores = reranker.predict(pairs)
    ranked = sorted(
        zip(docs, scores, strict=False),
        key=lambda x: float(x[1]),
        reverse=True,
    )
    out: list[Document] = []
    for doc, score in ranked[:top_n]:
        meta = dict(doc.metadata)
        meta["rerank_score"] = float(score)
        out.append(Document(page_content=doc.page_content, metadata=meta))
    return out


# 规范化 OpenAI 兼容 base_url，确保包含 /v1。
def _join_openai_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    parsed = parse.urlparse(base_url)
    if not parsed.scheme:
        return base_url
    if parsed.path.rstrip("/").endswith("/v1"):
        return base_url
    trimmed = base_url.rstrip("/")
    return f"{trimmed}/v1"


# 从 rerank 响应中提取并对齐各文档分数。
def _extract_rerank_scores(payload: dict[str, Any], *, doc_count: int) -> list[float]:
    raw_results = payload.get("results") or payload.get("data") or []
    if not isinstance(raw_results, list):
        raise RuntimeError("rerank 响应格式异常：results/data 不是列表")
    scores = [0.0] * doc_count
    found = False
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        score = item.get("relevance_score", item.get("score"))
        if isinstance(idx, int) and 0 <= idx < doc_count and score is not None:
            scores[idx] = float(score)
            found = True
    if not found:
        raise RuntimeError("rerank 响应格式异常：未解析到任何分数")
    return scores


# 使用 token 交并比计算简易词法相关性分数。
def _lexical_score(query: str, doc: str) -> float:
    q_tokens = {t for t in re.split(r"\W+", query.lower()) if t}
    d_tokens = {t for t in re.split(r"\W+", doc.lower()) if t}
    if not q_tokens or not d_tokens:
        return 0.0
    inter = len(q_tokens & d_tokens)
    union = len(q_tokens | d_tokens)
    return float(inter / union) if union else 0.0


# 将文本截断到 embedding 可接受长度上限。
def _truncate_for_embedding(text: str, *, max_chars: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars]


# 将超长分片进一步拆分，避免超过 embedding 输入限制。
def _split_for_embedding_limit(parts: list[str], *, max_chars: int, overlap: int) -> list[str]:
    out: list[str] = []
    for part in parts:
        text = part.strip()
        if not text:
            continue
        if len(text) <= max_chars:
            out.append(text)
            continue
        out.extend(_fixed_chunks(text, chunk_size=max_chars, overlap=overlap))
    return out


# 计算两个向量的点积。
def _dot(a: list[float], b: list[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b, strict=False)))


# 计算向量的 L2 范数。
def _norm(a: list[float]) -> float:
    return float(sum(x * x for x in a) ** 0.5)

```

### build_rag_kb
```python
# export RAG_EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
# export RAG_EMBEDDING_API_KEY=sk-ecwdspxzfiaqlfrpiyffvvolugfzapmtxhpobrkkmhlvlzxb
# export RAG_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
# export RAG_RERANK_BASE_URL=https://api.siliconflow.cn/v1
# export RAG_RERANK_API_KEY=sk-ecwdspxzfiaqlfrpiyffvvolugfzapmtxhpobrkkmhlvlzxb
# export RAG_RERANK_MODEL=BAAI/bge-reranker-v2-m3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

# 保证从项目根目录可导入 text2sql（支持在任意 cwd 运行）
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from text2sql.config import get_settings
from text2sql.rag_engine import RagEngine, split_documents


def build_pdf_from_txt(txt_path: Path, pdf_path: Path) -> None:
    text = txt_path.read_text(encoding="utf-8")
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    c.setFont("STSong-Light", 11)
    width, height = A4
    y = height - 40
    for line in text.splitlines():
        if y < 40:
            c.showPage()
            c.setFont("STSong-Light", 11)
            y = height - 40
        c.drawString(40, y, line[:80])
        y -= 16
    c.save()


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 RAG 知识库文档与索引")
    parser.add_argument(
        "--chunk-method",
        "--chunk_method",
        choices=["fixed", "sentence", "paragraph", "semantic"],
        default=None,
        help="切分策略（默认取配置）",
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="仅打印切分预览，不创建向量库",
    )
    args = parser.parse_args()

    settings = get_settings()
    engine = RagEngine(settings)
    print(
        "[INFO] Embedding API 参数: "
        f"base_url={settings.rag_embedding_base_url or settings.llm_base_url}, "
        f"timeout={settings.rag_embedding_timeout_seconds}s, "
        f"retries={settings.rag_embedding_max_retries}, "
        f"batch={settings.rag_embedding_batch_size}"
    )
    kb_dir = Path(settings.rag_kb_dir).resolve()
    kb_dir.mkdir(parents=True, exist_ok=True)

    txt_path = kb_dir / "sales_strategy_2026_2027.txt"
    if not txt_path.exists():
        raise FileNotFoundError(f"请先准备文本知识库文件：{txt_path}")

    pdf_path = kb_dir / "sales_strategy_2026_2027.pdf"
    build_pdf_from_txt(txt_path, pdf_path)
    print(f"[OK] 生成 PDF：{pdf_path}")

    method = args.chunk_method or settings.rag_chunk_method
    docs = engine.load_kb_documents()
    chunks = split_documents(
        docs,
        method=method,
        chunk_size=settings.rag_chunk_size,
        overlap=settings.rag_chunk_overlap,
        embeddings=engine.embeddings,
    )
    print(f"[INFO] 切分方式={method}, 文档数={len(docs)}, chunk 数={len(chunks)}")
    for i, c in enumerate(chunks[:3], start=1):
        print(f"[chunk-{i}] {c.page_content[:120].replace(chr(10), ' ')}...")

    if not args.preview_only:
        engine.ensure_index(method=method)
        print(f"[OK] 向量索引已构建：{Path(settings.rag_store_dir).resolve() / method}")


if __name__ == "__main__":
    main()
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
            "route": "",
            "rag_context": [],
            "rag_error": None,
        }
        cfg: dict[str, Any] = {"configurable": {"thread_id": self._thread_id}}
        # 合并 checkpoint：新输入用 add_messages 追加
        out = self._app.invoke(init, cfg)
        return out

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
    analyzer_skills_dir: str = Field(
        default="skills",
        description="skills 根目录，按 <skill>/SKILL.md 组织",
    )
    analyzer_enable_skill_tools: bool = Field(
        default=True,
        description="是否启用分析阶段的 skill 外部工具调用",
    )

    rag_enabled: bool = Field(default=True, description="是否启用 RAG 路由")
    rag_kb_dir: str = Field(default="knowledge_base", description="知识库文档目录")
    rag_store_dir: str = Field(default="outputs/rag_store", description="向量库目录")
    rag_chunk_method: Literal["fixed", "sentence", "paragraph", "semantic"] = Field(
        default="semantic",
        description="切分方式：fixed|sentence|paragraph|semantic",
    )
    rag_chunk_size: int = Field(default=500, ge=50, le=4000)
    rag_chunk_overlap: int = Field(default=80, ge=0, le=1000)
    rag_top_k: int = Field(default=12, ge=1, le=50, description="向量召回候选数")
    rag_top_n: int = Field(default=5, ge=1, le=20, description="重排后保留数")
    rag_embedding_model: str = Field(
        default="BAAI/bge-small-zh-v1.5",
        description="Embedding API 模型名（建议填写服务商已托管模型）",
    )
    rag_rerank_model: str = Field(
        default="BAAI/bge-reranker-v2-m3",
        description="Rerank API 模型名（建议填写服务商已托管模型）",
    )
    rag_embedding_api_key: str | None = Field(default=None, description="Embedding API Key")
    rag_embedding_base_url: str | None = Field(
        default=None,
        description="Embedding API Base URL（OpenAI 兼容）",
    )
    rag_embedding_timeout_seconds: int = Field(
        default=20,
        ge=3,
        le=300,
        description="Embedding API 超时秒数（避免长时间卡住）",
    )
    rag_embedding_max_retries: int = Field(
        default=1,
        ge=0,
        le=10,
        description="Embedding API 最大重试次数",
    )
    rag_embedding_batch_size: int = Field(
        default=8,
        ge=1,
        le=128,
        description="Embedding 批量大小（越小越稳，越大越快）",
    )
    rag_rerank_api_key: str | None = Field(default=None, description="Rerank API Key")
    rag_rerank_base_url: str | None = Field(
        default=None,
        description="Rerank API Base URL（优先调用 /rerank）",
    )
    rag_rerank_fallback_model: str = Field(
        default="qwen-plus",
        description="当 /rerank 不可用时，回退使用的廉价聊天模型",
    )
    rag_router_year_threshold: int = Field(
        default=2026,
        description="查询年份 >= 该值时优先走知识库",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def resolve_llm_base_url(settings: Settings) -> str:
    if settings.llm_base_url:
        return settings.llm_base_url
    return _DEFAULT_BASE_URLS.get(settings.llm_provider, _DEFAULT_BASE_URLS["openai"])

```
## 运行脚本
```
python3 scripts/build_rag_kb.py --chunk_method fixed
python3 scripts/functional_chat_demo.py --json "请总结2026年经营规划重点"
```

## 存储结果
- chroma.sqlite这是 Chroma 的元数据库。主要存集合信息、文档 ID、metadata、分片/segment 映射、版本信息等结构化数据。可以理解为“目录和账本”：告诉系统有哪些 collection、每条记录属于哪里、用什么索引

- data_level0.bin：存底层层级的向量节点数据（可理解为主数据区之一）

- 配套的 header.bin、length.bin、link_lists.bin：存索引参数、长度信息、图连接关系等


## 可优化点
- route(把业务逻辑给到router，知识库metadata)
- 切分方式
- rerank(topk选择)
- multi query
- 分解子问题
- 父子文档（选做）
- CRAG(选做)