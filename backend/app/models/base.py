"""
基础预测器接口
==============

定义所有预测模型的统一接口
"""

from abc import ABC, abstractmethod
import pandas as pd

from app.schemas.session_schema import ForecastResult


class BaseForecaster(ABC):
    """预测器基类"""

    @abstractmethod
    def forecast(self, df: pd.DataFrame, horizon: int = 30) -> ForecastResult:
        """
        执行时序预测

        Args:
            df: 标准化的时序数据，包含 ds 和 y 列
            horizon: 预测天数

        Returns:
            ForecastResult: 统一的预测结果，包含:
                - points: List[TimeSeriesPoint] 预测数据点
                - metrics: ForecastMetrics 模型性能指标
                - model: str 模型名称
        """
        pass
