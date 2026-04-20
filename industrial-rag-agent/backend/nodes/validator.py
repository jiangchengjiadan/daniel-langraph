"""话题验证器 - 智能领域分类"""
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

from backend.models.state import ConversationState
from backend.logging.config import get_logger
from backend.models.providers import get_llm

logger = get_logger(__name__)


def validate_topic_relevance(state: ConversationState) -> ConversationState:
    """
    验证用户查询是否属于电机售后知识领域。
    """
    logger.info("验证话题相关性...")
    enhanced_query = state.get("enhanced_query", "")
    logger.debug(f"增强后的查询: {enhanced_query}")

    classification_prompt = SystemMessage(
        content="""你是工业设备售后客服系统的话题分类专家。

相关话题（RELEVANT）包括：
- 电机、变频器等工业设备的产品规格和参数
- 电机安装、调试、维护、保养方法
- 电机无法启动、过热、振动等故障排查
- 变频器故障代码解读
- 轴承更换等配件更换指南
- 产品保修政策、售后服务流程
- 技术参数查询、设备选型建议

无关话题（IRRELEVANT）包括：
- 与工业设备无关的一般性问题
- 其他品牌产品的咨询
- 个人问题或无关闲聊
- 天气、新闻等通用知识查询

请直接回答：RELEVANT 或 IRRELEVANT，不要有其他内容。"""
    )

    user_question = HumanMessage(content=enhanced_query)

    # 直接调用 LLM 获取文本响应
    llm = get_llm(temperature=0)

    prompt = ChatPromptTemplate.from_messages([classification_prompt, user_question])
    response = prompt.format() + ""
    llm_response = llm.invoke(response)
    raw_response = llm_response.content.strip()

    logger.debug(f"LLM原始响应: {raw_response}")

    # 解析响应
    match = re.search(r'\b(RELEVANT|IRRELEVANT)\b', raw_response, re.IGNORECASE)
    if match:
        classification = match.group(1).upper()
    else:
        # 如果没匹配到，尝试关键词判断
        if any(keyword in raw_response.upper() for keyword in ['相关', '电机', '故障', '售后']):
            classification = "RELEVANT"
            logger.debug("关键词判断为相关话题")
        else:
            classification = "IRRELEVANT"
            logger.warning(f"无法解析分类结果，使用默认值: {raw_response}")

    # 提取置信度
    confidence_match = re.search(r'\b(HIGH|MEDIUM|LOW)\b', raw_response, re.IGNORECASE)
    confidence = confidence_match.group(1).upper() if confidence_match else "MEDIUM"

    state["topic_relevance"] = classification
    logger.info(f"话题分类: {classification} (置信度: {confidence})")

    return state
