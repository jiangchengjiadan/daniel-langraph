# 文档 RAG 与 Deep Research 工作台

基于 LangChain + Deep Agents 的文档工作台，支持 PPT、PDF、文本和图片格式。系统同时提供两种能力：

- **问答模式**：基于 RAG 的文档问答，返回带来源和图片的回答
- **研究模式**：围绕一个开放式研究任务，自动生成计划、证据和研究报告

## 特性

- **多格式支持**:
  - PPT/PPTX: 自动提取文本和图片
  - PDF: 提取文档文本内容
  - 文本文件: 支持 .txt, .md, .log 等格式
  - 图片: 支持 .jpg, .png, .gif 等格式，使用 Vision API 分析内容
- **标题生成**: LLM 为无标题页面生成标题
- **图片处理**: 提取图片保存到本地，通过 ImageServer 提供 HTTP 访问
- **页面合并**: LLM 判定连续页面是否合并 + 手动标记 (`<START_BLOCK>`/`<END_BLOCK>`)，合并连续的相关页面（父子分块架构）
- **父子分块**:
   - Child: 每页内容 → FAISS 向量库
   - Parent: 合并内容 → DocStore (JSON 文件)
- **混合检索**: BM25 关键词 + Vector 语义搜索，可动态调整权重
- **图文并茂**: 回答中保留 Markdown 图片链接
- **参考来源**: 清晰标注参考页码
- **双工作模式**:
  - 问答模式：适合快速查文档
  - 研究模式：适合生成任务计划、证据文件和 Markdown 报告
- **研究产物可见**:
  - `task.md`
  - `documents_overview.md`
  - `plan.md`
  - `evidence/q*.md`
  - `drafts/report_v1.md`
  - `quality_report.md`
  - `final/final_report.md`
- **Deep Agents 接入**:
  - 顶层由 Deep Agents 驱动研究任务
  - 主路径采用高层 `run_research_once` 工具保证收敛
  - 注册了 `document_analyst`、`evidence_collector`、`report_writer` 子代理作为补充能力


## 技术栈

| 组件 | 选择 |
|------|------|
| LLM 框架 | LangChain |
| Agent Harness | Deep Agents |
| LLM 模型 | OpenAI API 兼容接口 |
| Embeddings | OpenAI Embeddings (兼容接口) |
| 向量库 | FAISS |
| DocStore | LocalFileStore (JSON 文件) |
| 前端 | Streamlit |
| 图片存储 | 本地 HTTP 服务器 |

## 架构

```mermaid
graph TD
    A[文档上传] --> B{文件类型}
    B -->|PPT/PPTX| C[PPT Parser]
    B -->|PDF| D[PDF Parser]
    B -->|Text| E[Text Parser]
    B -->|Image| F[Image Parser]
    C --> G[文本提取]
    C --> H[图片提取]
    D --> G
    E --> G
    F --> I[Vision API 分析]
    I --> G
    H --> J[上传到图片服务器]
    G --> K[标题生成]
    J --> K
    K --> L[页面合并判断]
    L --> M[分块]
    M --> N[存储]
    N --> O[FAISS 向量库]
    N --> P[DocStore 父块]
    O --> Q[混合检索 BM25+Vector]
    P --> Q
    Q --> R[LLM 回答生成]
    R --> S[问答模式]
    Q --> T[Deep Research Service]
    T --> U[Deep Agents Orchestrator]
    U --> V[研究计划/证据/报告]
    V --> W[研究模式]
```

## Deep Research 架构补充

研究模式不是简单把用户问题直接喂给 LLM，而是先通过知识服务层做文档理解与证据收集，再由研究协调器输出工作区产物。

```mermaid
flowchart TD
    A["研究任务"] --> B["DeepResearchAgent"]
    B --> C["write_todos 制定计划"]
    C --> D["run_research_once 高层工具"]
    D --> E["DocumentKnowledgeService"]
    E --> F["list_documents / search_evidence / get_page_content"]
    F --> G["DeepResearchService"]
    G --> H["task.md / plan.md / evidence/*.md"]
    G --> I["drafts/report_v1.md"]
    G --> J["quality_report.md"]
    G --> K["final/final_report.md"]
```

相关设计文档：

- [Deep Research 技术方案](/Users/danielhe/enviroment/server/workspace/daniel-langraph/pptx-rag/docs/deep-research-agent-technical-design.md:1)
- [Deep Research 任务清单](/Users/danielhe/enviroment/server/workspace/daniel-langraph/pptx-rag/docs/deep-research-agent-task-list.md:1)

## 目录结构

```
pptx-rag/
├── app/                    # Streamlit 前端
│   └── streamlit_app.py    # 主应用入口
├── src/                    # 核心代码
│   ├── config.py           # 配置管理
│   ├── models.py           # Pydantic 数据模型
│   ├── logging.py          # 日志配置
│   ├── parser/             # 文档解析层
│   │   ├── base_parser.py  # 解析器基类
│   │   ├── pptx_parser.py  # PPT 解析
│   │   ├── pdf_parser.py   # PDF 解析
│   │   ├── text_parser.py  # 文本解析
│   │   ├── image_parser.py # 图片解析
│   │   └── image_handler.py # 图片处理
│   ├── processor/          # 内容处理层
│   │   ├── title_generator.py   # 标题生成
│   │   ├── chunking.py           # 子块创建
│   │   ├── merger.py             # 页面合并判断
│   │   └── parent_builder.py     # 父块构建
│   ├── storage/            # 存储层
│   │   ├── vector_store.py # FAISS 向量库
│   │   └── doc_store.py    # 父块文档存储
│   ├── retriever/          # 检索层
│   │   ├── hybrid_retriever.py  # 混合检索
│   │   └── parent_retriever.py  # 父块检索
│   ├── rag/                # RAG 问答链
│   │   └── chain.py        # 问答模式主处理链
│   ├── services/           # 可复用知识服务层
│   │   └── document_knowledge.py
│   ├── deep_research/      # Deep Research 模块
│   │   ├── agent.py
│   │   ├── services.py
│   │   ├── tools.py
│   │   ├── quality.py
│   │   ├── workspace.py
│   │   ├── prompts.py
│   │   └── schemas.py
│   └── server/             # 服务
│       └── image_server.py # 图片 HTTP 服务器
├── data/                   # 数据目录
│   ├── uploads/            # 上传文件
│   ├── images/             # 图片存储
│   ├── chunks/             # 父块 JSON 文件
│   ├── indexes/            # FAISS 索引
│   └── logs/               # 日志文件
├── tests/
├── .env                    # 环境配置
├── requirements.txt
└── README.md
```

## 安装

```bash
cd pptx-rag

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置 API 密钥（见下方配置部分）
```

如果你本地已经使用 `conda` 管理环境，也可以直接在现有环境里安装新增依赖。

## 配置

复制 `.env.example` 为 `.env` 并修改：

```env
# API 配置 (OpenAI 兼容接口)
API_BASE_URL=https://api.openai.com/v1  # 或你的自定义 API 端点
API_KEY=sk-your-api-key-here
LLM_MODEL=gpt-4  # 或你的自定义模型名称
EMBEDDING_MODEL=text-embedding-3-large  # 或你的自定义 embedding 模型

# 数据目录
DATA_DIR=./data

# 图片服务端口
IMAGE_SERVER_PORT=8080

# 检索设置
RETRIEVAL_K=2
RETRIEVAL_K_MULTIPLIER=2

# 检索权重 (BM25 + Vector = 1.0)
BM25_WEIGHT=0.4
VECTOR_WEIGHT=0.6

# LLM 设置
LLM_TEMPERATURE=0.1
LLM_NUM_CTX=4096
LLM_NUM_PREDICT=2048
```

**支持的 API 接口：**
- OpenAI 官方 API
- 阿里云通义千问 (DashScope)
- 智谱 AI (GLM)
- 任何 OpenAI 兼容的 API 端点

## 使用

```bash
# 启动应用
streamlit run app/streamlit_app.py
```

访问 `http://localhost:8501` 即可使用。

### 使用流程

1. **上传文档**: 侧边栏上传文档文件（支持 PPT、PDF、文本、图片）
2. **自动处理**: 点击"处理文档"，系统自动解析、提取内容
3. **选择模式**:
   - 问答模式：直接提问
   - 研究模式：输入研究任务并选择文档范围
4. **查看结果**:
   - 问答模式：获得图文并茂的回答和参考来源
   - 研究模式：查看计划、证据、质量检查和最终报告

### 研究模式验证

进入“研究模式”后，可以选择一个或多个已处理文档，然后输入类似任务：

- `请总结 PLC 故障判断培训文档中与电源故障诊断相关的要点，生成一份简短研究报告。`
- `请对比文档中 S7-200 和 S7-300 的结构差异，并输出一份培训版讲义。`
- `请整理与 PLC 指示灯判断有关的内容，保留关键图片和页码来源。`

当前页面会显示：

- `execution_mode`
- `execution_note`
- 研究计划
- 证据文件
- 最终报告

正常情况下，Deep Agents 路径会返回 `execution_mode=deepagents`。

### 示例问题（PLC故障判断培训.pptx）

仓库根目录包含示例文档 `PLC故障判断培训.pptx`。处理该文档后，可以尝试以下问题验证检索、父子分块和图片召回效果：

- `PLC系统中 S7-200 和 S7-300 系列分别用在哪些设备上？请结合图片说明它们的主要模块和指示灯。`
- `PLC运行故障诊断时，需要重点查看哪些指示灯？如果有相关示意图，请一起展示。`
- `PLC电源故障诊断应该关注哪些位置？请引用文档中的图片辅助说明。`
- `PLC系统架构示例包含哪些组成部分？请按第14到16页的内容总结，并保留相关架构图片。`
- `当机台启动后，如何通过输入输出指示灯判断是PLC模块问题还是现场连接问题？`
- `请总结这份PLC故障判断培训文档中，PLC现状、系统架构和故障诊断三部分的核心内容。`

### 用户提问后的查询逻辑

用户在页面输入问题后，系统不会直接把问题交给 LLM，而是先从知识库中召回相关页面，再扩展为父块上下文，最后生成带来源和图片的回答。

```mermaid
flowchart TD
    A["用户输入问题"] --> B{"是否选择指定文档"}
    B -->|"是"| C["按 file_name 过滤检索范围"]
    B -->|"否"| D["检索全部已加载文档"]
    C --> E["混合检索"]
    D --> E
    E --> F["BM25 关键词召回"]
    E --> G["FAISS 向量语义召回"]
    F --> H["按权重合并并去重"]
    G --> H
    H --> I["得到相关 Child 页面块"]
    I --> J{"Child 是否有 parent_id"}
    J -->|"有"| K["从 DocStore 读取 Parent 父块"]
    J -->|"无"| L["保留单页 Child 内容"]
    K --> M["拼接参考上下文"]
    L --> M
    M --> N["保留 Markdown 图片占位符"]
    N --> O["构造 QA Prompt"]
    O --> P["调用 LLM 生成回答"]
    P --> Q["返回答案、来源页码和图片"]
```

关键点：

- **BM25 + Vector 双路召回**：BM25 适合精确术语，向量检索适合理解相近语义。
- **Child 检索，Parent 回答**：检索阶段用单页子块提高命中精度，回答阶段替换成连续页面父块，减少上下文碎片。
- **图片保留**：如果父块内容包含 `![描述](http://localhost:8080/...)`，Prompt 会要求 LLM 原样保留，前端即可渲染图片。
- **来源页码**：系统从父块或单页上下文标记中解析页码，随回答一起返回。

### 支持的文件格式

| 格式 | 扩展名 | 说明 |
|------|--------|------|
| PowerPoint | .pptx, .ppt | 提取文本和图片 |
| PDF | .pdf | 提取文档文本 |
| 文本 | .txt, .md, .markdown, .log, .text | 按行分块处理 |
| 图片 | .jpg, .jpeg, .png, .gif, .bmp, .webp, .tiff | Vision API 分析内容 |

### 界面功能

- **文档管理**: 查看已加载的文档列表
- **问答设置**:
  - 选择特定文档或所有文档
  - 调整 BM25/向量检索权重
  - 设置检索结果数量
  - 调整 LLM Temperature
- **研究设置**:
  - 选择研究范围文档
  - 输入研究任务
  - 查看计划、证据、终稿
- **清空文档**: 清除所有已加载的文档

## 核心设计

### 父子分块架构

- **Child Chunk (子块)**: 每页内容，向量化后存入 FAISS 用于检索
- **Parent Chunk (父块)**: 合并后的连续多页内容，存入 DocStore 用于 LLM 回答

### 页面合并策略

1. **LLM 判定**: 使用 LLM 判断连续页面是否属于同一主题
2. **手动标记**: 在 PPT 备注中添加 `<START_BLOCK>` 和 `<END_BLOCK>` 强制合并

### 图片处理流程

1. 提取 PPT 中的图片，保存到 `data/images/{hash}/`
2. 启动本地 HTTP 服务器提供图片访问
3. 在文本中插入 `![描述](http://localhost:8080/...)` 占位符
4. 前端 Markdown 渲染时自动显示图片

### Deep Research 设计要点

1. **知识服务层解耦**：先把文档加载、检索、页内容读取从 `RAGChain` 中拆出来，形成可复用的 `DocumentKnowledgeService`
2. **高层工具优先**：Deep Agents 主代理优先调用 `run_research_once`，避免复杂任务下低层工具循环过长
3. **子代理补充**：注册 `document_analyst`、`evidence_collector`、`report_writer`，必要时通过 `task` 调用
4. **产物可追踪**：所有中间结果和终稿都落盘到工作区，便于调试、教学和复查

### 去重机制

同一文件重复上传时，系统自动：
1. 删除该文件在 DocStore 中的所有父块
2. 删除向量库中的所有相关 chunks
3. 删除对应的图片目录
4. 删除上传的 PPT 文件
5. 重新处理新文件

## 后续扩展

- [ ] MinIO 图片存储（替代本地文件系统）
- [ ] Redis/MongoDB DocStore（替代本地 JSON）
- [ ] Chroma/Milvus 向量库（替代 FAISS）
- [ ] 混合查询后，增加Rerank模型进行精排
- [ ] 用户认证
- [ ] 文档删除（按文件名选择性删除）
