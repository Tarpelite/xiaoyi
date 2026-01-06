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

class ProphetForecaster(BaseForecaster):
    """Prophet 时序预测器"""
    
    def forecast(self, df: pd.DataFrame, horizon: int = 30) -> Dict[str, Any]:
        """
        使用 Prophet 模型进行时序预测
        
        Args:
            df: 标准化的时序数据，包含 ds 和 y 列
            horizon: 预测天数
            
        Returns:
            预测结果字典
        """
        
        # 配置模型
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            changepoint_prior_scale=0.05,
        )
        
        # 训练模型
        model.fit(df[["ds", "y"]])
        
        # 生成未来时间点
        future = model.make_future_dataframe(periods=horizon, freq="D")
        forecast = model.predict(future)
        
        # 提取预测结果
        pred = forecast.tail(horizon)
        forecast_values = [
            {
                "date": row["ds"].strftime("%Y-%m-%d"),
                "value": round(row["yhat"], 2),
                "lower": round(row["yhat_lower"], 2),
                "upper": round(row["yhat_upper"], 2),
            }
            for _, row in pred.iterrows()
        ]
        
        # 计算训练集 MAE
        train_pred = forecast.head(len(df))
        mae = np.mean(np.abs(df["y"].values - train_pred["yhat"].values))
        
        return {
            "forecast": forecast_values,
            "metrics": {"mae": round(float(mae), 4)},
            "model": "prophet"
        }
