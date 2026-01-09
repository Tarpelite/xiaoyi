"""
统一数据层
==========

提供统一的数据获取接口，支持并行从多个数据源获取数据
"""

import asyncio
import time
from typing import List, Optional, Dict, Any

from loguru import logger

from app.data.models import (
    DataSourceType,
    DataQueryRequest,
    DataQueryResponse,
    SearchResult,
    ReportResult,
    NewsResult,
)
from app.data.sources import (
    get_akshare_source,
    get_tavily_source,
    get_report_client,
)


class UnifiedDataLayer:
    """
    统一数据层
    
    支持并行从多个数据源获取数据：
    - 研报 RAG (xiaoyi-rag-service)
    - Tavily 新闻搜索
    - AKShare 股票新闻
    """
    
    def __init__(
        self,
        report_service_url: str = None,
        tavily_api_key: str = None,
    ):
        """
        初始化数据层
        
        Args:
            report_service_url: 研报服务地址
            tavily_api_key: Tavily API Key
        """
        self._report_url = report_service_url
        self._tavily_key = tavily_api_key
        
        # 延迟初始化数据源
        self._report_client = None
        self._tavily_source = None
        self._akshare_source = None
    
    @property
    def report_client(self):
        """获取研报服务客户端"""
        if self._report_client is None:
            self._report_client = get_report_client(self._report_url)
        return self._report_client
    
    @property
    def tavily_source(self):
        """获取 Tavily 数据源"""
        if self._tavily_source is None:
            self._tavily_source = get_tavily_source(self._tavily_key)
        return self._tavily_source
    
    @property
    def akshare_source(self):
        """获取 AKShare 数据源"""
        if self._akshare_source is None:
            self._akshare_source = get_akshare_source()
        return self._akshare_source
    
    async def query(
        self,
        request: DataQueryRequest,
    ) -> DataQueryResponse:
        """
        统一查询接口
        
        Args:
            request: 查询请求
            
        Returns:
            查询响应
        """
        start_time = time.time()
        errors = []
        all_results: List[SearchResult] = []
        report_results: List[ReportResult] = []
        news_results: List[NewsResult] = []
        
        # 构建并行任务
        tasks = []
        source_names = []
        
        for source in request.sources:
            if source == DataSourceType.REPORT:
                tasks.append(self._query_reports(request))
                source_names.append("report")
            elif source == DataSourceType.TAVILY:
                tasks.append(self._query_tavily(request))
                source_names.append("tavily")
            elif source == DataSourceType.AKSHARE:
                tasks.append(self._query_akshare(request))
                source_names.append("akshare")
        
        # 并行执行
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                source_name = source_names[i]
                
                if isinstance(result, Exception):
                    logger.error(f"[DataLayer] {source_name} 查询失败: {result}")
                    errors.append(f"{source_name}: {str(result)}")
                elif isinstance(result, dict):
                    # 分类结果
                    if "reports" in result:
                        report_results.extend(result["reports"])
                        all_results.extend(result.get("search_results", []))
                    if "news" in result:
                        news_results.extend(result["news"])
                        all_results.extend(result.get("search_results", []))
        
        took_ms = (time.time() - start_time) * 1000
        
        return DataQueryResponse(
            query=request.query,
            results=all_results,
            report_results=report_results,
            news_results=news_results,
            total_count=len(all_results),
            took_ms=took_ms,
            errors=errors,
        )
    
    async def _query_reports(self, request: DataQueryRequest) -> Dict[str, Any]:
        """查询研报"""
        try:
            reports = await self.report_client.search_reports(
                query=request.query,
                top_k=request.top_k,
                use_rerank=request.use_rerank,
            )
            
            # 同时返回 SearchResult 格式
            search_results = [
                SearchResult(
                    source=DataSourceType.REPORT,
                    content=r.content,
                    title=r.title or r.file_name,
                    score=r.score,
                    file_name=r.file_name,
                    page_number=r.page_number,
                )
                for r in reports
            ]
            
            return {
                "reports": reports,
                "search_results": search_results,
            }
        except Exception as e:
            logger.error(f"[DataLayer] 研报查询失败: {e}")
            raise
    
    async def _query_tavily(self, request: DataQueryRequest) -> Dict[str, Any]:
        """查询 Tavily"""
        try:
            news = await self.tavily_source.search_news(
                query=request.query,
                top_k=request.top_k,
                days=request.days,
            )
            
            # 同时返回 SearchResult 格式
            search_results = [
                SearchResult(
                    source=DataSourceType.TAVILY,
                    content=n.content,
                    title=n.title,
                    url=n.url,
                    score=n.score,
                    date=n.published_date,
                )
                for n in news
            ]
            
            return {
                "news": news,
                "search_results": search_results,
            }
        except Exception as e:
            logger.error(f"[DataLayer] Tavily 查询失败: {e}")
            raise
    
    async def _query_akshare(self, request: DataQueryRequest) -> Dict[str, Any]:
        """查询 AKShare"""
        try:
            if not request.stock_code:
                return {"news": [], "search_results": []}
            
            news = await self.akshare_source.fetch_news(
                stock_code=request.stock_code,
                limit=request.top_k,
            )
            
            # 同时返回 SearchResult 格式
            search_results = [
                SearchResult(
                    source=DataSourceType.AKSHARE,
                    content=n.content,
                    title=n.title,
                    score=n.score,
                    date=n.published_date,
                )
                for n in news
            ]
            
            return {
                "news": news,
                "search_results": search_results,
            }
        except Exception as e:
            logger.error(f"[DataLayer] AKShare 查询失败: {e}")
            raise
    
    # ========== 便捷方法 ==========
    
    async def search_reports(
        self,
        query: str,
        top_k: int = 5,
        use_rerank: bool = True,
    ) -> List[ReportResult]:
        """
        仅搜索研报
        
        Args:
            query: 搜索查询
            top_k: 返回数量
            use_rerank: 是否使用重排序
            
        Returns:
            研报结果列表
        """
        return await self.report_client.search_reports(
            query=query,
            top_k=top_k,
            use_rerank=use_rerank,
        )
    
    async def search_news(
        self,
        query: str,
        top_k: int = 10,
        stock_code: Optional[str] = None,
        stock_name: Optional[str] = None,
        days: int = 30,
    ) -> List[NewsResult]:
        """
        搜索新闻（Tavily + AKShare）
        
        Args:
            query: 搜索查询
            top_k: 返回数量
            stock_code: 股票代码（可选，用于 AKShare）
            stock_name: 股票名称（可选，优化 Tavily 查询）
            days: 搜索天数
            
        Returns:
            新闻结果列表
        """
        tasks = []
        
        # Tavily 搜索
        search_query = f"{stock_name or query} 股票 新闻" if stock_name else query
        tasks.append(self.tavily_source.search_news(
            query=search_query,
            top_k=top_k,
            days=days,
        ))
        
        # AKShare 搜索（如果有股票代码）
        if stock_code:
            tasks.append(self.akshare_source.fetch_news(
                stock_code=stock_code,
                limit=top_k,
            ))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_news = []
        for result in results:
            if isinstance(result, list):
                all_news.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"[DataLayer] 新闻查询部分失败: {result}")
        
        # 按分数排序
        all_news.sort(key=lambda x: x.score, reverse=True)
        
        return all_news[:top_k * 2]  # 返回两倍数量（因为合并了两个数据源）
    
    async def search_all(
        self,
        query: str,
        top_k: int = 5,
        stock_code: Optional[str] = None,
        stock_name: Optional[str] = None,
        include_reports: bool = True,
        include_news: bool = True,
    ) -> DataQueryResponse:
        """
        搜索所有数据源
        
        Args:
            query: 搜索查询
            top_k: 每个数据源返回的数量
            stock_code: 股票代码
            stock_name: 股票名称
            include_reports: 是否包含研报
            include_news: 是否包含新闻
            
        Returns:
            统一响应
        """
        sources = []
        if include_reports:
            sources.append(DataSourceType.REPORT)
        if include_news:
            sources.append(DataSourceType.TAVILY)
            if stock_code:
                sources.append(DataSourceType.AKSHARE)
        
        request = DataQueryRequest(
            query=query,
            sources=sources,
            top_k=top_k,
            stock_code=stock_code,
            stock_name=stock_name,
        )
        
        return await self.query(request)


# 单例
_data_layer: Optional[UnifiedDataLayer] = None


def get_data_layer(
    report_service_url: str = None,
    tavily_api_key: str = None,
) -> UnifiedDataLayer:
    """获取统一数据层单例"""
    global _data_layer
    
    if _data_layer is None:
        _data_layer = UnifiedDataLayer(
            report_service_url=report_service_url,
            tavily_api_key=tavily_api_key,
        )
    
    return _data_layer
