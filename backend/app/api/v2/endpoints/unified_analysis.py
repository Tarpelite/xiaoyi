"""
统一分析 API 端点 (v2)
======================

提供统一的异步分析接口，支持 forecast/rag/news/chat 四种意图

架构:
- Controller (本文件): 处理 HTTP 请求/响应
- Service: 业务逻辑和编排
- Schema: 数据模型

端点:
- POST /create: 创建后台分析任务
- GET /history: 获取会话历史
- POST /suggestions: 获取追问建议
- GET /stream-resume: SSE 流式传输实时更新
- POST /backtest: 交互式回测
"""

from typing import List, Dict, Any

from fastapi import APIRouter, BackgroundTasks, Query, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.services.unified_analysis_service import UnifiedAnalysisService
from app.schemas.unified_analysis_schema import (
    CreateAnalysisRequest,
    BacktestRequest,
    BacktestResponse,
    HistoryResponse,
    SuggestionsRequest
)

router = APIRouter()


def get_service() -> UnifiedAnalysisService:
    """UnifiedAnalysisService 的依赖注入"""
    return UnifiedAnalysisService()


@router.post("/create")
async def create_analysis(
    request: CreateAnalysisRequest,
    background_tasks: BackgroundTasks,
    service: UnifiedAnalysisService = Depends(get_service)
) -> Dict[str, Any]:
    """
    创建分析任务（后台独立运行）
    
    任务通过 BackgroundTasks 独立运行，不依赖 SSE 连接。
    前端刷新后，后端任务不受影响。
    """
    return await service.create_analysis(request, background_tasks)


@router.get("/history/{session_id}")
def get_session_history(
    session_id: str,
    service: UnifiedAnalysisService = Depends(get_service)
) -> HistoryResponse:
    """
    获取会话历史（所有消息）
    
    返回该会话的所有消息。
    前端可根据 status 决定渲染方式。
    """
    return service.get_history(session_id)


@router.post("/suggestions")
async def get_suggestions(
    request: SuggestionsRequest,
    service: UnifiedAnalysisService = Depends(get_service)
) -> Dict[str, List[str]]:
    """
    获取快速追问建议
    """
    suggestions = await service.get_suggestions(request.session_id)
    return {"suggestions": suggestions}


@router.get("/stream-resume/{session_id}")
async def stream_resume(
    session_id: str,
    message_id: str = Query(..., description="消息 ID"),
    last_event_id: str = Query("0-0", description="最后接收的事件 ID，默认为 0-0"),
    service: UnifiedAnalysisService = Depends(get_service)
):
    """
    断点续传端点 - 使用异步 XREAD 从 Redis Stream 读取事件
    """
    return await service.stream_resume(session_id, message_id, last_event_id)


@router.post("/backtest")
async def backtest_prediction(
    request: BacktestRequest,
    service: UnifiedAnalysisService = Depends(get_service)
) -> BacktestResponse:
    """
    交互式时间旅行回测端点
    
    基于历史分割点重新预测，计算预测误差指标(MAE/RMSE/MAPE)
    """
    return await service.backtest_prediction(request)
