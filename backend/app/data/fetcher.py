"""
数据获取与预处理模块
====================

负责从 AKShare 等数据源获取金融数据并进行标准化预处理
"""

from typing import Dict, Any
import pandas as pd


class DataFetchError(Exception):
    """数据获取错误 - 用于分类和友好处理"""
    
    def __init__(self, error_type: str, original_error: str, context: Dict[str, Any]):
        """
        Args:
            error_type: 错误类型 - "invalid_code", "network", "permission", "unknown"
            original_error: 原始错误信息
            context: 上下文信息 {symbol, api_function, ...}
        """
        self.error_type = error_type
        self.original_error = original_error
        self.context = context
        super().__init__(f"{error_type}: {original_error}")


class DataFetcher:
    """AKShare 数据获取器"""
    
    @staticmethod
    def _fetch_real_data(config: Dict[str, Any]) -> pd.DataFrame:
        """
        实际获取数据（内部方法）
        
        Args:
            config: 数据配置字典
            
        Returns:
            原始数据 DataFrame
        """
        import akshare as ak
        
        api_map = {
            "stock_zh_a_hist": ak.stock_zh_a_hist,
            "stock_zh_index_daily_em": ak.stock_zh_index_daily_em,
            "fund_etf_hist_em": ak.fund_etf_hist_em,
            "stock_news_em": ak.stock_news_em,
        }
        
        func_name = config["api_function"]
        params = config["params"]
        
        if func_name not in api_map:
            raise ValueError(f"不支持的 API: {func_name}")
        
        df = api_map[func_name](**params)
        print(f"✅ 获取数据: {len(df)} 条")
        return df
    
    @staticmethod
    def fetch(config: Dict[str, Any]) -> pd.DataFrame:
        """
        根据配置从 AKShare 获取原始数据（带错误分类）
        
        Args:
            config: 数据配置字典，包含 api_function 和 params
            
        Returns:
            原始数据 DataFrame
            
        Raises:
            DataFetchError: 分类后的数据获取错误
        """
        try:
            df = DataFetcher._fetch_real_data(config)
            
            # 检查数据是否为空
            if df is None or len(df) == 0:
                symbol = config.get("params", {}).get("symbol", "unknown")
                raise DataFetchError(
                    error_type="invalid_code",
                    original_error=f"未能获取到 {symbol} 的数据，可能该代码不存在或已退市",
                    context={
                        "symbol": symbol,
                        "api_function": config.get("api_function", "unknown"),
                        "params": config.get("params", {})
                    }
                )
            
            return df
            
        except DataFetchError:
            # 直接重新抛出 DataFetchError
            raise
            
        except Exception as e:
            # 其他错误进行分类
            error_msg = str(e).lower()
            symbol = config.get("params", {}).get("symbol", "unknown")
            api_function = config.get("api_function", "unknown")
            
            # 分析错误类型
            if any(keyword in error_msg for keyword in ["not found", "不存在", "无", "代码错误", "invalid"]):
                error_type = "invalid_code"
            elif any(keyword in error_msg for keyword in ["timeout", "network", "连接", "timed out"]):
                error_type = "network"
            elif any(keyword in error_msg for keyword in ["permission", "403", "401", "权限", "forbidden"]):
                error_type = "permission"
            else:
                error_type = "unknown"
            
            # 抛出分类后的错误
            raise DataFetchError(
                error_type=error_type,
                original_error=str(e)[:500],  # 限制长度
                context={
                    "symbol": symbol,
                    "api_function": api_function,
                    "params": config.get("params", {})
                }
            )
    
    @staticmethod
    def prepare(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        """
        将原始数据转换为标准时序格式 (ds, y)
        
        Args:
            df: 原始数据 DataFrame
            config: 数据配置，包含 target_column
            
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
        target = config.get("target_column", "收盘")
        value_col = None
        for col in [target, "close", "Close", "收盘"]:
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

    @staticmethod
    def fetch_news(symbol: str, limit: int = 50) -> pd.DataFrame:
        """
        获取个股新闻数据

        Args:
            symbol: 股票代码，如 "600519"
            limit: 返回新闻条数限制

        Returns:
            新闻 DataFrame，包含标题、内容、时间等
        """
        import akshare as ak

        try:
            df = ak.stock_news_em(symbol=symbol)
            result = df.head(limit) if len(df) > limit else df
            print(f"✅ 获取新闻: {len(result)} 条")
            return result
        except Exception as e:
            print(f"⚠️ 获取新闻失败: {e}")
            return pd.DataFrame()
