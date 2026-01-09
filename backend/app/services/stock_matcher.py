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

# 常用股票的 Fallback 映射 (当 Qdrant 不可用时使用)
COMMON_STOCKS_FALLBACK = {
    # 白酒
    "茅台": ("600519", "贵州茅台", "SH"),
    "贵州茅台": ("600519", "贵州茅台", "SH"),
    "茅子": ("600519", "贵州茅台", "SH"),
    "五粮液": ("000858", "五粮液", "SZ"),
    "泸州老窖": ("000568", "泸州老窖", "SZ"),
    "洋河股份": ("002304", "洋河股份", "SZ"),
    "洋河": ("002304", "洋河股份", "SZ"),
    "山西汾酒": ("600809", "山西汾酒", "SH"),
    "汾酒": ("600809", "山西汾酒", "SH"),
    "古井贡酒": ("000596", "古井贡酒", "SZ"),
    # 银行
    "工商银行": ("601398", "工商银行", "SH"),
    "工行": ("601398", "工商银行", "SH"),
    "建设银行": ("601939", "建设银行", "SH"),
    "建行": ("601939", "建设银行", "SH"),
    "农业银行": ("601288", "农业银行", "SH"),
    "农行": ("601288", "农业银行", "SH"),
    "中国银行": ("601988", "中国银行", "SH"),
    "中行": ("601988", "中国银行", "SH"),
    "招商银行": ("600036", "招商银行", "SH"),
    "招行": ("600036", "招商银行", "SH"),
    "平安银行": ("000001", "平安银行", "SZ"),
    "交通银行": ("601328", "交通银行", "SH"),
    "交行": ("601328", "交通银行", "SH"),
    "兴业银行": ("601166", "兴业银行", "SH"),
    "浦发银行": ("600000", "浦发银行", "SH"),
    # 保险
    "中国平安": ("601318", "中国平安", "SH"),
    "平安": ("601318", "中国平安", "SH"),
    "中国人寿": ("601628", "中国人寿", "SH"),
    "人寿": ("601628", "中国人寿", "SH"),
    "中国太保": ("601601", "中国太保", "SH"),
    "太保": ("601601", "中国太保", "SH"),
    "新华保险": ("601336", "新华保险", "SH"),
    # 新能源/汽车
    "宁德时代": ("300750", "宁德时代", "SZ"),
    "宁德": ("300750", "宁德时代", "SZ"),
    "CATL": ("300750", "宁德时代", "SZ"),
    "比亚迪": ("002594", "比亚迪", "SZ"),
    "隆基绿能": ("601012", "隆基绿能", "SH"),
    "隆基": ("601012", "隆基绿能", "SH"),
    "阳光电源": ("300274", "阳光电源", "SZ"),
    "长城汽车": ("601633", "长城汽车", "SH"),
    "长城": ("601633", "长城汽车", "SH"),
    "上汽集团": ("600104", "上汽集团", "SH"),
    "上汽": ("600104", "上汽集团", "SH"),
    # 科技/互联网 (港股)
    "腾讯": ("00700", "腾讯控股", "HK"),
    "腾讯控股": ("00700", "腾讯控股", "HK"),
    "阿里巴巴": ("09988", "阿里巴巴-SW", "HK"),
    "阿里": ("09988", "阿里巴巴-SW", "HK"),
    "美团": ("03690", "美团-W", "HK"),
    "京东": ("09618", "京东集团-SW", "HK"),
    "小米": ("01810", "小米集团-W", "HK"),
    # A股科技
    "立讯精密": ("002475", "立讯精密", "SZ"),
    "立讯": ("002475", "立讯精密", "SZ"),
    "中芯国际": ("688981", "中芯国际", "SH"),
    "中芯": ("688981", "中芯国际", "SH"),
    "海康威视": ("002415", "海康威视", "SZ"),
    "海康": ("002415", "海康威视", "SZ"),
    "科大讯飞": ("002230", "科大讯飞", "SZ"),
    "讯飞": ("002230", "科大讯飞", "SZ"),
    # 石油/能源
    "中国石油": ("601857", "中国石油", "SH"),
    "中石油": ("601857", "中国石油", "SH"),
    "中国石化": ("600028", "中国石化", "SH"),
    "中石化": ("600028", "中国石化", "SH"),
    "中国海油": ("600938", "中国海油", "SH"),
    "海油": ("600938", "中国海油", "SH"),
    "贵州燃气": ("600903", "贵州燃气", "SH"),
    # 证券
    "中信证券": ("600030", "中信证券", "SH"),
    "中信": ("600030", "中信证券", "SH"),
    "华泰证券": ("601688", "华泰证券", "SH"),
    "华泰": ("601688", "华泰证券", "SH"),
    "国泰君安": ("601211", "国泰君安", "SH"),
    "东方财富": ("300059", "东方财富", "SZ"),
    # 医药
    "恒瑞医药": ("600276", "恒瑞医药", "SH"),
    "恒瑞": ("600276", "恒瑞医药", "SH"),
    "药明康德": ("603259", "药明康德", "SH"),
    "药明": ("603259", "药明康德", "SH"),
    "迈瑞医疗": ("300760", "迈瑞医疗", "SZ"),
    "迈瑞": ("300760", "迈瑞医疗", "SZ"),
    "片仔癀": ("600436", "片仔癀", "SH"),
    # 消费
    "海天味业": ("603288", "海天味业", "SH"),
    "海天": ("603288", "海天味业", "SH"),
    "伊利股份": ("600887", "伊利股份", "SH"),
    "伊利": ("600887", "伊利股份", "SH"),
    "蒙牛乳业": ("02319", "蒙牛乳业", "HK"),
    "蒙牛": ("02319", "蒙牛乳业", "HK"),
    "格力电器": ("000651", "格力电器", "SZ"),
    "格力": ("000651", "格力电器", "SZ"),
    "美的集团": ("000333", "美的集团", "SZ"),
    "美的": ("000333", "美的集团", "SZ"),
    # 通信/运营商
    "中国移动": ("600941", "中国移动", "SH"),
    "移动": ("600941", "中国移动", "SH"),
    "中国电信": ("601728", "中国电信", "SH"),
    "电信": ("601728", "中国电信", "SH"),
    "中国联通": ("600050", "中国联通", "SH"),
    "联通": ("600050", "中国联通", "SH"),
    # 地产
    "万科A": ("000002", "万科A", "SZ"),
    "万科": ("000002", "万科A", "SZ"),
    "保利发展": ("600048", "保利发展", "SH"),
    "保利": ("600048", "保利发展", "SH"),
    # 军工
    "中航沈飞": ("600760", "中航沈飞", "SH"),
    "沈飞": ("600760", "中航沈飞", "SH"),
    "中国中免": ("601888", "中国中免", "SH"),
    "中免": ("601888", "中国中免", "SH"),
}


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
        # 检查 Qdrant 集合是否存在
        collection_exists = self.ensure_collection_exists()

        if collection_exists:
            # 优先使用 Qdrant RAG 匹配
            # 先尝试精确匹配代码
            exact_result = self._exact_match(query)
            if exact_result:
                return exact_result

            # RAG 语义匹配
            return self._semantic_match(query, top_k)
        else:
            # Qdrant 不可用，使用 Fallback 映射
            return self._fallback_match(query)

    def _fallback_match(self, query: str) -> StockMatchResult:
        """
        Fallback 匹配 (当 Qdrant 不可用时)

        使用内置的常用股票映射表
        """
        clean_query = query.strip()

        # 精确匹配 Fallback 表
        if clean_query in COMMON_STOCKS_FALLBACK:
            code, name, market = COMMON_STOCKS_FALLBACK[clean_query]
            return StockMatchResult(
                success=True,
                stock_info=StockInfo(
                    stock_code=code,
                    stock_name=name,
                    market=market
                ),
                confidence=1.0
            )

        # 尝试模糊匹配 (包含关系)
        for key, (code, name, market) in COMMON_STOCKS_FALLBACK.items():
            if clean_query in key or key in clean_query:
                return StockMatchResult(
                    success=True,
                    stock_info=StockInfo(
                        stock_code=code,
                        stock_name=name,
                        market=market
                    ),
                    confidence=0.9
                )

        # 尝试匹配股票代码
        if clean_query.isdigit() and len(clean_query) == 6:
            for key, (code, name, market) in COMMON_STOCKS_FALLBACK.items():
                if code == clean_query:
                    return StockMatchResult(
                        success=True,
                        stock_info=StockInfo(
                            stock_code=code,
                            stock_name=name,
                            market=market
                        ),
                        confidence=1.0
                    )

        # 收集可能的建议
        suggestions = []
        for key, (code, name, market) in list(COMMON_STOCKS_FALLBACK.items())[:5]:
            if name not in [s.split("(")[0] for s in suggestions]:
                suggestions.append(f"{name}({code})")

        return StockMatchResult(
            success=False,
            suggestions=suggestions[:3],
            error_message=f"未能识别「{query}」，股票数据库正在初始化中。您可以尝试: {', '.join(suggestions[:3])}"
        )

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
