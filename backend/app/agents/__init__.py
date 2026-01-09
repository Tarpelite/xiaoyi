"""
Agents Module
=============

AI Agent 层，负责业务逻辑编排 (所有使用 LLM 的模块)
"""

from .report_agent import ReportAgent
from .intent_agent import IntentAgent
from .suggestion_agent import SuggestionAgent
from .error_explainer import ErrorExplainerAgent
from .sentiment_agent import SentimentAgent

# RAG Agent 可选导入（依赖 Qdrant 和 FlagEmbedding）
try:
    from .rag_agent import RAGAgent
    RAG_AVAILABLE = True
except ImportError as e:
    RAGAgent = None
    RAG_AVAILABLE = False
    print(f"[Warning] RAG Agent 不可用: {e}")

__all__ = [
    "ReportAgent",
    "IntentAgent",
    "SuggestionAgent",
    "ErrorExplainerAgent",
    "SentimentAgent",
    "RAGAgent",
    "RAG_AVAILABLE",
]
