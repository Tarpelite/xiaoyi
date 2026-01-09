"""
研报服务客户端
==============

对接 xiaoyi-rag-service 的 HTTP 客户端
"""

import asyncio
from typing import List, Optional

import httpx
from loguru import logger

from app.data.models import SearchResult, ReportResult, DataSourceType
from app.data.sources.base import BaseDataSource


class ReportServiceClient(BaseDataSource):
    """研报 RAG 服务客户端"""
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
    ):
        """
        初始化客户端
        
        Args:
            base_url: RAG 服务地址
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.REPORT
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client
    
    async def close(self):
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def is_available(self) -> bool:
        """检查服务是否可用（同步版本）"""
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/api/v1/health")
                return resp.status_code == 200
        except Exception:
            return False
    
    async def health_check(self) -> dict:
        """健康检查"""
        try:
            client = await self._get_client()
            resp = await client.get("/api/v1/health")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[ReportService] 健康检查失败: {e}")
            return {"status": "error", "error": str(e)}
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        mode: str = "hybrid",
        use_rerank: bool = True,
        filters: Optional[dict] = None,
        **kwargs
    ) -> List[SearchResult]:
        """
        搜索研报
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            mode: 搜索模式 (hybrid/vector/bm25)
            use_rerank: 是否使用重排序
            filters: 过滤条件
            
        Returns:
            统一格式的搜索结果
        """
        try:
            client = await self._get_client()
            
            request_body = {
                "query": query,
                "top_k": top_k,
                "mode": mode,
                "use_rerank": use_rerank,
            }
            
            if filters:
                request_body["filters"] = filters
            
            resp = await client.post("/api/v1/search", json=request_body)
            resp.raise_for_status()
            
            data = resp.json()
            
            # 转换为统一格式
            results = []
            for item in data.get("results", []):
                results.append(SearchResult(
                    source=DataSourceType.REPORT,
                    content=item.get("content", ""),
                    title=item.get("title") or item.get("file_name", ""),
                    score=item.get("score", 0),
                    file_name=item.get("file_name"),
                    page_number=item.get("page_number"),
                    raw_data=item,
                ))
            
            logger.info(f"[ReportService] 搜索完成: query={query[:30]}..., 结果数={len(results)}")
            return results
            
        except httpx.HTTPStatusError as e:
            logger.error(f"[ReportService] HTTP 错误: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"[ReportService] 搜索失败: {e}")
            return []
    
    async def search_reports(
        self,
        query: str,
        top_k: int = 5,
        use_rerank: bool = True,
        **kwargs
    ) -> List[ReportResult]:
        """
        搜索研报（返回详细的研报结果格式）
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            use_rerank: 是否使用重排序
            
        Returns:
            研报结果列表
        """
        try:
            client = await self._get_client()
            
            resp = await client.post("/api/v1/search", json={
                "query": query,
                "top_k": top_k,
                "mode": "hybrid",
                "use_rerank": use_rerank,
            })
            resp.raise_for_status()
            
            data = resp.json()
            
            results = []
            for item in data.get("results", []):
                results.append(ReportResult(
                    chunk_id=item.get("chunk_id", ""),
                    doc_id=item.get("doc_id", ""),
                    content=item.get("content", ""),
                    score=item.get("score", 0),
                    page_number=item.get("page_number", 0),
                    file_name=item.get("file_name", ""),
                    title=item.get("title"),
                    section_title=item.get("section_title"),
                    rerank_score=item.get("rerank_score"),
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"[ReportService] 搜索研报失败: {e}")
            return []


# 单例
_report_client: Optional[ReportServiceClient] = None


def get_report_client(base_url: str = None) -> ReportServiceClient:
    """获取研报服务客户端单例"""
    global _report_client
    
    if _report_client is None:
        from app.core.config import settings
        url = base_url or getattr(settings, "report_service_url", "http://localhost:8000")
        _report_client = ReportServiceClient(base_url=url)
    
    return _report_client
