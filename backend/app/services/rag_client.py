"""
RAG Service Client

HTTP client for calling the external RAG (Research Reports) service.
"""

import httpx
from typing import Optional, List
from pydantic import BaseModel

from app.core.config import settings


class SearchFilters(BaseModel):
    """搜索过滤条件"""
    doc_ids: Optional[List[str]] = None
    industries: Optional[List[str]] = None
    stock_codes: Optional[List[str]] = None
    report_types: Optional[List[str]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class SearchResultItem(BaseModel):
    """单条搜索结果"""
    chunk_id: str
    doc_id: str
    content: str
    score: float
    page_number: int
    file_name: str
    title: Optional[str] = None
    section_title: Optional[str] = None
    bm25_score: Optional[float] = None
    vector_score: Optional[float] = None
    rerank_score: Optional[float] = None


class SearchResponse(BaseModel):
    """搜索响应"""
    query: str
    total: int
    results: List[SearchResultItem]
    mode: str
    took_ms: float
    used_rerank: bool


class RAGClient:
    """
    HTTP client for RAG microservice.
    """

    def __init__(self, base_url: str = ""):
        # 使用传入的 URL 或从环境变量读取
        url = base_url or settings.RAG_SERVICE_URL
        self.base_url = url.rstrip("/") if url else ""
        self.timeout = 60.0  # seconds (RAG can be slow)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        mode: str = "hybrid",
        use_rerank: bool = True,
        filters: Optional[SearchFilters] = None
    ) -> SearchResponse:
        """
        Search research reports.

        Args:
            query: Search query
            top_k: Number of results to return
            mode: Search mode (hybrid, vector, bm25)
            use_rerank: Whether to use reranker
            filters: Optional filters

        Returns:
            SearchResponse with results
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                request_data = {
                    "query": query,
                    "top_k": top_k,
                    "mode": mode,
                    "use_rerank": use_rerank
                }
                if filters:
                    request_data["filters"] = filters.model_dump(exclude_none=True)

                response = await client.post(
                    f"{self.base_url}/api/v1/search",
                    json=request_data
                )
                response.raise_for_status()
                data = response.json()

                return SearchResponse(
                    query=data["query"],
                    total=data["total"],
                    results=[SearchResultItem(**r) for r in data["results"]],
                    mode=data["mode"],
                    took_ms=data["took_ms"],
                    used_rerank=data["used_rerank"]
                )

            except httpx.HTTPError as e:
                print(f"[RAGClient] HTTP error: {e}")
                return SearchResponse(
                    query=query,
                    total=0,
                    results=[],
                    mode=mode,
                    took_ms=0,
                    used_rerank=False
                )
            except Exception as e:
                print(f"[RAGClient] Error: {e}")
                return SearchResponse(
                    query=query,
                    total=0,
                    results=[],
                    mode=mode,
                    took_ms=0,
                    used_rerank=False
                )

    def search_sync(
        self,
        query: str,
        top_k: int = 5,
        mode: str = "hybrid",
        use_rerank: bool = True,
        filters: Optional[SearchFilters] = None
    ) -> SearchResponse:
        """
        Synchronous version of search.
        """
        with httpx.Client(timeout=self.timeout) as client:
            try:
                request_data = {
                    "query": query,
                    "top_k": top_k,
                    "mode": mode,
                    "use_rerank": use_rerank
                }
                if filters:
                    request_data["filters"] = filters.model_dump(exclude_none=True)

                response = client.post(
                    f"{self.base_url}/api/v1/search",
                    json=request_data
                )
                response.raise_for_status()
                data = response.json()

                return SearchResponse(
                    query=data["query"],
                    total=data["total"],
                    results=[SearchResultItem(**r) for r in data["results"]],
                    mode=data["mode"],
                    took_ms=data["took_ms"],
                    used_rerank=data["used_rerank"]
                )

            except httpx.HTTPError as e:
                print(f"[RAGClient] HTTP error: {e}")
                return SearchResponse(
                    query=query,
                    total=0,
                    results=[],
                    mode=mode,
                    took_ms=0,
                    used_rerank=False
                )
            except Exception as e:
                print(f"[RAGClient] Error: {e}")
                return SearchResponse(
                    query=query,
                    total=0,
                    results=[],
                    mode=mode,
                    took_ms=0,
                    used_rerank=False
                )

    async def health(self) -> dict:
        """Check service health"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.base_url}/api/v1/health")
                response.raise_for_status()
                return response.json()
            except Exception as e:
                return {
                    "status": "unavailable",
                    "error": str(e)
                }

    async def get_stats(self) -> dict:
        """Get service statistics"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.base_url}/api/v1/stats")
                response.raise_for_status()
                return response.json()
            except Exception as e:
                return {
                    "error": str(e)
                }


# Singleton instance
_client_instance: Optional[RAGClient] = None
# 缓存 RAG 服务可用性状态
_rag_available: Optional[bool] = None


def get_rag_client() -> RAGClient:
    """Get singleton client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = RAGClient()
    return _client_instance


async def check_rag_availability() -> bool:
    """
    检查并缓存 RAG 服务可用性

    在应用启动时调用，结果会被缓存
    """
    global _rag_available
    client = get_rag_client()
    health = await client.health()
    _rag_available = health.get("status") == "healthy"
    return _rag_available


def is_rag_available() -> bool:
    """
    获取 RAG 服务可用性状态（同步方法）

    Returns:
        bool: RAG 服务是否可用，如果未检查过则返回 False
    """
    global _rag_available
    return _rag_available if _rag_available is not None else False
