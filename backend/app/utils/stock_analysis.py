from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

def calculate_score(read_count: int, comment_count: int) -> float:
    """计算新闻的重要程度评分"""
    return read_count + comment_count * 5

def generate_price_points(close_prices: List[float], dates: List[str]) -> List[dict]:
    """生成价格点数据（包含模拟OHLC）"""
    if not close_prices or not dates:
        return []

    price_data = []
    for i, (close, date) in enumerate(zip(close_prices, dates)):
        # 模拟 OHLC 数据用于演示/回退（确保 close 是真实的）
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
    """分类价格转折点类型"""
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
    """合并相邻的异常区域"""
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
    基于波动率 > 2 个标准差检测异常区域
    (回退/旧版实现)
    """
    if len(prices) < 5:
        return []

    # 计算历史波动率（基于收益率）
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
        std_dev = 0.01  # 防止除以零

    anomaly_zones = []
    volatility_threshold = 2 * std_dev  # 2σ threshold

    for i in range(1, len(prices)):
        daily_return = abs((prices[i] - prices[i - 1]) / prices[i - 1])

        # 当波动率超过 2σ 时触发
        if daily_return > volatility_threshold:
            start_idx = max(0, i - 1)
            end_idx = min(len(prices) - 1, i + 1)

            anomaly_zones.append(
                {
                    "startDate": dates[start_idx],
                    "endDate": dates[end_idx],
                    "turnType": classify_turn_type(prices, i),
                    "changePercent": round(daily_return * 100, 2),
                    "volatility": round(daily_return / std_dev, 2),  # sigma 倍数
                }
            )

    merged_zones = merge_adjacent_zones(anomaly_zones, dates)

    return merged_zones
