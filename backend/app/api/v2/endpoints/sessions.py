"""
Sessions API 端点
==================

提供会话列表管理接口
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

from app.core.session import Session
from app.core.redis_client import get_redis
from app.core.auth import verify_token, User


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
async def create_session(
    request: Optional[CreateSessionRequest] = None, user: User = Depends(verify_token)
):
    """
    创建新会话

    Requires Authentication
    """
    req = request or CreateSessionRequest()

    session = Session.create(user_id=user.sub)

    # 如果提供了标题，更新标题
    if req.title:
        session.update_title(req.title)

    data = session.get()

    return CreateSessionResponse(
        session_id=session.session_id,
        title=data.title if data else "新对话",
        created_at=data.created_at if data else "",
    )


@router.get("/sessions", response_model=List[SessionListItem])
async def list_sessions(user: User = Depends(verify_token)):
    """
    获取所有会话列表

    Returns:
        List[SessionListItem]: 会话列表，按更新时间倒序
        Filtered by authenticated user
    """
    redis = get_redis()

    # 获取所有 session keys
    # Optimization: In production, use a set per user (user:{id}:sessions)
    # For now, we scan and filter (low scale assumption)
    session_keys = redis.keys("session:*")

    sessions = []
    for key in session_keys:
        # Redis keys are already strings in redis-py, no need to decode
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        session_id = key.split(":", 1)[1]
        session = Session(session_id)
        data = session.get()

        if data and data.user_id == user.sub:
            sessions.append(
                SessionListItem(
                    session_id=data.session_id,
                    title=data.title,
                    created_at=data.created_at,
                    updated_at=data.updated_at,
                    message_count=len(data.message_ids),
                )
            )

    # 按更新时间倒序排序
    sessions.sort(key=lambda x: x.updated_at, reverse=True)

    return sessions


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str, request: UpdateSessionRequest, user: User = Depends(verify_token)
):
    """
    更新会话信息（如标题）
    """
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    session = Session(session_id)
    data = session.get()

    if not data or data.user_id != user.sub:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    session.update_title(request.title)

    return {"success": True, "session_id": session_id, "title": request.title}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: User = Depends(verify_token)):
    """
    删除会话及其所有消息
    """
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    session = Session(session_id)
    data = session.get()

    if not data or data.user_id != user.sub:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    session.delete()

    return {"success": True, "deleted_session_id": session_id}
