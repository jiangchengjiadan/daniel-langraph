"""LLM服务模块"""

from langchain_openai import ChatOpenAI
from ..config import get_settings
import os

# 全局LLM实例
_llm_instance = None


def get_llm() -> ChatOpenAI:
    """
    获取LLM实例(单例模式)

    Returns:
        ChatOpenAI实例
    """
    global _llm_instance

    if _llm_instance is None:
        settings = get_settings()

        # 从环境变量读取配置（优先使用LLM_*环境变量）
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or settings.openai_api_key
        base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or settings.openai_base_url
        model = os.getenv("LLM_MODEL_ID") or os.getenv("OPENAI_MODEL") or settings.openai_model

        if not api_key:
            raise ValueError("LLM API Key未配置，请在.env中设置 LLM_API_KEY 或 OPENAI_API_KEY")

        _llm_instance = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=0.7
        )

        print(f"✅ LLM服务初始化成功")
        print(f"   模型: {model}")
        print(f"   Base URL: {base_url}")

    return _llm_instance


def reset_llm():
    """重置LLM实例(用于测试或重新配置)"""
    global _llm_instance
    _llm_instance = None

