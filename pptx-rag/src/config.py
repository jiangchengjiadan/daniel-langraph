# src/config.py
"""Configuration management for PPTx RAG"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


class Config:
    """Configuration class that loads from .env file"""

    _instance: Optional["Config"] = None
    _loaded: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not Config._loaded:
            self._load_env()
            Config._loaded = True

    def _load_env(self):
        """Load environment variables from .env file"""
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv()

    # API Configuration (OpenAI Compatible)
    @property
    def api_base_url(self) -> str:
        return os.getenv("API_BASE_URL", "https://api.openai.com/v1")

    @property
    def api_key(self) -> str:
        return os.getenv("API_KEY", "")

    @property
    def llm_model(self) -> str:
        return os.getenv("LLM_MODEL", "gpt-4")

    # Embedding Model
    @property
    def embedding_model(self) -> str:
        return os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

    # Data Directory
    @property
    def data_dir(self) -> Path:
        return Path(os.getenv("DATA_DIR", "./data"))

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def images_dir(self) -> Path:
        return self.data_dir / "images"

    @property
    def chunks_dir(self) -> Path:
        return self.data_dir / "chunks"

    @property
    def indexes_dir(self) -> Path:
        return self.data_dir / "indexes"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def workspace_dir(self) -> Path:
        default_path = self.data_dir / "workspace"
        override = os.getenv("WORKSPACE_DIR")
        return Path(override) if override else default_path

    # Image Server
    @property
    def image_server_port(self) -> int:
        return int(os.getenv("IMAGE_SERVER_PORT", "8080"))

    @property
    def image_server_url(self) -> str:
        return os.getenv("IMAGE_SERVER_URL", f"http://localhost:{self.image_server_port}")

    # Retrieval Settings
    @property
    def retrieval_k(self) -> int:
        """Number of results to retrieve"""
        return int(os.getenv("RETRIEVAL_K", "5"))

    @property
    def retrieval_k_multiplier(self) -> int:
        """Multiplier for internal retrieval (to allow filtering)"""
        return int(os.getenv("RETRIEVAL_K_MULTIPLIER", "2"))

    # LLM Settings
    @property
    def llm_temperature(self) -> float:
        """LLM temperature for response generation"""
        return float(os.getenv("LLM_TEMPERATURE", "0.1"))

    @property
    def llm_num_ctx(self) -> int:
        """LLM context window size"""
        return int(os.getenv("LLM_NUM_CTX", "4096"))

    @property
    def llm_num_predict(self) -> int:
        """LLM max predict tokens"""
        return int(os.getenv("LLM_NUM_PREDICT", "2048"))

    # Retrieval Weights
    @property
    def bm25_weight(self) -> float:
        return float(os.getenv("BM25_WEIGHT", "0.4"))

    @property
    def vector_weight(self) -> float:
        return float(os.getenv("VECTOR_WEIGHT", "0.6"))

    def ensure_directories(self):
        """Create all data directories if they don't exist"""
        for dir_path in [
            self.data_dir,
            self.upload_dir,
            self.images_dir,
            self.chunks_dir,
            self.indexes_dir,
            self.logs_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)


# Global config instance
config = Config()
