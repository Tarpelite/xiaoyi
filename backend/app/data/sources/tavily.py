"""
Tavily 数据源
=============

封装 Tavily API 进行网络新闻搜索
"""

import asyncio
from typing import List, Optional

from loguru import logger

from app.data.models import SearchResult, NewsResult, DataSourceType
from app.data.sources.base import BaseDataSource


class TavilyDataSource(BaseDataSource):
    """Tavily 新闻搜索数据源"""
    
    # 中国财经网站域名
    CN_FINANCE_DOMAINS = [
        "sina.com.cn",
        "eastmoney.com",
        "10jqka.com.cn",
        "163.com",
        "qq.com",
        "hexun.com",
        "caixin.com",
        "yicai.com",
        "wallstreetcn.com",
        "cls.cn",
        "stcn.com",
    ]
    
    # 股票名称映射
    STOCK_NAME_MAP = {
        "茅台": "贵州茅台",
        "比亚迪": "比亚迪汽车",
        "宁德时代": "宁德时代电池",
        "中石油": "中国石油",
        "中石化": "中国石化",
        "工商银行": "中国工商银行",
        "建设银行": "中国建设银行",
        "招商银行": "招商银行",
        "平安": "中国平安",
        "腾讯": "腾讯控股",
        "阿里巴巴": "阿里巴巴集团",
    }
    
    def __init__(self, api_key: str):
        """
        初始化 Tavily 数据源
        
        Args:
            api_key: Tavily API Key
        """
        self.api_key = api_key
        self._client = None
    
    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.TAVILY
    
    def _get_client(self):
        """获取 Tavily 客户端"""
        if self._client is None:
            from tavily import TavilyClient
            self._client = TavilyClient(api_key=self.api_key)
        return self._client
    
    def is_available(self) -> bool:
        """检查 API 是否可用"""
        return bool(self.api_key)
    
    def _optimize_query(self, query: str) -> str:
        """优化搜索查询"""
        for short, full in self.STOCK_NAME_MAP.items():
            if short in query:
                query = query.replace(short, full)
                break
        return query
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
        days: int = 30,
        search_depth: str = "basic",
        include_cn_finance: bool = True,
        **kwargs
    ) -> List[SearchResult]:
        """
        搜索新闻
        
        Args:
            query: 搜索关键词
            top_k: 返回结果数量
            days: 搜索过去多少天
            search_depth: 搜索深度 (basic/advanced)
            include_cn_finance: 是否限制为中文财经网站
            
        Returns:
            统一格式的搜索结果
        """
        try:
            optimized_query = self._optimize_query(query)
            
            search_params = {
                "query": optimized_query,
                "search_depth": search_depth,
                "max_results": top_k,
                "topic": "news",
                "days": min(days, 365),
            }
            
            if include_cn_finance:
                search_params["include_domains"] = self.CN_FINANCE_DOMAINS
            
            # 在线程中执行同步调用
            client = self._get_client()
            response = await asyncio.to_thread(client.search, **search_params)
            
            results = []
            for item in response.get("results", []):
                results.append(SearchResult(
                    source=DataSourceType.TAVILY,
                    content=item.get("content", ""),
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    score=item.get("score", 0),
                    date=item.get("published_date", ""),
                    raw_data=item,
                ))
            
            logger.info(f"[Tavily] 搜索完成: query={query[:30]}..., 结果数={len(results)}")
            return results
            
        except Exception as e:
            logger.error(f"[Tavily] 搜索失败: {e}")
            return []
    
    async def search_news(
        self,
        query: str,
        top_k: int = 10,
        days: int = 30,
        **kwargs
    ) -> List[NewsResult]:
        """
        搜索新闻（返回 NewsResult 格式）
        
        Args:
            query: 搜索关键词
            top_k: 返回结果数量
            days: 搜索天数
            
        Returns:
            新闻结果列表
        """
        search_results = await self.search(
            query=query,
            top_k=top_k,
            days=days,
            search_depth="advanced",
            **kwargs
        )
        
        return [
            NewsResult(
                source=DataSourceType.TAVILY,
                title=r.title or "",
                content=r.content,
                url=r.url,
                published_date=r.date,
                score=r.score,
            )
            for r in search_results
        ]


# 单例
_tavily_source: Optional[TavilyDataSource] = None


def get_tavily_source(api_key: str = None) -> TavilyDataSource:
    """获取 Tavily 数据源单例"""
    global _tavily_source
    
    if _tavily_source is None:
        from app.core.config import settings
        key = api_key or settings.tavily_api_key
        if not key:
            raise ValueError("Tavily API Key 未配置")
        _tavily_source = TavilyDataSource(api_key=key)
    
    return _tavily_source
