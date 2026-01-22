"""
模型预测模块
=============

支持多种预测模型：Prophet, XGBoost, RandomForest, DLinear
"""

import asyncio
import pandas as pd

from app.models import (
    ProphetForecaster,
    XGBoostForecaster,
    RandomForestForecaster,
    DLinearForecaster
)


async def run_forecast(
    df: pd.DataFrame,
    model: str,
    horizon: int,
    prophet_params: dict = None
) -> dict:
    """
    运行预测模型

    Args:
        df: 输入数据 DataFrame
        model: 模型名称 (prophet/xgboost/randomforest/dlinear)
        horizon: 预测天数
        prophet_params: Prophet 模型参数（可选）

    Returns:
        预测结果字典，包含 forecast 和 metrics
    """
    if model == "prophet":
        forecaster = ProphetForecaster()
        return await asyncio.to_thread(
            forecaster.forecast, df, horizon, prophet_params or {}
        )
    elif model == "xgboost":
        forecaster = XGBoostForecaster()
        return await asyncio.to_thread(forecaster.forecast, df, horizon)
    elif model == "randomforest":
        forecaster = RandomForestForecaster()
        return await asyncio.to_thread(forecaster.forecast, df, horizon)
    else:  # dlinear
        forecaster = DLinearForecaster()
        return await asyncio.to_thread(forecaster.forecast, df, horizon)
