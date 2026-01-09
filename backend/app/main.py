import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v2 import api_router as api_router_v2


async def init_stock_collection_if_needed():
    """
    后台初始化股票集合（如果不存在）

    - 检查 Qdrant 集合是否存在
    - 不存在则从 AkShare 加载数据并索引
    - 初始化期间使用 Fallback 机制保证服务可用
    """
    try:
        from app.services.stock_matcher import get_stock_matcher

        matcher = get_stock_matcher()

        # 检查集合是否已存在且有数据
        count = matcher.get_stock_count()
        if count > 0:
            print(f"[Startup] 股票集合已存在，共 {count} 条记录，跳过初始化")
            return

        print("[Startup] 股票集合不存在，开始后台初始化...")

        # 从 AkShare 加载股票列表
        records = matcher.load_stocks_from_akshare()
        if not records:
            print("[Startup] 加载股票列表失败，将使用 Fallback 机制")
            return

        print(f"[Startup] 加载了 {len(records)} 只股票，开始索引...")

        # 索引到 Qdrant
        matcher.index_stocks(records, batch_size=100)

        final_count = matcher.get_stock_count()
        print(f"[Startup] 股票集合初始化完成，共 {final_count} 条记录")

    except Exception as e:
        print(f"[Startup] 股票集合初始化失败: {e}，将使用 Fallback 机制")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：后台初始化股票集合（不阻塞）
    asyncio.create_task(init_stock_collection_if_needed())
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

app.include_router(api_router_v2, prefix="/api/v2")

@app.get("/")
async def root():
    return {"message": "小易猜猜 API", "version": "2.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
