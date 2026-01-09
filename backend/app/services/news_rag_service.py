"""
新闻 RAG 服务
=============

临时 Qdrant 集合的新闻 RAG 服务

功能:
1. 创建临时集合存储新闻
2. 合并多来源新闻 (Search + Domain Info)
3. 语义去重 (基于向量相似度)
4. RAG 检索相关新闻
5. LLM 总结新闻标题
"""

import os
import uuid
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import numpy as np

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
)

from app.rag.embedding import EmbeddingService
from app.rag.config import get_rag_config
from app.schemas.session_schema import (
    NewsItem,
    SummarizedNewsItem,
    NewsSummaryResult,
)


# 语义去重阈值
DEDUP_SIMILARITY_THRESHOLD = 0.85


class NewsRAGService:
    """新闻 RAG 服务"""

    def __init__(self, session_id: str):
        """
        初始化新闻 RAG 服务

        Args:
            session_id: 会话 ID，用于创建临时集合
        """
        config = get_rag_config()
        self.client = QdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port
        )
        self.embedding_service = EmbeddingService(config.embedding_model)
        self.session_id = session_id
        self.collection_name = f"news_temp_{session_id}"
        self._collection_created = False

    def _ensure_collection(self):
        """确保临时集合存在"""
        if self._collection_created:
            return

        # 检查集合是否已存在
        collections = self.client.get_collections().collections
        if any(c.name == self.collection_name for c in collections):
            self._collection_created = True
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
        self._collection_created = True
        print(f"[NewsRAG] 创建临时集合: {self.collection_name}")

    def cleanup(self):
        """清理临时集合"""
        try:
            self.client.delete_collection(self.collection_name)
            print(f"[NewsRAG] 删除临时集合: {self.collection_name}")
        except Exception as e:
            print(f"[NewsRAG] 删除集合失败: {e}")

    def merge_news(
        self,
        search_results: List[Dict],
        domain_results: List[Dict]
    ) -> List[NewsItem]:
        """
        合并多来源新闻

        Args:
            search_results: Search (Tavily) 结果
            domain_results: Domain Info (AkShare) 结果

        Returns:
            统一格式的新闻列表
        """
        news_items = []

        # 转换 Search 结果
        for item in search_results:
            news_items.append(NewsItem(
                title=item.get("title", ""),
                content=item.get("content", item.get("summary", "")),
                url=item.get("url", ""),
                published_date=item.get("published_date", ""),
                source_type="search",
                score=item.get("score", 0.0)
            ))

        # 转换 Domain Info 结果
        for item in domain_results:
            news_items.append(NewsItem(
                title=item.get("title", ""),
                content=item.get("content", item.get("summary", "")),
                url=item.get("url", item.get("link", "")),
                published_date=item.get("publish_time", item.get("published_date", "")),
                source_type="domain_info",
                score=item.get("score", 0.0)
            ))

        # 按时间排序 (最新在前)
        news_items.sort(key=lambda x: x.published_date, reverse=True)

        print(f"[NewsRAG] 合并新闻: search={len(search_results)}, domain={len(domain_results)}, total={len(news_items)}")
        return news_items

    def index_news(self, news_items: List[NewsItem]) -> int:
        """
        将新闻索引到临时集合

        Args:
            news_items: 新闻列表

        Returns:
            索引的新闻数量
        """
        if not news_items:
            return 0

        self._ensure_collection()

        # 准备文本
        texts = [f"{item.title} {item.content}" for item in news_items]

        # 向量化
        embeddings = self.embedding_service.encode(texts)

        # 构建 points
        points = []
        for i, item in enumerate(news_items):
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
                    "title": item.title,
                    "content": item.content,
                    "url": item.url,
                    "published_date": item.published_date,
                    "source_type": item.source_type,
                    "score": item.score,
                }
            ))

        # 写入
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

        print(f"[NewsRAG] 索引 {len(points)} 条新闻")
        return len(points)

    def retrieve(self, query: str, top_k: int = 10) -> List[NewsItem]:
        """
        检索相关新闻

        Args:
            query: 查询文本 (用户问题)
            top_k: 返回数量

        Returns:
            相关新闻列表
        """
        if not self._collection_created:
            return []

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

        # 转换结果
        news_items = []
        for point in results.points:
            payload = point.payload
            news_items.append(NewsItem(
                title=payload["title"],
                content=payload["content"],
                url=payload["url"],
                published_date=payload["published_date"],
                source_type=payload["source_type"],
                score=point.score if hasattr(point, "score") else 0.0
            ))

        print(f"[NewsRAG] 检索到 {len(news_items)} 条相关新闻")
        return news_items

    def semantic_dedup(
        self,
        news_items: List[NewsItem],
        threshold: float = DEDUP_SIMILARITY_THRESHOLD
    ) -> List[NewsItem]:
        """
        语义去重

        Args:
            news_items: 新闻列表
            threshold: 相似度阈值

        Returns:
            去重后的新闻列表
        """
        if len(news_items) <= 1:
            return news_items

        # 向量化所有新闻
        texts = [f"{item.title} {item.content}" for item in news_items]
        embeddings = self.embedding_service.encode(texts)
        dense_vectors = embeddings["dense"]  # (n, 1024)

        # 计算相似度矩阵
        # 归一化
        norms = np.linalg.norm(dense_vectors, axis=1, keepdims=True)
        normalized = dense_vectors / (norms + 1e-8)
        similarity_matrix = np.dot(normalized, normalized.T)

        # 贪心去重
        n = len(news_items)
        keep_mask = [True] * n

        for i in range(n):
            if not keep_mask[i]:
                continue
            for j in range(i + 1, n):
                if not keep_mask[j]:
                    continue
                if similarity_matrix[i, j] >= threshold:
                    # 保留内容更长的，或时间更新的
                    len_i = len(news_items[i].content)
                    len_j = len(news_items[j].content)
                    if len_j > len_i * 1.2:  # j 明显更长
                        keep_mask[i] = False
                        break
                    else:
                        keep_mask[j] = False

        deduped = [item for i, item in enumerate(news_items) if keep_mask[i]]

        print(f"[NewsRAG] 语义去重: {len(news_items)} -> {len(deduped)}")
        return deduped

    async def summarize_news(
        self,
        news_items: List[NewsItem],
        llm_client,  # LLM 客户端 (OpenAI 兼容)
    ) -> NewsSummaryResult:
        """
        使用 LLM 总结新闻

        Args:
            news_items: 新闻列表
            llm_client: LLM 客户端

        Returns:
            NewsSummaryResult
        """
        if not news_items:
            return NewsSummaryResult(
                summary_text="",
                news_items=[],
                total_before_dedup=0,
                total_after_dedup=0
            )

        summarized_items = []

        # 批量总结 (每次处理 5 条)
        for item in news_items:
            try:
                summarized = await self._summarize_single_news(item, llm_client)
                summarized_items.append(summarized)
            except Exception as e:
                print(f"[NewsRAG] 总结新闻失败: {e}")
                # 降级: 使用原始标题
                summarized_items.append(SummarizedNewsItem(
                    summarized_title=item.title[:50] if len(item.title) > 50 else item.title,
                    summarized_content=item.content[:100] if len(item.content) > 100 else item.content,
                    original_title=item.title,
                    url=item.url,
                    published_date=item.published_date,
                    source_type=item.source_type
                ))

        # 生成连贯段落
        summary_text = self._generate_summary_text(summarized_items)

        return NewsSummaryResult(
            summary_text=summary_text,
            news_items=summarized_items,
            total_before_dedup=len(news_items),
            total_after_dedup=len(summarized_items)
        )

    async def _summarize_single_news(
        self,
        item: NewsItem,
        llm_client
    ) -> SummarizedNewsItem:
        """总结单条新闻"""
        prompt = f"""你是一个金融新闻编辑。请对以下新闻进行总结：

原标题: {item.title}
原内容: {item.content[:500]}

要求:
1. summarized_title: 用一句话概括新闻要点，不超过25字
2. summarized_content: 用1-2句话说明具体内容，不超过60字
3. 保持客观中立，去除标题党成分
4. 突出与股票/金融相关的关键信息

只输出 JSON 格式，不要其他内容:
{{"summarized_title": "...", "summarized_content": "..."}}"""

        response = await llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )

        import json
        result = json.loads(response.choices[0].message.content)

        return SummarizedNewsItem(
            summarized_title=result["summarized_title"],
            summarized_content=result["summarized_content"],
            original_title=item.title,
            url=item.url,
            published_date=item.published_date,
            source_type=item.source_type
        )

    def _generate_summary_text(self, items: List[SummarizedNewsItem]) -> str:
        """生成连贯的新闻摘要文本"""
        if not items:
            return ""

        parts = []
        for i, item in enumerate(items[:5], 1):  # 最多 5 条
            parts.append(f"{i}. {item.summarized_title}: {item.summarized_content}")

        return "\n".join(parts)

    def process_news(
        self,
        search_results: List[Dict],
        domain_results: List[Dict],
        query: str,
        top_k: int = 10
    ) -> Tuple[List[NewsItem], List[NewsItem]]:
        """
        完整的新闻处理流程

        1. 合并新闻
        2. 索引到临时集合
        3. RAG 检索
        4. 语义去重

        Args:
            search_results: Search 结果
            domain_results: Domain Info 结果
            query: 用户问题
            top_k: 返回数量

        Returns:
            (all_news, relevant_news)
        """
        # 1. 合并
        all_news = self.merge_news(search_results, domain_results)
        if not all_news:
            return [], []

        # 2. 索引
        self.index_news(all_news)

        # 3. RAG 检索
        relevant_news = self.retrieve(query, top_k=top_k)

        # 4. 语义去重
        deduped_news = self.semantic_dedup(relevant_news)

        return all_news, deduped_news


def create_news_rag_service(session_id: str) -> NewsRAGService:
    """创建新闻 RAG 服务实例"""
    return NewsRAGService(session_id)
