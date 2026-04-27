"""查询优化器 - 自适应搜索改进"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

from backend.models.state import ConversationState
from backend.config.settings import settings
from backend.logging.config import get_logger
from backend.models.providers import get_llm

logger = get_logger(__name__)


def optimize_search_query(state: ConversationState) -> dict:
    """
    优化查询策略，当初始检索结果不佳时改进搜索查询。

    包含循环保护机制，防止无限优化。
    """
    logger.info("优化查询...")

    current_attempts = state.get("optimization_attempts", 0)

    # 防止无限优化循环
    if current_attempts >= settings.MAX_OPTIMIZATION_ATTEMPTS:
        logger.info("已达到最大优化次数")
        return {}

    current_query = state["enhanced_query"]

    optimization_prompt = SystemMessage(
        content="""你是查询优化专家。当前的查询未能检索到足够的相关信息。

你的任务是创建改进版本的查询，要求：
1. 使用不同的关键词或同义词
2. 调整查询结构以获得更好的匹配
3. 保持原始意图
4. 考虑同一概念的不同表达方式
5. 使查询更加具体和清晰

请仅输出优化后的查询，不要附带解释。"""
    )

    optimization_request = HumanMessage(
        content=f"需要优化的查询：{current_query}"
    )

    optimization_chain = ChatPromptTemplate.from_messages([optimization_prompt, optimization_request])
    llm = get_llm(temperature=0.2)

    formatted_prompt = optimization_chain.format()
    response = llm.invoke(formatted_prompt)
    optimized_query = response.content.strip()

    logger.info(f"优化查询（第{current_attempts + 1}次）：{optimized_query}")

    return {
        "enhanced_query": optimized_query,
        "optimization_attempts": current_attempts + 1,
    }
