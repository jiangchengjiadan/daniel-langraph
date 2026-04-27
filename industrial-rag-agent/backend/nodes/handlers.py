"""边情况处理器 - 无关话题和无结果处理"""
from langchain_core.messages import AIMessage

from backend.models.state import ConversationState
from backend.logging.config import get_logger

logger = get_logger(__name__)


def handle_off_topic_queries(state: ConversationState) -> dict:
    """
    处理超出知识领域的用户查询。
    """
    logger.info("处理无关话题查询...")

    off_topic_response = """您好！我是工业设备售后智能客服，专注于为您提供电机、变频器等工业设备的咨询和服务。

我的专业范围包括：
- 电机产品规格、选型建议
- 电机安装、调试指导
- 故障排查与解决方案
- 日常维护保养方法
- 配件更换指南
- 保修政策与售后服务

请问有什么关于工业设备的问题我可以帮您解答？"""

    return {"messages": [AIMessage(content=off_topic_response)]}


def handle_no_relevant_results(state: ConversationState) -> dict:
    """
    处理无法找到相关文档的情况。
    """
    logger.info("处理无结果情况...")

    no_results_response = """非常抱歉，我未能在我掌握的知识库中找到与您问题直接相关的信息。

这可能是因为：
1. 该问题超出了当前知识库的范围
2. 问题可能需要更具体的信息
3. 相关技术资料尚未录入系统

建议您：
- 尝试用不同的关键词描述您的问题
- 拨打客服热线：400-XXX-XXXX 获得人工支持
- 通过在线客服咨询更多技术细节

如果您有其他关于电机或工业设备的问题，我会继续为您服务！"""

    return {"messages": [AIMessage(content=no_results_response)]}
