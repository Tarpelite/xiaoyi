"""
SeasonalNaive 基线预测模型
==========================

基于季节性朴素预测的基线模型
- 如果数据量 >= seasonality，使用 y[t] = y[t - seasonality]
- 否则退化为 y[-1]（最后值）
"""

import pandas as pd
import numpy as np
from .base import BaseForecaster
from app.utils.trading_calendar import get_next_trading_days
from app.schemas.session_schema import ForecastResult, ForecastMetrics, TimeSeriesPoint


class SeasonalNaiveForecaster(BaseForecaster):
    """季节性朴素预测器（基线模型）"""

    def __init__(self, seasonality: int = 5):
        """
        Args:
            seasonality: 季节性周期，默认 5（一周交易日）
        """
        self.seasonality = seasonality

    def forecast(self, df: pd.DataFrame, horizon: int = 30) -> ForecastResult:
        """
        使用季节性朴素方法进行时序预测

        Args:
            df: 标准化的时序数据，包含 ds 和 y 列
            horizon: 预测天数

        Returns:
            ForecastResult: 统一的预测结果
        """
        if df.empty:
            raise ValueError("输入数据为空")

        values = df["y"].values
        last_date = df["ds"].iloc[-1]

        # 获取未来交易日
        trading_days = get_next_trading_days(last_date, horizon)

        # 判断是否使用季节性预测
        use_seasonal = len(df) >= self.seasonality

        forecast_points = []
        for i, future_date in enumerate(trading_days):
            if use_seasonal:
                # 季节性预测：y[t] = y[t - seasonality]
                if i < self.seasonality:
                    # 前 seasonality 个点，使用历史数据
                    # values[-seasonality + i] 对应历史中 seasonality 天前的值
                    pred_value = values[-self.seasonality + i]
                else:
                    # 超过 seasonality 的点，使用之前预测的值
                    pred_value = forecast_points[i - self.seasonality].value
            else:
                # 退化：使用最后一个值
                pred_value = values[-1]

            forecast_points.append(TimeSeriesPoint(
                date=future_date.strftime("%Y-%m-%d"),
                value=round(float(pred_value), 2),
                is_prediction=True
            ))

        # 计算训练集指标（使用尾部对齐）
        # 使用最后 seasonality 个点作为"实际值"，与前面 seasonality 个点（作为"预测值"）比较
        if len(values) >= self.seasonality * 2:
            # 有足够数据，使用季节性对齐计算
            # 实际值：最后 seasonality 个点
            # 预测值：seasonality 天前的值
            actual = values[-self.seasonality:]
            predicted = values[-self.seasonality * 2:-self.seasonality]
            residuals = actual - predicted
        elif len(values) >= self.seasonality:
            # 数据量刚好够 seasonality，使用第一个值作为预测
            actual = values[-self.seasonality:]
            predicted = np.full(self.seasonality, values[0])
            residuals = actual - predicted
        else:
            # 数据量不足 seasonality，使用简单方法
            if len(values) > 1:
                actual = values[1:]
                predicted = np.full(len(values) - 1, values[0])
                residuals = actual - predicted
            else:
                residuals = np.array([0.0])

        mae = np.mean(np.abs(residuals)) if len(residuals) > 0 else 0.0
        rmse = np.sqrt(np.mean(residuals ** 2)) if len(residuals) > 0 else 0.0

        return ForecastResult(
            points=forecast_points,
            metrics=ForecastMetrics(
                mae=round(float(mae), 4),
                rmse=round(float(rmse), 4)
            ),
            model="seasonal_naive"
        )
