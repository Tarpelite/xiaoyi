import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.core.config import settings
from app.core.utils import format_sse, df_to_table, df_to_chart, detect_anomalies, forecast_to_chart, STEPS
from app.core.session_manager import get_session_manager
from app.agents import FinanceChatAgent, IntentAgent, SuggestionAgent, RAGAgent, RAG_AVAILABLE
from app.data import DataFetcher
from app.models import (
    TimeSeriesAnalyzer,
    ProphetForecaster,
    XGBoostForecaster,
    RandomForestForecaster,
    DLinearForecaster
)
from app.sentiment import SentimentAnalyzer

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    session_id: Optional[str] = None  # 会话ID，可选
    history: Optional[List[Dict[str, str]]] = None  # 对话历史，可选（用于兼容）


class SuggestionsRequest(BaseModel):
    """快速追问建议请求模型"""
    session_id: Optional[str] = None  # 会话ID，可选

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """对话流式接口"""

    async def generate():
        try:
            # 初始化 Agent
            try:
                api_key = settings.api_key
            except ValueError as e:
                yield format_sse("error", {"message": str(e)})
                return

            agent = FinanceChatAgent(api_key)
            sentiment_analyzer = SentimentAnalyzer(api_key)
            user_input = request.message

            # 会话管理
            session_manager = get_session_manager()
            session_id = request.session_id

            # 如果没有提供 session_id，创建新会话
            if not session_id:
                session_id = session_manager.create_session()
                # 发送 session_id 给前端
                yield format_sse("session", {"session_id": session_id})

            # 获取对话历史（用于上下文）
            conversation_history = session_manager.get_recent_history(session_id, max_turns=5)

            # 添加用户消息到历史（在处理前添加，以便后续更新）
            session_manager.add_message(session_id, "user", user_input)

            # ========== 意图判断 ==========
            intent_agent = IntentAgent(api_key)
            intent_result = await asyncio.to_thread(intent_agent.judge_intent, user_input, conversation_history)
            intent = intent_result.get("intent", "analyze")
            intent_reason = intent_result.get("reason", "")

            # 从意图识别结果获取 tools、model 和 params
            intent_tools = intent_result.get("tools", {"forecast": True, "report_rag": False, "news_rag": False})
            model = intent_result.get("model", "prophet")
            intent_params = intent_result.get("params", {"history_days": 365, "forecast_horizon": 30})
            history_days = intent_params.get("history_days", 365)
            forecast_horizon = intent_params.get("forecast_horizon", 30)

            # 发送意图识别结果给前端（包含 tools、model 和 params）
            yield format_sse("intent", {
                "intent": intent,
                "reason": intent_reason,
                "tools": intent_tools,
                "model": model,
                "params": intent_params
            })

            # ========== RAG 研报检索分支 ==========
            if intent_tools.get("report_rag", False) and RAG_AVAILABLE:
                print(f"[RAG] 意图识别: report_rag=True")
                print(f"[RAG] 用户查询: {user_input}")

                # 使用 RAG Agent 检索研报并生成回答
                rag_agent = RAGAgent(api_key)
                full_answer = ""

                # 发送检索开始状态
                yield format_sse("step", {"steps": [
                    {"id": "rag_search", "name": "研报检索", "status": "running", "message": "正在检索相关研报..."}
                ]})

                # 检索相关文档
                print(f"[RAG] 开始检索...")
                retrieved_docs = await asyncio.to_thread(rag_agent.search_reports, user_input, 5)
                print(f"[RAG] 找到 {len(retrieved_docs)} 条相关内容")

                # 发送检索结果（来源信息）
                if retrieved_docs:
                    sources = []
                    source_summary = []
                    for doc in retrieved_docs:
                        sources.append({
                            "file_name": doc["file_name"],
                            "page_number": doc["page_number"],
                            "score": round(doc["score"], 3)
                        })
                        source_summary.append(f"{doc['file_name']}:{doc['page_number']}")
                    print(f"[RAG] 来源: {', '.join(source_summary)}")
                    yield format_sse("rag_sources", {"sources": sources, "count": len(retrieved_docs)})

                    yield format_sse("step", {"steps": [
                        {"id": "rag_search", "name": "研报检索", "status": "completed", "message": f"找到 {len(retrieved_docs)} 条相关内容"}
                    ]})
                else:
                    print(f"[RAG] 未找到相关研报")
                    yield format_sse("step", {"steps": [
                        {"id": "rag_search", "name": "研报检索", "status": "completed", "message": "未找到相关研报"}
                    ]})

                # 流式生成回答
                print(f"[RAG] 生成回答中...")
                yield format_sse("step", {"steps": [
                    {"id": "rag_search", "name": "研报检索", "status": "completed", "message": f"找到 {len(retrieved_docs)} 条相关内容"},
                    {"id": "rag_generate", "name": "生成回答", "status": "running", "message": "基于研报内容生成回答..."}
                ]})

                def stream_rag_answer():
                    return rag_agent.generate_answer_stream(user_input, retrieved_docs, conversation_history)

                generator = await asyncio.to_thread(stream_rag_answer)

                for chunk in generator:
                    full_answer += chunk
                    yield format_sse("text_delta", {"delta": chunk})

                yield format_sse("text_done", {"text": full_answer})
                print(f"[RAG] 回答生成完成, 长度: {len(full_answer)} 字符")

                yield format_sse("step", {"steps": [
                    {"id": "rag_search", "name": "研报检索", "status": "completed", "message": f"找到 {len(retrieved_docs)} 条相关内容"},
                    {"id": "rag_generate", "name": "生成回答", "status": "completed", "message": "回答生成完成"}
                ]})

                # 添加助手回复到会话历史
                session_manager.add_message(session_id, "assistant", full_answer)
                return

            # RAG 被请求但不可用时，提示用户
            if intent_tools.get("report_rag", False) and not RAG_AVAILABLE:
                print(f"[RAG] 研报检索功能未启用，跳过 RAG 分支")
                yield format_sse("content", {"content": {"type": "text", "text": "研报检索功能暂未启用，将使用其他方式回答您的问题。"}})

            # ========== 新闻搜索分支（仅当 forecast=False 时执行纯新闻搜索） ==========
            if intent_tools.get("news_rag", False) and not intent_tools.get("forecast", False):
                print(f"[News] 意图识别: news_rag=True, forecast=False")
                print(f"[News] 用户查询: {user_input}")

                from app.news import TavilyNewsClient

                # 发送搜索开始状态
                yield format_sse("step", {"steps": [
                    {"id": "news_extract", "name": "解析查询", "status": "running", "message": "正在解析搜索意图..."}
                ]})

                try:
                    # Step 1: 使用 LLM 提取关键词
                    keyword_result = await asyncio.to_thread(
                        intent_agent.extract_search_keywords,
                        user_input
                    )
                    keywords = keyword_result.get("keywords", user_input)
                    is_stock = keyword_result.get("is_stock", False)
                    stock_name = keyword_result.get("stock_name", "")
                    stock_code = keyword_result.get("stock_code", "")

                    print(f"[News] 关键词提取: keywords={keywords}, is_stock={is_stock}, stock_name={stock_name}, stock_code={stock_code}")

                    yield format_sse("step", {"steps": [
                        {"id": "news_extract", "name": "解析查询", "status": "completed", "message": f"关键词: {keywords}"},
                        {"id": "news_search", "name": "新闻搜索", "status": "running", "message": "正在搜索相关新闻..."}
                    ]})

                    tavily_client = TavilyNewsClient(settings.tavily_api_key)
                    tavily_results = {"results": [], "count": 0}
                    akshare_news_df = None

                    # Step 2: 根据是否股票相关选择数据源
                    if is_stock and stock_code:
                        # 股票相关：使用 AkShare + Tavily
                        print(f"[News] 股票搜索模式: AkShare + Tavily")

                        # 并行获取 AkShare 和 Tavily
                        akshare_news_df = await asyncio.to_thread(DataFetcher.fetch_news, stock_code, 50)
                        tavily_results = await asyncio.to_thread(
                            tavily_client.search_stock_news,
                            stock_name=stock_name or keywords,
                            days=30,
                            max_results=10
                        )
                    else:
                        # 非股票：仅 Tavily（使用中国域名过滤）
                        print(f"[News] 通用搜索模式: Tavily only")
                        tavily_results = await asyncio.to_thread(
                            tavily_client.search_stock_news,  # 仍使用中文域名过滤
                            stock_name=keywords,
                            days=30,
                            max_results=10
                        )

                    akshare_count = len(akshare_news_df) if akshare_news_df is not None and not akshare_news_df.empty else 0
                    tavily_count = tavily_results.get("count", 0)
                    total_count = akshare_count + tavily_count

                    print(f"[News] 找到新闻: AkShare={akshare_count}, Tavily={tavily_count}, 总计={total_count}")

                    yield format_sse("step", {"steps": [
                        {"id": "news_extract", "name": "解析查询", "status": "completed", "message": f"关键词: {keywords}"},
                        {"id": "news_search", "name": "新闻搜索", "status": "completed", "message": f"找到 {total_count} 条新闻"},
                        {"id": "news_summary", "name": "新闻总结", "status": "running", "message": "生成新闻摘要..."}
                    ]})

                    # Step 3: 构建综合新闻上下文
                    news_context_parts = []

                    # AkShare 新闻（无 URL）
                    if akshare_news_df is not None and not akshare_news_df.empty:
                        news_context_parts.append("=== 即时新闻（AkShare）===")
                        for _, row in akshare_news_df.head(15).iterrows():
                            title = row.get("新闻标题", row.get("标题", ""))
                            content = str(row.get("新闻内容", row.get("内容", "")))[:100]
                            if title:
                                news_context_parts.append(f"- {title}: {content}")

                    # Tavily 新闻（有 URL）
                    if tavily_results.get("results"):
                        news_context_parts.append("\n=== 网络新闻（Tavily，带URL）===")
                        for item in tavily_results["results"]:
                            title = item.get("title", "")
                            url = item.get("url", "")
                            content = item.get("content", "")[:100]
                            news_context_parts.append(f"- 【{title}】({url}): {content}")

                    news_context = "\n".join(news_context_parts) if news_context_parts else "未找到相关新闻。"

                    # Step 4: 流式生成 LLM 总结
                    full_answer = ""

                    def stream_news_summary():
                        return intent_agent.summarize_news_stream(user_input, news_context, conversation_history)

                    generator = await asyncio.to_thread(stream_news_summary)

                    for chunk in generator:
                        full_answer += chunk
                        yield format_sse("text_delta", {"delta": chunk})

                    yield format_sse("text_done", {"text": full_answer})

                    yield format_sse("step", {"steps": [
                        {"id": "news_extract", "name": "解析查询", "status": "completed", "message": f"关键词: {keywords}"},
                        {"id": "news_search", "name": "新闻搜索", "status": "completed", "message": f"找到 {total_count} 条新闻"},
                        {"id": "news_summary", "name": "新闻总结", "status": "completed", "message": "总结完成"}
                    ]})

                    session_manager.add_message(session_id, "assistant", full_answer)

                except ValueError as e:
                    # API Key 未配置
                    yield format_sse("content", {"content": {"type": "text", "text": f"新闻搜索服务未配置: {str(e)}"}})
                except Exception as e:
                    yield format_sse("content", {"content": {"type": "text", "text": f"新闻搜索失败: {str(e)}"}})
                    import traceback
                    print(f"[News] Error: {traceback.format_exc()}")

                return

            # 如果 forecast tool 关闭，或者只是提问，直接回答
            if not intent_tools.get("forecast", True) or intent == "answer":
                # 流式回答问题，不执行完整分析
                full_answer = ""

                # 使用流式生成器
                def stream_answer():
                    return intent_agent.answer_question_stream(user_input, conversation_history)

                generator = await asyncio.to_thread(stream_answer)

                for chunk in generator:
                    full_answer += chunk
                    # 发送文本片段
                    yield format_sse("text_delta", {"delta": chunk})

                # 发送完成信号
                yield format_sse("text_done", {"text": full_answer})

                # 添加助手回复到会话历史
                session_manager.add_message(session_id, "assistant", full_answer)
                return

            # 如果需要执行新分析且 forecast tool 开启，继续执行完整流程

            # 初始化步骤状态
            steps = [{"id": s["id"], "name": s["name"], "status": "pending"} for s in STEPS]

            # ========== 步骤1: 数据获取与预处理 ==========
            steps[0]["status"] = "running"
            steps[0]["message"] = "解析用户需求..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # NLP 解析（传递历史对话）
            parsed = await asyncio.to_thread(agent.nlp.parse, user_input, conversation_history)
            data_config = parsed["data_config"]
            analysis_config = parsed["analysis_config"]

            # 使用意图识别的历史窗口参数计算 start_date
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=history_days)).strftime("%Y%m%d")

            if "params" not in data_config:
                data_config["params"] = {}
            data_config["params"]["start_date"] = start_date
            data_config["params"]["end_date"] = end_date

            steps[0]["message"] = f"获取 {history_days} 天历史数据..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # 获取数据
            raw_df = await asyncio.to_thread(DataFetcher.fetch, data_config)
            df = await asyncio.to_thread(DataFetcher.prepare, raw_df, data_config)

            # 发送时序数据（表格）
            table_content = df_to_table(df, "历史时序数据（最近20条）", limit=20)
            yield format_sse("content", {"content": table_content})
            await asyncio.sleep(0.1)

            # 发送时序数据（图表）
            chart_content = df_to_chart(df, f"历史价格趋势（{len(df)}天）")
            yield format_sse("content", {"content": chart_content})
            await asyncio.sleep(0.1)

            steps[0]["status"] = "completed"
            steps[0]["message"] = f"已获取历史数据 {len(df)} 天"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # ========== 步骤2: 新闻获取与情绪分析（始终使用 AkShare + Tavily） ==========
            steps[1]["status"] = "running"
            steps[1]["message"] = "获取相关新闻..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # 获取股票代码和名称
            stock_symbol = data_config.get("params", {}).get("symbol", "")
            stock_name = parsed.get("analysis_config", {}).get("stock_name", user_input)

            from app.news import TavilyNewsClient

            # AkShare 新闻获取（始终执行）
            news_df = await asyncio.to_thread(DataFetcher.fetch_news, stock_symbol, 50)
            tavily_results = {"results": [], "count": 0}

            # Tavily 新闻获取（始终执行，用于补充和提供链接）
            try:
                tavily_client = TavilyNewsClient(settings.tavily_api_key)
                tavily_results = await asyncio.to_thread(
                    tavily_client.search_stock_news,
                    stock_name=stock_name,
                    days=30,
                    max_results=10
                )
                print(f"[Tavily] 找到 {tavily_results['count']} 条新闻")
            except Exception as e:
                print(f"[Tavily] 搜索失败（降级为仅 AkShare）: {e}")

            akshare_count = len(news_df) if news_df is not None and not news_df.empty else 0
            tavily_count = tavily_results.get("count", 0)
            total_count = akshare_count + tavily_count

            steps[1]["message"] = f"分析 {total_count} 条新闻情绪..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # 根据是否有 Tavily 结果选择分析方法
            if tavily_count > 0:
                # 使用增强版分析（带链接）
                sentiment_result = await asyncio.to_thread(
                    sentiment_analyzer.analyze_with_links,
                    news_df,
                    tavily_results
                )
                # 发送带链接的情绪分析结果
                yield format_sse("content", {"content": {"type": "text", "text": sentiment_result["formatted_text"]}})
            else:
                # Tavily 无结果时，使用原有分析方法（仅 AkShare，无链接）
                sentiment_result = await asyncio.to_thread(sentiment_analyzer.analyze, news_df)
                # 发送原有格式的情绪分析结果
                sentiment_text = f"""**市场情绪分析**

- 整体情绪: {sentiment_result.get('sentiment', '中性')}
- 情绪得分: {sentiment_result.get('overall_score', 0):.2f} (范围: -1 到 1)
- 分析新闻数: {sentiment_result.get('news_count', 0)}

**关键事件:**
"""
                key_events = sentiment_result.get('key_events', [])
                for i, event in enumerate(key_events[:5], 1):
                    sentiment_text += f"\n{i}. {event}"
                if sentiment_result.get('analysis_text'):
                    sentiment_text += f"\n\n**分析说明:** {sentiment_result.get('analysis_text')}"
                yield format_sse("content", {"content": {"type": "text", "text": sentiment_text}})

            await asyncio.sleep(0.1)

            steps[1]["status"] = "completed"
            steps[1]["message"] = f"情绪: {sentiment_result.get('sentiment', '中性')} (得分: {sentiment_result.get('overall_score', 0):.2f})"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # ========== 步骤3: 时序特征分析 ==========
            steps[2]["status"] = "running"
            steps[2]["message"] = "分析时序特征..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            features = await asyncio.to_thread(TimeSeriesAnalyzer.analyze_features, df)

            steps[2]["status"] = "completed"
            steps[2]["message"] = f"趋势: {features['trend']}, 波动性: {features['volatility']}"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # ========== 步骤4: 参数智能推荐 ==========
            steps[3]["status"] = "running"
            steps[3]["message"] = "根据情绪推荐模型参数..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # 参数推荐
            prophet_params = await asyncio.to_thread(
                sentiment_analyzer.recommend_params, sentiment_result, features
            )

            # 发送参数推荐结果
            params_text = f"""**Prophet 参数配置**

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| changepoint_prior_scale | {prophet_params.get('changepoint_prior_scale', 0.05):.3f} | 趋势变化敏感度 |
| seasonality_prior_scale | {prophet_params.get('seasonality_prior_scale', 10):.1f} | 季节性强度 |
| changepoint_range | {prophet_params.get('changepoint_range', 0.8):.2f} | 变点检测范围 |

**推荐理由:** {prophet_params.get('reasoning', '使用默认参数')}"""

            yield format_sse("content", {"content": {"type": "text", "text": params_text}})
            await asyncio.sleep(0.1)

            steps[3]["status"] = "completed"
            steps[3]["message"] = f"推荐参数已生成: {prophet_params.get('reasoning', '')[:30]}..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # ========== 步骤5: 模型训练与预测 ==========
            steps[4]["status"] = "running"
            steps[4]["message"] = f"训练 {model.upper()} 模型，预测 {forecast_horizon} 天..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # 使用意图识别的预测窗口参数
            horizon = forecast_horizon

            # 根据选择的模型进行预测
            if model == "prophet":
                prophet_forecaster = ProphetForecaster()
                forecast_result = await asyncio.to_thread(
                    prophet_forecaster.forecast, df, horizon, prophet_params
                )
            elif model == "xgboost":
                xgboost_forecaster = XGBoostForecaster()
                forecast_result = await asyncio.to_thread(xgboost_forecaster.forecast, df, horizon)
            elif model == "randomforest":
                rf_forecaster = RandomForestForecaster()
                forecast_result = await asyncio.to_thread(rf_forecaster.forecast, df, horizon)
            else:  # dlinear
                dlinear_forecaster = DLinearForecaster()
                forecast_result = await asyncio.to_thread(dlinear_forecaster.forecast, df, horizon)

            # 获取模型指标信息
            metrics_info = ", ".join([f"{k.upper()}: {v}" for k, v in forecast_result['metrics'].items()])
            steps[4]["status"] = "completed"
            steps[4]["message"] = f"{forecast_result['model'].upper()} 完成 ({metrics_info})"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # ========== 步骤6: 结果可视化 ==========
            steps[5]["status"] = "running"
            steps[5]["message"] = "生成图表中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # 发送模型性能表格
            model_table = {
                "type": "table",
                "title": "模型性能指标",
                "headers": ["指标", "数值"],
                "rows": [
                    [k.upper(), v] for k, v in forecast_result["metrics"].items()
                ]
            }
            yield format_sse("content", {"content": model_table})
            await asyncio.sleep(0.1)

            # 发送预测图表
            forecast_chart = forecast_to_chart(df, forecast_result["forecast"])
            yield format_sse("content", {"content": forecast_chart})
            await asyncio.sleep(0.1)

            steps[5]["status"] = "completed"
            steps[5]["message"] = "图表已生成"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # ========== 步骤7: 报告生成 ==========
            steps[6]["status"] = "running"
            steps[6]["message"] = "生成分析报告..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # 生成报告（包含情绪分析和对话历史）
            user_question = analysis_config.get("user_question", user_input)
            report = await asyncio.to_thread(
                agent.reporter.generate, user_question, features, forecast_result, sentiment_result, conversation_history
            )

            # 发送文本内容（分析报告）
            text_content = {
                "type": "text",
                "text": f"**综合分析报告**\n\n{report}"
            }
            yield format_sse("content", {"content": text_content})
            await asyncio.sleep(0.1)

            steps[6]["status"] = "completed"
            steps[6]["message"] = "分析报告已生成"
            yield format_sse("step", {"steps": steps})

            # 添加助手回复到会话历史
            session_manager.add_message(session_id, "assistant", report)

        except Exception as e:
            # 错误处理
            error_msg = {
                "type": "text",
                "text": f"处理过程中出现错误: {str(e)}"
            }
            yield format_sse("content", {"content": error_msg})
            import traceback
            print(f"Error: {traceback.format_exc()}")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/suggestions")
async def get_suggestions(request: SuggestionsRequest):
    """获取快速追问建议"""
    try:
        api_key = settings.api_key
    except ValueError as e:
        return {"error": str(e), "suggestions": []}
    
    session_manager = get_session_manager()
    session_id = request.session_id
    
    # 如果没有提供 session_id，返回默认建议
    if not session_id:
        default_suggestions = [
            "帮我分析一下茅台，预测下个季度走势",
            "查看最近的市场趋势",
            "对比几只白酒股的表现",
            "生成一份投资分析报告"
        ]
        return {"suggestions": default_suggestions}
    
    # 获取对话历史
    conversation_history = session_manager.get_recent_history(session_id, max_turns=5)
    
    # 生成建议
    suggestion_agent = SuggestionAgent(api_key)
    suggestions = await asyncio.to_thread(suggestion_agent.generate_suggestions, conversation_history)
    
    return {"suggestions": suggestions}
