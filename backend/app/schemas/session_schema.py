"""
Session 数据模型
================

定义分析会话的数据结构
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    """会话状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class TimeSeriesPoint(BaseModel):
    """时序数据点"""
    date: str
    value: float
    is_prediction: bool = False


class NewsItem(BaseModel):
    """新闻条目"""
    title: str
    summary: str
    date: str
    source: str


class ReportItem(BaseModel):
    """研报条目"""
    title: str
    summary: str
    pdf_path: str


class EmotionAnalysis(BaseModel):
    """情绪分析结果"""
    score: float = Field(..., ge=-1, le=1, description="情绪分数 -1到1")
    description: str = Field(..., description="情绪描述")


class AnalysisSession(BaseModel):
    """分析会话完整数据模型"""
    
    # 基础信息
    session_id: str
    context: str = ""
    steps: int = 0
    status: SessionStatus = SessionStatus.PENDING
    is_time_series: bool = True
    
    # 时序数据
    time_series_original: List[TimeSeriesPoint] = []
    time_series_full: List[TimeSeriesPoint] = []
    prediction_done: bool = False
    prediction_start_day: Optional[str] = None
    
    # 新增功能
    news_list: List[NewsItem] = []
    report_list: List[ReportItem] = []
    emotion: Optional[float] = None
    emotion_des: Optional[str] = None
    
    # 综合报告
    conclusion: str = ""
    
    # 对话模式（数据获取失败时）
    conversational_response: str = ""  # AI生成的对话回复
    error_type: Optional[str] = None  # "data_fetch_failed" 等
    
    # 元数据
    created_at: str
    updated_at: str
    error_message: Optional[str] = None
    
    # 额外配置
    stock_code: Optional[str] = None
    model_name: str = "prophet"


class CreateAnalysisRequest(BaseModel):
    """创建分析任务请求"""
    message: str = Field(..., description="用户问题")
    model: str = Field(default="prophet", description="预测模型")
    context: str = Field(default="", description="上下文")


class AnalysisStatusResponse(BaseModel):
    """分析状态响应"""
    session_id: str
    status: SessionStatus
    steps: int
    data: AnalysisSession
