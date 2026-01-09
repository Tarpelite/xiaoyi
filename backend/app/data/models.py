"""
数据层统一模型
==============

所有数据源返回的统一数据格式
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from enum import Enum


class DataSourceType(str, Enum):
    """数据源类型"""
    AKSHARE = "akshare"       # AKShare 股票/新闻数据
    TAVILY = "tavily"         # Tavily 网络搜索
    REPORT = "report"         # 研报 RAG 服务


class SearchResult(BaseModel):
    """统一搜索结果"""
    
    source: DataSourceType = Field(..., description="数据来源")
    content: str = Field(..., description="内容")
    title: Optional[str] = Field(None, description="标题")
    url: Optional[str] = Field(None, description="链接")
    score: float = Field(0.0, description="相关度得分")
    
    # 元数据
    date: Optional[str] = Field(None, description="日期")
    file_name: Optional[str] = Field(None, description="文件名（研报）")
    page_number: Optional[int] = Field(None, description="页码（研报）")
    
    # 原始数据（可选）
    raw_data: Optional[dict] = Field(None, description="原始数据")


class NewsResult(BaseModel):
    """新闻搜索结果"""
    
    source: DataSourceType = Field(..., description="数据来源")
    title: str = Field(..., description="标题")
    content: str = Field("", description="内容/摘要")
    url: Optional[str] = Field(None, description="链接")
    published_date: Optional[str] = Field(None, description="发布日期")
    score: float = Field(0.0, description="相关度得分")


class ReportResult(BaseModel):
    """研报检索结果"""
    
    chunk_id: str = Field(..., description="分块 ID")
    doc_id: str = Field(..., description="文档 ID")
    content: str = Field(..., description="内容")
    score: float = Field(..., description="相关度得分")
    page_number: int = Field(..., description="页码")
    file_name: str = Field(..., description="文件名")
    title: Optional[str] = Field(None, description="文档标题")
    section_title: Optional[str] = Field(None, description="章节标题")
    
    # Rerank 分数（可选）
    rerank_score: Optional[float] = Field(None, description="重排序得分")


class DataQueryRequest(BaseModel):
    """数据查询请求"""
    
    query: str = Field(..., description="查询内容")
    sources: List[DataSourceType] = Field(
        default=[DataSourceType.REPORT, DataSourceType.TAVILY],
        description="要查询的数据源"
    )
    top_k: int = Field(5, description="每个数据源返回的结果数量")
    
    # 可选参数
    stock_code: Optional[str] = Field(None, description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    days: int = Field(30, description="新闻搜索天数")
    use_rerank: bool = Field(True, description="是否使用 Rerank（研报）")


class DataQueryResponse(BaseModel):
    """数据查询响应"""
    
    query: str = Field(..., description="原始查询")
    results: List[SearchResult] = Field(default_factory=list, description="搜索结果")
    
    # 按来源分类的结果
    report_results: List[ReportResult] = Field(default_factory=list, description="研报结果")
    news_results: List[NewsResult] = Field(default_factory=list, description="新闻结果")
    
    # 统计
    total_count: int = Field(0, description="总结果数")
    took_ms: float = Field(0.0, description="耗时（毫秒）")
    
    # 错误信息
    errors: List[str] = Field(default_factory=list, description="错误信息")
