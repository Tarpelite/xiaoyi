"""
股票匹配服务
============

基于外部 RAG 服务的股票名称/代码匹配

功能:
1. 使用 LLM 意图识别中的 stock_full_name 进行查询
2. 调用外部 RAG 服务进行语义匹配验证
3. 返回匹配结果 (股票代码、名称、市场)
"""

import os
import httpx
from typing import Optional

from app.schemas.session_schema import StockInfo, StockMatchResult


# RAG 服务地址
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://10.139.197.44:8000")

# 匹配阈值
HIGH_CONFIDENCE_THRESHOLD = 0.85  # 高置信度匹配
LOW_CONFIDENCE_THRESHOLD = 0.5   # 低置信度匹配


class StockMatcher:
    """股票匹配服务 - 使用外部 RAG 服务"""

    _instance: Optional["StockMatcher"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.rag_service_url = RAG_SERVICE_URL
        self._initialized = True
        print(f"[StockMatcher] 初始化完成, RAG 服务: {self.rag_service_url}")

    def ensure_collection_exists(self) -> bool:
        """检查 RAG 服务是否可用"""
        try:
            response = httpx.get(
                f"{self.rag_service_url}/api/v1/health",
                timeout=10.0
            )
            if response.status_code == 200:
                return True
            return False
        except Exception as e:
            print(f"[StockMatcher] RAG 服务不可用: {e}")
            return False

    def get_stock_count(self) -> int:
        """获取 RAG 服务中的文档数量"""
        try:
            response = httpx.get(
                f"{self.rag_service_url}/api/v1/health",
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("total_documents", 0)
            return 0
        except Exception:
            return 0

    def match(self, stock_full_name: str, top_k: int = 3) -> StockMatchResult:
        """
        匹配股票

        Args:
            stock_full_name: LLM 生成的股票官方全称 (如 "贵州茅台", "中国石油")
            top_k: 返回候选数量

        Returns:
            StockMatchResult
        """
        if not stock_full_name:
            return StockMatchResult(
                success=False,
                error_message="未提供股票名称"
            )

        try:
            # 调用 RAG 服务搜索
            response = httpx.post(
                f"{self.rag_service_url}/api/v1/search",
                json={
                    "query": stock_full_name,
                    "top_k": top_k
                },
                timeout=30.0
            )

            if response.status_code != 200:
                print(f"[StockMatcher] RAG 服务返回错误: {response.status_code}")
                return StockMatchResult(
                    success=False,
                    error_message=f"股票查询服务暂时不可用"
                )

            data = response.json()
            results = data.get("results", [])

            if not results:
                return StockMatchResult(
                    success=False,
                    error_message=f"未找到与「{stock_full_name}」相关的股票，目前仅支持 A 股"
                )

            # 解析结果
            top_result = results[0]
            score = top_result.get("score", 0.0)
            metadata = top_result.get("metadata", {})

            # 从 metadata 中提取股票信息
            stock_code = metadata.get("stock_code", "")
            stock_name = metadata.get("stock_name", "")
            market = metadata.get("market", "")

            # 如果 metadata 中没有结构化信息，尝试从内容解析
            if not stock_code or not stock_name:
                content = top_result.get("content", "")
                parsed = self._parse_stock_content(content)
                if parsed:
                    stock_code = parsed.get("stock_code", stock_code)
                    stock_name = parsed.get("stock_name", stock_name)
                    market = parsed.get("market", market)

            if not stock_code or not stock_name:
                return StockMatchResult(
                    success=False,
                    error_message=f"无法解析股票信息"
                )

            stock_info = StockInfo(
                stock_code=stock_code,
                stock_name=stock_name,
                market=market or self._infer_market(stock_code)
            )

            # 检查状态
            status = metadata.get("status", "listed")
            if status == "delisted":
                return StockMatchResult(
                    success=False,
                    stock_info=stock_info,
                    confidence=score,
                    error_message=f"该股票「{stock_name}」已退市"
                )

            # 高置信度匹配
            if score >= HIGH_CONFIDENCE_THRESHOLD:
                return StockMatchResult(
                    success=True,
                    stock_info=stock_info,
                    confidence=score
                )

            # 中等置信度 - 返回建议
            if score >= LOW_CONFIDENCE_THRESHOLD:
                suggestions = []
                for r in results[:3]:
                    m = r.get("metadata", {})
                    name = m.get("stock_name", "")
                    code = m.get("stock_code", "")
                    if name and code:
                        suggestions.append(f"{name}({code})")

                return StockMatchResult(
                    success=False,
                    stock_info=stock_info,
                    confidence=score,
                    suggestions=suggestions,
                    error_message=f"你可能说的是: {', '.join(suggestions)}?"
                )

            # 低置信度 - 无法匹配
            return StockMatchResult(
                success=False,
                confidence=score,
                error_message=f"未找到与「{stock_full_name}」相关的股票，目前仅支持 A 股"
            )

        except httpx.TimeoutException:
            return StockMatchResult(
                success=False,
                error_message="股票查询服务超时，请稍后重试"
            )
        except Exception as e:
            print(f"[StockMatcher] 查询失败: {e}")
            return StockMatchResult(
                success=False,
                error_message=f"股票查询失败: {str(e)}"
            )

    def _parse_stock_content(self, content: str) -> Optional[dict]:
        """
        从 RAG 返回的文档内容中解析股票信息

        文档格式:
        股票名称: 贵州茅台
        股票代码: 600519
        市场: SH
        状态: listed
        """
        if not content:
            return None

        result = {}
        lines = content.strip().split("\n")
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                if key == "股票名称":
                    result["stock_name"] = value
                elif key == "股票代码":
                    result["stock_code"] = value
                elif key == "市场":
                    result["market"] = value
                elif key == "状态":
                    result["status"] = value

        return result if result else None

    def _infer_market(self, stock_code: str) -> str:
        """根据股票代码推断市场"""
        if not stock_code:
            return ""
        if stock_code.startswith("6"):
            return "SH"
        elif stock_code.startswith(("0", "3")):
            return "SZ"
        return "SZ"


# 全局单例
_stock_matcher: Optional[StockMatcher] = None


def get_stock_matcher() -> StockMatcher:
    """获取股票匹配服务单例"""
    global _stock_matcher
    if _stock_matcher is None:
        _stock_matcher = StockMatcher()
    return _stock_matcher
