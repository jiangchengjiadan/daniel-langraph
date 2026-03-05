下面是**完整、干净、无重复、标准 Markdown 格式**的整理版文档，你可以直接复制保存为 `.md` 文件使用：

---

# 第六课：用循环实现 ReAct 和工具调用

[来自：大模型RAG和Agent技术]()

行者常至为者常成  
2025年11月26日 23:28

---

## ReAct 智能体实现思路

结合“条件边”创建“循环”。这是实现 ReAct 风格的智能体（思考 -> 行动 -> 观察 -> 思考…）和工具调用的标准模式。

**核心讲解：**

“循环”(Cycle) 在 LangGraph 中并不是一个特殊的结构，它只是一个指向了“上游”节点的条件边。

标准的工具调用流程是：

- **Agent (LLM) 节点**：LLM 思考，决定是否调用工具。
- **条件边**：
  - 如果 LLM 不需要调用工具（它有答案了），则 -> END。
  - 如果 LLM 需要调用工具，则 -> Tool 节点。
- **Tool 节点**：执行工具（如搜索），获取结果。
- **固定边**：Tool 节点执行完毕后，自动 -> Agent (LLM) 节点。

Agent 节点收到工具结果，再次思考，循环开始…

流程图示意：
![image.png]()

---

## 实战代码

我们将构建一个“搜索智能体”，它只有一个工具：`duckduckgo_search`。

```python
import operator
from typing import Annotated, TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun

# --- 0. 设置 ---
llm = ChatOpenAI(temperature=0)
search_tool = DuckDuckGoSearchRun()

# --- 1. 定义工具 ---
# 使用 @tool 装饰器让函数成为一个 LangChain Tool
@tool
def search(query: str):
    """当需要搜索互联网以获取信息时使用此工具。"""
    print(f"--- 正在执行搜索: {query} ---")
    return search_tool.run(query)

tools = [search]

# 将工具绑定到 LLM，这样 LLM 才知道自己有哪些工具可用
llm_with_tools = llm.bind_tools(tools)

# --- 2. 定义状态 (State) ---
# 我们将使用 LangChain 的标准消息列表
class AgentState(TypedDict):
    """
    智能体状态定义
    
    这个状态跟踪对话中的所有消息，使用 Annotated[List[BaseMessage], operator.add]
    确保消息列表可以被正确地累加和更新。
    """
    messages: Annotated[List[BaseMessage], operator.add]

# --- 3. 定义节点 (Nodes) ---

# 节点1: Agent (LLM)
# 这个节点会调用 LLM。LLM 可能会返回一个 AIMessage（如果它能直接回答），
# 或者返回一个带有 'tool_calls' 的 AIMessage（如果它需要调用工具）。
def agent_node(state: AgentState):
    print("--- 正在执行 agent_node ---")
    # 传入整个消息历史
    response = llm_with_tools.invoke(state['messages'])
    # 我们总是将 LLM 的响应添加到消息列表中
    return {"messages": [response]}

# 节点2: Tool Executor
# 这个节点检查最新的 AIMessage。如果它有 'tool_calls'，
# 它就执行这些工具，并返回 ToolMessage
def tool_node(state: AgentState):
    print("--- 正在执行 tool_node ---")
    # 1. 获取最新的消息 (这应该是 agent_node 刚发出的 AIMessage)
    last_message = state['messages'][-1]
    
    # 2. 检查是否有工具调用
    if not last_message.tool_calls:
        # 理论上我们不应该在没有工具调用的情况下进入这个节点
        # 但作为安全检查
        print("--- tool_node 发现没有工具调用 ---")
        return {}

    # 3. 执行工具
    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call['name']
        tool_args = tool_call['args']
        
        # 找到我们定义的工具并执行
        if tool_name == "search":
            result = search.invoke(tool_args['query'])
            # 将结果封装成 ToolMessage
            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_call['id'])
            )
        else:
            # 处理未知的工具
            tool_messages.append(
                ToolMessage(content=f"未知工具: {tool_name}", tool_call_id=tool_call['id'])
            )
            
    # 4. 将工具的输出（ToolMessage）返回
    return {"messages": tool_messages}

# --- 4. 定义决策函数 (Conditional Edge) ---
def should_continue(state: AgentState):
    """
    决策函数：决定是否继续调用工具还是结束
    
    这个函数在agent_node之后被调用，检查最新的AIMessage是否包含工具调用。
    - 如果没有工具调用，说明LLM认为任务完成，返回"end"
    - 如果有工具调用，说明需要继续调用工具，返回"continue"
    
    Args:
        state (AgentState): 当前状态
        
    Returns:
        str: "end" 表示结束，"continue" 表示继续调用工具
    """
    
    print("--- 正在做决策 (should_continue) ---")
    last_message = state['messages'][-1]
    
    # 如果最新的消息 (AIMessage) *没有* tool_calls，说明 Agent 认为工作完成了。
    if not last_message.tool_calls:
        print("--- 决策: 结束 (END) ---")
        return "end"
    # 否则，说明 Agent 想要调用工具。
    else:
        print("--- 决策: 继续调用工具 (continue) ---")
        return "continue"

# --- 5. 定义图 (Graph) ---
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)

# --- 6. 定义图的结构 (Edges) ---
# 入口点是 'agent'
workflow.set_entry_point("agent")

# 添加条件边：
# 'agent' 节点之后，调用 'should_continue' 函数做决策
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        # 如果返回 "continue"，则下一步去 'tools' 节点
        "continue": "tools",
        # 如果返回 "end"，则流程结束
        "end": END
    }
)

# 添加固定边：
# 'tools' 节点执行完毕后，*总是* 回到 'agent' 节点，形成循环
workflow.add_edge("tools", "agent")

# --- 7. 编译图 ---
app = workflow.compile()

# --- 8. 运行图 ---
print("--- 开始运行图 ---")
# 初始状态是一个包含 HumanMessage 的列表
inputs = {"messages": [HumanMessage(content="北京今天的天气怎么样？")]}
final_state = app.invoke(inputs)

print("\n--- 最终结果 ---")
print(final_state['messages'][-1].content)

# --- 预期输出 (示例) ---
# --- 开始运行图 ---
# --- 正在执行 agent_node ---
# --- 正在做决策 (should_continue) ---
# --- 决策: 继续调用工具 (continue) ---
# --- 正在执行 tool_node ---
# --- 正在执行搜索: 北京今天的天气 ---
# --- 正在执行 agent_node ---
# --- 正在做决策 (should_continue) ---
# --- 决策: 结束 (END) ---
#
# --- 最终结果 ---
# (一个包含天气信息的、友好的回答)
```

---

## 本节重点

- **messages 状态**：使用 `Annotated[List[BaseMessage], operator.add]` 是构建 Agent 的标准做法。Agent 节点添加 AIMessage，Tool 节点添加 ToolMessage。
- **llm.bind_tools(tools)**：它让 LLM 知道自己有哪些工具可用，并以特定格式（tool_calls）输出。
- **循环的实现**：`agent -> (conditional) -> tools -> agent`。这个 `tools` 到 `agent` 的固定 `add_edge` 是创建循环的关键。

---

## 源代码

**本章项目代码，请从以下百度网盘下载：**

通过网盘分享的文件：chapter_06_react_tools.zip  
链接: [https://pan.baidu.com/s/1Lumh1Y9fK82wxxef9ykfWQ?pwd=fw4b]()  
提取码: fw4b

---
