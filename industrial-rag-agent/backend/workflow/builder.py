"""工作流构建器 - LangGraph流程编排"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from backend.models.state import ConversationState
from backend.nodes.enhancer import enhance_user_query
from backend.nodes.validator import validate_topic_relevance
from backend.nodes.retriever import fetch_relevant_content
from backend.nodes.assessor import assess_document_relevance
from backend.nodes.generator import generate_contextual_response
from backend.nodes.optimizer import optimize_search_query
from backend.nodes.handlers import handle_off_topic_queries, handle_no_relevant_results
from backend.logging.config import get_logger

logger = get_logger(__name__)


def route_by_topic(state: ConversationState) -> str:
    """基于话题相关性进行路由"""
    logger.debug(f"话题路由决策，topic_relevance: {state.get('topic_relevance', '')}")

    relevance = state.get("topic_relevance", "").strip().upper()

    if relevance == "RELEVANT":
        logger.debug("→ 继续内容检索")
        return "fetch_content"
    else:
        logger.debug("→ 路由到无关话题处理")
        return "handle_off_topic"


def route_by_document_quality(state: ConversationState) -> str:
    """基于文档质量进行路由"""
    logger.debug("文档质量路由决策")

    optimization_attempts = state.get("optimization_attempts", 0)

    if state.get("should_generate", False):
        logger.debug("→ 生成响应")
        return "generate_response"
    elif optimization_attempts >= 2:
        logger.debug("→ 达到最大优化次数，无结果处理")
        return "handle_no_results"
    else:
        logger.debug("→ 优化查询")
        return "optimize_query"


def route_by_document_quality_for_stream(state: ConversationState) -> str:
    """流式接口使用：检索完成后交给 API 层流式生成。"""
    logger.debug("流式文档质量路由决策")

    optimization_attempts = state.get("optimization_attempts", 0)

    if state.get("should_generate", False):
        logger.debug("→ 交给流式响应")
        return "stream_response"
    elif optimization_attempts >= 2:
        logger.debug("→ 达到最大优化次数，无结果处理")
        return "handle_no_results"
    else:
        logger.debug("→ 优化查询")
        return "optimize_query"


def build_workflow():
    """构建完整的RAG Agent工作流"""
    logger.info("构建工作流...")

    # 创建状态图
    workflow = StateGraph(ConversationState)

    # 添加处理节点
    workflow.add_node("enhance_query", enhance_user_query)
    workflow.add_node("validate_topic", validate_topic_relevance)
    workflow.add_node("handle_off_topic", handle_off_topic_queries)
    workflow.add_node("fetch_content", fetch_relevant_content)
    workflow.add_node("assess_relevance", assess_document_relevance)
    workflow.add_node("generate_response", generate_contextual_response)
    workflow.add_node("optimize_query", optimize_search_query)
    workflow.add_node("handle_no_results", handle_no_relevant_results)

    # 定义边连接
    # 1. 增强查询 → 话题验证
    workflow.add_edge("enhance_query", "validate_topic")

    # 2. 话题验证 → 条件路由
    workflow.add_conditional_edges(
        "validate_topic",
        route_by_topic,
        {
            "fetch_content": "fetch_content",
            "handle_off_topic": "handle_off_topic",
        }
    )

    # 3. 内容检索 → 相关性评估
    workflow.add_edge("fetch_content", "assess_relevance")

    # 4. 相关性评估 → 条件路由
    workflow.add_conditional_edges(
        "assess_relevance",
        route_by_document_quality,
        {
            "generate_response": "generate_response",
            "optimize_query": "optimize_query",
            "handle_no_results": "handle_no_results",
        }
    )

    # 5. 查询优化 → 重新检索（循环）
    workflow.add_edge("optimize_query", "fetch_content")

    # 6. 终止节点
    workflow.add_edge("generate_response", END)
    workflow.add_edge("handle_no_results", END)
    workflow.add_edge("handle_off_topic", END)

    # 设置入口点
    workflow.set_entry_point("enhance_query")

    logger.info("工作流构建完成")
    return workflow


def build_streaming_workflow():
    """构建流式接口专用工作流：不在图内执行最终生成。"""
    logger.info("构建流式工作流...")

    workflow = StateGraph(ConversationState)

    workflow.add_node("enhance_query", enhance_user_query)
    workflow.add_node("validate_topic", validate_topic_relevance)
    workflow.add_node("handle_off_topic", handle_off_topic_queries)
    workflow.add_node("fetch_content", fetch_relevant_content)
    workflow.add_node("assess_relevance", assess_document_relevance)
    workflow.add_node("optimize_query", optimize_search_query)
    workflow.add_node("handle_no_results", handle_no_relevant_results)

    workflow.add_edge("enhance_query", "validate_topic")
    workflow.add_conditional_edges(
        "validate_topic",
        route_by_topic,
        {
            "fetch_content": "fetch_content",
            "handle_off_topic": "handle_off_topic",
        }
    )
    workflow.add_edge("fetch_content", "assess_relevance")
    workflow.add_conditional_edges(
        "assess_relevance",
        route_by_document_quality_for_stream,
        {
            "stream_response": END,
            "optimize_query": "optimize_query",
            "handle_no_results": "handle_no_results",
        }
    )
    workflow.add_edge("optimize_query", "fetch_content")
    workflow.add_edge("handle_no_results", END)
    workflow.add_edge("handle_off_topic", END)
    workflow.set_entry_point("enhance_query")

    logger.info("流式工作流构建完成")
    return workflow


# 全局工作流实例
_workflow = None
_compiled_workflow = None
_streaming_workflow = None
_compiled_streaming_workflow = None


def get_workflow():
    """获取编译后的工作流"""
    global _workflow, _compiled_workflow

    if _compiled_workflow is None:
        _workflow = build_workflow()
        # 创建内存检查点存储
        memory = MemorySaver()
        _compiled_workflow = _workflow.compile(checkpointer=memory)
        logger.info("工作流编译完成")

    return _compiled_workflow


def get_streaming_workflow():
    """获取流式接口专用的编译工作流"""
    global _streaming_workflow, _compiled_streaming_workflow

    if _compiled_streaming_workflow is None:
        _streaming_workflow = build_streaming_workflow()
        memory = MemorySaver()
        _compiled_streaming_workflow = _streaming_workflow.compile(checkpointer=memory)
        logger.info("流式工作流编译完成")

    return _compiled_streaming_workflow
