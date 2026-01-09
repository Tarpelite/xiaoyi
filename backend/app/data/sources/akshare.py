"""
AKShare 数据源
==============

封装 AKShare API 获取股票数据和新闻
"""

import asyncio
from typing import List, Optional, Dict, Any

import pandas as pd
from loguru import logger

from app.data.models import SearchResult, NewsResult, DataSourceType
from app.data.sources.base import BaseDataSource


class AKShareDataSource(BaseDataSource):
    """AKShare 股票数据源"""
    
    def __init__(self):
        self._ak = None
    
    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.AKSHARE
    
    def _get_akshare(self):
        """延迟加载 AKShare"""
        if self._ak is None:
            import akshare as ak
            self._ak = ak
        return self._ak
    
    def is_available(self) -> bool:
        """检查 AKShare 是否可用"""
        try:
            self._get_akshare()
            return True
        except ImportError:
            return False
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
        stock_code: Optional[str] = None,
        **kwargs
    ) -> List[SearchResult]:
        """
        搜索新闻（通过股票代码）
        
        Args:
            query: 搜索查询（用于日志）
            top_k: 返回结果数量
            stock_code: 股票代码（必需）
            
        Returns:
            统一格式的搜索结果
        """
        if not stock_code:
            logger.warning("[AKShare] 未提供股票代码，无法搜索新闻")
            return []
        
        news_results = await self.fetch_news(stock_code, limit=top_k)
        
        return [
            SearchResult(
                source=DataSourceType.AKSHARE,
                content=n.content,
                title=n.title,
                score=0.5,  # AKShare 新闻没有相关度分数
                date=n.published_date,
                raw_data={"source": "akshare"},
            )
            for n in news_results
        ]
    
    async def fetch_news(
        self,
        stock_code: str,
        limit: int = 50,
    ) -> List[NewsResult]:
        """
        获取股票新闻
        
        Args:
            stock_code: 股票代码，如 "600519"
            limit: 返回条数
            
        Returns:
            新闻结果列表
        """
        try:
            ak = self._get_akshare()
            
            # 在线程中执行
            df = await asyncio.to_thread(ak.stock_news_em, symbol=stock_code)
            
            if df is None or df.empty:
                return []
            
            results = []
            for _, row in df.head(limit).iterrows():
                results.append(NewsResult(
                    source=DataSourceType.AKSHARE,
                    title=row.get("新闻标题", row.get("标题", "")),
                    content=str(row.get("新闻内容", row.get("内容", "")))[:500],
                    published_date=str(row.get("发布时间", "")),
                    score=0.5,
                ))
            
            logger.info(f"[AKShare] 获取新闻完成: stock_code={stock_code}, 结果数={len(results)}")
            return results
            
        except Exception as e:
            logger.error(f"[AKShare] 获取新闻失败: {e}")
            return []
    
    async def fetch_stock_data(
        self,
        config: Dict[str, Any],
    ) -> pd.DataFrame:
        """
        获取股票历史数据
        
        Args:
            config: 数据配置，包含 api_function 和 params
            
        Returns:
            原始数据 DataFrame
        """
        ak = self._get_akshare()
        
        api_map = {
            "stock_zh_a_hist": ak.stock_zh_a_hist,
            "stock_zh_index_daily_em": ak.stock_zh_index_daily_em,
            "fund_etf_hist_em": ak.fund_etf_hist_em,
            "stock_news_em": ak.stock_news_em,
        }
        
        func_name = config["api_function"]
        params = config["params"]
        
        if func_name not in api_map:
            raise ValueError(f"不支持的 API: {func_name}")
        
        df = await asyncio.to_thread(api_map[func_name], **params)
        logger.info(f"[AKShare] 获取数据: {len(df)} 条")
        return df
    
    @staticmethod
    def prepare_timeseries(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        """
        将原始数据转换为标准时序格式 (ds, y)
        
        Args:
            df: 原始数据 DataFrame
            config: 数据配置，包含 target_column
            
        Returns:
            标准化的 DataFrame
        """
        # 检测日期列
        date_col = None
        for col in ["日期", "date", "Date"]:
            if col in df.columns:
                date_col = col
                break
        
        # 检测目标值列
        target = config.get("target_column", "收盘")
        value_col = None
        for col in [target, "close", "Close", "收盘"]:
            if col in df.columns:
                value_col = col
                break
        
        if not date_col or not value_col:
            raise ValueError(f"无法识别列: {list(df.columns)}")
        
        result = pd.DataFrame({
            "ds": pd.to_datetime(df[date_col]),
            "y": df[value_col].astype(float)
        }).sort_values("ds").drop_duplicates("ds").reset_index(drop=True)
        
        logger.info(f"[AKShare] 数据准备: {len(result)} 条")
        return result


# 单例
_akshare_source: Optional[AKShareDataSource] = None


def get_akshare_source() -> AKShareDataSource:
    """获取 AKShare 数据源单例"""
    global _akshare_source
    
    if _akshare_source is None:
        _akshare_source = AKShareDataSource()
    
    return _akshare_source
