"""
API v2 路由
===========

统一异步分析接口
"""

from fastapi import APIRouter

from app.api.v2.endpoints import unified_analysis, sessions, stock_news, users

api_router = APIRouter()

# 注册 v2 端点
api_router.include_router(
    unified_analysis.router, prefix="/analysis", tags=["v2-analysis"]
)

api_router.include_router(sessions.router, prefix="", tags=["v2-sessions"])

api_router.include_router(stock_news.router, prefix="", tags=["v2-stock"])

api_router.include_router(users.router, prefix="", tags=["v2-users"])
