# MemPalace 接口

## 1. MemPalace 在本项目里做什么

- **Palace**：一个目录，里面是 **ChromaDB** 持久化数据（向量 + 元数据）。
- **Drawer**：一条可被语义检索的文本块；我们用 `collection.upsert` 写入。
- **Wing / Room**：MemPalace 用来过滤检索的元数据字段；一般约定为：
  - `wing` → 用户 ID（例如 `u_demo`）
  - `room` → 记忆层 `L1`（情景）或 `L2`（程序性）
- **检索**：使用 `search_memories`，内部会做向量检索 + 混合排序等。

更完整的概念（宫殿、房间、抽屉等）见官方文档：[The Palace](https://mempalaceofficial.com/concepts/the-palace.html)。

---

## 2. 环境准备

```bash
pip install mempalace chromadb
```

首次仅使用 **MemPalace 默认 `get_collection`** 做向量写入/检索时，通常会**自动拉取默认的本地 embedding 模型**（体积约几百 MB）。

若运行本仓库的 **`scripts/mempalace_tutorial_demo.py`（与 RAG 一致的云端 embedding）**，还需安装：

```bash
pip install langchain-chroma langchain-openai
```

并在 `.env` 中配置 `LLM_API_KEY`、`RAG_EMBEDDING_MODEL` 等。

---

## 3. 本项目用到的两个 API

### 3.1 `mempalace.palace.get_collection`

**作用**：打开（或创建）palace 目录下的**主抽屉集合**，得到可 `upsert` / `query` 的集合对象。

```python
from pathlib import Path
from mempalace.palace import get_collection

palace_path = Path("./outputs/my_palace").resolve()
palace_path.mkdir(parents=True, exist_ok=True)

collection = get_collection(str(palace_path), create=True)
```

- **`palace_path`**：palace 根目录的字符串路径。
- **`create=True`**：若不存在则创建；只读检索时可改为 `create=False`（与官方 CLI `mempalace search` 行为一致）。

### 3.2 `mempalace.searcher.search_memories`

**作用**：对 palace 做**程序化语义检索**（返回 `dict`，适合接到应用里）。

```python
from mempalace.searcher import search_memories

out = search_memories(
    query="用户喜欢什么样的回答",
    palace_path=str(palace_path),
    wing="u_demo",      # 可选：只查该 wing
    room="L2",          # 可选：只查该 room
    n_results=5,
)
```

**常见返回结构**（以官方 Python API 为准，字段名可能随版本微调）：

| 键 | 含义 |
|----|------|
| `query` | 本次查询文本 |
| `filters` | 使用的 `wing` / `room` 过滤 |
| `results` | 列表，每条含 `text`、`similarity`、`distance` 及与 drawer 相关的元信息 |
| `error` | 若 palace 不存在等，会出现错误说明 |

检索结果里**不保证**带回写入时的完整 `metadatas`（取决于版本与实现），因此本仓库在**正文**里冗余写了 `[memory_id=...]`、`[时间]`、`[标签]` 便于解析与展示。

---

## 4. 写入一条 Drawer（与 `text2sql/user_memory.py` 一致）

要点：

1. **`ids`**：唯一字符串，本项目用 `mem_xxx` 或自定义 drawer id。
2. **`documents`**：被 embedding 的文本；建议把需在检索结果里稳定读出的字段写进正文。
3. **`metadatas`**：与 MemPalace 过滤、展示相关的字段；**至少**建议包含 `wing`、`room`、`source_file`、`chunk_index`，并与官方 mining 习惯对齐（本项目单条记忆 `chunk_index=0`）。

```python
from mempalace.palace import get_collection

col = get_collection(str(palace_path), create=True)
memory_id = "mem_abc123"
user_id = "u_demo"
layer = "L2"  # 或 "L1"
content = "用户偏好：回答尽量简短。"
time_iso = "2026-05-15T10:00:00+08:00"
tags_csv = "habit,work"

doc = f"""[memory_id={memory_id}]
{content.strip()}

[时间] {time_iso}
[标签] {tags_csv}
"""

meta = {
    "wing": user_id,
    "room": layer,
    "source_file": f"memory://{memory_id}",
    "chunk_index": 0,
    "normalize_version": 2,
    "memory_id": memory_id,
    "user_id": user_id,
    "layer": layer,
    "time": time_iso,
    "tags": tags_csv,
}

col.upsert(ids=[memory_id], documents=[doc], metadatas=[meta])
```

---

## 5. 一键运行仓库自带示例（云端 Embedding）

脚本 `scripts/mempalace_tutorial_demo.py` 已与 **RAG 相同**：使用 `OpenAIEmbeddings`（`RAG_EMBEDDING_*` / `LLM_*`）+ `langchain_chroma.Chroma`；**不再调用** `mempalace.get_collection`。

运行后进入**交互式**自然语言对话：每轮自动读取项目根 `MEMORY.md`（若存在），并对 **L1 / L2** 做向量检索后注入系统提示；回复结束后由 **`MemoryCommitAgent`**（与主图 `commit_memory` 同源）决定是否写入新记忆。空库时默认写入一条示例 L2（`--no-seed-example` 可跳过）。

```bash
cd /path/to/text2sql_project
python3 scripts/mempalace_tutorial_demo.py
```

默认向量库目录：`outputs/mempalace_tutorial_cloud_emb/`（相对项目根，**勿**与 MemPalace 官方 palace 目录混用）。

运行前请在 `.env` 中配置与主项目一致的 **Embedding** 与 **聊天模型**（如 `LLM_API_KEY`、`LLM_MODEL`、`RAG_EMBEDDING_MODEL`，以及按需的 `RAG_EMBEDDING_BASE_URL` / `LLM_BASE_URL`）。

常用参数：

```bash
python3 scripts/mempalace_tutorial_demo.py --user-id u_alice
python3 scripts/mempalace_tutorial_demo.py --no-seed-example --no-memory-write
python3 scripts/mempalace_tutorial_demo.py --store-dir /tmp/tutorial_chroma
```

---

## 6. 进一步学习（官方）

- Python API 总览：[Python API | MemPalace](https://mempalaceofficial.com/reference/python-api.html)
- CLI（`mempalace init` / `mine` / `search`）：[CLI 参考](https://mempalaceofficial.com/reference/cli.html)
