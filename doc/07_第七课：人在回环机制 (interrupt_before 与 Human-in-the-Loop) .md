# 第七课：人在回环机制 (interrupt_before 与 Human-in-the-Loop)
来自：大模型RAG和Agent技术

行者常至为者常成
2025年11月28日 17:45

## 目标
学会如何使用"中断" (Interrupts) 来暂停图的执行，以便人类用户可以审查状态、提供反馈，然后再继续。

## 核心讲解
Human-in-the-Loop (HITL) 在构建可控、安全的智能体时非常重要。LangGraph 允许你在进入某个节点前自动暂停。

`app.compile(interrupt_before=["node_name"])` 就是实现这一功能的法宝。

当图运行到 `node_name` 之前时，它会暂停并返回当前的 state。你需要审查这个 state，然后调用 `app.continue()` 来继续，或者 `app.update_state()` 来修改状态后再继续。

## 实战代码
我们将构建一个"计划-审批-执行"流程：
- **节点A (planner):** 生成一个计划（例如，["步骤1", "步骤2"]）
- **中断点:** 在执行之前暂停，等待人类审批
- **节点B (executor):** (如果获批) 执行计划

流程图示意：
（上图中的虚线红色节点 **human_approval_node** 代表一个"中断点"）

```python
import operator
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

# --- 1. 定义状态 (State) ---
class PlanState(TypedDict):
    task: str           # 原始任务
    plan: List[str]     # 步骤列表
    feedback: str       # 人类反馈
    # 每次的执行结果都累加
    execution_log: Annotated[list, operator.add]

# --- 2. 定义节点 (Nodes) ---
def planner_node(state: PlanState):
    print("--- 正在执行 planner_node ---")
    task = state['task']
    # 这是一个模拟的计划
    plan = [f"步骤A: 分析 '{task}'", f"步骤B: 执行 '{task}'"]
    print(f"生成的计划: {plan}")
    return {"plan": plan, "feedback": "pending"}

def executor_node(state: PlanState):
    print("--- 正在执行 executor_node ---")
    plan = state['plan']
    logs = []
    for step in plan:
        # 模拟执行
        log_entry = f"已执行: {step}"
        print(log_entry)
        logs.append(log_entry)
    
    return {"execution_log": logs, "feedback": "done"}

# --- 3. 定义决策函数 (Conditional Edge) ---
def should_execute(state: PlanState):
    print("--- 正在做决策 (should_execute) ---")
    # 这个 feedback 字段将由人类在中断期间提供
    if state.get("feedback") == "approved":
        print("--- 决策: 批准，执行 ---")
        return "execute"
    else:
        print("--- 决策: 拒绝，结束 ---")
        return "end"

# --- 4. 定义图 (Graph) ---
workflow = StateGraph(PlanState)

workflow.add_node("planner", planner_node)
workflow.add_node("executor", executor_node)

# --- 5. 定义图的结构 (Edges) ---
workflow.set_entry_point("planner")

# 计划 -> 决策
workflow.add_conditional_edges(
    "planner",
    should_execute,
    {
        "execute": "executor",
        "end": END
    }
)

# 执行 -> 结束
workflow.add_edge("executor", END)

# --- 6. 编译图 (带中断) ---
#
# !! 重点在这里 !!
# 我们告诉图，在 *进入* 'executor' 节点 *之前*，或者在 *进入* 'END' 节点 *之前*
# (即 should_execute 决策之后)，暂停执行。
#
app = workflow.compile(interrupt_before=["executor", END])

# --- 7. 运行图 (交互式) ---

print("--- 开始运行图 ---")
task = {"task": "分析市场数据"}
# 第一次 invoke，图会运行到 "planner" 节点，
# 然后在进入 "executor" 或 "END" 之前暂停
initial_state = app.invoke(task)

print("\n--- 图已暂停 ---")
print(f"当前计划: {initial_state['plan']}")
print(f"当前状态: {initial_state['feedback']}")

# --- 人类审批 (模拟) ---
# 我们可以审查 'initial_state'
# 假设我们批准了
if initial_state['plan']:
    print("\n--- 人类已审批，准备继续 ---")
    
    # 我们使用 .continue() 来继续执行
    # 我们还可以在这里更新状态，例如设置 "feedback"
    # 注意：在 LangGraph v0.1+ 中，我们通过传入一个元组 (None, state_update) 来更新状态并继续
    # 或者使用 .update_state() 然后 .continue()
    
    # 简单起见，我们先更新状态，再继续
    app.update_state(initial_state, {"feedback": "approved"})
    
    # 调用 continue 时不带参数，它会使用更新后的状态
    final_state = app.continue_invoke(initial_state)

    print("\n--- 流程已完成 ---")
    print(f"执行日志: {final_state['execution_log']}")

else:
    print("--- 计划未生成，流程异常 ---")

# --- 预期输出 ---
# --- 开始运行图 ---
# --- 正在执行 planner_node ---
# 生成的计划: ["步骤A: 分析 '分析市场数据'", "步骤B: 执行 '分析市场数据'"]
# --- 正在做决策 (should_execute) ---
# --- 决策: 拒绝，结束 ---
#
# --- 图已暂停 ---
# 当前计划: ["步骤A: 分析 '分析市场数据'", "步骤B: 执行 '分析市场数据'"]
# 当前状态: pending
#
# --- 人类已审批，准备继续 ---
# --- 正在做决策 (should_execute) --- (注：更新状态后，决策会重新运行)
# --- 决策: 批准，执行 ---
# --- 正在执行 executor_node ---
# 已执行: 步骤A: 分析 '分析市场数据'
# 已执行: 步骤B: 执行 '分析市场数据'
#
# --- 流程已完成 ---
# 执行日志: ["已执行: 步骤A: 分析 '分析市场数据'", "已执行: 步骤B: 执行 '分析市场数据'"]
```

## 本节重点
- `app.compile(interrupt_before=["node_name"])`: 编译时指定中断点。
- `app.invoke()`: 第一次调用 invoke 时，它会运行直到中断点，并返回当前 state。
- `app.update_state(state, {"key": "value"})`: 在图暂停时，用这个方法来修改状态（例如，添加人类的反馈）。
- `app.continue_invoke(state)`: 使用这个方法让图从暂停的地方继续运行。

## 源代码
本章项目代码，请从以下百度网盘下载：
链接: [https://pan.baidu.com/s/1P-uHO6fVBSILJyWp2iLeWQ?pwd=t7eq]
提取码: t7eq

---
