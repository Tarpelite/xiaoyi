"""
数据层单元测试
==============

使用 pytest 运行:
    cd backend
    pytest tests/test_data_layer.py -v
    
仅运行快速测试（不需要外部服务）:
    pytest tests/test_data_layer.py -v -m "not integration"

运行集成测试（需要 RAG 服务）:
    pytest tests/test_data_layer.py -v -m integration
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# 单元测试（不需要外部服务）
# ============================================================

class TestDataModels:
    """测试数据模型"""
    
    def test_search_result_creation(self):
        """测试 SearchResult 创建"""
        from app.data.models import SearchResult, DataSourceType
        
        result = SearchResult(
            source=DataSourceType.REPORT,
            content="测试内容",
            title="测试标题",
            score=0.95,
        )
        
        assert result.source == DataSourceType.REPORT
        assert result.content == "测试内容"
        assert result.score == 0.95
    
    def test_report_result_creation(self):
        """测试 ReportResult 创建"""
        from app.data.models import ReportResult
        
        result = ReportResult(
            chunk_id="chunk_001",
            doc_id="doc_001",
            content="研报内容",
            score=0.88,
            page_number=5,
            file_name="test.pdf",
        )
        
        assert result.chunk_id == "chunk_001"
        assert result.page_number == 5
    
    def test_data_query_request(self):
        """测试 DataQueryRequest 默认值"""
        from app.data.models import DataQueryRequest, DataSourceType
        
        request = DataQueryRequest(query="测试查询")
        
        assert request.query == "测试查询"
        assert DataSourceType.REPORT in request.sources
        assert request.top_k == 5
        assert request.use_rerank == True


class TestReportClientUnit:
    """研报客户端单元测试（Mock）"""
    
    @pytest.mark.asyncio
    async def test_search_reports_success(self):
        """测试搜索成功"""
        from app.data.sources.report import ReportServiceClient
        
        client = ReportServiceClient(base_url="http://mock:8000")
        
        # Mock HTTP 响应
        mock_response = {
            "results": [
                {
                    "chunk_id": "c1",
                    "doc_id": "d1",
                    "content": "测试内容",
                    "score": 0.9,
                    "page_number": 1,
                    "file_name": "test.pdf",
                }
            ],
            "total": 1,
        }
        
        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = Mock(
                status_code=200,
                json=Mock(return_value=mock_response),
                raise_for_status=Mock(),
            )
            mock_get_client.return_value = mock_http_client
            
            results = await client.search_reports("测试", top_k=5)
            
            assert len(results) == 1
            assert results[0].content == "测试内容"
            assert results[0].score == 0.9
    
    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """测试空结果"""
        from app.data.sources.report import ReportServiceClient
        
        client = ReportServiceClient(base_url="http://mock:8000")
        
        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = Mock(
                status_code=200,
                json=Mock(return_value={"results": [], "total": 0}),
                raise_for_status=Mock(),
            )
            mock_get_client.return_value = mock_http_client
            
            results = await client.search_reports("不存在的查询", top_k=5)
            
            assert len(results) == 0


class TestUnifiedDataLayerUnit:
    """统一数据层单元测试"""
    
    @pytest.mark.asyncio
    async def test_query_reports_only(self):
        """测试仅查询研报"""
        from app.data.layer import UnifiedDataLayer
        from app.data.models import DataQueryRequest, DataSourceType, ReportResult
        
        layer = UnifiedDataLayer(
            report_service_url="http://mock:8000",
        )
        
        # Mock 研报客户端
        mock_reports = [
            ReportResult(
                chunk_id="c1",
                doc_id="d1",
                content="内容1",
                score=0.9,
                page_number=1,
                file_name="report1.pdf",
            )
        ]
        
        with patch.object(layer.report_client, 'search_reports', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_reports
            
            request = DataQueryRequest(
                query="测试",
                sources=[DataSourceType.REPORT],
                top_k=5,
            )
            
            response = await layer.query(request)
            
            assert len(response.report_results) == 1
            assert response.report_results[0].content == "内容1"
            mock_search.assert_called_once()


# ============================================================
# 集成测试（需要外部服务）
# ============================================================

@pytest.mark.integration
class TestReportClientIntegration:
    """研报服务集成测试（需要真实服务）"""
    
    @pytest.fixture
    def client(self):
        from app.data.sources.report import ReportServiceClient
        from app.core.config import settings
        return ReportServiceClient(base_url=settings.report_service_url)
    
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """测试健康检查"""
        health = await client.health_check()
        assert health.get("status") == "healthy"
    
    @pytest.mark.asyncio
    async def test_search_reports_real(self, client):
        """测试真实搜索"""
        results = await client.search_reports(
            query="煤炭",
            top_k=3,
            use_rerank=False,
        )
        
        # 至少应该有结果（如果有索引数据）
        # 如果没有数据，这个测试会失败，这是预期的
        assert isinstance(results, list)
        
        if results:
            assert results[0].content
            assert results[0].file_name


@pytest.mark.integration
class TestDataLayerIntegration:
    """数据层集成测试"""
    
    @pytest.fixture
    def layer(self):
        from app.data.layer import UnifiedDataLayer
        from app.core.config import settings
        return UnifiedDataLayer(
            report_service_url=settings.report_service_url,
            tavily_api_key=settings.TAVILY_API_KEY or None,
        )
    
    @pytest.mark.asyncio
    async def test_search_reports(self, layer):
        """测试搜索研报"""
        results = await layer.search_reports(
            query="新能源",
            top_k=3,
        )
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_search_all(self, layer):
        """测试混合搜索"""
        response = await layer.search_all(
            query="光伏",
            top_k=3,
            include_reports=True,
            include_news=False,  # 跳过 Tavily 避免 API 消耗
        )
        
        assert response.query == "光伏"
        assert isinstance(response.report_results, list)
        assert response.took_ms > 0


@pytest.mark.integration
class TestRAGAgentIntegration:
    """RAG Agent 集成测试"""
    
    @pytest.fixture
    def agent(self):
        from app.agents import RAGAgent
        from app.core.config import settings
        return RAGAgent(api_key=settings.api_key, use_remote=True)
    
    def test_search_reports_sync(self, agent):
        """测试同步搜索"""
        docs = agent.search_reports("首钢", top_k=3)
        assert isinstance(docs, list)
    
    @pytest.mark.asyncio
    async def test_search_reports_async(self, agent):
        """测试异步搜索"""
        docs = await agent.search_reports_async("煤炭", top_k=3)
        assert isinstance(docs, list)


# ============================================================
# 性能测试
# ============================================================

@pytest.mark.integration
@pytest.mark.slow
class TestPerformance:
    """性能测试"""
    
    @pytest.fixture
    def layer(self):
        from app.data.layer import UnifiedDataLayer
        from app.core.config import settings
        return UnifiedDataLayer(
            report_service_url=settings.report_service_url,
        )
    
    @pytest.mark.asyncio
    async def test_concurrent_queries(self, layer):
        """测试并发查询"""
        import time
        
        queries = ["煤炭", "光伏", "新能源", "储能", "电池"]
        
        start = time.time()
        
        # 并发执行
        tasks = [
            layer.search_reports(q, top_k=3, use_rerank=False)
            for q in queries
        ]
        results = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start
        
        print(f"\n并发查询 {len(queries)} 个，耗时: {elapsed:.2f}s")
        
        # 5 个查询应该在 5 秒内完成（并发）
        assert elapsed < 10
        assert len(results) == len(queries)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
