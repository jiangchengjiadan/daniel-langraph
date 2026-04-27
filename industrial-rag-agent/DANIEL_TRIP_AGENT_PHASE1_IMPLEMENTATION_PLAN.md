# daniel-trip-agent 第一阶段实施清单

日期：2026-04-27

目标：在不引入复杂优化器、不切换到 Deep Agents 的前提下，把当前单城市旅行 Agent 升级为 **参考 Trip.Planner 风格的多城市轻量规划器**。

## 1. 第一阶段范围

只做四件事：

1. 支持用户输入多个城市
2. 后端按输入顺序生成多城市 itinerary
3. 前端 UI/UX 改版，参考 Trip.Planner 的规划器风格
4. 结果页从“答案展示”升级为“轻量行程工作台”

不做：
- 城市间最优路线优化
- 拖拽排序
- 实时库存闭环下单
- 协作编辑
- 长期记忆
- Deep Agents 顶层编排

## 2. 验收标准

阶段完成后，应满足：

1. 首页支持输入 `cities: ["上海", "苏州", "杭州"]`
2. 后端返回包含多个城市的统一 itinerary
3. 每一天可显示：城市、景点、酒店、天气、预算小计
4. 前端整体视觉更接近 Trip.Planner，而不是聊天工具
5. 保留现有 LangGraph 工作流，不引入额外复杂架构

## 3. 实施清单

### A. 产品与交互

- 定义首页最小输入模型
  - 多城市输入
  - 日期
  - 天数
  - 风格
  - 折叠高级项：交通、住宿、额外要求
- 定义结果页布局
  - 左侧：按天 itinerary
  - 右侧：地图或城市摘要
  - 顶部：总览信息与预算摘要

### B. 后端数据模型

- `TripRequest` 增加 `cities: List[str]`
- 兼容旧字段 `city`
- `TripPlan` / `DayPlan` 增加 `city`
- LangGraph state 增加：
  - `cities`
  - `current_city`
  - `city_segments`

### C. 后端规划逻辑

- 增加“多城市天数分配”函数
  - 按用户输入顺序分配
  - 不做最优解
- 将现有单城市规划逻辑复用到每个城市
- 汇总多城市结果为统一 itinerary
- 在城市切换处补一段城际交通说明

### D. 数据增强与约束

- 复用现有：
  - 高德景点/酒店/天气
  - FlyAI 酒店/门票增强
  - 商品回填
- 继续保留现有价格兜底逻辑
- 增加最小多城市约束：
  - 城市顺序固定
  - 每天 2-3 个景点
  - 雨天少排强户外景点

### E. 前端 UI/UX 改版

首页参考 Trip.Planner，但做教学版最小实现：

- 大标题区去营销化，直接进入规划器
- 主输入区使用大尺寸、多段式表单
- 多城市输入采用：
  - 已选城市标签列表
  - 输入框回车添加
  - 支持删除，不做拖拽
- 风格选择采用卡片或分段按钮
- “更多偏好”折叠区收纳高级选项
- 主按钮视觉强调“开始规划”

结果页参考 Trip.Planner，但做轻量版：

- 顶部总览栏
  - 城市串联
  - 日期
  - 总天数
  - 总预算
- 左侧日程区
  - Day 卡片
  - 酒店卡
  - 景点卡
  - 天气与预算
- 右侧信息区
  - 地图占位或城市摘要
  - 城市切换摘要
- 减少聊天气泡和对话感
- 强化卡片式规划感

## 4. 任务拆分

### 任务 1：需求与接口定义

目标：
- 明确多城市输入和返回结构

输出：
- 请求/响应 schema 更新
- 字段兼容策略说明

涉及文件：
- `backend/app/models/schemas.py`
- `backend/app/api/routes/trip.py`

### 任务 2：多城市后端模型改造

目标：
- 后端支持 `cities`
- 单城市兼容不破坏

输出：
- schema 更新
- 参数归一化逻辑

涉及文件：
- `backend/app/models/schemas.py`
- `backend/app/agents/state.py`
- `backend/app/api/routes/trip.py`

### 任务 3：多城市规划逻辑

目标：
- 按城市顺序和旅行天数生成统一 itinerary

输出：
- 城市分段函数
- 多城市聚合逻辑

涉及文件：
- `backend/app/agents/langgraph_planner.py`
- `backend/app/agents/nodes/planner_node.py`
- 可能新增 `backend/app/agents/utils/itinerary_splitter.py`

### 任务 4：数据增强兼容多城市

目标：
- 高德与 FlyAI 增强在多城市情况下可继续工作

输出：
- 每个城市独立查询后汇总
- 保留价格兜底与预算回填

涉及文件：
- `backend/app/agents/nodes/hotel_node.py`
- `backend/app/agents/nodes/weather_node.py`
- `backend/app/agents/nodes/attraction_node.py`
- `backend/app/agents/nodes/product_enrichment_node.py`

### 任务 5：首页 UI/UX 改版

目标：
- 首页风格参考 Trip.Planner
- 输入更像旅行规划器

输出：
- 多城市输入组件
- 风格选择组件
- 折叠高级项

涉及文件：
- `frontend/src/views/*`
- `frontend/src/components/*`
- `frontend/src/types/*`
- `frontend/src/services/*`

### 任务 6：结果页 UI/UX 改版

目标：
- 结果页改为 itinerary 工作台风格

输出：
- 总览栏
- 天级 itinerary 卡片
- 右侧摘要区

涉及文件：
- `frontend/src/views/*`
- `frontend/src/components/*`

### 任务 7：联调与验收

目标：
- 跑通最小闭环

输出：
- 多城市示例请求可成功返回
- 前端可展示
- 基本预算、天气、酒店、景点正常显示

验证场景：
- `["上海", "苏州"]` 2 天游
- `["杭州", "乌镇", "上海"]` 4 天游

## 4.1 后端任务优先级

### P0：接口与模型兼容

目标：先让后端能接受多城市输入，同时不破坏现有单城市调用。

子任务：
- `TripRequest` 增加 `cities`，兼容 `city`
- `TripPlanState` 增加 `cities`、`current_city`、`city_segments`
- `DayPlan` 增加 `city` 字段
- `/api/trip/plan` 日志与参数读取改为优先使用 `cities`

依赖：无

### P1：多城市最小规划逻辑

目标：在不重写全部节点的前提下，先跑通按城市顺序的多城市 itinerary。

子任务：
- 新增城市天数分配函数
- 复用现有单城市规划逻辑逐城生成
- 合并多个城市的 `days`、`weather_info`、`budget`
- 在总建议里增加多城市串联说明

依赖：P0

### P2：多城市增强兼容

目标：确保高德 / FlyAI 在多城市情况下仍然可用。

子任务：
- 每个城市独立查询景点 / 酒店 / 天气
- 汇总商品回填结果
- 预算汇总和价格兜底继续生效

依赖：P1

### P3：联调与最小回归

目标：确认单城市没坏，多城市能跑。

子任务：
- 单城市回归请求
- 双城市请求
- 三城市请求

依赖：P2

## 4.2 前端任务优先级

### P0：类型与请求兼容

目标：前端先能发送 `cities`，并兼容旧结构。

子任务：
- `TripFormData` 增加 `cities`
- `DayPlan` 增加 `city`
- `TripPlan` 增加 `cities`
- API 请求 payload 改为多城市格式

依赖：后端 P0

### P1：首页 UI/UX 改版

目标：把首页从“表单页”改成更像 Trip.Planner 的规划入口。

子任务：
- 移除当前装饰性圆形背景
- 改成大输入区 + 轻说明文案
- 增加多城市标签输入
- 偏好改成更紧凑的卡片式选择
- 高级项折叠

依赖：前端 P0

### P2：结果页 UI/UX 改版

目标：把结果页从“信息堆叠展示”改成 itinerary 工作台。

子任务：
- 顶部总览栏展示城市串联、日期、预算
- 左侧日程卡展示每日城市、景点、酒店、天气
- 右侧保留地图/摘要区
- 降低“编辑器按钮密度”，先保留核心操作

依赖：前端 P0、后端 P1

### P3：视觉统一与移动端修正

目标：收口 Trip.Planner 风格，不做功能扩张。

子任务：
- 统一留白、边框、配色
- 收口按钮样式和卡片层级
- 修复移动端溢出和拥挤

依赖：前端 P1、P2

## 5. 建议执行顺序

按这个顺序做最稳：

1. 任务 1：需求与接口定义
2. 任务 2：多城市后端模型改造
3. 任务 3：多城市规划逻辑
4. 任务 4：数据增强兼容多城市
5. 任务 5：首页 UI/UX 改版
6. 任务 6：结果页 UI/UX 改版
7. 任务 7：联调与验收

## 6. 最终建议

第一阶段不要追求“像 Trip.Planner 的全部能力”，只追求三点：

1. 看起来像规划器
2. 输入支持多城市
3. 输出是结构化 itinerary

只要这三点成立，这个教学项目的改版方向就是正确的。
