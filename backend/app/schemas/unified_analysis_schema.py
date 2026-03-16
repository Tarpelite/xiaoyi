from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Re-export from session_schema for convenience in service
from app.schemas.session_schema import (
    CreateAnalysisRequest,
    BacktestRequest,
    BacktestResponse,
    BacktestMetrics,
    TimeSeriesPoint,
    MessageStatus,
)


class SuggestionsRequest(BaseModel):
    """快速追问建议请求模型"""
    session_id: Optional[str] = None


class HistoryMessage(BaseModel):
    """历史消息模型"""
    message_id: str
    user_query: str
    status: MessageStatus
    data: Optional[Dict[str, Any]] = None


class HistoryResponse(BaseModel):
    """历史记录响应模型"""
    session_id: str
    messages: List[HistoryMessage]


class StreamStatusResponse(BaseModel):
    """流状态响应"""
    status: Optional[str]
    message_status: str
    data: Optional[Dict[str, Any]]
