# Deep Research Agent 任务清单

本文档是 [deep-research-agent-technical-design.md](/Users/danielhe/enviroment/server/workspace/daniel-langraph/pptx-rag/docs/deep-research-agent-technical-design.md) 的实施版任务清单，用于指导 `pptx-rag` 向 `Deep Research Agent` 的演进。

## 1. 实施原则

- 优先复用现有 `parser / processor / storage / retriever`
- 不一次性推翻 `RAGChain`，先拆服务，再补 Deep Research 能力
- 先做最小可运行 MVP，再补充质量控制和长期记忆
- 所有中间产物尽量可见、可追踪、可复用

## 2. 当前分支

- 实施分支：`feature/deep-research-agent-plan`
- 说明：仓库默认分支为 `main`，无 `master`

## 3. 阶段划分

### Phase 0：知识服务层拆分

目标：

- 将 `RAGChain` 内的知识处理能力从 UI/问答流程中解耦
- 为 Deep Research 工具层提供稳定接口

完成标准：

- 新增可复用知识服务模块
- 保留现有问答功能可运行
- 后续 Deep Research 工具不直接依赖 Streamlit 状态

任务：

- [x] 新建 `src/services/` 目录
- [x] 新建 `src/services/document_knowledge.py`
- [x] 抽取文档加载能力
- [x] 抽取文档列表能力
- [x] 抽取检索能力
- [x] 抽取指定页内容读取能力
- [x] 抽取父块上下文构建能力
- [x] 让 `RAGChain` 改为组合知识服务，而非直接承载全部职责
- [x] 确保原 `ask()`、`ask_stream()`、`load_document()` 仍可工作

交付物：

- `src/services/document_knowledge.py`
- 经适配后的 `src/rag/chain.py`

依赖：

- 无

### Phase 1：Deep Research 最小骨架

目标：

- 新增可运行的 Deep Research 模块骨架
- 在没有复杂多子代理的前提下跑通“研究任务 -> 证据 -> 报告”链路

完成标准：

- 用户可以发起一个研究任务
- 系统可以生成计划、收集证据、生成报告文件
- 中间产物写入工作区

任务：

- [x] 新建 `src/deep_research/`
- [x] 新建 `src/deep_research/__init__.py`
- [x] 新建 `src/deep_research/schemas.py`
- [x] 新建 `src/deep_research/prompts.py`
- [x] 新建 `src/deep_research/services.py`
- [x] 新建 `src/deep_research/tools.py`
- [x] 新建 `src/deep_research/quality.py`
- [x] 新建 `src/deep_research/agent.py`
- [x] 新建 `src/deep_research/workspace.py`
- [x] 定义研究任务数据结构
- [x] 定义研究计划数据结构
- [x] 定义证据项数据结构
- [x] 定义报告元数据结构
- [x] 建立工作区目录约定
- [x] 实现任务文件写入
- [x] 实现计划文件写入
- [x] 实现证据文件写入
- [x] 实现报告草稿与终稿写入

交付物：

- `src/deep_research/*`
- 工作区目录结构

依赖：

- Phase 0

### Phase 2：工具层接入

目标：

- 把现有 RAG 能力封成研究任务可调用的稳定接口

完成标准：

- Deep Research 模块能通过统一工具接口使用知识能力
- 工具输出适合被 agent 或研究流程消费

任务：

- [ ] 实现 `ingest_document`
- [x] 实现 `list_documents`
- [x] 实现 `search_evidence`
- [x] 实现 `get_page_content`
- [x] 实现 `build_parent_context`
- [x] 统一工具返回格式
- [x] 为工具增加异常处理和日志

交付物：

- `src/deep_research/tools.py`

依赖：

- Phase 0
- Phase 1

### Phase 3：研究流程主链路

目标：

- 跑通最小研究闭环，不强依赖正式 Deep Agents 运行时
- 先以“研究协调器服务”方式落地，保证后续可替换为 Deep Agents

完成标准：

- 单次研究任务可以完成
- 可以输出结构化 Markdown 报告

任务：

- [x] 实现研究任务入口服务
- [x] 生成任务说明文件 `task.md`
- [x] 生成研究计划 `plan.md`
- [x] 生成文档概览 `documents_overview.md`
- [x] 按子问题写入 `evidence/*.md`
- [x] 生成 `drafts/report_v1.md`
- [x] 生成 `final/final_report.md`
- [x] 形成任务结果对象

交付物：

- `src/deep_research/services.py`
- `src/deep_research/agent.py`

依赖：

- Phase 1
- Phase 2

### Phase 4：质量检查

目标：

- 降低来源遗漏、图片丢失、结构缺项等问题

完成标准：

- 生成报告前后有最小质量检查
- 检查结果能反馈给用户

任务：

- [x] 实现引用完整性检查
- [x] 实现图片占位符保留检查
- [x] 实现必需章节检查
- [x] 实现未完成 Todo 检查
- [x] 将检查结果写入 `quality_report.md`

交付物：

- `src/deep_research/quality.py`

依赖：

- Phase 3

### Phase 5：前端接入

目标：

- 在 Streamlit 中增加研究模式入口
- 展示计划、证据和报告，而不只是聊天记录

完成标准：

- 用户可切换“问答模式 / 研究模式”
- 研究模式中可提交任务并查看报告

任务：

- [x] 在 `app/streamlit_app.py` 增加模式选择
- [x] 增加研究任务输入区域
- [x] 增加文档选择区域
- [x] 增加计划展示区
- [x] 增加证据文件展示区
- [x] 增加报告预览区
- [x] 保留原有问答模式不受影响

交付物：

- 更新后的 `app/streamlit_app.py`

依赖：

- Phase 3

### Phase 6：Deep Agents 正式接入

目标：

- 用 Deep Agents 替换当前“手写研究协调器”的主控逻辑
- 复用现有研究工具和工作区结构

完成标准：

- 主代理能用 Todo / Filesystem / Subagents 驱动研究任务
- 研究工具层不需要重写

任务：

- [x] 引入 `deepagents` 依赖
- [x] 评估运行环境与版本兼容性
- [x] 设计主代理 system prompt
- [x] 注册研究工具
- [x] 接入工作区 backend
- [x] 接入 `write_todos`
- [x] 接入文件系统工具
- [x] 接入 `document_analyst` 子代理
- [x] 接入 `evidence_collector` 子代理
- [x] 接入 `report_writer` 子代理
- [x] 验证中间产物与最终报告输出一致

当前说明：

- Deep Agents 主路径采用“高层 orchestrator + `run_research_once`”混合方案，优先保证收敛性
- `document_analyst`、`evidence_collector`、`report_writer` 已作为专用子代理注册，可在需要时通过 `task` 调用
- 实测研究任务已返回 `execution_mode=deepagents`，并稳定生成 `task / plan / evidence / quality / final_report` 产物

交付物：

- 正式 Deep Agents 版本主代理

依赖：

- Phase 1
- Phase 2
- Phase 3

### Phase 7：长期记忆与模板

目标：

- 在多轮和多任务间保留用户偏好与研究模板

完成标准：

- 可以跨任务复用模板或偏好

任务：

- [ ] 引入持久化 store
- [ ] 路由 `/memories/`
- [ ] 保存用户输出风格偏好
- [ ] 保存报告模板
- [ ] 保存术语表和领域映射

交付物：

- 长期记忆层

依赖：

- Phase 6

## 4. 优先级排序

### P0

- [x] Phase 0
- [x] Phase 1
- [x] Phase 2
- [x] Phase 3
- [x] Phase 5

### P1

- [x] Phase 4
- [ ] Phase 6

### P2

- [ ] Phase 7

## 5. 当前执行顺序

本轮直接执行：

1. Phase 0：知识服务层拆分
2. Phase 1：Deep Research 最小骨架
3. Phase 2：工具层接入
4. Phase 3：最小研究主链路
5. Phase 5：研究模式前端接入

本轮暂不强行完成：

- Deep Agents 正式接入
- 长期记忆
- 复杂质量修复循环

原因：

- 先把基础结构搭稳，后续接入 Deep Agents 才不会反复返工

## 6. 本轮验收标准

本轮完成后应满足：

- [x] 原问答功能仍可运行
- [x] 可上传并处理文档
- [x] 可发起研究任务
- [x] 可生成任务计划
- [x] 可生成证据文件
- [x] 可生成 Markdown 研究报告
- [x] 可在前端看到研究结果

## 7. 风险清单

- [ ] `RAGChain` 拆分后破坏原有行为
- [ ] 研究模式与问答模式状态互相污染
- [ ] 中间产物目录设计不稳定
- [ ] 工具输出不统一导致后续 Deep Agents 接入困难
- [ ] 过早接入正式 Deep Agents 导致调试复杂度过高

## 8. 实施记录

### 已完成

- [x] 技术方案文档已创建
- [x] 实施分支已创建

### 进行中

- [ ] Phase 6：正式 Deep Agents 接入

### 待完成

- [ ] 其余各阶段任务
