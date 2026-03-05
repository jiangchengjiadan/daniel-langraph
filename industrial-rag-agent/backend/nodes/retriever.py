"""内容检索器 - 智能文档获取"""
from backend.models.state import ConversationState
from backend.knowledge.base import get_retriever
from backend.logging.config import get_logger

logger = get_logger(__name__)


def fetch_relevant_content(state: ConversationState) -> ConversationState:
    """
    从向量数据库中检索与增强查询相关的文档。
    """
    logger.info("检索相关文档...")

    # 获取全局检索器
    retriever = get_retriever()

    # 执行检索
    retrieved_docs = retriever.invoke(state["enhanced_query"])

    logger.info(f"检索到 {len(retrieved_docs)} 篇文档")
    for i, doc in enumerate(retrieved_docs):
        source = doc.metadata.get("source", "未知")
        category = doc.metadata.get("category", "未分类")
        preview = doc.page_content[:60].replace("\n", " ")
        logger.debug(f"  文档 {i+1}: [{category}] {preview}...")

    state["retrieved_documents"] = retrieved_docs
    return state
