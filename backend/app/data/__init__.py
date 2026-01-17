"""
Data Services
=============

数据获取与处理模块:
- DataFetcher: AkShare 股票/新闻数据获取
- TavilyNewsClient: Tavily 新闻搜索
- format_datetime: 统一时间格式化（北京时间）
- extract_domain: 从 URL 提取域名
"""

from .fetcher import DataFetcher, format_datetime, extract_domain
from .tavily_client import TavilyNewsClient

__all__ = ["DataFetcher", "TavilyNewsClient", "format_datetime", "extract_domain"]
