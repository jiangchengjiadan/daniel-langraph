# 第八课：Checkpointer 与持久化
[来自：大模型 RAG 和 Agent 技术]()

行者常至为者常成  
2025年12月01日 23:53

## 目标
学习如何使用 Checkpointer (检查点) 来自动保存图的每一步状态，从而实现长时间运行的、可恢复的对话或任务。

## 核心讲解
Checkpointer 是 LangGraph 的“自动存档”系统。

当你为图配置了 Checkpointer 时，它会在每次 invoke (或 stream) 之后自动保存图的完整状态快照。

你需要提供：
- **存储后端**：LangGraph 提供了 MemorySaver (内存中，用于测试) 和 SqliteSaver (SQLite 数据库，用于生产)。
- **thread_id**：这是“会话 ID”。所有使用相同 thread_id 的 invoke 调用都会被视为同一场对话。

当你再次使用相同的 thread_id 调用 invoke 时，LangGraph 会自动从存储中加载上一次的 state，然后从那里继续。

## 实战代码
我们将使用**课程六**的“搜索智能体”，并为其添加持久化功能。

```python
import operator
from typing import Annotated, TypedDict, List
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
import uuid  # 用于生成唯一的 thread_id

# --- 复用课程六的代码 ---
# (0. 设置, 1. 定义工具, 2. 定义状态, 3. 定义节点, 4. 定义决策函数)

# --- 0. 设置 ---
llm = ChatOpenAI(temperature=0)
search_tool = DuckDuckGoSearchRun()

# --- 1. 定义工具 ---
@tool
def search(query: str):
    """当需要搜索互联网以获取信息时使用此工具。"""
    print(f"--- [工具] 搜索: {query} ---")
    return search_tool.run(query)

tools = [search]
llm_with_tools = llm.bind_tools(tools)

# --- 2. 定义状态 (State) ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# --- 3. 定义节点 (Nodes) ---
def agent_node(state: AgentState):
    print("--- [节点] Agent ---")
    response = llm_with_tools.invoke(state['messages'])
    return {"messages": [response]}

def tool_node(state: AgentState):
    print("--- [节点] Tool ---")
    last_message = state['messages'][-1]
    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call['name']
        tool_args = tool_call['args']
        if tool_name == "search":
            result = search.invoke(tool_args['query'])
            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_call['id'])
            )
    return {"messages": tool_messages}

# --- 4. 定义决策函数 (Conditional Edge) ---
def should_continue(state: AgentState):
    print("--- [决策] Should Continue? ---")
    if not state['messages'][-1].tool_calls:
        print("--- [决策] -> END ---")
        return "end"
    else:
        print("--- [决策] -> Tool ---")
        return "continue"

# --- 5. 定义图 (Graph) ---
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {"continue": "tools", "end": END}
)
workflow.add_edge("tools", "agent")

# --- 6. 编译图 (带 Checkpointer) ---

# !! 重点在这里 !!
# 我们使用 SqliteSaver.memory() 在内存中创建一个 SQLite 数据库 (用于演示)
# 在实际应用中，你会使用 SqliteSaver.from_conn_string("my_db.sqlite")
memory_saver = SqliteSaver.memory()

app = workflow.compile(
    checkpointer=memory_saver,
    # (课程七的内容) 如果我们想让图在人类介入时也保存状态，
    # 我们可以把 interrupt_before 和 checkpointer 结合使用
    # interrupt_before=["tools"] 
)

# --- 7. 运行图 (多轮对话) ---

# 我们需要一个"会话ID" (thread_id) 来标识这场对话
# 我们可以随机生成一个，或者使用用户ID等
thread_id = str(uuid.uuid4())

print(f"--- 开始新对话, Thread ID: {thread_id} ---")

# --- 第1轮对话 ---
print("\n--- 第 1 轮 ---")
config_1 = {"configurable": {"thread_id": thread_id}}
inputs_1 = {"messages": [HumanMessage(content="我叫 Bob")]}

# 第一次 invoke, 传入 config
response_1 = app.invoke(inputs_1, config=config_1)
print(f"AI: {response_1['messages'][-1].content}")

# --- 第2轮对话 ---
# *不* 需要传入 inputs_1 的状态！
# LangGraph 会自动从 Checkpointer 加载 'thread_id' 对应的历史记录
print("\n--- 第 2 轮 ---")
config_2 = {"configurable": {"thread_id": thread_id}}  # 使用 *相同* 的 thread_id
inputs_2 = {"messages": [HumanMessage(content="我的名字是什么?")]}

response_2 = app.invoke(inputs_2, config=config_2)
print(f"AI: {response_2['messages'][-1].content}")

# --- 第3轮对话 (带工具) ---
print("\n--- 第 3 轮 ---")
config_3 = {"configurable": {"thread_id": thread_id}}
inputs_3 = {"messages": [HumanMessage(content="北京今天的天气怎么样？")]}

response_3 = app.invoke(inputs_3, config=config_3)
print(f"AI: {response_3['messages'][-1].content}")

# --- 预期输出 ---
# --- 开始新对话, Thread ID: ... ---
#
# --- 第 1 轮 ---
# --- [节点] Agent ---
# --- [决策] Should Continue? ---
# --- [决策] -> END ---
# AI: 你好，Bob！很高兴认识你。
#
# --- 第 2 轮 ---
# --- [节点] Agent --- (它现在收到的 messages 是 [Human("我叫 Bob"), AI("你好..."), Human("我的名字是什么?")])
# --- [决策] Should Continue? ---
# --- [决策] -> END ---
# AI: 你的名字是 Bob。
#
# --- 第 3 轮 ---
# --- [节点] Agent ---
# --- [决策] Should Continue? ---
# --- [决策] -> Tool ---
# --- [节点] Tool ---
# --- [工具] 搜索: 北京今天的天气 ---
# --- [节点] Agent ---
# --- [决策] Should Continue? ---
# --- [决策] -> END ---
# AI: (关于北京天气的回答)
```

## 本节重点
- `SqliteSaver.memory()`：创建一个检查点存储。
- `app.compile(checkpointer=...)`：在编译时“插上”检查点。
- `config={"configurable": {"thread_id": "..."}}`：这是**最关键**的一步。invoke 时必须传入这个 config。
- **thread_id 是状态的唯一标识**。只要 thread_id 相同，LangGraph 就会自动加载该线程的所有历史 messages (或其他状态)，并在其基础上继续。你不需要（也不应该）手动管理历史记录。

## 源代码
本章项目代码，请从以下百度网盘下载：
通过网盘分享的文件：chapter_08_checkpointer.zip  
链接: [https://pan.baidu.com/s/1c_zF5oHKY1kVormBvS-Jkw?pwd=q7uu]()  
提取码: q7uu

---
