"""
API v2 路由
===========

统一异步分析接口
"""

from fastapi import APIRouter

from app.api.v2.endpoints import (
    unified_analysis,
    sessions,
    streaming_analysis,
    sse_subscribe,
    analysis_trigger
)

api_router = APIRouter()

# 注册 v2 端点
api_router.include_router(
    unified_analysis.router,
    prefix="/analysis",
    tags=["v2-analysis"]
)

api_router.include_router(
    sessions.router,
    prefix="",
    tags=["v2-sessions"]
)

# 注册 SSE 流式端点（旧架构，保留兼容）
api_router.include_router(
    streaming_analysis.router,
    prefix="",
    tags=["v2-streaming"]
)

# 注册新的Pub/Sub架构端点
api_router.include_router(
    analysis_trigger.router,
    prefix="",
    tags=["v2-pubsub"]
)

api_router.include_router(
    sse_subscribe.router,
    prefix="",
    tags=["v2-pubsub"]
)
