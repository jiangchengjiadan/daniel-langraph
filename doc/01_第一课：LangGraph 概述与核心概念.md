# 第一课：LangGraph 概述与核心概念

[来自： 大模型RAG和Agent技术]()

行者常至为者常成

2025年11月16日 00:40

---

## 1.1 为什么选择 LangGraph：状态管理与流程编排

在大型语言模型（LLM）应用开发中，传统链式调用（Chain）模式存在明显局限。它难以应对复杂、多步骤或需要长期记忆的任务，通常是无状态的，且流程固定，无法根据实时信息进行动态决策。

LangGraph 正是为了解决这些限制而诞生的**低层级编排框架和运行时环境**。它专注于构建**有状态**、**多步骤**、**长周期运行**的 Agent 应用程序，通过图形化模型来定义 Agent 的复杂行为。

LangGraph 的核心优势在于其提供的底层基础设施，保障了复杂 Agent 工作流的**可靠性**、**灵活性**和**可调试性**。

### 核心特性
- **持久执行 (Durable Execution)**：LangGraph 允许构建能够长时间运行且能容忍失败的 Agent。通过内置的检查点和持久化机制，流程可以在中断后从上次停止的位置恢复。
- **动态控制流**：框架能够支持复杂的控制结构，包括分支、合并和循环。这使得开发者可以设计单 Agent、多 Agent 或分层 Agent 等多样化的架构。
- **Human-in-the-Loop (人工介入)**：LangGraph 提供了在任何执行点检查和修改 Agent 状态的能力，便于人工监督和调试，提高了复杂系统的可控性。

### 底层运行机制
LangGraph 的底层运行机制基于消息传递和"超级步骤"（super-steps）的概念，这借鉴了 Google 的 Pregel 系统。这种架构意味着工作流不是一次性执行的，而是分解为离散的步骤，节点之间通过传递状态消息进行通信。

这种分步、可并行的特性是 LangGraph 区别于传统顺序执行框架的关键，因为它天然支持高并发和容错性，为 Agent 的弹性运行奠定了基础。

---

## 1.2 核心三要素：State、Node 和 Edge

LangGraph 将 Agent 工作流精确地建模为一个图结构，其运转依赖于三个核心组件的协作。

### State (状态)
状态是 LangGraph 中最核心的元素，它是一个在图中流动的"数据包"，是整个应用程序的共享数据结构，代表了流程在某一时刻的快照。图中所有的节点都会读取这个状态，并可以对其进行更新。

为了确保数据在复杂的、多 Agent 的工作流中保持清晰和一致，LangGraph 强制要求状态必须是**强类型**定义的，通常使用 Python 的 typing.TypedDict。

### Node (节点)
节点是执行具体工作的计算单元，是图中的"工人"。它就是一个 Python 函数或可调用对象。节点接收当前的状态 state 作为输入，执行一些逻辑，然后返回一个字典，这个字典里的内容将被用来更新状态。

它们可以是任意的 Python 函数、异步函数，也可以是 LangChain 的 Runnable 实例，如 LLM 或工具。一个节点接收完整的当前状态作为输入，执行其逻辑（无论是调用 AI 模型还是执行普通代码），然后返回一个包含状态更新的字典。

需要强调的是，节点返回的是**增量更新 (Delta Update)**，而不是整个新的状态。LangGraph 框架负责将这些更新安全地合并到中央状态中。

### Edge (边缘)
边缘定义了工作流的流程走向，它们连接了不同的节点。边缘本质上也是函数，其职责是决定当一个节点执行完成后，下一步应该执行哪个节点。边缘主要分为两种类型：

- **固定边缘 (Fixed Edges)**：使用 add_edge 定义，用于无条件地从 Node A 转向 Node B，适用于线性流程。
- **条件边缘 (Conditional Edges)**：使用 add_conditional_edges 定义，它们是动态控制流的基础。根据当前状态的内容，条件边缘可以决定下一步走向哪个节点，或者直接终止流程。

---

## 1.3 环境准备与 LangGraph 极简入门 (Hello World)

LangGraph 的安装非常简单。只需要安装核心库即可开始：

```bash
pip install -U langgraph langchain-core
```

### 实战代码

```python
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END

# --- 1. 定义状态 (State) ---
# 状态是图中流动的数据结构。
# 我们使用 TypedDict 来定义。
class MyGraphState(TypedDict):
    # 'messages' 键是一个列表，Annotated[list, operator.add] 
    # 是一个LangGraph的魔法：它告诉图，
    # 当一个节点返回 'messages' 时，不要覆盖它，而是"添加" (add) 到现有列表中。
    messages: Annotated[list, operator.add]

# --- 2. 定义节点 (Nodes) ---
# 节点是图中的"工人"，它们是接收状态并返回更新的函数。
def my_node(state: MyGraphState):
    print("--- 正在执行 my_node ---")
    # state 是当前状态的字典
    # 我们返回一个字典，其中包含要更新的状态部分
    return {"messages": ["Hello, LangGraph!"]}

# --- 3. 定义图 (Graph) ---
# StateGraph 是我们构建图的入口
workflow = StateGraph(MyGraphState)

# 添加一个名为 "greet" 的节点，它对应我们上面定义的 my_node 函数
workflow.add_node("greet", my_node)

# --- 4. 定义图的结构 (Edges) ---
# 设置入口点。图将从 "greet" 节点开始执行。
workflow.set_entry_point("greet")

# 添加一条边。"greet" 节点执行完毕后，流程结束 (END)。
workflow.add_edge("greet", END)

# --- 5. 编译图 ---
# compile() 方法将我们的图定义编译成一个可执行的 "app"
app = workflow.compile()

# --- 6. 运行图 ---
# 我们使用 .invoke() 来运行图。
# 必须提供一个初始状态。
initial_state = {"messages": []}
final_state = app.invoke(initial_state)

print("\n--- 最终结果 ---")
print(final_state)

# --- 预期输出 ---
# --- 正在执行 my_node ---
#
# --- 最终结果 ---
# {'messages': ['Hello, LangGraph!']}
```

### 本节重点
- **StateGraph(MyGraphState)**：先定义状态，再创建图。
- **Annotated[list, operator.add]**：这是让列表_累加_而不是_替换_的关键。operator.add 适用于列表（拼接）、数字（相加）等。
- **workflow.add_node("name", function)**：注册一个节点。
- **workflow.set_entry_point("name")**：指定从哪个节点开始。
- **workflow.add_edge("from_node", "to_node")**：连接两个节点。END 是一个特殊的保留字，表示流程结束。
- **app.invoke(initial_state)**：传入初始状态来启动图。

### 源代码
本章可运行的项目代码，请从以下百度网盘下载：

通过网盘分享的文件：chapter_01_overview.zip  
链接: [https://pan.baidu.com/s/15zfLWVziflI_se-RUkoZoA?pwd=uvup]()  
提取码: uvup

---
