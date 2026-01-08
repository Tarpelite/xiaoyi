"""
Chat API 新端点 - 异步任务版本
================================

创建分析任务和查询状态的API
"""

import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from app.core.config import settings

from app.schemas.session_schema import (
    CreateAnalysisRequest,
    AnalysisStatusResponse,
    SessionStatus
)
from app.core.session import Session
from app.core.tasks import get_task_processor
from app.core.session_manager import get_session_manager
from app.agents import IntentAgent

router = APIRouter()


@router.post("/create", response_model=dict)
async def create_analysis_task(
    request: CreateAnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    创建分析任务
    
    Request Body:
    {
        "message": "分析茅台未来一个月走势",
        "model": "prophet",
        "context": ""
    }
    
    Response:
    {
        "session_id": "uuid-xxxx",
        "status": "created",
        "intent": "analyze" 或 "answer"
    }
    """
    try:
        # 获取会话管理器（用于获取对话历史）
        session_manager = get_session_manager()
        
        # 从 context 中提取 session_id（如果有的话）
        # context 格式可能是 "session_id:xxx" 或直接是 session_id
        conversation_history = []
        existing_session_id = None
        
        if request.context:
            # 尝试从 context 中提取 session_id
            if request.context.startswith("session_id:"):
                existing_session_id = request.context.split(":")[1]
            elif len(request.context) > 20:  # UUID 通常很长
                existing_session_id = request.context
        
        # 如果有现有 session_id，获取对话历史
        if existing_session_id:
            try:
                conversation_history = session_manager.get_recent_history(existing_session_id, max_turns=5)
            except:
                pass  # 如果获取失败，使用空历史
        
        # 意图判断
        intent_agent = IntentAgent(settings.DEEPSEEK_API_KEY)
        intent_result = await asyncio.to_thread(
            intent_agent.judge_intent,
            request.message,
            conversation_history
        )
        intent = intent_result.get("intent", "analyze")
        
        # 如果意图是 "answer"，使用现有 session 或创建新 session
        if intent == "answer":
            # 对于问答，可以复用现有 session
            if existing_session_id and Session.exists(existing_session_id):
                session = Session(existing_session_id)
            else:
                session = Session.create(
                    context=request.context,
                    model_name=request.model
                )
            
            # 添加用户消息到会话历史
            if existing_session_id:
                session_manager.add_message(existing_session_id, "user", request.message)
            else:
                session_manager.add_message(session.session_id, "user", request.message)
            
            # 直接回答问题
            answer = await asyncio.to_thread(
                intent_agent.answer_question,
                request.message,
                conversation_history
            )
            
            # 添加助手回复到会话历史
            if existing_session_id:
                session_manager.add_message(existing_session_id, "assistant", answer)
            else:
                session_manager.add_message(session.session_id, "assistant", answer)
            
            # 保存回答到 session（清空旧的分析数据）
            session.save_conclusion(answer)
            session.mark_completed()
            
            return {
                "session_id": session.session_id,
                "status": "completed",
                "intent": "answer"
            }
        
        # 如果意图是 "analyze"，总是创建新的 session（避免显示旧数据）
        # 但保留对话历史用于后续的意图判断
        session = Session.create(
            context=request.context,
            model_name=request.model
        )
        
        # 添加用户消息到会话历史（使用新 session_id）
        session_manager.add_message(session.session_id, "user", request.message)
        
        task_processor = get_task_processor(settings.DEEPSEEK_API_KEY)
        background_tasks.add_task(
            task_processor.execute,
            session.session_id,
            request.message,
            request.model
        )
        
        return {
            "session_id": session.session_id,
            "status": "created",
            "intent": "analyze"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{session_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(session_id: str):
    """
    查询分析任务状态
    
    Response:
    {
        "session_id": "uuid",
        "status": "processing",
        "steps": 3,
        "data": {
            "session_id": "uuid",
            "context": "",
            "steps": 3,
            "status": "processing",
            ...
        }
    }
    """
    # 检查 session 是否存在
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 获取 session 数据
    session = Session(session_id)
    data = session.get()
    
    if not data:
        raise HTTPException(status_code=404, detail="Session data not found")
    
    return AnalysisStatusResponse(
        session_id=session_id,
        status=data.status,
        steps=data.steps,
        data=data
    )


@router.delete("/{session_id}")
async def delete_analysis_session(session_id: str):
    """
    删除分析会话
    
    Response:
    {
        "message": "Session deleted successfully"
    }
    """
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = Session(session_id)
    session.delete()
    
    return {"message": "Session deleted successfully"}
