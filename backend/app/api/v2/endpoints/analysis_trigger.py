"""
New Analysis Trigger Endpoint
==============================

触发后台worker的新endpoint
"""

from fastapi import APIRouter, BackgroundTasks, Query, HTTPException
from typing import Optional
from app.core.session import Session, Message
from app.schemas.session_schema import CreateAnalysisRequest

router = APIRouter()


@router.get("/v2/analysis/start")
async def start_analysis(
    message: str = Query(..., description="用户问题"),
    session_id: Optional[str] = Query(default=None, description="会话ID"),
    model: str = Query(default="prophet", description="预测模型"),
    context: str = Query(default="", description="上下文"),
    force_intent: Optional[str] = Query(default=None, description="强制意图"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    触发分析任务（Pub/Sub新架构）
    
    功能:
    1. 创建session和message
    2. 启动后台worker（独立于HTTP连接）
    3. 立即返回message_id
    4. 客户端使用message_id订阅 /stream/subscribe/{message_id}
    
    返回:
        {
            "session_id": "xxx",
            "message_id": "yyy",
            "status": "processing"
        }
    """
    # 创建或获取session
    if session_id and Session.exists(session_id):
        current_session = Session(session_id)
        session_data = current_session.get()
        model_name = model or session_data.model_name
    else:
        current_session = Session.create(context, model)
        session_id = current_session.session_id
        model_name = model
    
    # 创建message
    current_message = current_session.create_message(message)
    message_id = current_message.message_id
    
    # 添加对话历史
    current_session.add_conversation_message("user", message)
    
    print(f"[Trigger] Starting worker for message: {message_id}")
    
    # 启动后台worker
    from app.workers.llm_worker import llm_generation_worker
    
    background_tasks.add_task(
        llm_generation_worker,
        session_id,
        message_id,
        message,
        model_name,
        force_intent
    )
    
    return {
        "session_id": session_id,
        "message_id": message_id,
        "status": "processing"
    }
