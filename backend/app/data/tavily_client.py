"""
Tavily 新闻搜索客户端
====================

使用 Tavily API 搜索历史新闻，支持时间过滤和中文搜索
"""

from typing import List, Dict, Optional
from tavily import TavilyClient


class TavilyNewsClient:
    """Tavily 新闻搜索客户端"""

    # 股票名称映射（用于优化搜索）
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
        "京东": "京东集团",
        "小米": "小米集团",
        "美团": "美团点评",
        "百度": "百度公司",
        "网易": "网易公司",
    }

    def __init__(self, api_key: str):
        self.client = TavilyClient(api_key=api_key)

    def search(
        self,
        query: str,
        days: int = 30,
        max_results: int = 10,
        search_depth: str = "basic",  # "basic" 或 "advanced"
        include_domains: Optional[List[str]] = None,
    ) -> Dict:
        """
        搜索新闻

        Args:
            query: 搜索关键词
            days: 搜索过去多少天的新闻（Tavily 支持最多 365 天）
            max_results: 返回结果数量
            search_depth: 搜索深度
            include_domains: 限制搜索域名（可选）

        Returns:
            {
                "results": [...],
                "query": str,
                "count": int
            }
        """
        # 优化查询
        optimized_query = self._optimize_query(query)

        # 构建搜索参数
        search_params = {
            "query": optimized_query,
            "search_depth": search_depth,
            "max_results": max_results,
            "topic": "news",  # 限定为新闻搜索
        }

        # 时间过滤（Tavily 使用 days 参数）
        if days:
            search_params["days"] = min(days, 365)

        # 域名过滤
        if include_domains:
            search_params["include_domains"] = include_domains

        try:
            response = self.client.search(**search_params)

            results = []
            for item in response.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "published_date": item.get("published_date", ""),
                    "score": item.get("score", 0),
                })

            return {
                "results": results,
                "query": optimized_query,
                "count": len(results),
            }

        except Exception as e:
            print(f"[Tavily] 搜索失败: {e}")
            return {"results": [], "query": optimized_query, "count": 0, "error": str(e)}

    def search_stock_news(
        self,
        stock_name: str,
        days: int = 30,
        max_results: int = 10,
    ) -> Dict:
        """
        搜索股票相关新闻

        Args:
            stock_name: 股票名称，如 "茅台"、"比亚迪"
            days: 搜索天数
            max_results: 结果数量
        """
        # 构建搜索查询
        query = f"{stock_name} 股票 新闻"

        # 中国财经网站域名
        cn_finance_domains = [
            "sina.com.cn",
            "eastmoney.com",
            "10jqka.com.cn",
            "163.com",
            "qq.com",
            "hexun.com",
            "caixin.com",
            "yicai.com",
            "wallstreetcn.com",
        ]

        return self.search(
            query=query,
            days=days,
            max_results=max_results,
            search_depth="advanced",  # 股票新闻使用深度搜索
            include_domains=cn_finance_domains,
        )

    def _optimize_query(self, query: str) -> str:
        """优化搜索查询"""
        # 替换股票简称为全称
        for short, full in self.STOCK_NAME_MAP.items():
            if short in query:
                query = query.replace(short, full)
                break
        return query

    def format_results_for_llm(self, results: Dict) -> str:
        """
        将搜索结果格式化为 LLM 可读的文本
        """
        if not results.get("results"):
            return "未找到相关新闻。"

        formatted = f"搜索「{results['query']}」找到 {results['count']} 条新闻：\n\n"

        for i, item in enumerate(results["results"], 1):
            formatted += f"{i}. **{item['title']}**\n"
            if item.get("published_date"):
                formatted += f"   发布时间: {item['published_date']}\n"
            if item.get("content"):
                # 截取摘要
                content = item["content"][:200] + "..." if len(item["content"]) > 200 else item["content"]
                formatted += f"   摘要: {content}\n"
            formatted += f"   来源: {item['url']}\n\n"

        return formatted
