"""
股票匹配服务
============

基于 AkShare 的股票名称/代码匹配

流程:
1. LLM 意图识别生成 stock_full_name (官方全称)
2. 调用 AkShare 获取 A 股列表
3. 精确匹配股票名称或代码
"""

from typing import Optional, Dict
from functools import lru_cache
import akshare as ak

from app.schemas.session_schema import StockInfo, StockMatchResult


class StockMatcher:
    """股票匹配服务 - 使用 AkShare 直接查询"""

    _instance: Optional["StockMatcher"] = None
    _stock_cache: Optional[Dict] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        print("[StockMatcher] 初始化完成，使用 AkShare 直接查询")

    def _load_stock_list(self) -> Dict:
        """
        从 AkShare 加载 A 股列表

        Returns:
            {
                "by_name": {"贵州茅台": {"code": "600519", "market": "SH"}, ...},
                "by_code": {"600519": {"name": "贵州茅台", "market": "SH"}, ...}
            }
        """
        if StockMatcher._stock_cache is not None:
            return StockMatcher._stock_cache

        try:
            print("[StockMatcher] 从 AkShare 加载股票列表...")
            df = ak.stock_info_a_code_name()

            by_name = {}
            by_code = {}

            for _, row in df.iterrows():
                code = row["code"]
                name = row["name"]

                # 判断市场
                if code.startswith("6"):
                    market = "SH"
                elif code.startswith(("0", "3")):
                    market = "SZ"
                else:
                    market = "SZ"

                by_name[name] = {"code": code, "market": market}
                by_code[code] = {"name": name, "market": market}

            StockMatcher._stock_cache = {
                "by_name": by_name,
                "by_code": by_code
            }

            print(f"[StockMatcher] 加载了 {len(by_name)} 只股票")
            return StockMatcher._stock_cache

        except Exception as e:
            print(f"[StockMatcher] 加载股票列表失败: {e}")
            return {"by_name": {}, "by_code": {}}

    def ensure_collection_exists(self) -> bool:
        """检查是否能加载股票列表"""
        try:
            cache = self._load_stock_list()
            return len(cache.get("by_name", {})) > 0
        except Exception:
            return False

    def get_stock_count(self) -> int:
        """获取股票数量"""
        cache = self._load_stock_list()
        return len(cache.get("by_name", {}))

    def match(self, stock_full_name: str) -> StockMatchResult:
        """
        匹配股票

        Args:
            stock_full_name: LLM 生成的股票官方全称 (如 "贵州茅台") 或股票代码

        Returns:
            StockMatchResult
        """
        if not stock_full_name:
            return StockMatchResult(
                success=False,
                error_message="未提供股票名称"
            )

        query = stock_full_name.strip()
        cache = self._load_stock_list()

        # 1. 先尝试按名称精确匹配
        if query in cache["by_name"]:
            info = cache["by_name"][query]
            return StockMatchResult(
                success=True,
                stock_info=StockInfo(
                    stock_code=info["code"],
                    stock_name=query,
                    market=info["market"]
                ),
                confidence=1.0
            )

        # 2. 尝试按代码精确匹配
        if query in cache["by_code"]:
            info = cache["by_code"][query]
            return StockMatchResult(
                success=True,
                stock_info=StockInfo(
                    stock_code=query,
                    stock_name=info["name"],
                    market=info["market"]
                ),
                confidence=1.0
            )

        # 3. 尝试模糊匹配 (名称包含)
        matches = []
        for name, info in cache["by_name"].items():
            if query in name or name in query:
                matches.append((name, info))

        if len(matches) == 1:
            # 唯一匹配
            name, info = matches[0]
            return StockMatchResult(
                success=True,
                stock_info=StockInfo(
                    stock_code=info["code"],
                    stock_name=name,
                    market=info["market"]
                ),
                confidence=0.9
            )
        elif len(matches) > 1:
            # 多个匹配，返回建议
            suggestions = [f"{name}({info['code']})" for name, info in matches[:5]]
            return StockMatchResult(
                success=False,
                suggestions=suggestions,
                error_message=f"找到多个匹配，你可能说的是: {', '.join(suggestions)}?"
            )

        # 4. 无匹配
        return StockMatchResult(
            success=False,
            error_message=f"未找到股票「{query}」，请检查股票名称是否正确。目前仅支持 A 股。"
        )

    def refresh_cache(self):
        """刷新股票缓存"""
        StockMatcher._stock_cache = None
        self._load_stock_list()


# 全局单例
_stock_matcher: Optional[StockMatcher] = None


def get_stock_matcher() -> StockMatcher:
    """获取股票匹配服务单例"""
    global _stock_matcher
    if _stock_matcher is None:
        _stock_matcher = StockMatcher()
    return _stock_matcher
