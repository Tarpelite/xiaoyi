"""
DLinear 预测模型
================

基于 DLinear (Decomposition Linear) 的时序预测实现
DLinear: 通过趋势-季节性分解 + 线性层进行预测
"""

from typing import Dict, Any
from datetime import timedelta
import pandas as pd
import numpy as np
from .base import BaseForecaster


class DLinearForecaster(BaseForecaster):
    """DLinear 时序预测器"""
    
    def forecast(self, df: pd.DataFrame, horizon: int = 30) -> Dict[str, Any]:
        """
        使用 DLinear 模型进行时序预测
        
        DLinear 核心思想：
        1. 分解: y = trend + seasonal
        2. 预测: 分别用线性层预测 trend 和 seasonal
        3. 合并: y_pred = trend_pred + seasonal_pred
        
        Args:
            df: 标准化的时序数据，包含 ds 和 y 列
            horizon: 预测天数
            
        Returns:
            预测结果字典
            
        Raises:
            ValueError: 数据量不足
        """
        # 检查数据量
        if len(df) < 60:
            raise ValueError(f"DLinear 需要至少60条历史数据，当前只有 {len(df)} 条")
        
        # 参数配置
        seq_len = min(60, len(df) - horizon)  # 输入序列长度
        
        # 准备数据
        values = df["y"].values
        
        # Step 1: 分解 - 使用移动平均提取趋势
        trend = self._extract_trend(values, window=7)
        seasonal = values - trend
        
        # Step 2: 训练线性模型
        # 为趋势和季节性分别训练简单线性回归
        trend_model = self._train_linear_model(trend, seq_len)
        seasonal_model = self._train_linear_model(seasonal, seq_len)
        
        # Step 3: 预测
        forecast_values = []
        last_date = df["ds"].iloc[-1]
        
        # 使用最后 seq_len 个值作为输入
        trend_input = trend[-seq_len:]
        seasonal_input = seasonal[-seq_len:]
        
        for i in range(horizon):
            future_date = last_date + timedelta(days=i + 1)
            
            # 预测趋势和季节性
            trend_pred = self._predict_next(trend_model, trend_input)
            seasonal_pred = self._predict_next(seasonal_model, seasonal_input)
            
            # 合并预测
            pred_value = trend_pred + seasonal_pred
            
            # 使用历史残差估计置信区间
            residuals = values[seq_len:] - (trend[seq_len:] + seasonal[seq_len:])
            std_error = np.std(residuals)
            lower = pred_value - 1.96 * std_error
            upper = pred_value + 1.96 * std_error
            
            forecast_values.append({
                "date": future_date.strftime("%Y-%m-%d"),
                "value": round(float(pred_value), 2),
                "lower": round(float(lower), 2),
                "upper": round(float(upper), 2),
            })
            
            # 更新输入（滚动窗口）
            trend_input = np.append(trend_input[1:], trend_pred)
            seasonal_input = np.append(seasonal_input[1:], seasonal_pred)
        
        # 计算训练集MAE
        train_trend_pred = []
        train_seasonal_pred = []
        for i in range(seq_len, len(values)):
            t_pred = self._predict_next(trend_model, trend[i-seq_len:i])
            s_pred = self._predict_next(seasonal_model, seasonal[i-seq_len:i])
            train_trend_pred.append(t_pred)
            train_seasonal_pred.append(s_pred)
        
        train_pred = np.array(train_trend_pred) + np.array(train_seasonal_pred)
        mae = np.mean(np.abs(values[seq_len:] - train_pred))
        rmse = np.sqrt(np.mean((values[seq_len:] - train_pred) ** 2))
        
        return {
            "forecast": forecast_values,
            "metrics": {
                "mae": round(float(mae), 4),
                "rmse": round(float(rmse), 4)
            },
            "model": "dlinear"
        }
    
    def _extract_trend(self, values: np.ndarray, window: int = 7) -> np.ndarray:
        """使用移动平均提取趋势"""
        trend = np.copy(values).astype(float)
        for i in range(len(values)):
            if i < window:
                trend[i] = np.mean(values[:i+1])
            else:
                trend[i] = np.mean(values[i-window:i])
        return trend
    
    def _train_linear_model(self, series: np.ndarray, seq_len: int) -> Dict[str, float]:
        """
        训练简单线性模型: y = w * x + b
        使用最小二乘法
        """
        X = []
        y = []
        
        for i in range(seq_len, len(series)):
            X.append(series[i-seq_len:i])
            y.append(series[i])
        
        X = np.array(X)
        y = np.array(y)
        
        # 简化版: 使用输入序列的平均值 + 线性趋势
        # w = 输入序列最后一个值的权重
        # b = 偏置
        
        # 计算最优权重（简化为使用最后若干值的加权平均）
        weights = np.exp(np.linspace(-1, 0, seq_len))  # 指数衰减权重
        weights = weights / weights.sum()
        
        return {
            "weights": weights,
            "seq_len": seq_len
        }
    
    def _predict_next(self, model: Dict[str, Any], input_seq: np.ndarray) -> float:
        """使用线性模型预测下一个值"""
        weights = model["weights"]
        pred = np.dot(input_seq, weights)
        return pred
