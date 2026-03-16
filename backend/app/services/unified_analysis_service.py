import asyncio
import json
import math
import time
from typing import List, Dict, Optional, Any, AsyncGenerator

import pandas as pd
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.core.session import Session, Message
from app.core.streaming_task_processor import get_streaming_processor
from app.core.workflows import run_forecast
from app.core.redis_client import get_redis, get_async_redis
from app.agents import SuggestionAgent
from app.schemas.unified_analysis_schema import (
    CreateAnalysisRequest,
    BacktestRequest,
    BacktestMetrics,
    BacktestResponse,
    HistoryResponse,
    HistoryMessage,
    MessageStatus,
)


class UnifiedAnalysisService:
    """
    统一分析服务 (Unified Analysis Service)

    封装了会话管理、后台分析、流式传输、历史记录检索和回测的逻辑。
    """

    async def run_background_analysis(
        self, session_id: str, message_id: str, user_input: str, model_name: Optional[str]
    ):
        """后台运行分析任务（独立于 SSE 连接）"""
        streaming_processor = get_streaming_processor()
        await streaming_processor.execute_streaming(
            session_id, message_id, user_input, None, model_name
        )

    async def create_analysis(
        self, request: CreateAnalysisRequest, background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """
        创建新的分析会话/消息并调度后台处理
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
            self.run_background_analysis,
            session.session_id,
            message.message_id,
            request.message,
            request.model  # None 表示自动选择
        )

        return {
            "session_id": session.session_id,
            "message_id": message.message_id,
            "status": "created"
        }

    def get_history(self, session_id: str) -> HistoryResponse:
        """获取会话的完整历史记录"""
        if not Session.exists(session_id):
            raise HTTPException(status_code=404, detail="会话不存在")

        session = Session(session_id)
        all_messages = session.get_all_messages()

        messages = []
        for msg in all_messages:
            data = msg.get()
            if data:
                # 转换 MessageStatus 
                status = MessageStatus(data.status) if isinstance(data.status, str) else data.status
                
                messages.append(
                    HistoryMessage(
                        message_id=msg.message_id,
                        user_query=data.user_query,
                        status=status,
                        data=data.model_dump() if hasattr(data, "model_dump") else data
                    )
                )

        return HistoryResponse(session_id=session_id, messages=messages)

    async def get_suggestions(self, session_id: Optional[str]) -> List[str]:
        """根据历史记录生成追问建议"""
        if not session_id or not Session.exists(session_id):
            return [
                "帮我分析一下茅台，预测下个季度走势",
                "查看最近的市场趋势",
                "对比几只白酒股的表现",
                "生成一份投资分析报告"
            ]

        session = Session(session_id)
        conversation_history = session.get_conversation_history()

        suggestion_agent = SuggestionAgent()
        # 在线程池中运行同步 agent
        suggestions = await asyncio.to_thread(
            suggestion_agent.generate_suggestions,
            conversation_history
        )
        return suggestions

    async def stream_resume(
        self, session_id: str, message_id: str, last_event_id: str = "0-0"
    ):
        """
        恢复特定消息的事件流 - 使用异步 XREAD 从 Redis Stream 读取事件
        返回 JSON 状态（如果已完成）或 StreamingResponse（如果处于活动状态）
        """
        if not Session.exists(session_id):
            raise HTTPException(status_code=404, detail="会话不存在")

        message_obj = Message(message_id, session_id)
        data = message_obj.get()

        if not data:
            raise HTTPException(status_code=404, detail="消息不存在")

        # 检查是否已完成
        if data.stream_status not in ("streaming", None, ""):
            return {
                "status": data.stream_status,
                "message_status": data.status.value,
                "data": data.model_dump()
            }

        # 定义生成器
        stream_key = f"stream-events:{message_id}"

        async def event_stream():
            nonlocal last_event_id
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
                            block=2000 # 阻塞 2 秒
                        )
                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                        break

                    # 超时没有新数据
                    if not events:
                        # 检查任务是否已结束
                        check_data = message_obj.get()
                        if check_data and check_data.stream_status not in ("streaming", None, ""):
                            # 任务完成
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

                                # 检查载荷中的 stream 结束标记
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

    async def backtest_prediction(self, request: BacktestRequest) -> BacktestResponse:
        """
        交互式时间旅行回测端点
        基于历史分割点重新预测，计算预测误差指标(MAE/RMSE/MAPE)
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
        # 解析 split_date 字符串进行简单比较
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

        # 运行预测（从 MessageData 获取模型名称）
        model_to_use = data.model_name if data.model_name else "prophet"
        
        # 调用预测工作流
        forecast_result = await run_forecast(
            df,
            model_to_use,
            horizon,
            {}  # Prophet参数
        )
        
        backtest_points = forecast_result.points
        
        # 对齐日期（确保预测和ground truth长度一致）
        backtest_aligned = {p.date: p.value for p in backtest_points}
        ground_truth_aligned = {p.date: p.value for p in ground_truth_points}
        
        common_dates = set(backtest_aligned.keys()) & set(ground_truth_aligned.keys())
        
        if not common_dates:
             raise HTTPException(500, "预测数据与ground truth无重叠日期")

        # 5. 计算误差指标
        errors = []
        abs_percentage_errors = []
        
        for date in sorted(list(common_dates)):
            pred = backtest_aligned[date]
            actual = ground_truth_aligned[date]
            error = actual - pred
            errors.append(error)
            
            if actual != 0:
                abs_percentage_errors.append(abs(error / actual) * 100)

        mae = sum(abs(e) for e in errors) / len(errors) if errors else 0.0
        rmse = math.sqrt(sum(e**2 for e in errors) / len(errors)) if errors else 0.0
        mape = sum(abs_percentage_errors) / len(abs_percentage_errors) if abs_percentage_errors else 0.0
        
        calculation_time_ms = int((time.time() - start_time) * 1000)
        
        # 6. 构建响应
        return BacktestResponse(
            metrics=BacktestMetrics(
                mae=round(mae, 4),
                rmse=round(rmse, 4),
                mape=round(mape, 2),
                calculation_time_ms=calculation_time_ms
            ),
            backtest_data=backtest_points,
            ground_truth=ground_truth_points,
            split_date=request.split_date,
            split_index=split_index
        )
