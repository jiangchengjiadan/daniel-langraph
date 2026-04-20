"""集中配置模块"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Settings:
    """应用配置"""

    # 项目根目录
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.parent

    # API 模型配置（兼容 OpenAI SDK 的服务）
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL: str | None = os.getenv("OPENAI_BASE_URL")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Embedding 配置
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # 向量数据库配置
    CHROMA_PERSIST_DIR: Path = Path(os.getenv("CHROMA_PERSIST_DIR", "./backend/knowledge/chroma_db"))

    # 检索配置
    RETRIEVAL_K: int = 3  # 每次检索返回的文档数量
    MAX_OPTIMIZATION_ATTEMPTS: int = 2  # 最大查询优化次数

    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    LOG_FILE: Path = Path(os.getenv("LOG_FILE", "./logs/app.log"))


settings = Settings()
