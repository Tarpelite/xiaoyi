"""
Auto ARIMA 预测模型
===================

基于 pmdarima 的自动 ARIMA 时序预测实现
"""

from typing import Dict, Any
import pandas as pd
import numpy as np
from .base import BaseForecaster


class AutoARIMAForecaster(BaseForecaster):
    """Auto ARIMA 时序预测器"""

    def forecast(self, df: pd.DataFrame, horizon: int = 30) -> Dict[str, Any]:
        """
        使用 Auto ARIMA 模型进行时序预测

        Args:
            df: 标准化的时序数据，包含 ds 和 y 列
            horizon: 预测天数

        Returns:
            预测结果字典
        """
        from pmdarima import auto_arima

        # 准备数据
        y = df["y"].values
        dates = pd.to_datetime(df["ds"])

        # 自动选择最优 ARIMA 参数
        model = auto_arima(
            y,
            start_p=0, start_q=0,
            max_p=5, max_q=5,
            m=1,  # 非季节性
            d=None,  # 自动确定差分阶数
            seasonal=False,
            stepwise=True,
            suppress_warnings=True,
            error_action="ignore",
            trace=False,
            n_fits=20,
        )

        # 预测
        forecast_values_raw, conf_int = model.predict(
            n_periods=horizon,
            return_conf_int=True,
            alpha=0.05  # 95% 置信区间
        )

        # 生成未来日期
        last_date = dates.iloc[-1]
        future_dates = pd.date_range(
            start=last_date + pd.Timedelta(days=1),
            periods=horizon,
            freq="D"
        )

        # 构建预测结果
        forecast_list = [
            {
                "date": future_dates[i].strftime("%Y-%m-%d"),
                "value": round(float(forecast_values_raw[i]), 2),
                "lower": round(float(conf_int[i, 0]), 2),
                "upper": round(float(conf_int[i, 1]), 2),
            }
            for i in range(horizon)
        ]

        # 计算训练集 MAE (使用拟合值)
        fitted_values = model.predict_in_sample()
        mae = np.mean(np.abs(y - fitted_values))

        # 获取模型阶数信息
        order = model.order  # (p, d, q)

        return {
            "forecast": forecast_list,
            "metrics": {
                "mae": round(float(mae), 4),
                "aic": round(float(model.aic()), 2),
                "order": f"({order[0]},{order[1]},{order[2]})"
            },
            "model": "autoarima"
        }
