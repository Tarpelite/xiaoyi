"""
统一分析 API 端点 (v2)
======================

提供统一的异步分析接口，支持 forecast/rag/news/chat 四种意图

架构:
- Session: 一整个多轮对话 (复用同一 session_id)
- Message: 每轮 QA (每次查询创建新 message_id)

轮询间隔建议: 0.5s (500ms)
"""

import asyncio
import json
import os
import concurrent.futures
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.session import Session, Message
from app.core.unified_tasks import get_task_processor
from app.schemas.session_schema import (
    CreateAnalysisRequest,
    AnalysisStatusResponse,
    SessionStatus,
    BacktestRequest,
    BacktestResponse
)
from app.agents import SuggestionAgent, IntentAgent


class SuggestionsRequest(BaseModel):
    """快速追问建议请求模型"""
    session_id: Optional[str] = None


# 轮询间隔常量 (供前端参考)
RECOMMENDED_POLL_INTERVAL_MS = 500

router = APIRouter()


@router.post("/create", response_model=dict)
async def create_analysis_task(
    request: CreateAnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    创建分析任务（统一入口）

    支持四种意图：
    - forecast: 完整预测分析（7步）
    - rag: 研报检索（2步）
    - news: 新闻搜索（2步）
    - chat: 纯对话（1步）

    架构说明:
    - Session: 整个多轮对话复用同一 session_id
    - Message: 每次查询创建新 message_id，存储该轮分析结果

    Args:
        request: 请求体
            - message: 用户问题
            - session_id: 会话ID（可选，用于多轮对话）
            - model: 预测模型（prophet/xgboost/randomforest/dlinear）
            - context: 上下文
            - force_intent: 强制指定意图

    Returns:
        {
            "session_id": "uuid-xxx",
            "message_id": "uuid-yyy",
            "status": "created"
        }
    """
    try:
        api_key = settings.api_key
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 获取或创建 Session
    if request.session_id and Session.exists(request.session_id):
        # 复用已有 session
        session = Session(request.session_id)
    else:
        # 创建新 session
        session = Session.create(
            context=request.context,
            model_name=request.model
        )

    # 为本次查询创建新 Message
    message = session.create_message(request.message)

    # 添加用户消息到对话历史
    session.add_conversation_message("user", request.message)

    # 在后台启动任务 (传入 message_id)
    task_processor = get_task_processor(api_key)
    background_tasks.add_task(
        task_processor.execute,
        session.session_id,
        message.message_id,  # 新增: 传入 message_id
        request.message,
        request.model,
        request.force_intent
    )

    return {
        "session_id": session.session_id,
        "message_id": message.message_id,
        "status": "created"
    }


@router.get("/status/{session_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    session_id: str,
    message_id: Optional[str] = Query(default=None, description="消息ID，不传则返回当前消息")
):
    """
    查询分析任务状态

    前端轮询间隔建议: 500ms (0.5s)

    Args:
        session_id: 会话 ID
        message_id: 消息 ID（可选，不传则返回当前正在处理的消息）

    Returns:
        AnalysisStatusResponse: 包含消息数据
            - session_id: 会话 ID
            - message_id: 消息 ID
            - status: 状态 (pending/processing/completed/error)
            - steps: 当前步骤
            - total_steps: 总步骤数
            - data: 消息数据 (MessageData)
    """
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    session = Session(session_id)

    # 获取指定消息或当前消息
    if message_id:
        message = session.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="消息不存在")
    else:
        message = session.get_current_message()
        if not message:
            raise HTTPException(status_code=404, detail="无活动消息")

    data = message.get()
    if not data:
        raise HTTPException(status_code=404, detail="消息数据不存在")

    return AnalysisStatusResponse(
        session_id=session_id,
        message_id=message.message_id,
        status=data.status,
        steps=data.steps,
        total_steps=data.total_steps,
        data=data
    )


@router.get("/history/{session_id}")
async def get_session_history(session_id: str):
    """
    获取会话历史（用于页面刷新后恢复）

    Args:
        session_id: 会话 ID

    Returns:
        {
            "session_id": "uuid-xxx",
            "messages": [
                {
                    "message_id": "uuid-yyy",
                    "user_query": "用户问题",
                    "status": "completed",
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


@router.delete("/{session_id}")
async def delete_analysis_session(session_id: str):
    """
    删除分析会话

    Args:
        session_id: 会话 ID

    Returns:
        {"message": "会话已删除"}
    """
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    session = Session(session_id)
    session.delete()

    return {"message": "会话已删除"}


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
    try:
        api_key = settings.api_key
    except ValueError as e:
        return {"error": str(e), "suggestions": []}

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
    suggestion_agent = SuggestionAgent(api_key)
    suggestions = await asyncio.to_thread(
        suggestion_agent.generate_suggestions,
        conversation_history
    )

    return {"suggestions": suggestions}


@router.post("/stream")
async def stream_analysis(
    request: CreateAnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    流式分析接口 - 实时返回思考过程

    SSE 事件类型:
    - thinking: 思考内容片段 {"type": "thinking", "content": "..."}
    - session: 会话信息 {"type": "session", "session_id": "...", "message_id": "..."}
    - intent: 意图结果 {"type": "intent", "intent": "forecast|chat|...", "is_forecast": true|false}
    - done: 思考完成 {"type": "done"}

    完成后前端使用 polling 获取后续分析结果
    """
    try:
        api_key = settings.api_key
    except ValueError as e:
        async def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # 获取或创建 Session
    if request.session_id and Session.exists(request.session_id):
        session = Session(request.session_id)
    else:
        session = Session.create(
            context=request.context,
            model_name=request.model
        )

    # 创建 Message
    message = session.create_message(request.message)
    session.add_conversation_message("user", request.message)

    # 获取对话历史
    conversation_history = session.get_conversation_history()

    # 使用 asyncio.Queue 实现真正的流式传输
    thinking_queue: asyncio.Queue = asyncio.Queue()

    async def event_stream():
        """SSE 事件流生成器"""
        # 1. 发送 session 信息
        yield f"data: {json.dumps({'type': 'session', 'session_id': session.session_id, 'message_id': message.message_id})}\n\n"

        # 2. 获取事件循环并启动线程
        loop = asyncio.get_running_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        def run_intent_in_thread():
            """在线程中运行意图识别"""
            intent_agent = IntentAgent(api_key)

            def on_thinking_chunk(chunk: str):
                # 线程安全地将内容放入队列
                loop.call_soon_threadsafe(thinking_queue.put_nowait, ('thinking', chunk))

            intent, _ = intent_agent.recognize_intent_streaming(
                request.message,
                conversation_history,
                on_thinking_chunk
            )
            # 发送完成信号
            loop.call_soon_threadsafe(thinking_queue.put_nowait, ('intent_done', intent))

        # 提交到线程池
        future = loop.run_in_executor(executor, run_intent_in_thread)

        # 3. 从队列读取并流式输出
        intent = None
        while True:
            try:
                # 使用超时避免永久阻塞
                event_type, data = await asyncio.wait_for(thinking_queue.get(), timeout=60.0)

                if event_type == 'thinking':
                    yield f"data: {json.dumps({'type': 'thinking', 'content': data})}\n\n"
                elif event_type == 'intent_done':
                    intent = data
                    break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'error', 'message': '意图识别超时'})}\n\n"
                return

        # 等待线程完成
        await future
        executor.shutdown(wait=False)

        if not intent:
            yield f"data: {json.dumps({'type': 'error', 'message': '意图识别失败'})}\n\n"
            return

        # 4. 发送意图结果
        yield f"data: {json.dumps({'type': 'intent', 'intent': 'forecast' if intent.is_forecast else 'chat', 'is_forecast': intent.is_forecast, 'reason': intent.reason})}\n\n"

        # 5. 保存意图到 Message
        message.save_unified_intent(intent)

        # 6. 处理超出范围的情况
        if not intent.is_in_scope:
            message.save_conclusion(intent.out_of_scope_reply or "抱歉，我是金融时序分析助手，暂不支持此类问题。")
            message.update_step_detail(1, "completed", "超出服务范围")
            message.mark_completed()
            yield f"data: {json.dumps({'type': 'done', 'completed': True})}\n\n"
            return

        message.update_step_detail(1, "completed", f"意图: {'预测' if intent.is_forecast else '对话'}")

        # 7. 启动后台任务处理剩余步骤
        task_processor = get_task_processor(api_key)
        background_tasks.add_task(
            task_processor.execute_after_intent,
            session.session_id,
            message.message_id,
            request.message,
            intent
        )

        # 8. 发送完成信号
        yield f"data: {json.dumps({'type': 'done', 'completed': False})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
    return {"suggestions": suggestions}


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
    from app.schemas.session_schema import BacktestMetrics, TimeSeriesPoint
    import time
    import pandas as pd
    import math
    
    start_time = time.time()
    
    # 1. 验证会话和消息
    if not Session.exists(request.session_id):
        raise HTTPException(404, "会话不存在")
    
    message = Message(request.message_id, request.session_id)
    data = message.get()
    
    if not data:
        raise HTTPException(404, "消息不存在")
    
    if not data.is_forecast or not data.time_series_original:
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
    
    # 获取API key
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(500, "API key not configured")
    
    # 4. 重新预测（复用现有预测逻辑）
    try:
        # Use the api_key obtained from os.getenv, or fall back to settings.api_key if preferred
        # For now, keeping the user's provided api_key logic.
        pass 
    except ValueError as e:
        raise HTTPException(500, str(e))
    
    task_processor = get_task_processor(api_key)
    
    # 转换为DataFrame
    df = pd.DataFrame({
        "ds": pd.to_datetime([p.date for p in train_points]),
        "y": [p.value for p in train_points]
    })
    
    # 运行预测
    model_to_use = data.model_name if hasattr(data, 'model_name') and data.model_name else "prophet"
    forecast_result = await task_processor._run_forecast(
        df,
        model_to_use,
        horizon,
        {}  # Prophet参数
    )
    
    # 提取预测结果
    backtest_points = [
        TimeSeriesPoint(
            date=item["date"],
            value=item["value"],
            is_prediction=True
        )
        for item in forecast_result["forecast"]
    ]
    
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
    
    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = math.sqrt(sum(e**2 for e in errors) / len(errors))
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
