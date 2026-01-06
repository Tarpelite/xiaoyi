"""
数据获取与预处理模块
====================

负责从 AKShare 等数据源获取金融数据并进行标准化预处理
"""

from typing import Dict, Any
import pandas as pd


class DataFetcher:
    """AKShare 数据获取器"""
    
    @staticmethod
    def fetch(config: Dict[str, Any]) -> pd.DataFrame:
        """
        根据配置从 AKShare 获取原始数据
        
        Args:
            config: 数据配置字典，包含 api_function 和 params
            
        Returns:
            原始数据 DataFrame
            
        Raises:
            ValueError: 不支持的 API 函数
        """
        import akshare as ak
        
        api_map = {
            "stock_zh_a_hist": ak.stock_zh_a_hist,
            "stock_zh_index_daily_em": ak.stock_zh_index_daily_em,
            "fund_etf_hist_em": ak.fund_etf_hist_em,
        }
        
        func_name = config["api_function"]
        params = config["params"]
        
        if func_name not in api_map:
            raise ValueError(f"不支持的 API: {func_name}")
        
        df = api_map[func_name](**params)
        print(f"✅ 获取数据: {len(df)} 条")
        return df
    
    @staticmethod
    def prepare(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        """
        将原始数据转换为标准时序格式 (ds, y)
        
        Args:
            df: 原始数据 DataFrame
            config: 数据配置，包含 target_column
            
        Returns:
            标准化的 DataFrame，包含 ds (日期) 和 y (目标值) 列
            
        Raises:
            ValueError: 无法识别日期列或目标列
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
        
        # 标准化格式
        result = pd.DataFrame({
            "ds": pd.to_datetime(df[date_col]),
            "y": df[value_col].astype(float)
        }).sort_values("ds").drop_duplicates("ds").reset_index(drop=True)
        
        print(f"✅ 数据准备: {len(result)} 条, {result['ds'].min().date()} ~ {result['ds'].max().date()}")
        return result
