"""对话状态模型定义"""
from typing import List, Optional, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.documents import Document
from pydantic import BaseModel, Field


class ConversationState(TypedDict):
    """对话状态 - 工作流中传递的状态数据结构"""
    conversation_history: Optional[List[BaseMessage]]  # 对话历史
    retrieved_documents: Optional[List[Document]]       # 检索到的文档
    topic_relevance: Optional[str]                      # 话题相关性分类
    enhanced_query: Optional[str]                       # 增强后的查询
    should_generate: Optional[bool]                     # 是否应该生成响应
    optimization_attempts: Optional[int]                # 查询优化尝试次数
    current_query: Optional[HumanMessage]              # 当前用户查询


class TopicRelevance(BaseModel):
    """话题相关性分类输出模型"""
    classification: str = Field(
        description="话题分类结果：RELEVANT（相关）或 IRRELEVANT（无关）"
    )
    confidence: str = Field(
        description="置信度：HIGH、MEDIUM 或 LOW"
    )


class DocumentRelevance(BaseModel):
    """文档相关性评估输出模型"""
    relevance: str = Field(
        description="相关性评估：RELEVANT 或 IRRELEVANT"
    )
    reasoning: str = Field(
        description="评估理由的简要说明"
    )
