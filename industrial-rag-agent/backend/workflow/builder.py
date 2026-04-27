"""工作流构建器 - LangGraph流程编排"""
from langgraph.graph import StateGraph, END

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


def build_workflow() -> StateGraph:
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
