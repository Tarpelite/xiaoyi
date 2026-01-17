"""
数据获取与预处理模块
====================

负责从 AKShare 等数据源获取金融数据并进行标准化预处理

架构:
- _call_akshare(): 统一的底层 AKShare 接口调用
- fetch_stock_data(): 获取股票历史数据
- fetch_news(): 获取个股新闻
- prepare(): 数据预处理为标准时序格式
- format_datetime(): 统一时间格式化（北京时间）
"""

from typing import Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import pandas as pd


# 北京时区
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def format_datetime(dt_str: str) -> str:
    """
    统一时间格式化为北京时间，精确到小时

    支持的输入格式:
    - ISO 8601: "2025-01-16T14:30:00Z", "2025-01-16T14:30:00+08:00"
    - 中文格式: "2025年01月16日 14:30", "01月16日 14:30"
    - 常见格式: "2025-01-16 14:30:00", "2025/01/16 14:30"
    - AKShare 格式: "2025-01-16 14:30"

    Returns:
        格式化后的时间字符串，如 "01-16 14:00"
        解析失败时返回 "-"
    """
    if not dt_str or dt_str == "-":
        return "-"

    dt_str = str(dt_str).strip()

    # 处理空白字符串、"None"、"null" 等无效值
    if not dt_str or dt_str.lower() in ("none", "null", "undefined", ""):
        return "-"

    try:
        dt = None

        # 1. RFC 2822 格式 (Tavily 返回): "Sun, 04 Jan 2026 00:16:55 GMT"
        if "," in dt_str and "GMT" in dt_str:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(dt_str)
            except Exception:
                pass

        # 2. ISO 8601 格式
        if dt is None and "T" in dt_str:
            # 移除毫秒部分
            clean = re.sub(r"\.\d+", "", dt_str)
            try:
                if clean.endswith("Z"):
                    dt = datetime.fromisoformat(clean.replace("Z", "+00:00"))
                else:
                    dt = datetime.fromisoformat(clean)
            except ValueError:
                pass

        # 2. 中文格式 "2025年01月16日 14:30" 或 "01月16日 14:30"
        if dt is None:
            match = re.match(r"(\d{4})?年?(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})", dt_str)
            if match:
                year = int(match.group(1)) if match.group(1) else datetime.now().year
                month, day, hour, minute = map(int, match.groups()[1:])
                dt = datetime(year, month, day, hour, minute, tzinfo=BEIJING_TZ)

        # 3. 标准格式 "2025-01-16 14:30:00" 或 "2025-01-16 14:30"
        if dt is None:
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"]:
                try:
                    dt = datetime.strptime(dt_str, fmt)
                    dt = dt.replace(tzinfo=BEIJING_TZ)
                    break
                except ValueError:
                    continue

        # 4. 只有日期 "2025-01-16"
        if dt is None:
            for fmt in ["%Y-%m-%d", "%Y/%m/%d"]:
                try:
                    dt = datetime.strptime(dt_str, fmt)
                    dt = dt.replace(tzinfo=BEIJING_TZ)
                    break
                except ValueError:
                    continue

        if dt:
            # 转换到北京时间
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=BEIJING_TZ)
            else:
                dt = dt.astimezone(BEIJING_TZ)

            # 显示完整的年月日小时 "YYYY-MM-DD HH:00"
            if dt.hour > 0 or dt.minute > 0:
                return dt.strftime("%Y-%m-%d %H:00")
            else:
                # 只有日期，显示 "YYYY-MM-DD"
                return dt.strftime("%Y-%m-%d")

        # 无法解析时返回 "-"，不返回原字符串（避免显示奇怪的格式）
        return "-"

    except Exception:
        return "-"


def extract_domain(url: str) -> str:
    """
    从 URL 提取域名作为来源名称

    Args:
        url: 新闻链接

    Returns:
        域名，如 "eastmoney.com"、"sina.com.cn"
    """
    if not url:
        return ""

    match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    if match:
        return match.group(1)

    return ""


class DataFetchError(Exception):
    """数据获取错误 - 用于分类和友好处理"""

    def __init__(self, error_type: str, original_error: str, context: Dict[str, Any] = None):
        """
        Args:
            error_type: 错误类型 - "invalid_code", "network", "permission", "unknown"
            original_error: 原始错误信息
            context: 上下文信息 {api_name, symbol, ...}
        """
        self.error_type = error_type
        self.original_error = original_error
        self.context = context or {}
        super().__init__(f"{error_type}: {original_error}")


class DataFetcher:
    """AKShare 数据获取器"""

    # ========== 底层统一接口 ==========

    @staticmethod
    def _call_akshare(
        api_name: str,
        critical: bool = True,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        统一的 AKShare 接口调用

        Args:
            api_name: AKShare API 名称，如 "stock_zh_a_hist", "stock_news_em"
            critical: 是否为关键数据
                - True: 失败时抛出 DataFetchError
                - False: 失败时返回空 DataFrame（用于可选数据如新闻）
            context: 错误上下文信息，用于生成友好错误消息
            **kwargs: 传递给 AKShare API 的参数

        Returns:
            API 返回的 DataFrame

        Raises:
            DataFetchError: 当 critical=True 且获取失败时抛出
        """
        import akshare as ak

        ctx = {"api_name": api_name, **(context or {})}

        try:
            func = getattr(ak, api_name, None)
            if func is None:
                raise ValueError(f"AKShare 不存在接口: {api_name}")

            df = func(**kwargs)

            if df is None or len(df) == 0:
                if critical:
                    symbol = kwargs.get("symbol", "unknown")
                    raise DataFetchError(
                        error_type="invalid_code",
                        original_error=f"未能获取到 {symbol} 的数据",
                        context=ctx
                    )
                return pd.DataFrame()

            print(f"✅ [{api_name}] 获取数据: {len(df)} 条")
            return df

        except DataFetchError:
            raise
        except Exception as e:
            if critical:
                raise DataFetchError(
                    error_type=DataFetcher._classify_error(e),
                    original_error=str(e)[:500],
                    context=ctx
                )
            print(f"⚠️ [{api_name}] 获取失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def _classify_error(e: Exception) -> str:
        """
        基于异常类型和错误信息分类错误

        Returns:
            错误类型: "invalid_code", "network", "permission", "unknown"
        """
        error_msg = str(e).lower()

        # 优先使用异常类型判断
        if isinstance(e, (ConnectionError, TimeoutError)):
            return "network"

        # 回退到关键词匹配
        if any(kw in error_msg for kw in ["not found", "不存在", "无", "代码错误", "invalid"]):
            return "invalid_code"
        if any(kw in error_msg for kw in ["timeout", "network", "连接", "timed out"]):
            return "network"
        if any(kw in error_msg for kw in ["permission", "403", "401", "权限", "forbidden"]):
            return "permission"

        return "unknown"

    # ========== 上层业务接口 ==========

    @staticmethod
    def fetch_stock_data(
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> pd.DataFrame:
        """
        获取股票历史数据

        Args:
            symbol: 股票代码，如 "600519"
            start_date: 开始日期，如 "20240101"
            end_date: 结束日期，如 "20250101"
            adjust: 复权类型 ("qfq"前复权, "hfq"后复权, ""不复权)

        Returns:
            原始数据 DataFrame

        Raises:
            DataFetchError: 获取失败时抛出
        """
        return DataFetcher._call_akshare(
            "stock_zh_a_hist",
            critical=True,
            context={"symbol": symbol},
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )

    @staticmethod
    def fetch_news(symbol: str, limit: int = 50) -> pd.DataFrame:
        """
        获取个股新闻数据

        Args:
            symbol: 股票代码，如 "600519"
            limit: 返回新闻条数限制

        Returns:
            新闻 DataFrame，包含标题、内容、时间等
            获取失败时返回空 DataFrame（新闻是可选数据）
        """
        df = DataFetcher._call_akshare(
            "stock_news_em",
            critical=False,  # 新闻是可选数据，失败不阻断主流程
            context={"symbol": symbol},
            symbol=symbol
        )
        return df.head(limit) if len(df) > limit else df

    # ========== 数据预处理 ==========

    @staticmethod
    def prepare(df: pd.DataFrame, target_column: str = "收盘") -> pd.DataFrame:
        """
        将原始数据转换为标准时序格式 (ds, y)

        Args:
            df: 原始数据 DataFrame
            target_column: 目标值列名，默认为 "收盘"

        Returns:
            标准化的 DataFrame，包含 ds (日期) 和 y (目标值) 列

        Raises:
            ValueError: 无法识别日期列或目标列
        """
        # 检测日期列
        date_col = None
        for col in ["日期", "date", "Date"]:
            if col in df.columns:
                date_col = col
                break

        # 检测目标值列
        value_col = None
        for col in [target_column, "close", "Close", "收盘"]:
            if col in df.columns:
                value_col = col
                break

        if not date_col or not value_col:
            raise ValueError(f"无法识别列: {list(df.columns)}")

        # 标准化格式
        result = pd.DataFrame({
            "ds": pd.to_datetime(df[date_col]),
            "y": df[value_col].astype(float)
        }).sort_values("ds").drop_duplicates("ds").reset_index(drop=True)

        print(f"✅ 数据准备: {len(result)} 条, {result['ds'].min().date()} ~ {result['ds'].max().date()}")
        return result
