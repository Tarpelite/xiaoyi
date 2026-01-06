from fastapi import APIRouter
from app.api.v1.endpoints import chat, news, prediction, upload

api_router = APIRouter()

api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
# api_router.include_router(news.router, prefix="/news", tags=["news"])
# api_router.include_router(prediction.router, prefix="/prediction", tags=["prediction"])
# api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
