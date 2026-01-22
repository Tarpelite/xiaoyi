"""
新闻获取模块
=============

纯功能模块：获取新闻数据，不涉及 LLM 调用
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Tuple
import pandas as pd

from app.core.config import settings
from app.data import DataFetcher, TavilyNewsClient, format_datetime, extract_domain
from app.schemas.session_schema import NewsItem


async def fetch_akshare_news(stock_code: str, limit: int = 20) -> List[NewsItem]:
    """
    获取 AkShare 股票新闻

    纯数据获取，不涉及 LLM

    Args:
        stock_code: 股票代码
        limit: 获取数量限制

    Returns:
        新闻列表
    """
    if not stock_code:
        return []

    try:
        news_df = await asyncio.to_thread(DataFetcher.fetch_news, stock_code, limit)
        if news_df is None or news_df.empty:
            return []

        return [
            NewsItem(
                title=row.get("新闻标题", ""),
                content=row.get("新闻内容", "")[:300] if row.get("新闻内容") else "",
                url=str(row.get("新闻链接", "")),
                published_date=format_datetime(str(row.get("发布时间", ""))),
                source_type="domain_info",
                source_name=str(row.get("文章来源", ""))
            )
            for _, row in news_df.iterrows()
        ]
    except Exception as e:
        print(f"[News] AkShare 获取失败: {e}")
        return []


async def fetch_tavily_news(
    stock_name: str,
    days: int = 30,
    max_results: int = 5
) -> List[NewsItem]:
    """
    获取 Tavily 新闻搜索结果

    纯数据获取，不涉及 LLM

    Args:
        stock_name: 股票名称
        days: 搜索时间范围（天数）
        max_results: 最大结果数

    Returns:
        新闻列表
    """
    if not stock_name:
        return []

    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        client = TavilyNewsClient(settings.tavily_api_key)
        result = await asyncio.to_thread(
            client.search_stock_news,
            stock_name=stock_name,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results
        )

        return [
            NewsItem(
                title=item.get("title", ""),
                content=item.get("content", "")[:300],
                url=item.get("url", ""),
                published_date=format_datetime(item.get("published_date", "")),
                source_type="search",
                source_name=extract_domain(item.get("url", ""))
            )
            for item in result.get("results", [])
        ]
    except Exception as e:
        print(f"[News] Tavily 获取失败: {e}")
        return []


async def fetch_news_all(
    stock_code: str,
    stock_name: str,
    days: int = 30,
    akshare_limit: int = 5,
    tavily_limit: int = 5
) -> Tuple[List[NewsItem], dict]:
    """
    获取全部新闻（AkShare + Tavily 并行）

    纯数据获取，不涉及 LLM

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        days: 搜索时间范围（天数）
        akshare_limit: AkShare 新闻数量
        tavily_limit: Tavily 新闻数量

    Returns:
        (news_items, sentiment_data)
    """
    # 并行获取原始数据
    akshare_task = _fetch_akshare_raw(stock_code, 20)
    tavily_task = _fetch_tavily_raw(stock_name, days, tavily_limit)

    results = await asyncio.gather(akshare_task, tavily_task, return_exceptions=True)

    news_df = results[0] if not isinstance(results[0], Exception) else None
    tavily_results = results[1] if not isinstance(results[1], Exception) else {"results": [], "count": 0}

    news_items = []

    # 转换 AkShare 新闻
    if news_df is not None and not news_df.empty:
        for _, row in news_df.head(akshare_limit).iterrows():
            news_items.append(NewsItem(
                title=row.get("新闻标题", ""),
                content=row.get("新闻内容", "")[:300] if row.get("新闻内容") else "",
                url=str(row.get("新闻链接", "")),
                published_date=format_datetime(str(row.get("发布时间", ""))),
                source_type="domain_info",
                source_name=str(row.get("文章来源", ""))
            ))

    # 转换 Tavily 新闻
    for item in tavily_results.get("results", [])[:tavily_limit]:
        url = item.get("url", "")
        pub_date = item.get("published_date") or ""
        news_items.append(NewsItem(
            title=item.get("title", ""),
            content=item.get("content", "")[:300],
            url=url,
            published_date=format_datetime(pub_date) if pub_date else "-",
            source_type="search",
            source_name=extract_domain(url)
        ))

    akshare_count = min(akshare_limit, len(news_df) if news_df is not None else 0)
    tavily_count = len(tavily_results.get("results", [])[:tavily_limit])
    print(f"[News] 获取新闻: AkShare {akshare_count} 条, Tavily {tavily_count} 条")

    # 构建情感分析数据
    sentiment_data = {
        "news_df": news_df,
        "tavily_results": tavily_results,
        "news_count": len(news_items)
    }

    return news_items, sentiment_data


async def _fetch_akshare_raw(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """
    获取 AkShare 原始数据（内部使用）

    返回 DataFrame 供情感分析使用
    """
    if not stock_code:
        return pd.DataFrame()

    return await asyncio.to_thread(DataFetcher.fetch_news, stock_code, limit)


async def _fetch_tavily_raw(
    stock_name: str,
    days: int = 30,
    max_results: int = 5
) -> dict:
    """
    获取 Tavily 原始数据（内部使用）

    返回原始 dict 供情感分析使用
    """
    if not stock_name:
        return {"results": [], "count": 0}

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    client = TavilyNewsClient(settings.tavily_api_key)
    return await asyncio.to_thread(
        client.search_stock_news,
        stock_name=stock_name,
        start_date=start_date,
        end_date=end_date,
        max_results=max_results
    )


async def search_web(keywords: List[str], days: int = 30, max_results: int = 10) -> List[dict]:
    """
    通用网络搜索（非股票专用）

    返回原始 dict 格式，供聊天流程使用

    Args:
        keywords: 搜索关键词列表
        days: 搜索时间范围（天数）
        max_results: 最大结果数

    Returns:
        搜索结果列表
    """
    if not keywords:
        return []

    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        client = TavilyNewsClient(settings.tavily_api_key)
        query = " ".join(keywords[:3])

        result = await asyncio.to_thread(
            client.search,
            query=query,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results
        )
        print(f"[Search] 网络搜索时间范围: {start_date} ~ {end_date}")
        return result.get("results", [])
    except Exception as e:
        print(f"[Search] 搜索失败: {e}")
        return []


async def fetch_domain_news(stock_code: str, keywords: List[str]) -> List[dict]:
    """
    获取领域新闻 (AkShare)

    返回原始 dict 格式，供聊天流程使用

    Args:
        stock_code: 股票代码
        keywords: 关键词列表

    Returns:
        新闻列表
    """
    if not stock_code and not keywords:
        return []

    try:
        if stock_code:
            news_df = await asyncio.to_thread(DataFetcher.fetch_news, stock_code, 20)
        else:
            return []

        if news_df is None or news_df.empty:
            return []

        items = []
        for _, row in news_df.head(10).iterrows():
            items.append({
                "title": row.get("新闻标题", ""),
                "content": row.get("新闻内容", "")[:200] if row.get("新闻内容") else "",
                "url": row.get("新闻链接", ""),
                "date": str(row.get("发布时间", ""))
            })
        return items
    except Exception as e:
        print(f"[Domain] 获取新闻失败: {e}")
        return []
