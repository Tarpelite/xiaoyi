"""
数据获取模块
=============

股票数据和 RAG 研报获取
"""

import asyncio
from typing import List
import pandas as pd

from app.data import DataFetcher
from app.data.rag_searcher import RAGSearcher
from app.schemas.session_schema import RAGSource


async def fetch_stock_data(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取股票历史数据

    Args:
        stock_code: 股票代码
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)

    Returns:
        处理后的 DataFrame，遇到错误时抛出 DataFetchError
    """
    raw_df = await asyncio.to_thread(
        DataFetcher.fetch_stock_data,
        stock_code, start_date, end_date
    )
    df = await asyncio.to_thread(DataFetcher.prepare, raw_df)
    return df


async def fetch_rag_reports(rag_searcher: RAGSearcher, keywords: List[str]) -> List[RAGSource]:
    """
    检索研报

    Args:
        rag_searcher: RAG 搜索器实例
        keywords: 关键词列表

    Returns:
        研报来源列表
    """
    if not keywords:
        return []

    try:
        query = " ".join(keywords[:3])
        docs = await asyncio.to_thread(
            rag_searcher.search_reports,
            query,
            5
        )

        return [
            RAGSource(
                filename=doc["file_name"],
                page=doc["page_number"],
                content_snippet=doc.get("content", "")[:200],
                score=doc["score"]
            )
            for doc in docs
        ]
    except Exception as e:
        print(f"[RAG] 研报检索失败: {e}")
        return []
