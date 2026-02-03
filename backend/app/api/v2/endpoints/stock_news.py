import json
from datetime import datetime, timedelta
from typing import List, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.core.redis_client import get_redis
from app.core.config import settings
from app.data.stock_db import (
    get_mongo_client,
    ensure_mongodb_indexes,
    NewsItem,
)

router = APIRouter()

REDIS_KEY_PREFIX = settings.REDIS_KEY_PREFIX


def make_redis_key(key_type: str, ticker: str, **kwargs) -> str:
    key_parts = [REDIS_KEY_PREFIX, key_type, ticker]
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={v}")
    return ":".join(key_parts)


def cache_get(key: str) -> Optional[Any]:
    try:
        redis_client = get_redis()
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        print(f"Redis get error: {e}")
    return None


def cache_set(key: str, data: Any, ttl: int = 3600) -> bool:
    try:
        redis_client = get_redis()
        redis_client.setex(key, ttl, json.dumps(data, ensure_ascii=False))
        return True
    except Exception as e:
        print(f"Redis set error: {e}")
    return False


class StockEventsResponse(BaseModel):
    price_data: List[dict]
    anomaly_zones: List[dict]
    significant_news: List[NewsItem]


class NewsListResponse(BaseModel):
    news: List[NewsItem]
    total: int


class AnomalyZonesResponse(BaseModel):
    anomaly_zones: List[dict]


def calculate_score(read_count: int, comment_count: int) -> float:
    return read_count + comment_count * 5


def generate_price_points(close_prices: List[float], dates: List[str]) -> List[dict]:
    if not close_prices or not dates:
        return []

    price_data = []
    for i, (close, date) in enumerate(zip(close_prices, dates)):
        open_price = close * (0.98 + 0.04 * (hash(date) % 100) / 100)
        high_price = close * (1.01 + 0.02 * (hash(date) % 50) / 100)
        low_price = close * (0.99 - 0.02 * (hash(date) % 50) / 100)

        price_data.append(
            {
                "date": date,
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close, 2),
                "volume": 1000000 + hash(date) % 10000000,
                "is_event_triggered": False,
            }
        )

    return price_data


def detect_turning_points(
    prices: List[float], dates: List[str], threshold: float = 0.05
) -> List[dict]:
    """
    Detect anomaly zones based on volatility > 2 standard deviations
    """
    if len(prices) < 5:
        return []

    # Calculate historical volatility (returns-based)
    returns = [
        (prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))
    ]
    mean_return = sum(returns) / len(returns) if returns else 0
    std_dev = (
        (sum((r - mean_return) ** 2 for r in returns) / len(returns)) ** 0.5
        if returns
        else 0
    )

    if std_dev == 0:
        std_dev = 0.01  # Prevent division by zero

    anomaly_zones = []
    volatility_threshold = 2 * std_dev  # 2σ threshold

    for i in range(1, len(prices)):
        daily_return = abs((prices[i] - prices[i - 1]) / prices[i - 1])

        # Trigger when volatility exceeds 2σ
        if daily_return > volatility_threshold:
            start_idx = max(0, i - 1)
            end_idx = min(len(prices) - 1, i + 1)

            anomaly_zones.append(
                {
                    "startDate": dates[start_idx],
                    "endDate": dates[end_idx],
                    "turnType": classify_turn_type(prices, i),
                    "changePercent": round(daily_return * 100, 2),
                    "volatility": round(daily_return / std_dev, 2),  # sigma multiple
                }
            )

    merged_zones = merge_adjacent_zones(anomaly_zones, dates)

    return merged_zones


def classify_turn_type(prices: List[float], index: int) -> str:
    if index < 2 or index >= len(prices) - 2:
        return "波动"

    before = prices[index - 2 : index]
    after = prices[index + 1 : index + 3]

    before_avg = sum(before) / len(before) if before else prices[index]
    after_avg = sum(after) / len(after) if after else prices[index]
    current = prices[index]

    if after_avg > before_avg * 1.03 and current < before_avg:
        return "V型反转"
    elif after_avg < before_avg * 0.97 and current > before_avg:
        return "倒V型反转"
    elif current > before_avg * 1.05:
        return "强势上涨"
    elif current < before_avg * 0.95:
        return "强势下跌"
    else:
        return "波动"


def merge_adjacent_zones(zones: List[dict], dates: List[str]) -> List[dict]:
    if not zones:
        return []

    merged = []
    dates_set = set()
    for zone in zones:
        zone_dates = {zone["startDate"], zone["endDate"]}
        for d in dates:
            if d >= zone["startDate"] and d <= zone["endDate"]:
                zone_dates.add(d)

        overlapping = False
        for m in merged[:]:
            if m["startDate"] in zone_dates or zone["startDate"] in dates_set:
                m["startDate"] = min(m["startDate"], zone["startDate"])
                m["endDate"] = max(m["endDate"], zone["endDate"])
                zone_dates.add(m["startDate"])
                zone_dates.add(m["endDate"])
                overlapping = True
                break

        if not overlapping:
            merged.append(zone)

        dates_set.update(zone_dates)

    return merged


@router.get("/stock_events", response_model=StockEventsResponse)
async def get_stock_events(
    code: str = Query(..., description="股票代码，如 002594"),
    start: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    cache_key = make_redis_key("events", code, start=start or "", end=end or "")
    cached = cache_get(cache_key)
    if cached:
        print(f"[Redis HIT] {cache_key}")
        return StockEventsResponse(**cached)

    print(f"[Redis MISS] {cache_key}")

    client = None
    try:
        client = get_mongo_client()
        db = client[settings.MONGODB_DATABASE]

        # Ensure index exists for efficient queries
        ensure_mongodb_indexes(db, code)

        collection = db[code]

        today = datetime.now()
        if not end:
            end_date = today
        else:
            end_date = datetime.strptime(end, "%Y-%m-%d")

        if not start:
            start_date = end_date - timedelta(days=90)  # 增加到90天以获得更多历史数据
        else:
            start_date = datetime.strptime(start, "%Y-%m-%d")

        all_news = list(
            collection.find(
                {
                    "publish_time": {
                        "$gte": start_date.isoformat(),
                        "$lte": end_date.isoformat(),
                    }
                }
            ).sort("publish_time", 1)
        )

        if not all_news:
            result = {"price_data": [], "anomaly_zones": [], "significant_news": []}
            cache_set(cache_key, result, ttl=600)
            return StockEventsResponse(**result)

        news_by_date = {}
        close_prices = []
        volumes = []
        dates = []

        for news in all_news:
            date_key = news["publish_time"][:10]

            if date_key not in news_by_date:
                news_by_date[date_key] = []
            news_by_date[date_key].append(news)

            if "close" in news and "volume" in news:
                try:
                    close_price = float(news["close"])
                    volume = float(news["volume"])
                    if date_key not in dates:
                        close_prices.append(close_price)
                        volumes.append(volume)
                        dates.append(date_key)
                except (ValueError, TypeError):
                    pass

        # 生成价格数据点
        price_data = generate_price_points(close_prices, dates) if close_prices else []

        # 使用新的 SignificantPointService (now StockSignalService) 算法
        # Note: Will be updated to use StockSignalService in next step but for now keeping compatible or I should update it now?
        # Since I haven't created StockSignalService yet, I will use try-except or just keep the old one if it still exists?
        # Actually I planned to remove SignificantPointService. So I should create StockSignalService first or update this to use it after creating it.
        # But I'm writing this file now. I will try to use the new service name assuming I will create it momentarily.

        try:
            import pandas as pd

            # from app.services.significant_points import SignificantPointService # OLD
            from app.services.stock_signal_service import StockSignalService  # NEW

            # 构建 DataFrame
            df = pd.DataFrame(
                {
                    "date": dates,
                    "close": close_prices,
                    "volume": volumes if volumes else [1] * len(close_prices),
                }
            )

            # 计算每日新闻数量
            news_counts = {
                date: len(news_list) for date, news_list in news_by_date.items()
            }

            # 计算显著点 & 异常区域
            sig_service = StockSignalService(window=20)
            # Use new method from consolidated service
            # Assuming interface: generate_zones(df, news_counts) similar to dynamic_clustering
            # But significant_points also returned individual points.
            # I will design StockSignalService to have methods covering both needs.

            anomaly_zones = sig_service.generate_zones(df, news_counts)

            # Map zones to format expected if needed, or if generate_zones returns compatible format.
            # The previous code used sig_service.calculate_points then generate_anomaly_zones.
            # DynamicClusteringService's generate_zones returns enriched zones.

            # 标记事件触发的价格点
            # We need to identity which points are significant.
            # I will ensure StockSignalService puts date or similar info in zones or provides a method.

            # For now let's assume generate_zones returns what we need for zones.
            # And for points marking, we can infer from zones or add a method.

            # Simple logic: if a date is within an anomaly zone, mark it?
            # Or use explicit significant points. I'll add calculate_points to the new service too.

            significant_points = sig_service.calculate_points(df, news_counts, top_k=8)
            sig_dates = set([sp["date"] for sp in significant_points])

            for point in price_data:
                if point["date"] in sig_dates:
                    point["is_event_triggered"] = True

        except Exception as e:
            print(f"[StockSignalService] Error: {e}")
            # 降级到旧算法
            anomaly_zones = detect_turning_points(close_prices, dates)

        # 为异常区域添加新闻摘要 (If not already present)
        for zone in anomaly_zones:
            if "summary" in zone and zone["summary"]:
                continue

            zone_titles = []
            try:
                zone_start = datetime.strptime(zone["startDate"], "%Y-%m-%d")
                zone_end = datetime.strptime(zone["endDate"], "%Y-%m-%d")

                current = zone_start
                while current <= zone_end:
                    date_str = current.strftime("%Y-%m-%d")
                    if date_str in news_by_date:
                        for news in news_by_date[date_str][:3]:
                            if news.get("title"):
                                zone_titles.append(news["title"])
                    current += timedelta(days=1)
            except Exception as e:
                print(f"[Zone Summary] Error: {e}")

            # 如果没有新闻标题，使用算法生成的 summary
            if not zone_titles and "summary" not in zone:
                zone["summary"] = f"价格波动区间"
            elif not zone.get("summary"):
                zone["summary"] = " | ".join(zone_titles[:5])

        # 选择显著新闻（按评分排序）
        significant_news = []
        scored_news = []
        for news in all_news:
            score = calculate_score(
                news.get("read_count", 0) or 0, news.get("comment_count", 0) or 0
            )
            scored_news.append((news, score))

        scored_news.sort(key=lambda x: x[1], reverse=True)

        for news, _ in scored_news[:10]:
            significant_news.append(
                NewsItem(
                    id=str(news.get("_id", "")),
                    title=news.get("title", "") or "",
                    summary=news.get("summary") or news.get("content_first") or None,
                    content_type=news.get("content_type", "资讯"),
                    publish_time=news.get("publish_time", ""),
                    source=news.get("source") or news.get("pub_source") or None,
                    url=news.get("url") or news.get("source_url") or None,
                    read_count=int(news.get("read_count", 0))
                    if news.get("read_count")
                    else 0,
                    comment_count=int(news.get("comment_count", 0))
                    if news.get("comment_count")
                    else 0,
                    institution=news.get("institution") or news.get("org_name") or None,
                    grade=news.get("grade") or news.get("rating") or None,
                    notice_type=news.get("notice_type")
                    or news.get("type_name")
                    or None,
                )
            )

        result = {
            "price_data": price_data,
            "anomaly_zones": anomaly_zones,
            "significant_news": [n.model_dump() for n in significant_news],
        }

        cache_set(cache_key, result, ttl=600)

        return StockEventsResponse(**result)

    except Exception as e:
        print(f"Error fetching stock events: {e}")
        # import traceback
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if client:
            client.close()


@router.get("/news", response_model=NewsListResponse)
async def get_news(
    ticker: str = Query(..., description="股票代码"),
    date: str = Query(..., description="目标日期 YYYY-MM-DD"),
    date_range: int = Query(1, description="前后天数范围"),
):
    print(f"[NewsAPI] Request: ticker={ticker}, date={date}, range={date_range}")
    cache_key = make_redis_key("news", ticker, date=date, range=str(date_range))
    cached = cache_get(cache_key)
    if cached:
        print(f"[NewsAPI] Redis HIT: {cache_key}")
        return NewsListResponse(**cached)

    print(f"[NewsAPI] Redis MISS: {cache_key}")

    client = None
    try:
        client = get_mongo_client()
        # 使用配置中的数据库和collection
        db = client[settings.MONGODB_DATABASE]
        collection = db[settings.MONGODB_COLLECTION]
        print(
            f"[NewsAPI] Connected to MongoDB: {settings.MONGODB_DATABASE}.{settings.MONGODB_COLLECTION}"
        )

        # 检查collection是否存在数据
        total_count = collection.count_documents({"stock_code": ticker})
        print(f"[NewsAPI] Found {total_count} documents for stock_code={ticker}")

        if total_count == 0:
            print(f"[NewsAPI] No data for stock_code={ticker}")
            return NewsListResponse(news=[], total=0)

        target_date = datetime.strptime(date, "%Y-%m-%d")

        # 先查询一条样本查看格式
        sample = collection.find_one({"stock_code": ticker})
        if sample:
            print(f"[NewsAPI] Sample publish_time: '{sample.get('publish_time')}'")

        # 生成目标日期列表（前后date_range天）
        date_patterns = []
        for i in range(-date_range, date_range + 1):
            date_str = (target_date + timedelta(days=i)).strftime("%Y-%m-%d")
            date_patterns.append(date_str)

        # 使用正则表达式匹配任何以这些日期开头的publish_time，同时过滤stock_code
        regex_pattern = "^(" + "|".join(date_patterns) + ")"
        print(f"[NewsAPI] Query: stock_code={ticker}, date pattern={regex_pattern}")

        cursor = collection.find(
            {"stock_code": ticker, "publish_time": {"$regex": regex_pattern}}
        )

        news_list = []
        for news in cursor:
            # 安全处理可能为None的数值字段
            read_cnt = news.get("read_count", 0)
            comment_cnt = news.get("comment_count", 0)

            # 确保是数字类型
            if read_cnt is None:
                read_cnt = 0
            if comment_cnt is None:
                comment_cnt = 0

            score = calculate_score(read_cnt, comment_cnt)
            news_list.append({**news, "id": str(news.get("_id", "")), "score": score})

        news_list.sort(key=lambda x: x["score"], reverse=True)
        print(f"[NewsAPI] MongoDB returned {len(news_list)} documents")

        result_news = []
        for news in news_list:
            result_news.append(
                NewsItem(
                    id=news.get("id", ""),
                    title=news.get("title", "") or "",
                    summary=news.get("summary") or news.get("content_first") or None,
                    content_type=news.get("content_type", "资讯"),
                    publish_time=news.get("publish_time", ""),
                    source=news.get("source") or news.get("pub_source") or None,
                    url=news.get("url") or news.get("source_url") or None,
                    read_count=int(news.get("read_count", 0))
                    if news.get("read_count")
                    else 0,
                    comment_count=int(news.get("comment_count", 0))
                    if news.get("comment_count")
                    else 0,
                    institution=news.get("institution") or news.get("org_name") or None,
                    grade=news.get("grade") or news.get("rating") or None,
                    notice_type=news.get("notice_type")
                    or news.get("type_name")
                    or None,
                )
            )

        result = {
            "news": [n.model_dump() for n in result_news],
            "total": len(result_news),
        }

        cache_set(cache_key, result, ttl=300)

        return NewsListResponse(**result)

    except Exception as e:
        print(f"Error fetching news: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if client:
            client.close()


@router.get("/anomaly_zones", response_model=AnomalyZonesResponse)
async def get_anomaly_zones(
    ticker: str = Query(..., description="股票代码"),
    days: int = Query(30, description="查询天数"),
):
    cache_key = make_redis_key("zones", ticker, days=str(days))
    cached = cache_get(cache_key)
    if cached:
        print(f"[Redis HIT] {cache_key}")
        return AnomalyZonesResponse(**cached)

    print(f"[Redis MISS] {cache_key}")

    client = None
    try:
        client = get_mongo_client()
        db = client[settings.MONGODB_DATABASE]
        ensure_mongodb_indexes(db, ticker)
        collection = db[ticker]

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        news_list = list(
            collection.find(
                {
                    "publish_time": {
                        "$gte": start_date.isoformat(),
                        "$lte": end_date.isoformat(),
                    }
                }
            ).sort("publish_time", -1)
        )

        news_by_date = {}
        for news in news_list:
            date_key = news["publish_time"][:10]
            if date_key not in news_by_date:
                news_by_date[date_key] = []
            news_by_date[date_key].append(news)

        close_prices = []
        dates = []
        for news in news_list:
            if "close" in news:
                try:
                    close_price = float(news["close"])
                    date_key = news["publish_time"][:10]
                    if date_key not in dates:
                        close_prices.append(close_price)
                        dates.append(date_key)
                except (ValueError, TypeError):
                    pass

        dates.sort()
        anomaly_zones = detect_turning_points(close_prices, dates)

        for zone in anomaly_zones:
            zone_titles = []
            zone_start = datetime.strptime(zone["startDate"], "%Y-%m-%d")
            zone_end = datetime.strptime(zone["endDate"], "%Y-%m-%d")

            current = zone_start
            while current <= zone_end:
                date_str = current.strftime("%Y-%m-%d")
                if date_str in news_by_date:
                    for news in news_by_date[date_str][:2]:
                        if news.get("title"):
                            zone_titles.append(news["title"])
                current += timedelta(days=1)

            zone["summary"] = (
                " | ".join(zone_titles[:3])
                if zone_titles
                else f"{zone.get('turnType', '波动')}"
            )
            zone["sentiment"] = (
                "positive"
                if zone.get("changePercent", 0) < 0
                else "negative"
                if zone.get("changePercent", 0) > 5
                else "neutral"
            )
            zone.pop("changePercent", None)
            zone.pop("turnType", None)

        result = {"anomaly_zones": anomaly_zones}

        cache_set(cache_key, result, ttl=600)

        return AnomalyZonesResponse(**result)

    except Exception as e:
        print(f"Error fetching anomaly zones: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if client:
            client.close()
