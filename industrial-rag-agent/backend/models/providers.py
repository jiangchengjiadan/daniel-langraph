"""模型 provider 工厂。"""
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from backend.config.settings import settings


def _openai_kwargs() -> dict:
    """返回 OpenAI 兼容 API 的公共参数。"""
    kwargs = {}
    if settings.OPENAI_API_KEY:
        kwargs["api_key"] = settings.OPENAI_API_KEY
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = settings.OPENAI_BASE_URL
    return kwargs


def get_llm(temperature: float = 0.3) -> ChatOpenAI:
    """创建聊天模型实例。"""
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=temperature,
        **_openai_kwargs(),
    )


def get_embeddings() -> OpenAIEmbeddings:
    """创建 embedding 模型实例。"""
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        **_openai_kwargs(),
    )
