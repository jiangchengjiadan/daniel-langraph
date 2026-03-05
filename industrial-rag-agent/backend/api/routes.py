"""API路由 - 对话接口（支持流式输出）"""
from typing import Optional, AsyncGenerator
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessageChunk
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama

from backend.workflow.builder import get_workflow
from backend.config.settings import settings
from backend.logging.config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """对话请求模型"""
    message: str
    thread_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    """对话响应模型"""
    response: str
    thread_id: str


def create_streaming_llm() -> BaseChatModel:
    """创建支持流式的 LLM"""
    return ChatOllama(
        model=settings.LLM_MODEL,
        base_url=settings.LLM_BASE_URL,
        temperature=0.3,
        reasoning=False,
    )


async def generate_streaming_response(
    conversation_history: list,
    doc_context: str,
    current_question: str,
) -> AsyncGenerator[str, None]:
    """生成流式响应"""
    llm = create_streaming_llm()

    response_template = """你是专业的工业设备售后客服工程师。

你的任务是根据知识库信息和对话历史，用markdown格式回答用户的问题。

格式要求：
1. 使用markdown格式组织内容
2. 一级标题用"## "开头，二级标题用"### "开头
3. 列表项用"- "或"1. "开头
4. 重点内容用"**...**"加粗
5. 代码或术语用"`...`"标注
6. 在回答末尾用"> 来源：xxx"标注信息来源

对话历史：
{conversation_history}

相关知识：
{document_context}

当前问题：{current_question}

请给出专业、准确的回答："""

    prompt = ChatPromptTemplate.from_template(response_template)

    # 构建消息
    history_text = ""
    for msg in conversation_history:
        if isinstance(msg, HumanMessage):
            history_text += f"用户：{msg.content}\n"
        elif isinstance(msg, AIMessageChunk):
            history_text += f"客服：{msg.content[:200]}...\n"

    # 使用 LLM 的流式方法
    messages = prompt.format_messages(
        conversation_history=history_text,
        document_context=doc_context,
        current_question=current_question
    )

    # 流式输出
    async for chunk in llm.astream(messages):
        if chunk.content:
            yield f"data: {chunk.content}\n\n"

    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    处理用户对话请求（非流式）。
    """
    logger.info(f"收到消息: {request.message[:50]}... (thread_id: {request.thread_id})")

    try:
        workflow = get_workflow()
        input_state = {
            "current_query": HumanMessage(content=request.message)
        }
        config = {
            "configurable": {
                "thread_id": request.thread_id
            }
        }

        result = workflow.invoke(input_state, config=config)

        conversation_history = result.get("conversation_history", [])
        if conversation_history:
            last_message = conversation_history[-1]
            response_text = last_message.content
        else:
            response_text = "抱歉，处理过程中出现了问题。"

        logger.info(f"响应长度: {len(response_text)} 字符")

        return ChatResponse(
            response=response_text,
            thread_id=request.thread_id
        )

    except Exception as e:
        logger.error(f"处理消息时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理消息时出错: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    处理用户对话请求（流式输出）。
    使用 SSE (Server-Sent Events) 协议。
    """
    logger.info(f"收到流式消息: {request.message[:50]}... (thread_id: {request.thread_id})")

    try:
        workflow = get_workflow()
        input_state = {
            "current_query": HumanMessage(content=request.message)
        }
        config = {
            "configurable": {
                "thread_id": request.thread_id
            }
        }

        # 执行工作流获取相关文档
        result = workflow.invoke(input_state, config=config)

        conversation_history = result.get("conversation_history", [])
        relevant_docs = result.get("retrieved_documents", [])
        enhanced_query = result.get("enhanced_query", "")

        # 构建文档上下文
        doc_context = ""
        for i, doc in enumerate(relevant_docs):
            source = doc.metadata.get("source", "未知")
            category = doc.metadata.get("category", "未分类")
            doc_context += f"\n【文档{i+1}】来源：{source}（{category}）\n"
            doc_context += f"{doc.page_content}\n"

        # 生成流式响应
        async def event_generator():
            async for chunk in generate_streaming_response(
                conversation_history=conversation_history,
                doc_context=doc_context,
                current_question=enhanced_query or request.message
            ):
                yield chunk

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    except Exception as e:
        logger.error(f"处理流式消息时出错: {str(e)}")
        error_stream = f"data: 抱歉，处理消息时出错：{str(e)}\n\n"
        error_stream += "data: [DONE]\n\n"
        return StreamingResponse(
            iter([error_stream]),
            media_type="text/event-stream",
        )


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}
