"""
RAG 研报搜索模块
================

基于外部 RAG 服务的研报检索 (通过 RAG_SERVICE_URL 环境变量配置)
"""

from typing import Dict, Any, List
from app.services.rag_client import get_rag_client, RAGClient


class RAGSearcher:
    """研报知识库搜索器"""

    def __init__(self):
        self.rag_client: RAGClient = get_rag_client()

    def search_reports(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索相关研报内容

        Args:
            query: 用户查询
            top_k: 返回结果数量

        Returns:
            检索结果列表，包含内容、来源、页码等
        """
        response = self.rag_client.search_sync(
            query=query,
            top_k=top_k,
            mode="hybrid",
            use_rerank=True
        )

        return [
            {
                "content": r.content,
                "file_name": r.file_name,
                "page_number": r.page_number,
                "score": r.score,
                "doc_id": r.doc_id,
                "title": r.title,
                "section_title": r.section_title
            }
            for r in response.results
        ]
