"""
SSE Subscriber Endpoint
=======================

纯订阅端点：历史回放 + 实时Pub/Sub转发
"""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.core.sse.pubsub_manager import RedisPubSubManager, get_message_channel
from app.core.sse.state_manager import SSEStateManager
from app.core.sse import SSEStreamGenerator
from app.core.session import Message

router = APIRouter()


@router.get("/v2/stream/subscribe/{message_id}")
async def subscribe_to_message(message_id: str, session_id: str):
    """
    订阅消息的SSE流
    
    功能:
    1. 从buffer回放已有内容（历史）
    2. 订阅Redis Pub/Sub接收实时更新
    3. 转发事件到SSE客户端
    4. 检测完成信号并优雅关闭
    
    Args:
        message_id: 消息ID
        session_id: 会话ID（用于验证）
        
    Returns:
        SSE流响应
    """
    # 验证消息存在
    message = Message(message_id, session_id)
    message_data = message.get()
    if not message_data:
        raise HTTPException(status_code=404, detail="Message not found")
    
    state_manager = SSEStateManager()
    pubsub = RedisPubSubManager()
    sse_generator = SSEStreamGenerator()
    channel = get_message_channel(message_id)
    
    async def event_generator():
        """SSE事件生成器"""
        try:
            print(f"[SSE Subscribe] Starting stream for message: {message_id}")
            
            # ===== A. 历史回放 =====
            buffer = state_manager.get_full_buffer(message_id)
            
            # 回放thinking
            if buffer.get("thinking"):
                event_data = json.dumps({
                    "chunk": "",
                    "accumulated": buffer["thinking"]
                })
                yield f"event: thinking_chunk\ndata: {event_data}\n\n"
                
                complete_data = json.dumps({
                    "thinking_content": buffer["thinking"],
                    "total_length": len(buffer["thinking"])
                })
                yield f"event: thinking_complete\ndata: {complete_data}\n\n"
            
            # 回放intent
            if buffer.get("intent"):
                intent_data = json.dumps(buffer["intent"])
                yield f"event: intent_determined\ndata: {intent_data}\n\n"
            
            # 回放steps
            if buffer.get("steps"):
                for step in buffer["steps"]:
                    step_data = json.dumps(step)
                    yield f"event: step_update\ndata: {step_data}\n\n"
            
            # 回放conclusion
            if buffer.get("conclusion"):
                conclusion_data = json.dumps({"conclusion": buffer["conclusion"]})
                yield f"event: analysis_complete\ndata: {conclusion_data}\n\n"
                # 如果已完成，直接退出
                if message_data.status == "completed":
                    print(f"[SSE Subscribe] Message already completed, ending stream")
                    return
            
            # ===== B. 实时订阅 =====
            print(f"[SSE Subscribe] Starting Pub/Sub subscription to channel: {channel}")
            
            async for redis_message in pubsub.subscribe(channel):
                event_type = redis_message.get("type")
                event_data = redis_message.get("data", {})
                
                print(f"[SSE Subscribe] Received event: {event_type}")
                
                # 转发事件到SSE (raw SSE format)
                event_json = json.dumps(event_data)
                yield f"event: {event_type}\ndata: {event_json}\n\n"
                
                # 检测完成信号
                if event_type in ["analysis_complete", "error"]:
                    print(f"[SSE Subscribe] Stream complete for message: {message_id}")
                    break
                    
        except Exception as e:
            print(f"[SSE Subscribe] Error: {e}")
            # 发送错误事件
            error_json = json.dumps({
                "error": str(e),
                "error_code": "SUBSCRIBE_ERROR"
            })
            yield f"event: error\ndata: {error_json}\n\n"
        
        finally:
            # 清理Pub/Sub连接
            await pubsub.close()
            print(f"[SSE Subscribe] Connection closed for message: {message_id}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
