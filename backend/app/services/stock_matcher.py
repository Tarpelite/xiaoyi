"""
股票匹配服务
============

基于 Qdrant RAG 的股票名称/代码匹配服务

功能:
1. 使用 AkShare 获取 A 股股票列表
2. 将股票信息向量化存入 Qdrant
3. 提供 RAG 匹配接口，支持模糊匹配
"""

import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    SparseIndexParams,
    Prefetch,
    FusionQuery,
    Fusion,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.rag.embedding import EmbeddingService
from app.rag.config import get_rag_config
from app.schemas.session_schema import StockInfo, StockMatchResult


# 股票集合名称
STOCK_COLLECTION_NAME = "stocks_info"

# 匹配阈值
HIGH_CONFIDENCE_THRESHOLD = 0.85  # 高置信度匹配
LOW_CONFIDENCE_THRESHOLD = 0.5   # 低置信度匹配


@dataclass
class StockRecord:
    """股票记录"""
    stock_code: str      # 股票代码，如 "600519"
    stock_name: str      # 股票名称，如 "贵州茅台"
    market: str          # 市场，"SH" 或 "SZ"
    aliases: List[str]   # 别名列表，如 ["茅台", "茅子"]
    status: str = "listed"  # 状态: listed / delisted
    list_date: str = ""     # 上市日期
    delist_date: str = ""   # 退市日期 (如果有)


class StockMatcher:
    """股票匹配服务"""

    _instance: Optional["StockMatcher"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return

        config = get_rag_config()
        self.client = QdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port
        )
        self.embedding_service = EmbeddingService(config.embedding_model)
        self.collection_name = STOCK_COLLECTION_NAME
        self._initialized = True

        print(f"[StockMatcher] 初始化完成, Qdrant: {config.qdrant_host}:{config.qdrant_port}")

    def ensure_collection_exists(self) -> bool:
        """确保股票集合存在"""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            print(f"[StockMatcher] 集合 {self.collection_name} 不存在，请先运行 init_stock_collection()")
            return False

        return True

    def init_collection(self):
        """初始化股票集合 (仅首次运行)"""
        # 检查集合是否已存在
        collections = self.client.get_collections().collections
        if any(c.name == self.collection_name for c in collections):
            print(f"[StockMatcher] 集合 {self.collection_name} 已存在")
            return

        # 创建集合
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=1024,  # BGE-M3 维度
                    distance=Distance.COSINE
                )
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams()
                )
            }
        )
        print(f"[StockMatcher] 创建集合: {self.collection_name}")

    def load_stocks_from_akshare(self) -> List[StockRecord]:
        """
        从 AkShare 加载 A 股股票列表

        Returns:
            股票记录列表
        """
        try:
            import akshare as ak

            print("[StockMatcher] 从 AkShare 加载股票列表...")

            # 获取 A 股股票代码和名称
            df = ak.stock_info_a_code_name()

            records = []
            for _, row in df.iterrows():
                code = row["code"]
                name = row["name"]

                # 判断市场
                if code.startswith("6"):
                    market = "SH"
                elif code.startswith(("0", "3")):
                    market = "SZ"
                else:
                    market = "SZ"  # 默认深圳

                # 生成别名 (简单规则)
                aliases = self._generate_aliases(name)

                records.append(StockRecord(
                    stock_code=code,
                    stock_name=name,
                    market=market,
                    aliases=aliases,
                    status="listed"
                ))

            print(f"[StockMatcher] 加载了 {len(records)} 只股票")
            return records

        except Exception as e:
            print(f"[StockMatcher] 加载股票列表失败: {e}")
            return []

    def _generate_aliases(self, stock_name: str) -> List[str]:
        """
        生成股票别名

        简单规则:
        - 去掉常见后缀 (股份、集团、科技、电子等)
        - 提取核心词
        """
        aliases = []

        # 常见后缀
        suffixes = ["股份", "集团", "科技", "电子", "控股", "实业", "有限公司", "有限", "公司", "A", "B"]

        # 去掉后缀
        short_name = stock_name
        for suffix in suffixes:
            short_name = short_name.replace(suffix, "")

        if short_name and short_name != stock_name:
            aliases.append(short_name)

        # 特殊映射 (常用简称)
        special_aliases = {
            "贵州茅台": ["茅台", "茅子"],
            "五粮液": ["五粮液"],
            "中国平安": ["平安"],
            "招商银行": ["招行"],
            "工商银行": ["工行", "宇宙行"],
            "建设银行": ["建行"],
            "农业银行": ["农行"],
            "中国银行": ["中行"],
            "宁德时代": ["宁德", "CATL"],
            "比亚迪": ["比亚迪"],
            "腾讯控股": ["腾讯"],
            "阿里巴巴": ["阿里"],
        }

        if stock_name in special_aliases:
            aliases.extend(special_aliases[stock_name])

        return list(set(aliases))

    def index_stocks(self, records: List[StockRecord], batch_size: int = 100):
        """
        将股票记录索引到 Qdrant

        Args:
            records: 股票记录列表
            batch_size: 批处理大小
        """
        if not records:
            print("[StockMatcher] 没有股票记录需要索引")
            return

        # 确保集合存在
        self.init_collection()

        # 准备文本 (用于向量化)
        texts = []
        for r in records:
            # 拼接名称和别名作为检索文本
            text = f"{r.stock_name} {r.stock_code} {' '.join(r.aliases)}"
            texts.append(text)

        # 批量向量化
        print(f"[StockMatcher] 向量化 {len(texts)} 条股票记录...")
        embeddings = self.embedding_service.encode(texts, batch_size=batch_size)

        # 构建 points
        points = []
        for i, record in enumerate(records):
            point_id = str(uuid.uuid4())
            points.append(PointStruct(
                id=point_id,
                vector={
                    "dense": embeddings["dense"][i].tolist(),
                    "sparse": SparseVector(
                        indices=embeddings["sparse"][i]["indices"],
                        values=embeddings["sparse"][i]["values"]
                    )
                },
                payload={
                    "stock_code": record.stock_code,
                    "stock_name": record.stock_name,
                    "market": record.market,
                    "aliases": record.aliases,
                    "status": record.status,
                    "list_date": record.list_date,
                    "delist_date": record.delist_date,
                }
            ))

        # 批量写入
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
            print(f"[StockMatcher] 写入 {i + len(batch)}/{len(points)}")

        print(f"[StockMatcher] 索引完成: {len(points)} 条记录")

    def match(self, query: str, top_k: int = 3) -> StockMatchResult:
        """
        匹配股票

        Args:
            query: 用户输入的股票名称/代码/别名
            top_k: 返回候选数量

        Returns:
            StockMatchResult
        """
        if not self.ensure_collection_exists():
            return StockMatchResult(
                success=False,
                error_message="股票数据库未初始化，请联系管理员"
            )

        # 先尝试精确匹配代码
        exact_result = self._exact_match(query)
        if exact_result:
            return exact_result

        # RAG 语义匹配
        return self._semantic_match(query, top_k)

    def _exact_match(self, query: str) -> Optional[StockMatchResult]:
        """精确匹配股票代码"""
        # 清理查询
        clean_query = query.strip()

        # 检查是否是股票代码格式 (6位数字)
        if not clean_query.isdigit() or len(clean_query) != 6:
            return None

        # 精确查询代码
        results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="stock_code",
                        match=MatchValue(value=clean_query)
                    )
                ]
            ),
            limit=1
        )

        points = results[0]
        if not points:
            return None

        payload = points[0].payload
        stock_info = StockInfo(
            stock_code=payload["stock_code"],
            stock_name=payload["stock_name"],
            market=payload["market"]
        )

        # 检查是否已退市
        if payload.get("status") == "delisted":
            return StockMatchResult(
                success=False,
                stock_info=stock_info,
                confidence=1.0,
                error_message=f"该股票已于 {payload.get('delist_date', '未知日期')} 退市"
            )

        return StockMatchResult(
            success=True,
            stock_info=stock_info,
            confidence=1.0
        )

    def _semantic_match(self, query: str, top_k: int = 3) -> StockMatchResult:
        """语义匹配"""
        # 编码查询
        query_embedding = self.embedding_service.encode_query(query)

        # 混合检索
        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(
                    query=query_embedding["dense"].tolist(),
                    using="dense",
                    limit=top_k * 2
                ),
                Prefetch(
                    query=SparseVector(
                        indices=query_embedding["sparse"]["indices"],
                        values=query_embedding["sparse"]["values"]
                    ),
                    using="sparse",
                    limit=top_k * 2
                )
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=top_k
        )

        if not results.points:
            return StockMatchResult(
                success=False,
                error_message=f"未找到与「{query}」相关的股票，目前仅支持 A 股"
            )

        # 分析结果
        top_point = results.points[0]
        top_score = top_point.score if hasattr(top_point, "score") else 0.0
        payload = top_point.payload

        stock_info = StockInfo(
            stock_code=payload["stock_code"],
            stock_name=payload["stock_name"],
            market=payload["market"]
        )

        # 检查是否已退市
        if payload.get("status") == "delisted":
            return StockMatchResult(
                success=False,
                stock_info=stock_info,
                confidence=top_score,
                error_message=f"该股票「{stock_info.stock_name}」已于 {payload.get('delist_date', '未知日期')} 退市"
            )

        # 高置信度匹配
        if top_score >= HIGH_CONFIDENCE_THRESHOLD:
            return StockMatchResult(
                success=True,
                stock_info=stock_info,
                confidence=top_score
            )

        # 中等置信度 - 返回建议
        if top_score >= LOW_CONFIDENCE_THRESHOLD:
            suggestions = []
            for point in results.points[:3]:
                p = point.payload
                suggestions.append(f"{p['stock_name']}({p['stock_code']})")

            return StockMatchResult(
                success=False,
                stock_info=stock_info,
                confidence=top_score,
                suggestions=suggestions,
                error_message=f"你可能说的是: {', '.join(suggestions)}?"
            )

        # 低置信度 - 无法匹配
        return StockMatchResult(
            success=False,
            confidence=top_score,
            error_message=f"未找到与「{query}」相关的股票，目前仅支持 A 股"
        )

    def get_stock_count(self) -> int:
        """获取已索引的股票数量"""
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count
        except Exception:
            return 0


# 全局单例
_stock_matcher: Optional[StockMatcher] = None


def get_stock_matcher() -> StockMatcher:
    """获取股票匹配服务单例"""
    global _stock_matcher
    if _stock_matcher is None:
        _stock_matcher = StockMatcher()
    return _stock_matcher


async def init_stock_collection():
    """
    初始化股票集合 (从 AkShare 加载数据)

    用法:
        python -c "import asyncio; from app.services.stock_matcher import init_stock_collection; asyncio.run(init_stock_collection())"
    """
    matcher = get_stock_matcher()

    # 检查是否已有数据
    count = matcher.get_stock_count()
    if count > 0:
        print(f"[StockMatcher] 股票集合已有 {count} 条记录")
        return

    # 从 AkShare 加载
    records = matcher.load_stocks_from_akshare()
    if not records:
        print("[StockMatcher] 加载股票列表失败")
        return

    # 索引
    matcher.index_stocks(records)
    print(f"[StockMatcher] 初始化完成，共 {matcher.get_stock_count()} 条记录")


if __name__ == "__main__":
    import asyncio
    asyncio.run(init_stock_collection())
