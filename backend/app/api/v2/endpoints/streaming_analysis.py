"""
Streaming Analysis API Endpoint (SSE) - V2
==========================================

提供基于Server-Sent Events (SSE)的流式分析接口，支持真正的token-by-token打字机效果

核心特性:
- 实时返回thinking过程 (token级别) - 使用Queue桥接同步callback和异步SSE
- 实时返回chat响应 (token级别)
- 支持断线重连恢复
- 完善的错误处理
- 心跳保活

架构:
1. SSE endpoint接收请求
2. 创建AsyncQueue用于事件通信
3. 在后台线程执行IntentAgent,callback推送chunk到Queue
4. SSE stream从Queue读取并实时发送
5. Redis持久化中间状态
"""

import asyncio
import traceback
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, BackgroundTasks, Query
from fastapi.responses import StreamingResponse

from app.core.session import Session, Message
from app.core.sse import SSEStreamGenerator, SSEStateManager
from app.schemas.session_schema import CreateAnalysisRequest
from app.schemas.sse_schema import (
    SessionCreatedEvent,
    ThinkingChunkEvent,
    ThinkingCompleteEvent,
    IntentDeterminedEvent,
    StepUpdateEvent,
    AnalysisCompleteEvent,
    ErrorEvent,
    ErrorCode,
)
from app.agents import IntentAgent
from app.core.config import settings
from app.core.unified_tasks import UnifiedTaskProcessorV3


router = APIRouter()


@router.get("/v2/stream/analysis")
async def stream_analysis_v2(
    message: str = Query(..., description="用户问题"),
    session_id: Optional[str] = Query(default=None, description="会话ID"),
    model: str = Query(default="prophet", description="预测模型"),
    context: str = Query(default="", description="上下文"),
    force_intent: Optional[str] = Query(default=None, description="强制意图"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    SSE流式分析接口 (V2) - 改为GET以支持EventSource
    
    实时返回thinking、intent、chat等内容，支持token级别的打字机效果
    
    SSE事件类型:
    - session_created: 会话创建
    - thinking_chunk: 思考内容片段 (实时)
    - thinking_complete: 思考完成
    - intent_determined: 意图确定
    - step_update: 步骤更新
    - error: 错误
    - heartbeat: 心跳
    
    Args:
        message: 用户问题
        session_id: 会话ID (可选)
        model: 预测模型
        context: 上下文
        force_intent: 强制意图
    
    Returns:
        StreamingResponse: SSE事件流
    """
    
    # 将query params转换为CreateAnalysisRequest
    request = CreateAnalysisRequest(
        message=message,
        session_id=session_id,
        model=model,
        context=context,
        force_intent=force_intent
    )
    
    # 从查询参数获取message_id（如果是续接请求）
    message_id = request.message_id if hasattr(request, 'message_id') else None
    
    # 确定session_id和model_name
    model_name: str
    
    if request.session_id and Session.exists(request.session_id):
        current_session = Session(request.session_id)
        session_data = current_session.get()
        session_id = request.session_id
        model_name = request.model or session_data.model_name
    else:
        # 创建新session
        current_session = Session.create(request.context, request.model)
        session_id = current_session.session_id
        model_name = request.model
    
    # ===== 幂等性检查 =====
    # 如果提供了message_id，说明是续接请求，直接使用现有消息
    if message_id:
        print(f"[SSE] Reconnecting to existing message: {message_id}")
        # 验证消息存在
        current_message = Message(message_id, session_id)
        message_data = current_message.get()
        if not message_data:
            raise HTTPException(status_code=404, detail="Message not found")
    else:
        # 新请求：检查session最后一条消息是否正在处理
        session_data = current_session.get()
        
        if session_data and session_data.message_ids:  # 修复：messages → message_ids
            last_msg_id = session_data.message_ids[-1]
            last_msg = Message(last_msg_id, session_id)
            last_msg_data = last_msg.get()
            
            # 如果最后一条消息是同样的query且正在处理，复用它
            if (last_msg_data and 
                last_msg_data.status == "processing" and 
                last_msg_data.user_query == request.message):
                print(f"[SSE] Reusing existing processing message: {last_msg_id}")
                message_id = last_msg_id
                current_message = last_msg
            else:
                # 创建新消息
                current_message = current_session.create_message(request.message)
                message_id = current_message.message_id
        else:
            # 新session或session无消息，创建新消息
            current_message = current_session.create_message(request.message)
            message_id = current_message.message_id
    
    print(f"[Session] Using session: {session_id}")
    print(f"[Message] Using message: {message_id}")
    
    # 添加用户消息到对话历史
    current_session.add_conversation_message("user", request.message)
    
    # 初始化SSE工具
    sse_generator = SSEStreamGenerator(heartbeat_interval=15)
    state_manager = SSEStateManager()
    
    # 事件队列 - 用于在同步callback和异步SSE之间传递事件
    event_queue: asyncio.Queue = asyncio.Queue()
    
    async def event_stream() -> AsyncGenerator[str, None]:
        """
        SSE事件流生成器
        
        流程:
        1. 发送session_created
        2. 启动意图识别后台任务 (推送thinking_chunk到queue)
        3. 从queue读取事件并发送
        4. 直到收到完成信号
        """
        try:
            # 1. 发送会话创建事件
            yield await sse_generator.send_event(
                SessionCreatedEvent(
                    session_id=session_id,
                    message_id=message_id,
                    data={"session_id": session_id, "message_id": message_id}
                )
            )
            
            # 2. 发送步骤开始事件
            yield await sse_generator.send_event(
                StepUpdateEvent.create(
                    session_id, message_id,
                    step=1, status="running", message="分析用户意图..."
                )
            )
            
            # ===== 历史回放：如果Redis中已有thinking内容，先发送 =====
            existing_thinking = state_manager.get_thinking_content(message_id)
            if existing_thinking:
                # 一次性发送已有的thinking内容
                yield await sse_generator.send_event(
                    ThinkingChunkEvent.create(
                        session_id, message_id,
                        chunk="",  # 不需要chunk，因为是历史回放
                        accumulated=existing_thinking
                    )
                )
                
                # 检查thinking是否已完成
                if state_manager.is_thinking_complete(message_id):
                    yield await sse_generator.send_event(
                        ThinkingCompleteEvent(
                            session_id=session_id,
                            message_id=message_id,
                            data={
                                "thinking_content": existing_thinking,
                                "total_length": len(existing_thinking)
                            }
                        )
                    )
                    
                    # 检查是否有intent
                    message_data = current_message.get()
                    if message_data and message_data.unified_intent:
                        yield await sse_generator.send_event(
                            IntentDeterminedEvent(
                                session_id=session_id,
                                message_id=message_id,
                                data=message_data.unified_intent.model_dump()
                            )
                        )
                    
                    # 历史已完成，发送完成事件
                    yield await sse_generator.send_event(
                        AnalysisCompleteEvent(
                            session_id=session_id,
                            message_id=message_id,
                            data={}
                        )
                    )
                    # 不return，让后续逻辑决定是否触发后台任务
            
            # ===== 检查任务状态 =====
            check_message_data = current_message.get()
            print(f"[SSE Debug] Status: {check_message_data.status if check_message_data else 'None'}")
            print(f"[SSE Debug] existing_thinking: {len(existing_thinking) if existing_thinking else 0} chars")
            print(f"[SSE Debug] is_thinking_complete: {state_manager.is_thinking_complete(message_id)}")
            
            if check_message_data and check_message_data.status == "completed":
                # 任务已完成，不再重复执行
                print(f"[SSE] Message {message_id} already completed")
                return
            
            # 如果thinking已完成但整体任务未完成，只触发后台任务
            if existing_thinking and state_manager.is_thinking_complete(message_id):
                print(f"[SSE] Thinking complete, triggering background analysis...")
                background_tasks.add_task(
                    execute_remaining_analysis,
                    session_id, message_id, request.message
                )
                return
            
            # ===== 实时流式处理 =====
            # 3. 创建事件队列
            event_queue: asyncio.Queue = asyncio.Queue()
            
            # 4. 启动意图识别任务
            intent_task = asyncio.create_task(
                run_intent_recognition_background(
                    session_id, message_id, request.message,
                    current_session, current_message, model_name, request.force_intent,
                    event_queue, sse_generator, state_manager
                )
            )
            
            # 3. 从队列读取并发送事件
            while True:
                try:
                    # 等待事件，超时30秒
                    event_data = await asyncio.wait_for(event_queue.get(), timeout=30)
                    
                    if event_data == "COMPLETE":
                        # 收到完成信号，退出
                        break
                    elif event_data == "ERROR":
                        # 收到错误信号
                        break
                    else:
                        # 发送SSE事件
                        yield event_data
                        
                except asyncio.TimeoutError:
                    # 队列超时，发送心跳
                    pass
            
            # 等待intent任务完成
            await intent_task
            
            # 4. 执行后续分析 (后台任务)
            background_tasks.add_task(
                execute_remaining_analysis,
                session_id, message_id, request.message
            )
            
        except asyncio.TimeoutError:
            # 超时错误
            yield await sse_generator.send_event(
                ErrorEvent.create(
                    session_id=session_id,
                    message_id=message_id,
                    error="分析超时，请稍后重试",
                    error_code=ErrorCode.TIMEOUT,
                    retry_able=True
                )
            )
            current_message.mark_error("Timeout")
            
        except Exception as e:
            # 其他错误
            print(f"❌ SSE Stream Error: {traceback.format_exc()}")
            yield await sse_generator.send_event(
                ErrorEvent.create(
                    session_id=session_id,
                    message_id=message_id,
                    error=f"分析失败: {str(e)}",
                    error_code=ErrorCode.INTERNAL_ERROR,
                    retry_able=True
                )
            )
            current_message.mark_error(str(e))
    
    # 返回SSE响应
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用nginx缓冲
        }
    )


async def run_intent_recognition_background(
    session_id: str,
    message_id: str,
    user_input: str,
    session: Session,
    message: Message,
    model_name: str,
    force_intent: str,
    event_queue: asyncio.Queue,
    sse_generator: SSEStreamGenerator,
    state_manager: SSEStateManager
):
    """
    在后台运行意图识别，通过Queue推送事件
    
    这个函数作为async task运行，内部调用同步的IntentAgent
    """
    try:
        # 获取对话历史
        conversation_history = session.get_conversation_history()
        
        # 发送步骤更新
        await event_queue.put(
            await sse_generator.send_event(
                StepUpdateEvent.create(
                    session_id, message_id, 1, "running", "分析用户意图..."
                )
            )
        )
        
        # 更新步骤
        message.update_step_detail(1, "running", "分析用户意图...")
        
        # 强制意图
        if force_intent:
            processor = UnifiedTaskProcessorV3(settings.api_key)
            intent = processor._create_forced_intent(force_intent, model_name)
            message.save_unified_intent(intent)
            
            await event_queue.put(
                await sse_generator.send_event(
                    IntentDeterminedEvent(
                        session_id=session_id,
                        message_id=message_id,
                        data=intent.model_dump()
                    )
                )
            )
            await event_queue.put("COMPLETE")
            return
        
        # 流式意图识别
        accumulated_thinking = ""
        
        # 获取当前事件循环（在async上下文中）
        loop = asyncio.get_running_loop()
        
        def on_thinking_chunk(chunk: str):
            """
            思考内容回调 - 在同步线程中调用
            
            这里我们不能直接await，所以使用call_soon_threadsafe
            """
            nonlocal accumulated_thinking
            accumulated_thinking += chunk
            
            # 存储到Redis
            print(f"[Debug] Saving thinking chunk: {len(chunk)} chars, total: {len(accumulated_thinking)}")
            state_manager.append_thinking_chunk(message_id, chunk)
            
            # 创建SSE事件并推送到队列 (使用线程安全方式)
            async def push_event():
                await event_queue.put(
                    await sse_generator.send_event(
                        ThinkingChunkEvent.create(
                            session_id, message_id, chunk, accumulated_thinking
                        )
                    )
                )
            
            # 在事件循环中调度（使用之前捕获的loop引用）
            asyncio.run_coroutine_threadsafe(push_event(), loop)
        
        # 执行流式识别 (在线程池中运行)
        intent_agent = IntentAgent(settings.api_key)
        
        intent, full_thinking = await asyncio.to_thread(
            intent_agent.recognize_intent_streaming,
            user_input,
            conversation_history,
            on_thinking_chunk
        )
        
        # 保存intent和thinking
        message.save_unified_intent(intent, full_thinking)
        state_manager.mark_thinking_complete(message_id)
        
        # 发送thinking完成事件
        await event_queue.put(
            await sse_generator.send_event(
                ThinkingCompleteEvent(
                    session_id=session_id,
                    message_id=message_id,
                    data={
                        "thinking_content": full_thinking,
                        "total_length": len(full_thinking)
                    }
                )
            )
        )
        
        # 发送intent确定事件
        await event_queue.put(
            await sse_generator.send_event(
                IntentDeterminedEvent(
                    session_id=session_id,
                    message_id=message_id,
                    data=intent.model_dump()
                )
            )
        )
        
        # 更新步骤
        message.update_step_detail(1, "completed", f"意图: {'预测' if intent.is_forecast else '对话'}")
        await event_queue.put(
            await sse_generator.send_event(
                StepUpdateEvent.create(
                    session_id, message_id, 1, "completed", 
                    f"意图: {'预测' if intent.is_forecast else '对话'}"
                )
            )
        )
        
        # 发送完成信号
        await event_queue.put("COMPLETE")

        # 🔥 关键修复：intent完成后立即触发后续分析（独立于SSE）
        if not intent.is_in_scope:
            print(f"[Background] Triggering remaining analysis for {message_id}")
            # 在新的后台任务中执行，不依赖SSE连接
            asyncio.create_task(
                execute_remaining_analysis(session_id, message_id, user_input)
            )
        
    except Exception as e:
        print(f"❌ Intent recognition error: {traceback.format_exc()}")
        await event_queue.put(
            await sse_generator.send_event(
                ErrorEvent.create(
                    session_id, message_id,
                    error=f"意图识别失败: {str(e)}",
                    error_code=ErrorCode.LLM_ERROR
                )
            )
        )
        await event_queue.put("ERROR")
        message.mark_error(str(e))


async def execute_remaining_analysis(
    session_id: str,
    message_id: str,
    user_input: str
):
    """
    执行剩余分析步骤 (后台任务)
    
    包括: 股票验证、数据获取、预测/聊天、报告生成
    """
    try:
        session = Session(session_id)
        message = Message(message_id, session_id)
        
        # 获取已识别的intent
        message_data = message.get()
        if not message_data or not message_data.unified_intent:
            return
        
        intent = message_data.unified_intent
        
        # 执行后续步骤
        processor = UnifiedTaskProcessorV3(settings.api_key)
        await processor.execute_after_intent(
            session_id, message_id, user_input, intent
        )
        
        print(f"✅ Analysis complete for message {message_id}")
        
    except Exception as e:
        print(f"❌ Background analysis error: {traceback.format_exc()}")
        message.mark_error(str(e))
