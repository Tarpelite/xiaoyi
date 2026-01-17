"""
Background LLM Worker for Pub/Sub Architecture
===============================================

独立的LLM生成worker，不依赖SSE连接
"""

import asyncio
import traceback
from app.core.session import Session, Message
from app.core.sse.pubsub_manager import RedisPubSubManager, get_message_channel
from app.core.sse.state_manager import SSEStateManager
from app.agents import IntentAgent
from app.core.config import settings
from app.core.unified_tasks import UnifiedTaskProcessorV3


async def llm_generation_worker(
    session_id: str,
    message_id: str,
    user_input: str,
    model_name: str = "prophet",
    force_intent: str = None
):
    """
    独立运行的LLM生成worker
    
    功能:
    - 执行intent识别（流式）
    - 每个token发布到Redis Pub/Sub
    - 同时持久化到message buffer
    - 完成后执行后续分析任务
    - 不依赖SSE连接，即使客户端断开也继续运行
    
    Args:
        session_id: 会话ID
        message_id: 消息ID
        user_input: 用户输入
        model_name: 模型名称
        force_intent: 强制意图（测试用）
    """
    pubsub = RedisPubSubManager()
    state_manager = SSEStateManager()
    channel = get_message_channel(message_id)
    
    try:
        print(f"[Worker] Starting LLM generation for message: {message_id}")
        
        # 获取session和message对象
        session = Session(session_id)
        message = Message(message_id, session_id)
        
        # 强制意图处理
        if force_intent:
            processor = UnifiedTaskProcessorV3(settings.api_key)
            intent = processor._create_forced_intent(force_intent, model_name)
            message.save_unified_intent(intent)
            
            # 发布intent事件
            await pubsub.publish(channel, {
                "type": "intent_determined",
                "data": intent.model_dump()
            })
            
            # 更新buffer
            state_manager.update_buffer(message_id, {
                "intent": intent.model_dump()
            })
            
            print(f"[Worker] Forced intent applied: {force_intent}")
            return
        
        # ===== Intent识别（流式） =====
        conversation_history = session.get_conversation_history()
        accumulated_thinking = ""
        
        # 创建agent
        intent_agent = IntentAgent(settings.api_key)
        
        # 获取事件循环（在async上下文中）
        loop = asyncio.get_running_loop()
        
        # 定义thinking callback
        def on_thinking_chunk(chunk: str):
            """Thinking内容回调（同步环境）"""
            nonlocal accumulated_thinking
            accumulated_thinking += chunk
            
            # 持久化到Redis
            state_manager.append_thinking_chunk(message_id, chunk)
            
            # 发布到Pub/Sub（使用run_coroutine_threadsafe，不阻塞）
            asyncio.run_coroutine_threadsafe(
                pubsub.publish(channel, {
                    "type": "thinking_chunk",
                    "data": {
                        "chunk": chunk,
                        "accumulated": accumulated_thinking
                    }
                }),
                loop
            )
        
        # 执行流式识别
        print(f"[Worker] Starting intent recognition...")
        intent, full_thinking = await asyncio.to_thread(
            intent_agent.recognize_intent_streaming,
            user_input,
            conversation_history,
            on_thinking_chunk
        )
        
        # 保存intent和thinking
        message.save_unified_intent(intent, full_thinking)
        state_manager.mark_thinking_complete(message_id)
        
        # 更新buffer
        state_manager.update_buffer(message_id, {
            "thinking": full_thinking,
            "intent": intent.model_dump()
        })
        print(f"[Worker] Buffer updated with thinking ({len(full_thinking)} chars) and intent")
        
        # 发布thinking完成事件
        await pubsub.publish(channel, {
            "type": "thinking_complete",
            "data": {
                "thinking_content": full_thinking,
                "total_length": len(full_thinking)
            }
        })
        
        # 发布intent确定事件
        await pubsub.publish(channel, {
            "type": "intent_determined",
            "data": intent.model_dump()
        })
        
        print(f"[Worker] Intent recognition complete: is_in_scope={intent.is_in_scope}, is_forecast={intent.is_forecast}")
        
        # ===== 执行后续分析任务 =====
        if intent.is_in_scope and not intent.is_forecast:
            # Non-forecast in-scope: chat response
            print(f"[Worker] Chat intent detected, executing remaining analysis...")
            from app.api.v2.endpoints.streaming_analysis import execute_remaining_analysis
            await execute_remaining_analysis(session_id, message_id, user_input)
        elif intent.is_in_scope and intent.is_forecast:
            # Forecast: full analysis pipeline
            print(f"[Worker] Forecast intent detected, executing full analysis...")
            from app.api.v2.endpoints.streaming_analysis import execute_remaining_analysis
            await execute_remaining_analysis(session_id, message_id, user_input)
        
        # 发布完成事件
        await pubsub.publish(channel, {
            "type": "analysis_complete",
            "data": {}
        })
        
        print(f"[Worker] Analysis complete for message: {message_id}")
        
    except Exception as e:
        print(f"[Worker] Error in LLM generation: {traceback.format_exc()}")
        
        # 发布错误事件
        await pubsub.publish(channel, {
            "type": "error",
            "data": {
                "error": str(e),
                "error_code": "WORKER_ERROR"
            }
        })
        
        # 标记message为error
        try:
            message = Message(message_id, session_id)
            message.mark_error(str(e))
        except:
            pass
    
    finally:
        # 清理
        await pubsub.close()
