"""相关性评估器 - 文档质量控制"""
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama

from backend.models.state import ConversationState
from backend.config.settings import settings
from backend.logging.config import get_logger

logger = get_logger(__name__)


def assess_document_relevance(state: ConversationState) -> ConversationState:
    """
    评估每个检索到的文档是否与用户问题真正相关。
    """
    logger.info("评估文档相关性...")
    enhanced_query = state.get("enhanced_query", "")

    assessment_prompt = SystemMessage(
        content="""你是文档相关性评估专家。判断每篇文档是否对回答用户问题有帮助。

文档是相关的（RELEVANT），如果它包含：
- 直接回答问题的信息
- 对完整回答有支持作用的内容
- 有助于理解问题的背景知识

文档是无关的（IRRELEVANT），如果它：
- 讨论的主题与问题完全无关
- 不包含回答问题所需的信息
- 没有任何参考价值

请直接回答：RELEVANT 或 IRRELEVANT，不要有其他内容。"""
    )

    llm = ChatOllama(
        model=settings.LLM_MODEL,
        base_url=settings.LLM_BASE_URL,
        temperature=0,
        reasoning=False,
    )

    relevant_documents = []

    for i, doc in enumerate(state["retrieved_documents"]):
        user_question = HumanMessage(
            content=f"问题：{enhanced_query}\n\n待评估文档：\n{doc.page_content}"
        )

        prompt = ChatPromptTemplate.from_messages([assessment_prompt, user_question])
        response = prompt.format() + ""
        llm_response = llm.invoke(response)
        raw_response = llm_response.content.strip()

        logger.debug(f"文档 {i+1} 原始响应: {raw_response}")

        # 解析响应
        match = re.search(r'\b(RELEVANT|IRRELEVANT)\b', raw_response, re.IGNORECASE)
        if match:
            relevance = match.group(1).upper()
        else:
            relevance = "IRRELEVANT"
            logger.warning(f"无法解析文档 {i+1} 相关性，使用默认 IRRELEVANT")

        source = doc.metadata.get("source", "未知")
        logger.info(f"文档 {i+1}: {relevance} [{source}]")

        if relevance == "RELEVANT":
            relevant_documents.append(doc)

    # 更新状态
    state["retrieved_documents"] = relevant_documents
    state["should_generate"] = len(relevant_documents) > 0

    logger.info(f"最终相关文档数: {len(relevant_documents)}")
    return state
