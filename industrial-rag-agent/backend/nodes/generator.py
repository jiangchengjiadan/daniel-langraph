"""响应生成器 - 上下文感知回答"""
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage
from langchain_ollama import ChatOllama

from backend.models.state import ConversationState
from backend.config.settings import settings
from backend.logging.config import get_logger

logger = get_logger(__name__)


def generate_contextual_response(state: ConversationState) -> ConversationState:
    """
    基于检索到的相关文档和对话历史生成最终响应。
    """
    logger.info("生成响应...")

    if "conversation_history" not in state or state["conversation_history"] is None:
        raise ValueError("响应生成需要对话历史")

    # 提取组件
    conversation_context = state["conversation_history"]
    relevant_docs = state["retrieved_documents"]
    enhanced_question = state["enhanced_query"]

    # 构建文档上下文
    doc_context = ""
    for i, doc in enumerate(relevant_docs):
        source = doc.metadata.get("source", "未知")
        category = doc.metadata.get("category", "未分类")
        doc_context += f"\n【文档{i+1}】来源：{source}（{category}）\n"
        doc_context += f"{doc.page_content}\n"

    # 构建对话历史上下文（仅用于参考，不包含系统消息）
    history_text = ""
    for msg in conversation_context:
        if isinstance(msg, HumanMessage):
            history_text += f"用户：{msg.content}\n"
        elif isinstance(msg, AIMessage):
            history_text += f"客服：{msg.content[:200]}...\n"

    # 响应提示模板
    response_template = """你是专业的工业设备售后客服工程师。

你的任务是根据知识库信息和对话历史，用markdown格式回答用户的问题。

格式要求：
1. 使用markdown格式组织内容
2. 一级标题用"## "开头，二级标题用"### "开头，标题单独一行，和其后的正文分开
3. 列表项用"- "或"1. "开头，每个列表项的文字单独一段
4. 重点内容用"**...**"加粗
5. 代码或术语用"`...`"标注
6. 在回答末尾用"> 来源：xxx"标注信息来源，和前文分段，单独一行。

对话历史：
{conversation_history}

相关知识：
{document_context}

当前问题：{current_question}

请给出专业、准确的回答："""

    response_prompt = ChatPromptTemplate.from_template(response_template)
    llm = ChatOllama(
        model=settings.LLM_MODEL,
        base_url=settings.LLM_BASE_URL,
        temperature=0.3,
        reasoning=False,
    )

    # 生成响应
    response_chain = response_prompt | llm
    response = response_chain.invoke({
        "conversation_history": history_text,
        "document_context": doc_context,
        "current_question": enhanced_question
    })

    generated_response = response.content.strip()

    # 添加到对话历史
    state["conversation_history"].append(AIMessage(content=generated_response))

    logger.info(f"响应生成完成，长度: {len(generated_response)} 字符")
    return state
