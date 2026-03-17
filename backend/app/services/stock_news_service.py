from typing import List, Dict, Optional, Any, Tuple
import json
import pandas as pd
from datetime import datetime, timedelta

from app.core.config import settings
from app.data.stock_db import get_mongo_client, ensure_mongodb_indexes, NewsItem
from app.services.stock_signal_service import StockSignalService

from app.utils.cache import make_redis_key, cache_get, cache_set
from app.utils.stock_analysis import (
    calculate_score,
    generate_price_points,
    detect_turning_points
)

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
            # 生成价格数据点
            price_data = generate_price_points(close_prices, dates) if close_prices else []

            # 使用新的 SignificantPointService (now StockSignalService) 算法
            # Note: Will be updated to use StockSignalService in next step but for now keeping compatible or I should update it now?
            # Since I haven't created StockSignalService yet, I will use try-except or just keep the old one if it still exists?
            # Actually I planned to remove SignificantPointService. So I should create StockSignalService first or update this to use it after creating it.
            # But I'm writing this file now. I will try to use the new service name assuming I will create it momentarily.

            try:
                # 构建 DataFrame
                df = pd.DataFrame({
                    "date": dates,
                    "close": close_prices,
                    "volume": volumes if volumes else [1] * len(close_prices),
                })

                # 计算每日新闻数量
                news_counts = {
                    date: len(news_list) for date, news_list in news_by_date.items()
                }

                # 计算显著点 & 异常区域
                # Use new method from consolidated service
                # Assuming interface: generate_zones(df, news_counts) similar to dynamic_clustering
                # But significant_points also returned individual points.
                # I will design StockSignalService to have methods covering both needs.
                anomaly_zones = self.signal_service.generate_zones(df, news_counts)

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

                significant_points = self.signal_service.calculate_points(df, news_counts, top_k=8)
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
                except Exception:
                    pass

                # 如果没有新闻标题，使用算法生成的 summary
                if not zone_titles and "summary" not in zone:
                    zone["summary"] = "价格波动区间"
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
            # 使用配置中的数据库和collection
            db = client[settings.MONGODB_DATABASE]
            collection = db[settings.MONGODB_COLLECTION]
            print(
            f"[NewsAPI] Connected to MongoDB: {settings.MONGODB_DATABASE}.{settings.MONGODB_COLLECTION}"
            )

            # 检查collection是否存在数据
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
            cursor = collection.find(
                {"stock_code": ticker, "publish_time": {"$regex": regex_pattern}}
            )

            news_list = []
            for news in cursor:
                # 安全处理可能为None的数值字段
                read_cnt = news.get("read_count", 0) or 0
                comment_cnt = news.get("comment_count", 0) or 0

                # 确保是数字类型
                if read_cnt is None:
                    read_cnt = 0
                if comment_cnt is None:
                    comment_cnt = 0


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
            print(f"[Redis HIT] {cache_key}")
            return cached

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


