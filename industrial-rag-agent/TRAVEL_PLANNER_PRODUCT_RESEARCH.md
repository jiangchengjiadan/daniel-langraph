# 旅行规划产品调研报告

调研日期：2026-04-27

本报告基于公开可访问的官方产品页与帮助中心，重点看三类问题：市场上主流旅行规划产品做了什么、这些功能大致如何实现、对自建旅行规划 Agent 有什么启发。

## 1. 市场上主流产品分型

当前旅行规划产品大致分成四类：

1. 搜索/比价平台扩展型：Google Travel、KAYAK Trips  
   强项是航班、酒店、价格变化、实时状态。
2. 行程组织型：TripIt  
   强项是自动汇总预订、提醒、共享、离线查看。
3. 地图与路线型：Wanderlog、Roadtrippers  
   强项是地图排布、多点路线、协作、沿途发现。
4. AI 一体化规划型：Trip.com Trip.Planner  
   强项是“生成式规划 + 交易闭环”。

## 2. 代表产品与功能

### Google Travel / Google Flights

公开可见功能包括：
- 酒店筛选、比价、地图与详情页
- 航班价格追踪
- “Best / Cheapest”排序
- 部分行程有价格保障

实现判断：
- 核心不是自由生成 itinerary，而是基于大规模航旅库存、规则排序、价格预测模型和 partner feed。
- 这类产品的“智能”主要在排序、预测、过滤，不在长文本规划。

来源：
- https://support.google.com/travel/answer/6276008
- https://support.google.com/travel/answer/6235879
- https://support.google.com/travel/answer/7664728
- https://support.google.com/travel/answer/9430556

### TripIt

公开可见功能包括：
- 转发确认邮件后自动生成行程
- 跨平台聚合预订
- 实时航班提醒
- 地图、导航、附近地点
- 共享与离线访问

实现判断：
- 核心是邮件解析、结构化 itinerary 数据模型、提醒系统和状态同步。
- 它不是“帮你想去哪”，而是“帮你组织已经订好的东西”。

来源：
- https://www.tripit.com/web
- https://www.tripit.com/web/free/trip-planner

### KAYAK Trips

公开可见功能包括：
- 自动导入预订
- 手动补充活动
- 实时航班/登机口更新
- 协作编辑

实现判断：
- 与 TripIt 类似，本质是 booking aggregation。
- 关键能力是确认函解析、统一事件模型、通知系统。

来源：
- https://www.kayak.com/trips
- https://www.kayak.com/c/help/account-trips/

### Wanderlog

公开可见功能包括：
- itinerary 与 map 同屏
- 路线自动优化
- 预订导入
- 协作编辑
- 预算、分账、打包清单
- AI Assistant

实现判断：
- 核心价值在“结构化编辑器 + 地图联动”。
- AI 更像辅助入口，真正留存能力来自可编辑 itinerary、地图、协作和预算工具。
- 路线优化大概率是基于地图服务 ETA/距离矩阵做启发式排序，不是纯 LLM。

来源：
- https://wanderlog.com/

### Roadtrippers

公开可见功能包括：
- 起终点路线规划
- 沿途景点发现
- 允许设置偏离主路线距离
- 燃油成本估算
- 酒店搜索与预订
- AI Autopilot 自动规划

实现判断：
- 这是典型“路线优先”产品。
- 关键壁垒是路线缓冲区 POI 检索、兴趣点库、偏航约束和多站点编辑。
- AI Autopilot 更像在既有规则和 POI 库上做快速组装，而不是从零生成。

来源：
- https://roadtrippers.com/about/
- https://roadtrippers.com/about/features/
- https://roadtrippers.com/autopilot/
- https://roadtrippers.com/get-started/

### Trip.com Trip.Planner

公开可见功能包括：
- 只需目的地、天数、风格即可生成 itinerary
- 航班、火车、酒店、餐厅、景点一体化
- 可导入既有预订
- 画布式调整
- 实时可用性与风格化推荐

实现判断：
- 这是“AI 生成 + OTA 库存 + 可编辑行程画布”的组合。
- 关键不是单次生成，而是把生成结果放回可交易、可修改、可预订的结构化界面。
- 官方还提到开放时间、典型游览时长、交通估算和已验证数据，说明其生成并不是纯模型自由发挥，而是强依赖受约束数据源。

来源：
- https://www.trip.com/tripplanner
- https://www.trip.com/newsroom/trip-com-launches-trip-planner-smart-itineraries-tailored-to-your-travel-style-with-real-time-recommendations/

## 3. 共性功能总结

高频出现的能力有：
- 结构化 itinerary
- 地图联动
- 预订导入
- 实时库存/价格/状态
- 协作与共享
- 离线访问
- 路线优化
- 预算管理
- 生成式 AI 辅助

结论很直接：真正成熟的产品，AI 几乎都不是唯一主角。稳定的结构化数据、地图能力、价格与库存、编辑器、通知系统，才是主干。

## 4. 对“怎么实现”的归纳

从这些产品可以反推出一套常见技术分层：

1. 数据层  
   POI 库、酒店/航班库存、开放时间、评价、地图与路线、价格与状态 feed。

2. 规划层  
   - 规则引擎：营业时间、交通时长、住宿偏好、预算约束  
   - 优化器：路线排序、多日分配、时间窗冲突处理  
   - LLM：解释、摘要、风格化输出、缺失信息补全

3. 编辑层  
   不是只返回一段文本，而是返回结构化 itinerary，用户可拖拽、替换、删除、重排。

4. 运营层  
   同步、协作、消息提醒、价格波动、预订跳转或闭环交易。

## 5. 对你们项目的启发

如果是 `daniel-trip-agent` 这类项目，我建议优先补这几类能力，而不是先追求更强的“聊天感”：

- 把 itinerary 做成稳定的结构化对象，而不是只看自然语言
- 增强地图与路线约束，而不是只依赖 LLM 生成顺序
- 给酒店/景点价格打“来源可信度”和“更新时间”
- 支持用户二次编辑：换酒店、删景点、压缩预算、改亲子/豪华风格
- 把 FlyAI、高德、天气等外部数据源做统一置信度回填

如果以后要上 Deep Agents，更适合放在顶层做：
- 多轮需求澄清
- 方案比较
- 偏好记忆
- 导出不同版本行程

而底层路线规划、预算回填、价格校验、商品匹配，仍然应保留确定性代码。
