"""查询增强器 - 智能问题重写"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

from backend.models.state import ConversationState
from backend.logging.config import get_logger
from backend.models.providers import get_llm
from backend.nodes.utils import extract_text_content

logger = get_logger(__name__)


def enhance_user_query(state: ConversationState) -> dict:
    """
    增强用户查询，将上下文相关的查询转化为自包含的优化查询。

    策略：
    1. 第一个问题直接使用原始查询
    2. 有对话历史时，生成简洁的增强查询（不超过30字）
    """
    messages = state["messages"]
    original_query = extract_text_content(messages[-1].content)
    logger.info(f"增强查询: {original_query}")

    # 检查是否有对话上下文（第一个问题直接使用原始查询）
    if len(messages) <= 1:
        # 首个问题，直接使用原始查询
        enhanced_query = original_query
        logger.info(f"首个问题 - 使用原始查询: {enhanced_query}")
    else:
        # 有对话历史，生成简洁的增强查询
        previous_messages = messages[:-1]
        current_question = original_query

        # 构建简洁的增强提示
        context_messages = [
            SystemMessage(
                content="""你是工业设备售后客服的查询优化专家。

你的任务：将用户问题改写为简洁的搜索查询（不超过30字）。

规则：
1. 融入上下文关键信息
2. 保持原始意图
3. 使用专业术语
4. 不要添加解释性内容

直接输出优化后的查询。"""
            )
        ]
        context_messages.extend(previous_messages)
        context_messages.append(HumanMessage(content=f"问题：{current_question}"))

        # 生成增强查询
        enhancement_prompt = ChatPromptTemplate.from_messages(context_messages)
        llm = get_llm(temperature=0.1)

        response = llm.invoke(enhancement_prompt.format())
        enhanced_query = response.content.strip()

        # 限制长度
        if len(enhanced_query) > 50:
            enhanced_query = enhanced_query[:50].rsplit(' ', 1)[0] + "..."

        logger.info(f"增强查询结果: {enhanced_query}")

    return {
        "enhanced_query": enhanced_query,
        "retrieved_documents": [],
        "topic_relevance": "",
        "should_generate": False,
        "optimization_attempts": 0,
    }
