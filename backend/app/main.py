import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v2 import api_router as api_router_v2

app = FastAPI(title="小易猜猜 API", version="2.0.0")

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
