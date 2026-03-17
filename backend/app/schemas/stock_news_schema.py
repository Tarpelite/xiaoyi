from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from app.data.stock_db import NewsItem

class StockEventsResponse(BaseModel):
    price_data: List[dict]
    anomaly_zones: List[dict]
    significant_news: List[NewsItem]


class NewsListResponse(BaseModel):
    news: List[NewsItem]
    total: int


class AnomalyZonesResponse(BaseModel):
    anomaly_zones: List[dict]
