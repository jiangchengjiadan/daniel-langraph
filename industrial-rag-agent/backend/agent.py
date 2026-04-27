"""LangGraph Platform 入口 - 导出编译后的 graph

langgraph.json 指向此模块的 graph 变量。
不传入 checkpointer，由 LangGraph Server 自动注入。
"""
from backend.workflow.builder import build_workflow

graph = build_workflow().compile()
