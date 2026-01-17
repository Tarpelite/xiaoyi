"""
Sessions API 端点
==================

提供会话列表管理接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.core.session import Session
from app.core.redis_client import get_redis


class SessionListItem(BaseModel):
    """会话列表项"""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    title: Optional[str] = None
    context: Optional[str] = None


class CreateSessionResponse(BaseModel):
    """创建会话响应"""
    session_id: str
    title: str
    created_at: str


class UpdateSessionRequest(BaseModel):
    """更新会话请求"""
    title: str


router = APIRouter()


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest = None):
    """
    创建新会话

    Args:
        request: 可选的创建请求
            - title: 会话标题（可选，默认"新对话"）
            - context: 上下文信息（可选）

    Returns:
        CreateSessionResponse: 包含 session_id, title, created_at
    """
    req = request or CreateSessionRequest()

    session = Session.create(context=req.context)

    # 如果提供了标题，更新标题
    if req.title:
        session.update_title(req.title)

    data = session.get()

    return CreateSessionResponse(
        session_id=session.session_id,
        title=data.title if data else "新对话",
        created_at=data.created_at if data else ""
    )


@router.get("/sessions", response_model=List[SessionListItem])
async def list_sessions():
    """
    获取所有会话列表
    
    Returns:
        List[SessionListItem]: 会话列表，按更新时间倒序
    """
    redis = get_redis()
    
    # 获取所有 session keys
    session_keys = redis.keys("session:*")
    
    sessions = []
    for key in session_keys:
        # Redis keys are already strings in redis-py, no need to decode
        if isinstance(key, bytes):
            key = key.decode('utf-8')
        session_id = key.split(':', 1)[1]
        session = Session(session_id)
        data = session.get()
        
        if data:
            sessions.append(SessionListItem(
                session_id=data.session_id,
                title=data.title,
                created_at=data.created_at,
                updated_at=data.updated_at,
                message_count=len(data.message_ids)
            ))
    
    # 按更新时间倒序排序
    sessions.sort(key=lambda x: x.updated_at, reverse=True)
    
    return sessions


@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, request: UpdateSessionRequest):
    """
    更新会话信息（如标题）
    
    Args:
        session_id: 会话 ID
        request: 更新请求
    
    Returns:
        {"success": true, "session_id": "...", "title": "..."}
    """
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    
    session = Session(session_id)
    session.update_title(request.title)
    
    return {
        "success": True,
        "session_id": session_id,
        "title": request.title
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    删除会话及其所有消息
    
    Args:
        session_id: 会话 ID
    
    Returns:
        {"success": true, "deleted_session_id": "..."}
    """
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    
    session = Session(session_id)
    session.delete()
    
    return {
        "success": True,
        "deleted_session_id": session_id
    }
