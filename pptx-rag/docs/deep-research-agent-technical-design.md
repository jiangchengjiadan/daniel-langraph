# PPTX-RAG -> Deep Research Agent 技术方案

## 1. 背景与目标

当前 `pptx-rag` 项目是一个高质量的文档 RAG 系统，已经具备以下能力：

- 多格式解析：PPT/PPTX、PDF、文本、图片
- 页面级分块与父子块组织
- 混合检索：BM25 + Vector
- 图片提取与回答保留
- 来源页码标注

这些能力足以支撑“文档问答”，但还不足以支撑“研究任务”。如果要验证 Deep Agents 是否适合该类产品，不能只是把聊天入口替换成 Deep Agent，而应把产品目标升级为“文档研究助手”。

本方案目标是把项目改造成一个可持续多轮工作的 `Deep Research Agent`，支持：

- 面向多个文档的研究任务拆解
- 自动制定研究计划与执行步骤
- 多文档证据收集与归档
- 生成研究报告、培训讲义、对比分析等结构化产物
- 保留图片、来源页码、文档名等证据链信息

一句话定义：

> 该项目不再只是回答一个问题，而是帮助用户完成一项文档研究工作。


## 2. 适用性判断

选择 Deep Agents 作为顶层编排是合理的，原因如下：

- 任务天然是多步骤的，不是单次问答
- 需要文件系统来保存中间研究产物
- 需要任务规划能力来拆解研究问题
- 需要子代理来分离“文档理解”“证据收集”“报告生成”
- 用户通常会在一个线程里持续追问、迭代修改报告

同时，本项目不适合完全抛弃原有 RAG 逻辑。正确做法应为：

- Deep Agents 负责“研究过程编排”
- 现有 `pptx-rag` 逻辑继续负责“文档解析、存储、检索、上下文构建”

因此，推荐架构是：

> Deep Agents 顶层协调 + 现有 RAG 能力工具化复用


## 3. 产品目标与非目标

### 3.1 产品目标

第一阶段产品目标：

- 用户上传多个文档
- 用户输入一项研究任务
- 系统自动拆解研究步骤
- 系统调用检索能力收集证据
- 系统输出可读的 Markdown 报告
- 报告中保留图片与来源信息

第二阶段产品目标：

- 支持报告重写、摘要版、培训版、技术版多种输出
- 支持对比分析与冲突证据整理
- 支持研究线程复用和长期偏好记忆
- 支持人工审批关键写入或定稿

### 3.2 非目标

第一阶段不做以下内容：

- 不做外部 Web 搜索
- 不做复杂团队协作审批流
- 不做过多专用子代理
- 不重写现有 parser / retriever / vector store
- 不追求“全自动无人监督”式研究闭环


## 4. 用户场景

典型输入示例：

- “帮我研究这几份 PLC 培训资料中关于故障诊断的核心方法，形成一份 1500 字报告。”
- “对比文档 A 和文档 B 中关于 S7-200 与 S7-300 的差异，并保留关键图片。”
- “整理一份给售前团队用的讲义，主题是 PLC 模块、指示灯、故障定位。”
- “找出和电源故障有关的所有页，先整理证据，再给出结论和建议。”

典型输出类型：

- 快速回答 `Quick Answer`
- 证据包 `Evidence Pack`
- 研究报告 `Research Report`
- 培训讲义 `Training Brief`
- 文档对比 `Comparison Report`


## 5. 总体架构

## 5.1 架构原则

- 保留现有文档处理链路，避免重写成熟模块
- 把 Deep Agent 放在最顶层，负责规划和协作
- 把原有能力通过工具暴露给 Agent
- 把中间结果写入工作区，增强可观察性和可追踪性
- 把最终输出设计成文件产物，而不仅是聊天回复

## 5.2 架构分层

```text
┌──────────────────────────────────────────────┐
│                UI / API Layer                │
│ 上传文档、提交研究任务、查看计划/证据/报告     │
└──────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│          Deep Research Orchestrator          │
│ Deep Agent 主代理：规划、调度、汇总、交互      │
└──────────────────────────────────────────────┘
                      │
      ┌───────────────┼────────────────┐
      ▼               ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│document_     │ │evidence_     │ │report_       │
│analyst       │ │collector     │ │writer        │
└──────────────┘ └──────────────┘ └──────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│         Existing PPTX-RAG Services           │
│ parser / processor / storage / retriever     │
└──────────────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
┌──────────────────┐   ┌────────────────────────┐
│ Knowledge Index  │   │ Workspace / Memories   │
│ FAISS + DocStore │   │ 计划、证据、报告、偏好   │
└──────────────────┘   └────────────────────────┘
```


## 6. 核心能力设计

### 6.1 主代理能力

主代理 `research_orchestrator` 负责：

- 理解用户研究意图
- 生成 Todo 计划
- 判断需要分析哪些文档
- 决定何时调用子代理或工具
- 汇总证据并生成最终报告
- 基于用户追问继续改写已有报告

主代理应始终围绕“研究交付物”而不是“一次回答”来行动。

### 6.2 子代理能力

推荐第一阶段只保留 3 个子代理。

#### document_analyst

职责：

- 理解文档整体结构
- 找出关键章节、关键页码、关键图片
- 形成文档级摘要

输出：

- 文档摘要
- 章节线索
- 值得引用的关键页面

#### evidence_collector

职责：

- 针对某个研究子问题执行检索
- 收集证据片段
- 保留文档名、页码、图片占位符
- 合并重复证据并标记冲突

输出：

- 证据 markdown 文件
- 证据清单
- 冲突或不足说明

#### report_writer

职责：

- 根据计划和证据生成结构化报告
- 控制报告风格和篇幅
- 保留图片和来源
- 输出初稿和终稿

输出：

- 报告初稿
- 摘要版
- 最终稿


## 7. 工作流设计

一次标准研究任务的执行流程如下：

1. 用户上传或选择多个文档
2. 用户输入研究任务
3. 主代理生成 Todo 计划
4. 主代理调用 `list_documents` 和文档摘要能力识别候选资料
5. `document_analyst` 输出文档概览
6. 主代理将主题拆成若干研究子问题
7. `evidence_collector` 针对子问题收集证据
8. 每个子问题的证据写入工作区
9. 主代理检查是否需要补充证据
10. `report_writer` 生成报告草稿
11. 主代理执行质量检查
12. 输出最终报告并响应用户

建议在工作区保存以下文件：

```text
/workspace/
  ├── task.md
  ├── plan.md
  ├── documents_overview.md
  ├── evidence/
  │   ├── q1.md
  │   ├── q2.md
  │   └── q3.md
  ├── drafts/
  │   ├── report_v1.md
  │   └── report_v2.md
  └── final/
      └── final_report.md
```


## 8. 技术实现方案

### 8.1 保留与复用的现有模块

以下模块应尽量复用：

- `src/parser/*`
- `src/processor/*`
- `src/storage/*`
- `src/retriever/*`

这些模块已经沉淀了：

- 文档解析
- 图像提取
- 分块策略
- 父子块构建
- 向量与 BM25 检索

这些都是 Deep Research 的知识处理底座，不应重写。

### 8.2 需要新增的模块

建议新增目录：

```text
src/deep_research/
  ├── __init__.py
  ├── agent.py
  ├── subagents.py
  ├── tools.py
  ├── services.py
  ├── prompts.py
  ├── quality.py
  ├── schemas.py
  └── backends.py
```

模块职责如下：

- `agent.py`
  - 创建主 Deep Agent
  - 注入 tools、subagents、backend、checkpointer

- `subagents.py`
  - 定义 `document_analyst`、`evidence_collector`、`report_writer`

- `tools.py`
  - 把现有 RAG 能力封装成 LangChain tools

- `services.py`
  - 适配现有 `RAGChain` 或拆出的知识服务

- `prompts.py`
  - 研究计划、证据提取、报告撰写 prompt

- `quality.py`
  - 对来源、图片、结构完整性做最终检查

- `schemas.py`
  - 定义研究任务、证据项、报告元数据结构

- `backends.py`
  - 配置 Deep Agents backend 路由


## 9. 工具设计

不建议让 Agent 直接操作底层存储类。应通过稳定工具暴露能力。

第一阶段建议实现以下工具。

### 9.1 文档管理工具

`ingest_document(file_path: str) -> str`

- 读取并处理文档
- 建立索引
- 返回文档元信息和处理结果摘要

`list_documents() -> str`

- 返回已加载文档列表
- 包含名称、页数、处理状态、更新时间

### 9.2 检索与上下文工具

`search_evidence(query: str, file_name: Optional[str], top_k: int = 5) -> str`

- 调用现有 hybrid retriever
- 返回带页码和图片占位符的命中结果

`get_page_content(file_name: str, pages: list[int]) -> str`

- 获取指定页内容
- 适合做精读和核对

`build_parent_context(hit_ids: list[str]) -> str`

- 把若干命中整理成高质量回答上下文

### 9.3 研究工作区工具

这些工具可以直接使用 Deep Agents 的文件系统工具，不必重复造轮子：

- `ls`
- `read_file`
- `write_file`
- `edit_file`
- `glob`
- `grep`

第一阶段不额外实现自定义写文件工具。

### 9.4 报告辅助工具

`generate_structured_summary(context: str, mode: str) -> str`

- 生成摘要、讲义或技术综述

`validate_report(report_path: str) -> str`

- 检查报告是否存在来源遗漏
- 检查是否丢失图片占位符
- 检查报告结构是否完整


## 10. 数据与存储设计

### 10.1 知识存储

继续使用现有方案：

- `FAISS` 存储向量索引
- `DocStore` 存储父块内容
- 本地图像目录保存图片资源

### 10.2 工作区存储

研究线程中间产物建议使用 Deep Agents 的工作区文件系统。

本地开发环境建议：

- 使用 `FilesystemBackend(root_dir=".", virtual_mode=True)`
- 工作目录限定在项目内部，例如 `app/data/workspace/`

推荐路径：

```text
app/data/workspace/
  ├── sessions/
  │   └── {thread_id}/
  └── exports/
```

### 10.3 长期记忆

第一阶段可以不启用长期记忆。

第二阶段可加入：

- 用户报告偏好
- 常用模板
- 常见术语映射
- 经人工确认过的标准结论

推荐使用：

- `StoreBackend`
- 或 `CompositeBackend`

路径建议：

```text
/memories/user_prefs/
/memories/templates/
/memories/domain_terms/
```


## 11. API 与前端设计

### 11.1 API 设计

建议不要沿用单一问答接口。新增研究型接口：

`POST /api/research/tasks`

- 创建研究任务
- 输入：task、selected_documents、output_mode

`GET /api/research/tasks/{task_id}`

- 返回任务状态、todo、当前阶段

`GET /api/research/tasks/{task_id}/artifacts`

- 返回计划、证据、草稿、终稿文件列表

`GET /api/research/tasks/{task_id}/report`

- 返回最终报告

`POST /api/research/tasks/{task_id}/followup`

- 在原线程上继续追问或改写

### 11.2 前端设计

如果继续使用 Streamlit，建议从“单聊天框”升级为“三栏布局”：

- 左栏：文档列表、任务配置
- 中栏：Agent 对话与执行进度
- 右栏：Todo、证据文件、报告预览

关键可见元素必须包括：

- 当前 Todo 列表
- 当前正在分析的文档
- 已完成的证据文件
- 最终报告预览

否则用户无法感知 Deep Agents 的过程价值。


## 12. 输出格式规范

所有最终报告建议采用 Markdown，基础结构如下：

```markdown
# 研究报告标题

## 1. 研究目标

## 2. 核心结论

## 3. 证据分析

## 4. 关键图片

## 5. 风险与不足

## 6. 参考来源
```

报告生成时必须满足：

- 保留图片占位符
- 标注文档名
- 标注页码
- 引用证据与结论分离
- 在证据不足时明确说明


## 13. 质量控制

为避免 Deep Research 输出质量下降，建议在最终写稿前增加一层检查。

### 13.1 必查项

- 是否所有关键结论都有来源
- 是否图片占位符被遗漏或改写
- 是否存在无来源的推断
- 是否遗漏用户要求的输出格式
- 是否覆盖了所有 Todo 中标为 completed 的子任务

### 13.2 实现方式

建议增加 `quality.py`：

- `check_citations`
- `check_images_preserved`
- `check_required_sections`
- `check_unanswered_questions`

主代理在交付前必须调用质量检查并根据结果修正一次。


## 14. 安全与权限

本项目会用到文件系统能力，因此需要限制写入范围。

建议：

- 仅允许访问项目内 `app/data/workspace/`
- 使用 `virtual_mode=True`
- 不允许访问仓库外路径
- 如果开放 UI 给多人使用，不直接暴露真实磁盘路径

如果后续接入 Web 服务场景，应避免直接使用不受限制的本地文件系统 backend。


## 15. 分阶段实施计划

### Phase 0：代码整理

目标：

- 梳理 `RAGChain` 与底层能力的边界
- 提取可复用知识服务层

动作：

- 从 `src/rag/chain.py` 拆出 `DocumentKnowledgeService`
- 保持现有问答功能可运行

交付：

- 一个独立的知识服务接口层

### Phase 1：Deep Research MVP

目标：

- 跑通基本研究任务

动作：

- 新增 `src/deep_research/`
- 实现主代理
- 实现 3 个子代理
- 实现核心检索工具
- 实现工作区文件输出
- 前端增加任务提交与报告展示

交付：

- 支持单线程研究任务
- 生成最终 Markdown 报告

### Phase 2：质量与可观察性

目标：

- 提升输出可靠性和可追踪性

动作：

- 增加质量检查层
- 增加 artifact 浏览能力
- 增加任务状态 API

交付：

- 可查看 todo、证据、草稿、终稿

### Phase 3：长期记忆与模板

目标：

- 让 Agent 在多轮和多任务间积累工作记忆

动作：

- 加入 `StoreBackend`
- 保存用户偏好和模板
- 引入标准化报告模板

交付：

- 支持个性化研究输出


## 16. MVP 范围定义

第一版必须完成：

- 多文档选择
- 研究任务输入
- Todo 自动拆解
- 证据收集
- Markdown 报告生成
- 来源和图片保留

第一版可以暂缓：

- 长期 memory
- 报告导出 PDF
- 高级人工审批流
- 多种复杂子代理组合
- 外部 Web research


## 17. 验收标准

满足以下条件即可视为 MVP 可用：

- 能处理至少 2 份文档
- 能完成一次主题研究任务
- 能生成结构化报告
- 报告中包含来源与页码
- 有图片时能保留图片占位符
- 用户可以基于原任务继续追问
- 中间过程文件可见

建议验收样例：

- “对比 PLC 文档中不同系列模块的功能差异并保留相关图片”
- “总结文档中关于电源故障诊断的证据与建议”
- “把一组培训资料整理成给销售团队的简版讲义”


## 18. 风险与应对

### 风险 1：目标没有升级

如果产品仍然只是“问答”，Deep Agents 的价值不明显。

应对：

- 明确将任务定义为研究、分析、整理、生成交付物

### 风险 2：子代理过多

子代理越多，稳定性越差，排查成本越高。

应对：

- 第一阶段只保留 3 个子代理

### 风险 3：复用不足

如果重写解析和检索模块，会显著拉长工期。

应对：

- 现有知识服务必须作为底层复用

### 风险 4：输出不可控

报告可能丢失来源、页码、图片。

应对：

- 加入独立质量检查层

### 风险 5：工作区文件混乱

没有约定目录结构时，很快会失控。

应对：

- 强制按 `session/task/artifact` 结构存储


## 19. 推荐落地路径

推荐按以下顺序推进：

1. 先拆分当前 `RAGChain`，形成稳定知识服务层
2. 再实现 `search_evidence`、`get_page_content`、`list_documents` 三个核心工具
3. 建立主代理与单子代理最小闭环
4. 跑通“研究任务 -> 证据 -> 报告”一条链路
5. 再加入多子代理和质量检查

这样能最小化风险，并且保留原项目已有成果。


## 20. 结论

`pptx-rag` 改造成 `Deep Research Agent` 是一个可落地、值得做的实验方向。

正确姿势不是“把原项目全部改写成 Deep Agents”，而是：

- 保留现有 RAG 作为知识能力底座
- 用 Deep Agents 管理研究任务的规划、协作和产物输出

最终形成的不是一个“更复杂的问答机器人”，而是一个“能完成研究工作的文档分析助手”。

这是本项目最合理、也最能体现 Deep Agents 价值的升级方向。
