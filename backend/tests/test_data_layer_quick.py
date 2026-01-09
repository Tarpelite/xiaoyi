#!/usr/bin/env python
"""
数据层快速测试脚本
==================

用法:
    cd backend
    python tests/test_data_layer_quick.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_result(name: str, success: bool, detail: str = ""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {name}")
    if detail:
        print(f"       {detail}")


async def test_report_client():
    """测试研报服务客户端"""
    print_header("测试 1: 研报服务客户端 (ReportServiceClient)")
    
    from app.data.sources import get_report_client
    
    client = get_report_client(settings.report_service_url)
    print(f"服务地址: {settings.report_service_url}")
    
    # 1.1 健康检查
    try:
        health = await client.health_check()
        success = health.get("status") == "healthy"
        print_result(
            "健康检查",
            success,
            f"status={health.get('status')}, chunks={health.get('total_chunks', 0)}"
        )
    except Exception as e:
        print_result("健康检查", False, str(e))
        return False
    
    # 1.2 搜索测试
    try:
        results = await client.search_reports(
            query="焦煤",
            top_k=3,
            use_rerank=False,  # 先不用 rerank，更快
        )
        success = len(results) > 0
        print_result(
            "搜索测试 (query='焦煤')",
            success,
            f"返回 {len(results)} 条结果"
        )
        
        if results:
            r = results[0]
            print(f"\n       首条结果:")
            print(f"       - file: {r.file_name}")
            print(f"       - page: {r.page_number}")
            print(f"       - score: {r.score:.4f}")
            print(f"       - content: {r.content[:100]}...")
    except Exception as e:
        print_result("搜索测试", False, str(e))
        return False
    
    return True


async def test_unified_data_layer():
    """测试统一数据层"""
    print_header("测试 2: 统一数据层 (UnifiedDataLayer)")
    
    from app.data import get_data_layer, DataSourceType
    
    layer = get_data_layer(
        report_service_url=settings.report_service_url,
        tavily_api_key=settings.TAVILY_API_KEY or None,
    )
    
    # 2.1 仅研报搜索
    try:
        results = await layer.search_reports(
            query="新能源",
            top_k=3,
            use_rerank=False,
        )
        success = len(results) > 0
        print_result(
            "仅研报搜索",
            success,
            f"返回 {len(results)} 条研报"
        )
    except Exception as e:
        print_result("仅研报搜索", False, str(e))
    
    # 2.2 混合搜索（研报 + Tavily）
    if settings.TAVILY_API_KEY:
        try:
            response = await layer.search_all(
                query="光伏行业",
                top_k=3,
                include_reports=True,
                include_news=True,
            )
            print_result(
                "混合搜索 (研报+新闻)",
                True,
                f"研报={len(response.report_results)}, 新闻={len(response.news_results)}, 耗时={response.took_ms:.0f}ms"
            )
            
            if response.errors:
                print(f"       ⚠️ 部分错误: {response.errors}")
        except Exception as e:
            print_result("混合搜索", False, str(e))
    else:
        print_result("混合搜索", False, "TAVILY_API_KEY 未配置，跳过")
    
    return True


async def test_rag_agent():
    """测试 RAG Agent"""
    print_header("测试 3: RAG Agent")
    
    from app.agents import RAGAgent
    
    try:
        agent = RAGAgent(api_key=settings.api_key, use_remote=True)
        
        # 3.1 搜索研报
        docs = agent.search_reports("首钢", top_k=3)
        success = len(docs) > 0
        print_result(
            "RAGAgent.search_reports()",
            success,
            f"返回 {len(docs)} 条结果"
        )
        
        if not docs:
            print("       ⚠️ 无结果，跳过生成测试")
            return True
        
        # 3.2 生成回答（可选，会消耗 API）
        test_generate = input("\n是否测试 LLM 生成回答？(y/N): ").strip().lower() == 'y'
        
        if test_generate:
            answer = agent.generate_answer(
                query="首钢资源的主要业务是什么？",
                retrieved_docs=docs,
            )
            success = len(answer) > 50
            print_result(
                "RAGAgent.generate_answer()",
                success,
                f"回答长度: {len(answer)} 字符"
            )
            print(f"\n       回答摘要: {answer[:200]}...")
        else:
            print("       跳过 LLM 生成测试")
        
    except Exception as e:
        print_result("RAG Agent", False, str(e))
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_rag_agent_async():
    """测试 RAG Agent 异步方法"""
    print_header("测试 4: RAG Agent 异步搜索")
    
    from app.agents import RAGAgent
    
    try:
        agent = RAGAgent(api_key=settings.api_key, use_remote=True)
        
        # 异步搜索
        docs = await agent.search_reports_async("煤炭", top_k=3)
        success = len(docs) > 0
        print_result(
            "RAGAgent.search_reports_async()",
            success,
            f"返回 {len(docs)} 条结果"
        )
        
    except Exception as e:
        print_result("RAG Agent 异步", False, str(e))
        return False
    
    return True


async def main():
    print("\n" + "="*60)
    print("       xiaoyi 数据层测试")
    print("="*60)
    
    print(f"\n配置:")
    print(f"  - REPORT_SERVICE_URL: {settings.report_service_url}")
    print(f"  - TAVILY_API_KEY: {'已配置' if settings.TAVILY_API_KEY else '未配置'}")
    print(f"  - DEEPSEEK_API_KEY: {'已配置' if settings.DEEPSEEK_API_KEY else '未配置'}")
    
    results = []
    
    # 测试 1: 研报服务客户端
    results.append(await test_report_client())
    
    # 测试 2: 统一数据层
    results.append(await test_unified_data_layer())
    
    # 测试 3: RAG Agent（同步）
    results.append(await test_rag_agent())
    
    # 测试 4: RAG Agent（异步）
    results.append(await test_rag_agent_async())
    
    # 汇总
    print_header("测试汇总")
    passed = sum(results)
    total = len(results)
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 所有测试通过!")
    else:
        print("\n⚠️ 部分测试失败，请检查配置和服务状态")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
