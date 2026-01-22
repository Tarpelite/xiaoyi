"""
Prophet 预测模型
================

基于 Facebook Prophet 的时序预测实现
"""

from typing import Dict, Any
import pandas as pd
import numpy as np
from .base import BaseForecaster
from prophet import Prophet
from app.utils.trading_calendar import get_trading_calendar
from app.schemas.session_schema import ForecastResult, ForecastMetrics, TimeSeriesPoint
class ProphetForecaster(BaseForecaster):
    """Prophet 时序预测器"""

    def forecast(
        self,
        df: pd.DataFrame,
        horizon: int = 30,
        prophet_params: Dict[str, Any] = None
    ) -> ForecastResult:
        """
        使用 Prophet 模型进行时序预测

        Args:
            df: 标准化的时序数据，包含 ds 和 y 列
            horizon: 预测天数
            prophet_params: Prophet 模型参数（可选），支持:
                - changepoint_prior_scale: 趋势变化敏感度 (默认 0.05)
                - seasonality_prior_scale: 季节性强度 (默认 10)
                - changepoint_range: 变点检测范围 (默认 0.8)

        Returns:
            ForecastResult: 统一的预测结果
        """
        # 使用传入参数或默认值
        params = prophet_params or {}

        # 配置模型
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            changepoint_prior_scale=params.get("changepoint_prior_scale", 0.05),
            seasonality_prior_scale=params.get("seasonality_prior_scale", 10),
            changepoint_range=params.get("changepoint_range", 0.8),
        )

        # 训练模型
        model.fit(df[["ds", "y"]])

        # 生成未来时间点（多生成以确保有足够交易日）
        future = model.make_future_dataframe(periods=horizon * 2, freq="D")
        forecast = model.predict(future)

        # 获取交易日历并过滤
        trading_calendar = get_trading_calendar()
        pred = forecast.tail(horizon * 2)
        forecast_points = []
        for _, row in pred.iterrows():
            date_str = row["ds"].strftime("%Y-%m-%d")
            if not trading_calendar or date_str in trading_calendar:
                forecast_points.append(TimeSeriesPoint(
                    date=date_str,
                    value=round(row["yhat"], 2),
                    is_prediction=True
                ))
                if len(forecast_points) >= horizon:
                    break

        # 计算训练集指标
        train_pred = forecast.head(len(df))
        residuals = df["y"].values - train_pred["yhat"].values
        mae = np.mean(np.abs(residuals))
        rmse = np.sqrt(np.mean(residuals ** 2))

        return ForecastResult(
            points=forecast_points,
            metrics=ForecastMetrics(
                mae=round(float(mae), 4),
                rmse=round(float(rmse), 4)
            ),
            model="prophet"
        )
