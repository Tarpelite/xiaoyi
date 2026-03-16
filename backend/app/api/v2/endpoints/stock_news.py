import json
from datetime import datetime, timedelta
from typing import List, Optional, Any
from fastapi import APIRouter, HTTPException, Query

from app.schemas.stock_news_schema import (
    StockEventsResponse,
    NewsListResponse,
    AnomalyZonesResponse
)
from app.services.stock_news_service import StockNewsService

router = APIRouter()
stock_service = StockNewsService()

@router.get("/stock_events", response_model=StockEventsResponse)
async def get_stock_events(
    code: str = Query(..., description="股票代码，如 002594"),
    start: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    try:
        data = stock_service.get_stock_events(code, start, end)
        return StockEventsResponse(**data)
    except Exception as e:
        print(f"Error fetching stock events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news", response_model=NewsListResponse)
async def get_news(
    ticker: str = Query(..., description="股票代码"),
    date: str = Query(..., description="目标日期 YYYY-MM-DD"),
    date_range: int = Query(1, description="前后天数范围"),
):
    try:
        data = stock_service.get_news(ticker, date, date_range)
        return NewsListResponse(**data)
    except Exception as e:
        print(f"Error fetching news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomaly_zones", response_model=AnomalyZonesResponse)
async def get_anomaly_zones(
    ticker: str = Query(..., description="股票代码"),
    days: int = Query(30, description="查询天数"),
):
    try:
        data = stock_service.get_anomaly_zones(ticker, days)
        return AnomalyZonesResponse(**data)
    except Exception as e:
        print(f"Error fetching anomaly zones: {e}")
        raise HTTPException(status_code=500, detail=str(e))
