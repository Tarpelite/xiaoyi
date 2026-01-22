"""
格式转换模块
=============

数据格式转换工具函数
"""

from typing import List
import pandas as pd

from app.schemas.session_schema import TimeSeriesPoint


def df_to_points(df: pd.DataFrame, is_prediction: bool = False) -> List[TimeSeriesPoint]:
    """
    DataFrame 转换为时序数据点

    Args:
        df: 包含 ds 和 y 列的 DataFrame
        is_prediction: 是否为预测数据

    Returns:
        时序数据点列表
    """
    points = []
    for _, row in df.iterrows():
        points.append(TimeSeriesPoint(
            date=str(row["ds"].date()) if hasattr(row["ds"], "date") else str(row["ds"]),
            value=float(row["y"]),
            is_prediction=is_prediction
        ))
    return points
