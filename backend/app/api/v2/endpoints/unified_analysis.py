"""
统一分析 API 端点 (v2)
======================

提供统一的异步分析接口，支持 forecast/rag/news/chat 四种意图

架构:
- Session: 一整个多轮对话 (复用同一 session_id)
- Message: 每轮 QA (每次查询创建新 message_id)

核心端点:
- POST /create: 创建后台任务，返回 message_id
- GET /stream-resume: 追赶历史事件 + 订阅实时事件 (SSE)
- GET /history: 刷新后恢复已完成的历史消息
"""

import asyncio
import json
import math
import time
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.session import Session, Message
from app.core.streaming_task_processor import get_streaming_processor
from app.core.workflows import run_forecast
from app.core.redis_client import get_redis, get_async_redis
from app.schemas.session_schema import (
    CreateAnalysisRequest,
    BacktestRequest,
    BacktestResponse,
    BacktestMetrics,
    TimeSeriesPoint,
)
from app.agents import SuggestionAgent


class SuggestionsRequest(BaseModel):
    """快速追问建议请求模型"""
    session_id: Optional[str] = None


router = APIRouter()


async def run_background_analysis(session_id: str, message_id: str, user_input: str, model_name: str):
    """后台运行分析任务（独立于 SSE 连接）"""
    streaming_processor = get_streaming_processor()
    await streaming_processor.execute_streaming(
        session_id, message_id, user_input, None, model_name
    )


@router.post("/create")
async def create_analysis(
    request: CreateAnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    创建分析任务（后台独立运行）

    任务通过 BackgroundTasks 独立运行，不依赖 SSE 连接。
    前端刷新后，后端任务不受影响。

    Args:
        request: CreateAnalysisRequest
            - message: 用户问题
            - model: 预测模型
            - session_id: 会话 ID（可选）

    Returns:
        - session_id: 会话 ID
        - message_id: 消息 ID
        - status: "created"
    """
    # 获取或创建 Session
    if request.session_id and Session.exists(request.session_id):
        session = Session(request.session_id)
    else:
        session = Session.create()

    # 检查是否是首条消息（用于自动生成标题）
    session_data = session.get()
    is_first_message = session_data and len(session_data.message_ids) == 0

    # 创建 Message
    message = session.create_message(request.message)

    # 如果是首条消息，自动生成标题
    if is_first_message:
        session.auto_generate_title(request.message)

    session.add_conversation_message("user", request.message)

    # 后台任务独立运行
    background_tasks.add_task(
        run_background_analysis,
        session.session_id,
        message.message_id,
        request.message,
        request.model or "prophet"
    )

    return {
        "session_id": session.session_id,
        "message_id": message.message_id,
        "status": "created"
    }


@router.get("/history/{session_id}")
async def get_session_history(session_id: str):
    """
    获取会话历史（所有消息）

    返回该会话的所有消息，每条消息带有 status 标记。
    前端根据 status 决定渲染方式：
    - completed/error: 直接渲染完整内容
    - pending/processing: 调用 /stream-resume 进行 catch-up + listen

    Args:
        session_id: 会话 ID

    Returns:
        {
            "session_id": "uuid-xxx",
            "messages": [
                {
                    "message_id": "uuid-yyy",
                    "user_query": "用户问题",
                    "status": "completed" | "processing" | "pending" | "error",
                    "data": MessageData
                },
                ...
            ]
        }
    """
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    session = Session(session_id)
    all_messages = session.get_all_messages()

    messages = []
    for msg in all_messages:
        data = msg.get()
        if data:
            messages.append({
                "message_id": msg.message_id,
                "user_query": data.user_query,
                "status": data.status,
                "data": data
            })

    return {
        "session_id": session_id,
        "messages": messages
    }


@router.post("/suggestions")
async def get_suggestions(request: SuggestionsRequest):
    """
    获取快速追问建议

    Args:
        request: 请求体
            - session_id: 会话ID（可选）

    Returns:
        {"suggestions": ["建议1", "建议2", ...]}
    """
    session_id = request.session_id

    # 如果没有提供 session_id，返回默认建议
    if not session_id or not Session.exists(session_id):
        default_suggestions = [
            "帮我分析一下茅台，预测下个季度走势",
            "查看最近的市场趋势",
            "对比几只白酒股的表现",
            "生成一份投资分析报告"
        ]
        return {"suggestions": default_suggestions}

    # 获取对话历史
    session = Session(session_id)
    conversation_history = session.get_conversation_history()

    # 生成建议
    suggestion_agent = SuggestionAgent()
    suggestions = await asyncio.to_thread(
        suggestion_agent.generate_suggestions,
        conversation_history
    )

    return {"suggestions": suggestions}


@router.get("/stream-resume/{session_id}")
async def stream_resume(
    session_id: str,
    message_id: str = Query(..., description="消息 ID"),
    last_event_id: str = Query("0-0", description="最后接收的事件 ID，默认为 0-0")
):
    """
    断点续传端点 - 使用异步 XREAD 从 Redis Stream 读取事件

    Args:
        session_id: 会话 ID
        message_id: 消息 ID
        last_event_id: 最后接收的事件 ID，默认为 0-0

    Returns:
        SSE 流
    """
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    message_obj = Message(message_id, session_id)
    data = message_obj.get()

    if not data:
        raise HTTPException(status_code=404, detail="消息不存在")

    stream_key = f"stream-events:{message_id}"

    # 如果任务已完成，直接返回 JSON
    if data.stream_status not in ("streaming", None, ""):
        return {
            "status": data.stream_status,
            "message_status": data.status.value,
            "data": data.model_dump()
        }

    async def event_stream():
        nonlocal last_event_id

        # 获取异步 Redis 连接
        r = get_async_redis()

        try:
            # 先发送当前状态
            yield f"data: {json.dumps({'type': 'resume', 'current_data': data.model_dump()})}\n\n"

            while True:
                try:
                    # 异步 XREAD：阻塞等待新事件，不会卡住事件循环
                    events = await r.xread(
                        streams={stream_key: last_event_id},
                        count=10,
                        block=2000  # 阻塞 2 秒
                    )
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    break

                # 超时没有新数据
                if not events:
                    # 检查任务是否已结束
                    check_data = message_obj.get()
                    if check_data and check_data.stream_status not in ("streaming", None, ""):
                        yield f"data: {json.dumps({'type': 'done', 'completed': True})}\n\n"
                        break
                    continue

                # 处理事件
                for stream_name, message_list in events:
                    for msg_id, fields in message_list:
                        last_event_id = msg_id

                        if "data" in fields:
                            event_data = fields["data"]
                            yield f"data: {event_data}\n\n"

                            # 检查是否结束
                            try:
                                payload = json.loads(event_data)
                                if payload.get("type") in ("done", "error"):
                                    await r.aclose()
                                    return
                            except json.JSONDecodeError:
                                pass

        except asyncio.CancelledError:
            pass
        finally:
            await r.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"}
    )


@router.post("/backtest")
async def backtest_prediction(request: "BacktestRequest"):
    """
    交互式时间旅行回测端点
    
    基于历史分割点重新预测，计算预测误差指标(MAE/RMSE/MAPE)
    
    Args:
        request: BacktestRequest
            - session_id: 会话ID
            - message_id: 消息ID  
            - split_date: 分割点日期 (YYYY-MM-DD)
            - forecast_horizon: 可选，预测天数
    
    Returns:
        BacktestResponse:
            - metrics: 误差指标
            - backtest_data: 回测预测结果
            - ground_truth: 实际历史数据
    """
    start_time = time.time()
    
    # 1. 验证会话和消息
    if not Session.exists(request.session_id):
        raise HTTPException(404, "会话不存在")
    
    message = Message(request.message_id, request.session_id)
    data = message.get()
    
    if not data:
        raise HTTPException(404, "消息不存在")
    
    # 检查是否是预测类型的消息
    is_forecast = data.intent == 'forecast' or (data.unified_intent and data.unified_intent.is_forecast)
    if not is_forecast or not data.time_series_original:
        raise HTTPException(400, "该消息不包含预测数据")
    
    original_data = data.time_series_original

    # 2. 找到分割点索引
    split_index = -1
    for i, point in enumerate(original_data):
        if point.date >= request.split_date:
            split_index = i
            break

    if split_index < 0:
        raise HTTPException(400, f"分割日期 {request.split_date} 不在数据范围内")
    
    # 确保有足够的训练数据（至少60个点）
    if split_index < 60:
        raise HTTPException(400, f"分割点过早，训练数据不足（需要至少60个点，当前{split_index}个）")
    
    train_points = original_data[:split_index]
    ground_truth_points = original_data[split_index:]
    
    # 4. 计算horizon: max(90天, ground_truth长度)
    # 这样即使ground_truth较短，也会显示完整的90天预测
    horizon = max(90, len(ground_truth_points))

    # 转换为DataFrame
    df = pd.DataFrame({
        "ds": pd.to_datetime([p.date for p in train_points]),
        "y": [p.value for p in train_points]
    })

    # 运行预测
    model_to_use = data.model_name if hasattr(data, 'model_name') and data.model_name else "prophet"
    forecast_result = await run_forecast(
        df,
        model_to_use,
        horizon,
        {}  # Prophet参数
    )
    
    # 提取预测结果（forecast_result 是 ForecastResult 对象）
    backtest_points = forecast_result.points
    
    # 对齐日期（确保预测和ground truth长度一致）
    backtest_aligned = {}
    for p in backtest_points:
        backtest_aligned[p.date] = p.value
    
    ground_truth_aligned = {}
    for p in ground_truth_points:
        ground_truth_aligned[p.date] = p.value
    
    common_dates = set(backtest_aligned.keys()) & set(ground_truth_aligned.keys())
    
    if not common_dates:
        raise HTTPException(500, "预测数据与ground truth无重叠日期")
    
    # 5. 计算误差指标
    errors = []
    abs_percentage_errors = []
    
    for date in sorted(common_dates):
        pred = backtest_aligned[date]
        actual = ground_truth_aligned[date]
        error = actual - pred
        errors.append(error)
        
        if actual != 0:
            abs_percentage_errors.append(abs(error / actual) * 100)

    mae = sum(abs(e) for e in errors) / len(errors) if errors else 0.0
    rmse = math.sqrt(sum(e**2 for e in errors) / len(errors)) if errors else 0.0
    mape = sum(abs_percentage_errors) / len(abs_percentage_errors) if abs_percentage_errors else 0
    
    calculation_time_ms = int((time.time() - start_time) * 1000)
    
    # 6. 构建响应
    # 返回所有预测点（即使超过ground_truth）
    # 但metrics只基于有ground_truth的日期计算
    return BacktestResponse(
        metrics=BacktestMetrics(
            mae=round(mae, 4) if common_dates else 0.0,
            rmse=round(rmse, 4) if common_dates else 0.0,
            mape=round(mape, 2) if common_dates else 0.0,
            calculation_time_ms=calculation_time_ms
        ),
        backtest_data=backtest_points,  # 返回所有预测点
        ground_truth=ground_truth_points,  # 返回所有ground_truth（可能比预测短）
        split_date=request.split_date,
        split_index=split_index
    )
