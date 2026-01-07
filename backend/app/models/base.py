"""
基础预测器接口
==============

定义所有预测模型的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd


class BaseForecaster(ABC):
    """预测器基类"""
    
    @abstractmethod
    def forecast(self, df: pd.DataFrame, horizon: int = 30) -> Dict[str, Any]:
        """
        执行时序预测
        
        Args:
            df: 标准化的时序数据，包含 ds 和 y 列
            horizon: 预测天数
            
        Returns:
            预测结果字典，包含:
                - forecast: List[Dict] 预测值列表
                - metrics: Dict 模型性能指标
                - model: str 模型名称
        """
        pass
