"""
DLinear 预测模型
================

基于论文 "Are Transformers Effective for Time Series Forecasting?" 的完整实现
DLinear: 通过 Series Decomposition + Two Linear Layers 进行预测

参考: https://arxiv.org/abs/2205.13504
"""

from typing import Dict, Any, Tuple
from datetime import timedelta
import pandas as pd
import numpy as np
from .base import BaseForecaster
from app.utils.trading_calendar import get_trading_calendar

class MovingAverage:
    """移动平均核用于趋势提取"""
    
    def __init__(self, kernel_size: int = 25):
        """
        Args:
            kernel_size: 移动平均窗口大小，论文推荐 25
        """
        self.kernel_size = kernel_size
    
    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        使用移动平均提取趋势分量
        
        Args:
            x: 输入序列 (n,)
            
        Returns:
            趋势分量 (n,)
        """
        # 使用 padding 确保输出长度不变
        padding = (self.kernel_size - 1) // 2
        x_padded = np.pad(x, (padding, padding), mode='edge')
        
        # 应用移动平均
        trend = np.convolve(x_padded, np.ones(self.kernel_size) / self.kernel_size, mode='valid')
        
        return trend


class SeriesDecomposition:
    """时序序列分解模块"""
    
    def __init__(self, kernel_size: int = 25):
        self.moving_avg = MovingAverage(kernel_size)
    
    def forward(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        分解时序为趋势和季节性
        
        Args:
            x: 输入序列
            
        Returns:
            (trend, seasonal) 元组
        """
        trend = self.moving_avg.forward(x)
        seasonal = x - trend
        return trend, seasonal


class LinearLayer:
    """线性层: y = Wx + b"""
    
    def __init__(self, input_size: int, output_size: int = 1):
        """
        Args:
            input_size: 输入特征维度 (seq_len)
            output_size: 输出维度，默认1
        """
        self.input_size = input_size
        self.output_size = output_size
        # 初始化权重 (使用 Xavier 初始化)
        limit = np.sqrt(6.0 / (input_size + output_size))
        self.W = np.random.uniform(-limit, limit, (input_size, output_size))
        self.b = np.zeros(output_size)
    
    def fit(self, X: np.ndarray, y: np.ndarray, alpha: float = 0.01):
        """
        使用最小二乘法 + L2正则化训练线性层
        
        Args:
            X: 训练数据 (n_samples, input_size)
            y: 目标值 (n_samples, output_size)
            alpha: L2 正则化系数
        """
        # 添加正则化的最小二乘解: W = (X^T X + αI)^(-1) X^T y
        XtX = X.T @ X
        reg = alpha * np.eye(self.input_size)
        self.W = np.linalg.solve(XtX + reg, X.T @ y).reshape(-1, self.output_size)
        
        # 计算偏置
        predictions = X @ self.W
        self.b = np.mean(y - predictions, axis=0)
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        预测
        
        Args:
            X: 输入数据 (n_samples, input_size) 或 (input_size,)
            
        Returns:
            预测值 (n_samples, output_size) 或 (output_size,)
        """
        if X.ndim == 1:
            return (X @ self.W + self.b).flatten()
        return X @ self.W + self.b


class DLinearForecaster(BaseForecaster):
    """
    DLinear 时序预测器
    
    架构:
    1. Series Decomposition: 分解为趋势和季节性
    2. Two Linear Layers: 分别对趋势和季节性建模
    3. Aggregation: 合并两个分量的预测结果
    """
    
    def __init__(self, seq_len: int = 96, kernel_size: int = 25):
        """
        Args:
            seq_len: 输入序列长度，论文默认 96
            kernel_size: 移动平均核大小，论文推荐 25
        """
        self.seq_len = seq_len
        self.decomposition = SeriesDecomposition(kernel_size)
        self.trend_layer = None
        self.seasonal_layer = None
    
    def forecast(self, df: pd.DataFrame, horizon: int = 30) -> Dict[str, Any]:
        """使用 DLinear 模型进行时序预测"""
        # 检查数据量
        min_required = self.seq_len + 20
        if len(df) < min_required:
            raise ValueError(f"DLinear 需要至少 {min_required} 条历史数据，当前只有 {len(df)} 条")
        
        values = df["y"].values
        
        trend, seasonal = self.decomposition.forward(values)
        X_trend, y_trend = self._create_sequences(trend, self.seq_len)
        X_seasonal, y_seasonal = self._create_sequences(seasonal, self.seq_len)
        
        # 训练单步预测线性层
        self.trend_layer = LinearLayer(self.seq_len, 1)
        self.seasonal_layer = LinearLayer(self.seq_len, 1)
        self.trend_layer.fit(X_trend, y_trend, alpha=0.01)
        self.seasonal_layer.fit(X_seasonal, y_seasonal, alpha=0.01)
        
        # 计算置信区间
        train_pred_trend = self.trend_layer.predict(X_trend).flatten()
        train_pred_seasonal = self.seasonal_layer.predict(X_seasonal).flatten()
        residuals = (y_trend.flatten() + y_seasonal.flatten()) - (train_pred_trend + train_pred_seasonal)
        std_error = np.std(residuals)
        
        # 递归预测 - 使用原始值窗口
        forecast_values = []
        last_date = df["ds"].iloc[-1]
        
        # 初始化窗口为最后seq_len个原始值
        value_window = values[-self.seq_len:].copy()
        
        for i in range(horizon):
            # 在for循环之前
            trading_days = get_next_trading_days(last_date, horizon)
            for i in range(horizon):
                future_date = trading_days[i]
            
            # 分解当前窗口
            window_trend, window_seasonal = self.decomposition.forward(value_window)
            
            # 使用最后seq_len个trend/seasonal进行预测
            trend_pred = float(self.trend_layer.predict(window_trend).item())
            seasonal_pred = float(self.seasonal_layer.predict(window_seasonal).item())
            
            # 组合得到原始值预测
            pred_value = trend_pred + seasonal_pred
            
            forecast_values.append({
                "date": future_date.strftime("%Y-%m-%d"),
                "value": round(pred_value, 2),
                "lower": round(pred_value - 1.96 * std_error, 2),
                "upper": round(pred_value + 1.96 * std_error, 2),
            })
            
            # 更新窗口：移除最旧值，添加新预测值
            value_window = np.append(value_window[1:], pred_value)
        
        mae = np.mean(np.abs(residuals))
        rmse = np.sqrt(np.mean(residuals ** 2))
        
        return {
            "forecast": forecast_values,
            "metrics": {"mae": round(float(mae), 4), "rmse": round(float(rmse), 4)},
            "model": "dlinear"
        }
    
    def _create_sequences(
        self,
        data: np.ndarray,
        seq_len: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """创建序列训练数据"""
        X, y = [], []
        
        for i in range(len(data) - seq_len):
            X.append(data[i:i + seq_len])
            y.append([data[i + seq_len]])
        
        return np.array(X), np.array(y)
