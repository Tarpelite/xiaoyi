"""
时序分析模块
============

提供时序数据特征分析和特征工程功能
"""

from typing import Dict, Any
import pandas as pd
import numpy as np


class TimeSeriesAnalyzer:
    """时序特征分析器"""
    
    @staticmethod
    def analyze_features(df: pd.DataFrame) -> Dict[str, Any]:
        """
        分析时序数据的统计特征
        
        Args:
            df: 标准化的时序数据，包含 ds 和 y 列
            
        Returns:
            包含趋势、波动性、统计指标的字典
        """
        y = df["y"].values
        
        # 趋势分析
        mid = len(y) // 2
        first_mean, second_mean = np.mean(y[:mid]), np.mean(y[mid:])
        if second_mean > first_mean * 1.05:
            trend = "上升"
        elif second_mean < first_mean * 0.95:
            trend = "下降"
        else:
            trend = "平稳"
        
        # 波动性分析
        cv = np.std(y) / np.mean(y) if np.mean(y) != 0 else 0
        volatility = "高" if cv > 0.3 else ("中" if cv > 0.1 else "低")
        
        # 统计特征
        return {
            "trend": trend,
            "volatility": volatility,
            "mean": round(float(np.mean(y)), 2),
            "std": round(float(np.std(y)), 2),
            "min": round(float(np.min(y)), 2),
            "max": round(float(np.max(y)), 2),
            "latest": round(float(y[-1]), 2),
            "data_points": len(y),
            "date_range": f"{df['ds'].min().date()} ~ {df['ds'].max().date()}"
        }
    
    @staticmethod
    def create_features(df: pd.DataFrame, max_lag: int = 30) -> pd.DataFrame:
        """
        创建时序特征用于机器学习模型
        
        Args:
            df: 标准化的时序数据
            max_lag: 最大滞后阶数
            
        Returns:
            包含工程特征的 DataFrame
        """
        feature_df = df.copy()
        
        # 滞后特征
        for lag in [1, 7, 14, 30]:
            if lag <= max_lag and lag < len(feature_df):
                feature_df[f"lag_{lag}"] = feature_df["y"].shift(lag)
        
        # 移动平均特征
        for window in [7, 14, 30]:
            if window < len(feature_df):
                feature_df[f"ma_{window}"] = feature_df["y"].rolling(window=window, min_periods=1).mean()
                feature_df[f"std_{window}"] = feature_df["y"].rolling(window=window, min_periods=1).std()
        
        # 时间特征
        feature_df["day_of_week"] = feature_df["ds"].dt.dayofweek
        feature_df["day_of_month"] = feature_df["ds"].dt.day
        feature_df["month"] = feature_df["ds"].dt.month
        feature_df["quarter"] = feature_df["ds"].dt.quarter
        
        # 趋势特征
        feature_df["trend"] = np.arange(len(feature_df))
        
        # 填充 NaN
        feature_df = feature_df.bfill().fillna(0)
        
        return feature_df
