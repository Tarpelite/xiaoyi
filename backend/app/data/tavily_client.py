"""
Tavily 新闻搜索客户端
====================

使用 Tavily API 搜索历史新闻，支持时间过滤和中文搜索
"""

from typing import List, Dict, Optional
from tavily import TavilyClient

# 中文财经网站域名白名单
# Tavily 默认返回英文结果，需要限制搜索域名以获取中文新闻
CN_FINANCE_DOMAINS = [
    "eastmoney.com",     # 东方财富
    "sina.com.cn",       # 新浪财经
    "163.com",           # 网易财经
    "qq.com",            # 腾讯财经
    "hexun.com",         # 和讯
    "10jqka.com.cn",     # 同花顺
    "stockstar.com",     # 证券之星
    "cnstock.com",       # 中国证券网
    "stcn.com",          # 证券时报
    "cs.com.cn",         # 中证网
]


class TavilyNewsClient:
    """Tavily 新闻搜索客户端"""

    def __init__(self, api_key: str):
        self.client = TavilyClient(api_key=api_key)

    def search(
        self,
        query: str,
        start_date: Optional[str] = None,  # 格式: YYYY-MM-DD
        end_date: Optional[str] = None,    # 格式: YYYY-MM-DD
        days: Optional[int] = None,        # 保留向后兼容，当 start_date/end_date 未指定时使用
        max_results: int = 10,
        search_depth: str = "advanced",  # "basic" 或 "advanced"
        include_domains: Optional[List[str]] = None,
    ) -> Dict:
        # 构建搜索参数
        search_params = {
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "topic": "news",  # 限定为新闻搜索
        }

        # 时间过滤：优先使用 start_date/end_date，其次降级到 days
        if start_date:
            search_params["start_date"] = start_date
        if end_date:
            search_params["end_date"] = end_date

        # 如果没有指定精确日期范围，则使用 days 参数
        if not start_date and not end_date and days:
            search_params["days"] = min(days, 365)

        # 域名过滤
        if include_domains:
            search_params["include_domains"] = include_domains

        try:
            response = self.client.search(**search_params)

            results = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "published_date": item.get("published_date", ""),
                    "score": item.get("score", 0),
                }
                for item in response.get("results", [])
            ]

            return {
                "results": results,
                "query": query,
                "count": len(results),
            }

        except Exception as e:
            print(f"[Tavily] 搜索失败: {e}")
            return {"results": [], "query": query, "count": 0, "error": str(e)}

    def search_stock_news(
        self,
        stock_name: str,
        start_date: Optional[str] = None,  # 格式: YYYY-MM-DD
        end_date: Optional[str] = None,    # 格式: YYYY-MM-DD
        days: int = 30,                    # 保留作为 fallback，当 start_date/end_date 未指定时使用
        max_results: int = 10,
    ) -> Dict:
        # 构建搜索查询
        query = f"{stock_name} 股票"

        # 限制中文财经域名，解决 Tavily 默认返回英文结果的问题
        return self.search(
            query=query,
            start_date=start_date,
            end_date=end_date,
            days=days if not start_date and not end_date else None,
            max_results=max_results,
            search_depth="advanced",
            include_domains=CN_FINANCE_DOMAINS,
        )
