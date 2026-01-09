"""
数据源抽象基类
==============

所有数据源都需要实现这个接口
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.data.models import SearchResult, DataSourceType


class BaseDataSource(ABC):
    """数据源抽象基类"""
    
    @property
    @abstractmethod
    def source_type(self) -> DataSourceType:
        """数据源类型"""
        pass
    
    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 5,
        **kwargs
    ) -> List[SearchResult]:
        """
        搜索数据
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            **kwargs: 额外参数
            
        Returns:
            搜索结果列表
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        pass
