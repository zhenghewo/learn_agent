## 常见框架
- mem0 
- mempalace
- ReMe


## mem设计

以ReMe为例（CoPaw）:

### 存储方式
文件 + 向量数据库 （为何使用文件：利用本身的文件系统, 用户友好/随用户项目绑定）
(BM25 / TF-IDF)

- MEMORY.md
- memory/每日日志 （markdown可压缩）
- sessions/序列化的消息记录 (json)

- sessions里的消息会更新，会压缩覆盖之前的信息

{
    "content": [最新内容]
    "compressed_summary": [压缩内容]
}
 memory的压缩信息会存到向量数据库（自身保存了完整内容）

 memory_search -> 混合检索（BM25+向量库混合）


### 写入文件

- 异步写入md
- filewatcher 异步写入向量数据库