import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v2 import api_router as api_router_v2
from app.services.stock_matcher import get_stock_matcher
from app.services.rag_client import get_rag_client


async def check_external_services():
    """
    检查外部服务连接状态

    - RAG 服务 (股票匹配 + 研报检索)
    """
    # 检查 RAG 服务 (Stock Matcher 也使用同一个 RAG 服务)
    try:
        rag_client = get_rag_client()
        health = await rag_client.health()
        if health.get("status") == "healthy":
            doc_count = health.get('total_documents', 0)
            print(f"[Startup] RAG 服务连接正常，文档数量: {doc_count}")

            # Stock Matcher 使用同一个 RAG 服务
            stock_matcher = get_stock_matcher()
            if stock_matcher.ensure_collection_exists():
                print(f"[Startup] Stock Matcher 使用 RAG 服务: {stock_matcher.rag_service_url}")
            else:
                print("[Startup] Stock Matcher RAG 服务检查失败")
        else:
            print(f"[Startup] RAG 服务状态: {health.get('status', 'unknown')}")
    except Exception as e:
        print(f"[Startup] RAG 服务连接失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：检查外部服务连接（不阻塞）
    asyncio.create_task(check_external_services())
    yield
    # 关闭时：清理资源（如需要）


app = FastAPI(title="小易猜猜 API", version="2.0.0", lifespan=lifespan)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(api_router_v2, prefix="/api")

@app.get("/")
async def root():
    return {"message": "小易猜猜 API", "version": "2.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
