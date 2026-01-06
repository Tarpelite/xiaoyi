from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    message: str
    model: str = "prophet"  # 预测模型，可选 "prophet" 或 "xgboost"
