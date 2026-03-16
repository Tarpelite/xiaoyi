from typing import List, Dict, Optional, Any, Tuple
import json
import pandas as pd
from datetime import datetime, timedelta
from app.core.redis_client import get_redis
from app.core.config import settings
from app.data.stock_db import get_mongo_client, ensure_mongodb_indexes, NewsItem
from app.services.stock_signal_service import StockSignalService

REDIS_KEY_PREFIX = settings.REDIS_KEY_PREFIX

# Redis Helpers
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

# Calculation Helpers
def calculate_score(read_count: int, comment_count: int) -> float:
    return read_count + comment_count * 5

def generate_price_points(close_prices: List[float], dates: List[str]) -> List[dict]:
    if not close_prices or not dates:
        return []

    price_data = []
    for i, (close, date) in enumerate(zip(close_prices, dates)):
        # Simulate OHLC data for demo/fallback (ensure close is real)
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

def detect_turning_points(
    prices: List[float], dates: List[str], threshold: float = 0.05
) -> List[dict]:
    """
    Detect anomaly zones based on volatility > 2 standard deviations
    (Fallback / Legacy implementation)
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

class StockNewsService:
    def __init__(self):
        self.signal_service = StockSignalService(window=20)

    def get_stock_events(
        self,
        code: str,
        start: Optional[str] = None,
        end: Optional[str] = None
    ) -> Dict[str, Any]:
        cache_key = make_redis_key("events", code, start=start or "", end=end or "")
        cached = cache_get(cache_key)
        if cached:
            print(f"[Redis HIT] {cache_key}")
            return cached

        print(f"[Redis MISS] {cache_key}")

        client = None
        try:
            client = get_mongo_client()
            db = client[settings.MONGODB_DATABASE]
            ensure_mongodb_indexes(db, code)
            collection = db[code]

            today = datetime.now()
            if not end:
                end_date = today
            else:
                end_date = datetime.strptime(end, "%Y-%m-%d")

            if not start:
                start_date = end_date - timedelta(days=90)
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
                return result

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

            price_data = generate_price_points(close_prices, dates) if close_prices else []

            try:
                df = pd.DataFrame({
                    "date": dates,
                    "close": close_prices,
                    "volume": volumes if volumes else [1] * len(close_prices),
                })
                
                news_counts = {
                    date: len(news_list) for date, news_list in news_by_date.items()
                }

                anomaly_zones = self.signal_service.generate_zones(df, news_counts)
                significant_points = self.signal_service.calculate_points(df, news_counts, top_k=8)
                sig_dates = set([sp["date"] for sp in significant_points])

                for point in price_data:
                    if point["date"] in sig_dates:
                        point["is_event_triggered"] = True

            except Exception as e:
                print(f"[StockSignalService] Error: {e}")
                anomaly_zones = detect_turning_points(close_prices, dates)

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
                except Exception:
                    pass

                if not zone_titles and "summary" not in zone:
                    zone["summary"] = "价格波动区间"
                elif not zone.get("summary"):
                    zone["summary"] = " | ".join(zone_titles[:5])

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
                        read_count=int(news.get("read_count", 0)) if news.get("read_count") else 0,
                        comment_count=int(news.get("comment_count", 0)) if news.get("comment_count") else 0,
                        institution=news.get("institution") or news.get("org_name") or None,
                        grade=news.get("grade") or news.get("rating") or None,
                        notice_type=news.get("notice_type") or news.get("type_name") or None,
                    ).model_dump()
                )

            result = {
                "price_data": price_data,
                "anomaly_zones": anomaly_zones,
                "significant_news": significant_news,
            }

            cache_set(cache_key, result, ttl=600)
            return result

        except Exception as e:
            print(f"Error fetching stock events: {e}")
            raise e
        finally:
            if client:
                client.close()

    def get_news(
        self,
        ticker: str,
        date: str,
        date_range: int = 1
    ) -> Dict[str, Any]:
        cache_key = make_redis_key("news", ticker, date=date, range=str(date_range))
        cached = cache_get(cache_key)
        if cached:
            return cached

        client = None
        try:
            client = get_mongo_client()
            db = client[settings.MONGODB_DATABASE]
            collection = db[settings.MONGODB_COLLECTION]

            target_date = datetime.strptime(date, "%Y-%m-%d")
            date_patterns = []
            for i in range(-date_range, date_range + 1):
                date_str = (target_date + timedelta(days=i)).strftime("%Y-%m-%d")
                date_patterns.append(date_str)

            regex_pattern = "^(" + "|".join(date_patterns) + ")"
            cursor = collection.find(
                {"stock_code": ticker, "publish_time": {"$regex": regex_pattern}}
            )

            news_list = []
            for news in cursor:
                read_cnt = news.get("read_count", 0) or 0
                comment_cnt = news.get("comment_count", 0) or 0
                score = calculate_score(read_cnt, comment_cnt)
                news_list.append({**news, "id": str(news.get("_id", "")), "score": score})

            news_list.sort(key=lambda x: x["score"], reverse=True)

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
                        read_count=int(news.get("read_count", 0)) if news.get("read_count") else 0,
                        comment_count=int(news.get("comment_count", 0)) if news.get("comment_count") else 0,
                        institution=news.get("institution") or news.get("org_name") or None,
                        grade=news.get("grade") or news.get("rating") or None,
                        notice_type=news.get("notice_type") or news.get("type_name") or None,
                    ).model_dump()
                )

            result = {
                "news": result_news,
                "total": len(result_news),
            }

            cache_set(cache_key, result, ttl=300)
            return result

        except Exception as e:
            print(f"Error fetching news: {e}")
            raise e
        finally:
            if client:
                client.close()

    def get_anomaly_zones(
        self,
        ticker: str,
        days: int = 30
    ) -> Dict[str, Any]:
        cache_key = make_redis_key("zones", ticker, days=str(days))
        cached = cache_get(cache_key)
        if cached:
            return cached

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
                # Cleanup internal fields
                zone.pop("changePercent", None)
                zone.pop("turnType", None)

            result = {"anomaly_zones": anomaly_zones}
            cache_set(cache_key, result, ttl=600)
            return result

        except Exception as e:
            print(f"Error fetching anomaly zones: {e}")
            raise e
        finally:
            if client:
                client.close()


