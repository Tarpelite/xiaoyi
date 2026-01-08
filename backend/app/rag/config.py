"""
RAG 配置模块
"""

from pydantic import BaseModel
from typing import Optional
import os

# 计算项目根目录（backend 的父目录）
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
_DEFAULT_PDF_DIR = os.path.join(_PROJECT_ROOT, "energy_reports_test")


class RAGConfig(BaseModel):
    """RAG 系统配置"""

    # Qdrant 配置
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    collection_name: str = "energy_reports"

    # Embedding 配置
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024

    # 文档处理配置
    pdf_directory: str = _DEFAULT_PDF_DIR
    chunk_size: int = 512
    chunk_overlap: int = 50

    # 检索配置
    default_top_k: int = 5

    class Config:
        env_prefix = "RAG_"


def get_rag_config() -> RAGConfig:
    """获取 RAG 配置（支持环境变量覆盖）"""
    return RAGConfig(
        qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
        qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
        pdf_directory=os.getenv("RAG_PDF_DIRECTORY", _DEFAULT_PDF_DIR),
    )
