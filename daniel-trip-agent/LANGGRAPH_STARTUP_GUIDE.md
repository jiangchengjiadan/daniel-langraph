# LangGraph 版本启动指南 🚀

## 📋 准备工作清单

### 1. 系统要求
- ✅ Python 3.10+
- ✅ Node.js 20+ 推荐（后端通过 `npx` 启动高德 MCP Server）
- ✅ 高德地图 API 密钥（MCP服务端API + Web端JavaScript API）
- ✅ LLM API 密钥（OpenAI/DeepSeek等）

---

## 🔧 后端启动步骤

### 步骤 1: 创建并激活虚拟环境

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate

# Windows:
# venv\Scripts\activate
```

### 步骤 2: 安装依赖

```bash
# 安装所有依赖（包括 LangGraph 和 LangChain）
pip install -r requirements.txt
```

**主要新增依赖：**
- `langgraph>=0.2.0` - 图编排框架
- `langchain>=0.3.0` - LangChain 核心
- `langchain-openai>=0.2.0` - OpenAI 集成
- `langchain-core>=0.3.0` - LangChain 核心组件
- `langchain-community>=0.3.0` - 社区工具
- `langchain-mcp-adapters>=0.2.1` - 将 MCP Server 工具转换为 LangChain tools
- `mcp>=1.12.0` - MCP Python 协议支持

### 步骤 3: 配置环境变量

检查 `backend/.env` 文件，确保配置以下变量：

```bash
# LLM配置
OPENAI_API_KEY=sk-xxx                    # 你的OpenAI API密钥
OPENAI_API_BASE=https://api.openai.com/v1  # API基础URL
LLM_MODEL=gpt-4                          # 使用的模型

# 高德地图配置
AMAP_MAPS_API_KEY=your_amap_key          # 高德 MCP Server 使用的服务端API密钥
AMAP_MCP_COMMAND=npx
AMAP_MCP_PACKAGE=@amap/amap-maps-mcp-server
AMAP_MCP_TIMEOUT=30

# LangGraph 开关（默认启用）
USE_LANGGRAPH=true                       # true=使用LangGraph, false=回滚到HelloAgents
```

**重要说明：**
- `USE_LANGGRAPH=true`：使用新的 LangGraph 实现（默认，推荐）
- `USE_LANGGRAPH=false`：回滚到原来的 HelloAgents 实现
- 后端旅行规划节点会通过 `langchain-mcp-adapters` 启动官方高德 MCP Server，并调用 `maps_text_search`、`maps_weather` 等工具。

### 步骤 4: 验证基本功能（可选）

```bash
# 在虚拟环境中运行验证脚本
python test_langgraph_basic.py
```

预期输出：
```
============================================================
LangGraph 实现基本验证
============================================================

测试1: 检查模块导入
✅ 所有模块导入成功!

测试2: 规划器初始化
✅ 规划器初始化成功!

测试3: 状态结构验证
✅ 状态结构验证成功!

============================================================
🎉 所有测试通过!
============================================================
```

### 步骤 5: 启动后端服务

```bash
# 方式1: 使用 run.py（推荐）
python run.py

# 方式2: 使用 uvicorn 直接启动
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

**验证后端启动成功：**

访问健康检查接口：
```bash
curl http://localhost:8000/api/trip/health
```

预期返回（LangGraph版本）：
```json
{
  "status": "healthy",
  "service": "trip-planner",
  "implementation": "LangGraph",
  "version": "2.0"
}
```

---

## 🎨 前端启动步骤

### 步骤 1: 安装依赖

```bash
cd frontend

# 安装 npm 依赖
npm install
```

### 步骤 2: 配置环境变量

创建 `frontend/.env` 文件：

```bash
# 复制示例文件
cp .env .env

# 编辑 .env 文件
vim .env  # 或使用其他编辑器
```

配置内容：
```bash
# 后端 API 地址（确保与后端端口一致）
VITE_API_BASE_URL=http://localhost:8000

# 高德地图 Web 端 JavaScript API Key
VITE_AMAP_WEB_KEY=your_amap_web_key
```

**注意：** 前端需要的是**高德地图 Web 端 JavaScript API Key**，与后端的服务端 API Key 不同。

### 步骤 3: 启动开发服务器

```bash
npm run dev
```

预期输出：
```
  VITE v6.0.7  ready in 500 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### 步骤 4: 访问应用

在浏览器中打开：`http://localhost:5173`

---

## ✅ 完整启动检查清单

### 后端检查
- [ ] 虚拟环境已激活
- [ ] 所有依赖已安装（包括 langgraph、langchain）
- [ ] `.env` 文件已配置（LLM API Key、高德地图 MCP API Key）
- [ ] `USE_LANGGRAPH=true` 已设置
- [ ] 本机可以运行 `npx -y @amap/amap-maps-mcp-server`
- [ ] 后端服务已启动在 `http://localhost:8000`
- [ ] 健康检查接口返回 `"implementation": "LangGraph"`

### 前端检查
- [ ] npm 依赖已安装
- [ ] `.env` 文件已配置（API Base URL、高德地图 Web Key）
- [ ] 前端服务已启动在 `http://localhost:5173`
- [ ] 浏览器能正常访问页面

---

## 🔍 验证 LangGraph 是否正常工作

### 方法 1: 查看日志

后端启动时应该看到：
```
INFO:     🔧 使用 LangGraph 实现
INFO:     初始化 LangGraph 旅行规划器...
INFO:     ✅ LangGraph 旅行规划器初始化成功
```

### 方法 2: 测试旅行规划

1. 在前端填写旅行信息
2. 点击"生成旅行计划"
3. 查看后端日志，应该看到：
   ```
   INFO:     📊 开始执行 LangGraph 工作流...
   INFO:     📋 执行日志:
   INFO:       - attraction_search: success
   INFO:       - weather_query: success
   INFO:       - hotel_search: success
   INFO:       - itinerary_planning: success
   INFO:     ✅ 旅行计划生成完成!
   ```

---

## 🐛 常见问题排查

### 问题 1: ModuleNotFoundError: No module named 'langgraph'

**原因：** 依赖未安装或虚拟环境未激活

**解决：**
```bash
# 确认虚拟环境已激活
source venv/bin/activate

# 重新安装依赖
pip install -r requirements.txt
```

### 问题 2: 后端返回 "服务不可用"

**原因：** 环境变量配置错误

**解决：**
1. 检查 `backend/.env` 文件
2. 确认 `OPENAI_API_KEY` 和 `AMAP_MAPS_API_KEY` 已正确配置
3. 重启后端服务

### 问题 3: 前端无法连接后端

**原因：** API 地址配置错误

**解决：**
1. 检查 `frontend/.env` 中的 `VITE_API_BASE_URL`
2. 确认后端服务正在运行
3. 测试后端健康检查接口：`curl http://localhost:8000/api/trip/health`

### 问题 4: 想回滚到 HelloAgents 版本

**解决：**
1. 修改 `backend/.env`：
   ```bash
   USE_LANGGRAPH=false
   ```
2. 重启后端服务
3. 验证：健康检查接口应返回 `"implementation": "HelloAgents"`

---

## 📊 性能对比

### HelloAgents（原版本）
- **执行方式：** 顺序串行
- **响应时间：** 25-35 秒
- **节点执行：** 景点搜索 → 天气查询 → 酒店搜索 → 行程规划

### LangGraph（新版本）
- **执行方式：** 前3个节点并行执行
- **响应时间：** 预计 15-25 秒（提升 30-50%）
- **节点执行：** (景点搜索 || 天气查询 || 酒店搜索) → 行程规划

---

## 🎯 关键改进点

1. **并行执行**：景点、天气、酒店搜索同时进行
2. **类型安全**：TypedDict 提供完整的类型检查
3. **错误处理**：更精细的错误处理和 fallback 机制
4. **状态管理**：统一的状态在节点间自动传递
5. **可观测性**：详细的执行日志和状态追踪

---

## 📚 相关文档

- **迁移计划：** `/Users/danielhe/.claude/plans/squishy-dancing-willow.md`
- **原版 README：** `README.md`
- **API 文档：** 启动后访问 `http://localhost:8000/docs`

---

## 💡 提示

- 首次使用建议先用 `USE_LANGGRAPH=true` 测试新版本
- 如遇问题可随时切换回 `USE_LANGGRAPH=false`
- 前端无需任何修改，完全兼容新旧版本

祝使用愉快！🎉
