"""
中国股市交易日历工具

使用AKShare获取中国股市的交易日数据，包含所有节假日信息
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Set
from functools import lru_cache


@lru_cache(maxsize=1)
def get_trading_calendar() -> Set[str]:
    """
    获取中国股市交易日历（带缓存）
    
    Returns:
        Set[str]: 交易日期集合，格式为 'YYYY-MM-DD'
    """
    try:
        df = ak.tool_trade_date_hist_sina()
        # 转换为集合以便快速查询
        trading_dates = set(df['trade_date'].astype(str).tolist())
        return trading_dates
    except Exception as e:
        print(f"获取交易日历失败: {e}")
        # 降级方案：返回空集合，使用BDay
        return set()


def get_next_trading_days(start_date: pd.Timestamp, n_days: int) -> List[pd.Timestamp]:
    """
    获取从指定日期开始的未来N个交易日
    
    Args:
        start_date: 起始日期
        n_days: 需要的交易日数量
        
    Returns:
        List[pd.Timestamp]: 交易日列表
    """
    trading_calendar = get_trading_calendar()
    
    if not trading_calendar:
        # 降级方案：使用BDay
        from pandas.tseries.offsets import BDay
        return [start_date + BDay(i + 1) for i in range(n_days)]
    
    # 使用交易日历
    trading_days = []
    current_date = start_date + timedelta(days=1)
    
    # 向前查找直到找到足够的交易日
    max_search_days = n_days * 3  # 最多查找3倍天数（考虑节假日）
    search_count = 0
    
    while len(trading_days) < n_days and search_count < max_search_days:
        date_str = current_date.strftime('%Y-%m-%d')
        if date_str in trading_calendar:
            trading_days.append(pd.Timestamp(date_str))
        
        current_date += timedelta(days=1)
        search_count += 1
    
    return trading_days


def is_trading_day(date: pd.Timestamp) -> bool:
    """
    检查指定日期是否为交易日
    
    Args:
        date: 要检查的日期
        
    Returns:
        bool: 是否为交易日
    """
    trading_calendar = get_trading_calendar()
    
    if not trading_calendar:
        # 降级方案：检查是否为工作日
        return date.weekday() < 5
    
    date_str = date.strftime('%Y-%m-%d')
    return date_str in trading_calendar
