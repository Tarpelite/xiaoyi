"""
Data Services
=============

数据获取与处理模块

提供统一的数据获取接口，支持：
- 研报 RAG (xiaoyi-rag-service)
- Tavily 新闻搜索
- AKShare 股票数据/新闻
"""

# 保留原有的 DataFetcher（向后兼容）
from .fetcher import DataFetcher

# 新的统一数据层
from .layer import UnifiedDataLayer, get_data_layer
from .models import (
    DataSourceType,
    SearchResult,
    NewsResult,
    ReportResult,
    DataQueryRequest,
    DataQueryResponse,
)
from .sources import (
    BaseDataSource,
    AKShareDataSource,
    TavilyDataSource,
    ReportServiceClient,
    get_akshare_source,
    get_tavily_source,
    get_report_client,
)

__all__ = [
    # 原有
    "DataFetcher",
    
    # 统一数据层
    "UnifiedDataLayer",
    "get_data_layer",
    
    # 模型
    "DataSourceType",
    "SearchResult",
    "NewsResult",
    "ReportResult",
    "DataQueryRequest",
    "DataQueryResponse",
    
    # 数据源
    "BaseDataSource",
    "AKShareDataSource",
    "TavilyDataSource",
    "ReportServiceClient",
    "get_akshare_source",
    "get_tavily_source",
    "get_report_client",
]
