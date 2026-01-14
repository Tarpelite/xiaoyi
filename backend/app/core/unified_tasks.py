"""
统一任务处理器 V3
==================

基于新的统一架构:
1. 统一意图识别 (UnifiedIntent)
2. 股票 RAG 匹配 (当 stock_mention 非空时)
3. 并行数据获取
4. 新闻 RAG 服务 (语义去重)
5. Session/Message 分离管理

架构:
- Session: 存储对话历史，用于 LLM 上下文
- Message: 存储单轮分析结果，用于前端展示
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.core.session import Session, Message
from app.core.config import settings
from app.schemas.session_schema import (
    SessionStatus,
    StepStatus,
    TimeSeriesPoint,
    UnifiedIntent,
    ResolvedKeywords,
    StockMatchResult,
    StockInfo,
    SummarizedNewsItem,
    ReportItem,
    RAGSource,
    NewsItem,
)

# Services
from app.services.stock_matcher import get_stock_matcher
# NewsRAGService 暂时不使用，直接用 LLM 批量总结
# from app.services.news_rag_service import create_news_rag_service

# Agents
from app.agents import (
    IntentAgent,
    RAGAgent,
    ReportAgent,
    ErrorExplainerAgent,
    SentimentAgent,
)

# Data & Models
from app.data import DataFetcher
from app.data.fetcher import DataFetchError
from app.models import (
    TimeSeriesAnalyzer,
    ProphetForecaster,
    XGBoostForecaster,
    RandomForestForecaster,
    DLinearForecaster
)


class UnifiedTaskProcessorV3:
    """
    统一任务处理器 V3

    核心流程:
    1. 意图识别 (一次 LLM 调用返回所有信息)
    2. 股票验证 (当 stock_mention 非空时)
    3. 并行数据获取 (RAG, Search, Domain Info)
    4. 预测流程或对话流程
    5. 结果生成
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.intent_agent = IntentAgent(api_key)
        self.rag_agent = RAGAgent(api_key)
        self.report_agent = ReportAgent(api_key)
        self.error_explainer = ErrorExplainerAgent(api_key)
        self.sentiment_agent = SentimentAgent(api_key)
        self.stock_matcher = get_stock_matcher()

    async def execute(
        self,
        session_id: str,
        message_id: str,
        user_input: str,
        model_name: str = "prophet",
        force_intent: Optional[str] = None
    ):
        """
        执行统一任务

        Args:
            session_id: 会话 ID
            message_id: 消息 ID (存储分析结果)
            user_input: 用户输入
            model_name: 预测模型名称
            force_intent: 强制指定意图类型
        """
        # Session 用于对话历史，Message 用于存储分析结果
        session = Session(session_id)
        message = Message(message_id, session_id)

        try:
            # 获取对话历史
            conversation_history = session.get_conversation_history()

            # === 阶段 1: 意图识别 ===
            message.update_step_detail(1, "running", "分析用户意图...")

            if force_intent:
                intent = self._create_forced_intent(force_intent, model_name)
            else:
                intent = await asyncio.to_thread(
                    self.intent_agent.recognize_intent,
                    user_input,
                    conversation_history
                )

            # 保存意图
            message.save_unified_intent(intent)

            # 检查是否超出范围
            if not intent.is_in_scope:
                message.save_conclusion(intent.out_of_scope_reply or "抱歉，我是金融时序分析助手，暂不支持此类问题。")
                message.update_step_detail(1, "completed", "超出服务范围")
                message.mark_completed()
                return

            message.update_step_detail(1, "completed", f"意图: {'预测' if intent.is_forecast else '对话'}")

            # === 阶段 2: 股票验证 (当 stock_mention 非空时) ===
            stock_match_result = None
            resolved_keywords = None

            if intent.stock_mention:
                # 使用 LLM 生成的官方全称进行 RAG 查询，若无则使用原始输入
                query_name = intent.stock_full_name or intent.stock_mention
                message.update_step_detail(2, "running", f"验证股票: {query_name}")

                stock_match_result = await asyncio.to_thread(
                    self.stock_matcher.match,
                    query_name
                )

                message.save_stock_match(stock_match_result)

                if not stock_match_result.success:
                    # 股票验证失败，终止流程
                    error_msg = stock_match_result.error_message or "股票验证失败"
                    message.save_conclusion(error_msg)
                    message.update_step_detail(2, "error", error_msg)
                    message.mark_completed()
                    return

                # 解析最终关键词
                stock_info = stock_match_result.stock_info
                resolved_keywords = self.intent_agent.resolve_keywords(
                    intent,
                    stock_name=stock_info.stock_name if stock_info else None,
                    stock_code=stock_info.stock_code if stock_info else None
                )
                message.save_resolved_keywords(resolved_keywords)

                message.update_step_detail(
                    2, "completed",
                    f"匹配: {stock_info.stock_name}({stock_info.stock_code})" if stock_info else "无匹配"
                )
            else:
                # 无股票提及，直接使用原始关键词
                resolved_keywords = ResolvedKeywords(
                    search_keywords=intent.raw_search_keywords,
                    rag_keywords=intent.raw_rag_keywords,
                    domain_keywords=intent.raw_domain_keywords
                )

            # === 阶段 3+: 根据意图执行 ===
            if intent.is_forecast:
                await self._execute_forecast_v3(
                    message, session, user_input, intent, stock_match_result,
                    resolved_keywords, conversation_history
                )
            else:
                await self._execute_chat_v3(
                    message, session, user_input, intent, stock_match_result,
                    resolved_keywords, conversation_history
                )

            # 标记完成
            message.mark_completed()

            # 添加助手回复到对话历史
            data = message.get()
            if data and data.conclusion:
                session.add_conversation_message("assistant", data.conclusion)

        except Exception as e:
            import traceback
            print(f"❌ Task execution error: {traceback.format_exc()}")
            message.mark_error(str(e))
            raise

    def _create_forced_intent(self, force_type: str, model_name: str) -> UnifiedIntent:
        """创建强制指定的意图"""
        return UnifiedIntent(
            is_in_scope=True,
            is_forecast=(force_type == "forecast"),
            enable_rag=(force_type == "rag"),
            enable_search=(force_type in ["news", "forecast"]),
            enable_domain_info=(force_type in ["news", "forecast"]),
            forecast_model=model_name,
            reason="用户强制指定"
        )

    async def execute_after_intent(
        self,
        session_id: str,
        message_id: str,
        user_input: str,
        intent: UnifiedIntent
    ):
        """
        在意图识别完成后继续执行分析

        用于流式接口：意图识别通过 SSE 流式返回后，
        剩余步骤（股票验证、数据获取、预测等）通过此方法在后台执行

        Args:
            session_id: 会话 ID
            message_id: 消息 ID
            user_input: 用户输入
            intent: 已识别的意图（包含 forecast_model 等参数）
        """
        session = Session(session_id)
        message = Message(message_id, session_id)

        try:
            conversation_history = session.get_conversation_history()

            # === 阶段 2: 股票验证 (当 stock_mention 非空时) ===
            stock_match_result = None
            resolved_keywords = None

            if intent.stock_mention:
                # 使用 LLM 生成的官方全称进行 RAG 查询，若无则使用原始输入
                query_name = intent.stock_full_name or intent.stock_mention
                message.update_step_detail(2, "running", f"验证股票: {query_name}")

                stock_match_result = await asyncio.to_thread(
                    self.stock_matcher.match,
                    query_name
                )

                message.save_stock_match(stock_match_result)

                if not stock_match_result.success:
                    error_msg = stock_match_result.error_message or "股票验证失败"
                    message.save_conclusion(error_msg)
                    message.update_step_detail(2, "error", error_msg)
                    message.mark_completed()
                    return

                stock_info = stock_match_result.stock_info
                resolved_keywords = self.intent_agent.resolve_keywords(
                    intent,
                    stock_name=stock_info.stock_name if stock_info else None,
                    stock_code=stock_info.stock_code if stock_info else None
                )
                message.save_resolved_keywords(resolved_keywords)

                message.update_step_detail(
                    2, "completed",
                    f"匹配: {stock_info.stock_name}({stock_info.stock_code})" if stock_info else "无匹配"
                )
            else:
                resolved_keywords = ResolvedKeywords(
                    search_keywords=intent.raw_search_keywords,
                    rag_keywords=intent.raw_rag_keywords,
                    domain_keywords=intent.raw_domain_keywords
                )

            # === 阶段 3+: 根据意图执行 ===
            if intent.is_forecast:
                await self._execute_forecast_v3(
                    message, session, user_input, intent, stock_match_result,
                    resolved_keywords, conversation_history
                )
            else:
                await self._execute_chat_v3(
                    message, session, user_input, intent, stock_match_result,
                    resolved_keywords, conversation_history
                )

            # 标记完成
            message.mark_completed()

            # 添加助手回复到对话历史
            data = message.get()
            if data and data.conclusion:
                session.add_conversation_message("assistant", data.conclusion)

        except Exception as e:
            import traceback
            print(f"❌ execute_after_intent error: {traceback.format_exc()}")
            message.mark_error(str(e))
            raise

    # ========== 预测流程 ==========

    async def _execute_forecast_v3(
        self,
        message: Message,
        session: Session,
        user_input: str,
        intent: UnifiedIntent,
        stock_match: Optional[StockMatchResult],
        keywords: ResolvedKeywords,
        conversation_history: List[dict]
    ):
        """
        执行预测流程 (V3)

        阶段:
        1. 准备阶段 (意图+股票验证) - 已完成
        2. 数据获取 (并行)
        3. 分析处理 (并行)
        4. 模型预测
        5. 报告生成
        """
        stock_info = stock_match.stock_info if stock_match else None
        stock_code = stock_info.stock_code if stock_info else ""
        stock_name = stock_info.stock_name if stock_info else user_input

        # === 阶段 2: 数据获取 (并行) ===
        message.update_step_detail(3, "running", "获取历史数据和新闻...")

        # 设置日期范围
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=intent.history_days)).strftime("%Y%m%d")

        # 并行获取数据
        stock_data_task = self._fetch_stock_data(stock_code, start_date, end_date)
        news_task = self._fetch_news_combined(stock_code, stock_name, keywords)
        rag_task = self._fetch_rag_reports(keywords.rag_keywords) if intent.enable_rag else asyncio.sleep(0)

        results = await asyncio.gather(
            stock_data_task,
            news_task,
            rag_task,
            return_exceptions=True
        )

        # 处理股票数据获取结果
        df = None
        if isinstance(results[0], DataFetchError):
            # 使用 ErrorExplainerAgent 生成友好的错误解释
            error_explanation = await asyncio.to_thread(
                self.error_explainer.explain_data_fetch_error,
                results[0],
                user_input
            )
            message.save_conclusion(error_explanation)
            message.update_step_detail(3, "error", "数据获取失败")
            return
        elif isinstance(results[0], Exception):
            message.save_conclusion(f"获取数据时发生错误: {str(results[0])}")
            message.update_step_detail(3, "error", "数据获取失败")
            return
        else:
            df = results[0]

        news_result = results[1] if not isinstance(results[1], Exception) else ([], {})
        rag_sources = results[2] if not isinstance(results[2], Exception) and intent.enable_rag else []

        if df is None or df.empty:
            message.save_conclusion(f"无法获取 {stock_name} 的历史数据，请检查股票代码是否正确。")
            message.update_step_detail(3, "error", "数据获取失败")
            return

        # 保存数据
        original_points = self._df_to_points(df, is_prediction=False)
        message.save_time_series_original(original_points)

        news_items, sentiment_result = news_result
        # 使用 LLM 总结新闻标题
        if news_items:
            summarized_news = await self._summarize_news_items(session.session_id, news_items)
        else:
            summarized_news = []
        message.save_news(summarized_news)

        if rag_sources:
            message.save_rag_sources(rag_sources)

        message.update_step_detail(3, "completed", f"历史数据 {len(df)} 天, 新闻 {len(news_items)} 条")

        # === 阶段 3: 分析处理 (并行) ===
        message.update_step_detail(4, "running", "分析时序特征和市场情绪...")

        # 并行分析
        features_task = asyncio.to_thread(TimeSeriesAnalyzer.analyze_features, df)
        sentiment_task = self._analyze_sentiment(sentiment_result)

        analysis_results = await asyncio.gather(
            features_task,
            sentiment_task,
            return_exceptions=True
        )

        features = analysis_results[0] if not isinstance(analysis_results[0], Exception) else {}
        emotion_result = analysis_results[1] if not isinstance(analysis_results[1], Exception) else {}

        # 保存情绪
        if emotion_result:
            message.save_emotion(
                emotion_result.get("score", 0),
                emotion_result.get("description", "中性")
            )

        message.update_step_detail(
            4, "completed",
            f"趋势: {features.get('trend', 'N/A')}, 情绪: {emotion_result.get('description', 'N/A')}"
        )

        # === 阶段 4: 模型预测 ===
        message.update_step_detail(5, "running", f"训练 {intent.forecast_model.upper()} 模型...")

        # 获取推荐参数
        prophet_params = await asyncio.to_thread(
            self.sentiment_agent.recommend_params,
            sentiment_result or {},
            features
        )

        # 运行预测
        # 计算预测天数: 预测到 max(最后数据日期 + 3个月, 今天)
        last_date = df['ds'].max().to_pydatetime()
        target_date_from_start = last_date + timedelta(days=90)  # 最后一天 + 3个月
        target_date_to_today = datetime.now()
        target_date = max(target_date_from_start, target_date_to_today)
        forecast_horizon = (target_date - last_date).days
        
        forecast_result = await self._run_forecast(
            df,
            intent.forecast_model,
            max(forecast_horizon, 1),  # 至少预测1天
            prophet_params
        )

        # 保存预测结果
        full_points = original_points + self._forecast_to_points(forecast_result["forecast"])
        prediction_start = forecast_result["forecast"][0]["date"] if forecast_result["forecast"] else ""
        message.save_time_series_full(full_points, prediction_start)

        metrics_info = ", ".join([f"{k.upper()}: {v}" for k, v in forecast_result.get('metrics', {}).items()])
        message.update_step_detail(5, "completed", f"预测完成 ({metrics_info})")
        
        # 保存使用的模型名称到session
        session_data = session.get()
        if session_data:
            session_data.model_name = intent.forecast_model
            session._save(session_data)

        # === 阶段 5: 报告生成 ===
        message.update_step_detail(6, "running", "生成分析报告...")

        report = await asyncio.to_thread(
            self.report_agent.generate,
            user_input,
            features,
            forecast_result,
            emotion_result or {},  # 使用分析后的情绪结果，包含 score 和 description
            conversation_history
        )
        message.save_conclusion(report)

        message.update_step_detail(6, "completed", "报告生成完成")

    async def _fetch_stock_data(self, stock_code: str, start_date: str, end_date: str):
        """获取股票历史数据，遇到错误时抛出 DataFetchError"""
        data_config = {
            "api_function": "stock_zh_a_hist",
            "params": {
                "symbol": stock_code,
                "start_date": start_date,
                "end_date": end_date,
                "adjust": "qfq"
            }
        }

        raw_df = await asyncio.to_thread(DataFetcher.fetch, data_config)
        df = await asyncio.to_thread(DataFetcher.prepare, raw_df, data_config)
        return df

    async def _fetch_news_combined(
        self,
        stock_code: str,
        stock_name: str,
        keywords: ResolvedKeywords
    ) -> tuple:
        """
        获取合并新闻 (AkShare + Tavily)

        简化版：各取前5条，共10条新闻

        Returns:
            (news_items, sentiment_data)
        """
        news_items = []
        tavily_results = {"results": [], "count": 0}
        news_df = None

        # AkShare 新闻 (取前5条)
        try:
            news_df = await asyncio.to_thread(DataFetcher.fetch_news, stock_code, 20)
        except Exception as e:
            print(f"[News] AkShare 获取失败: {e}")

        # Tavily 新闻 (取前5条)
        try:
            from app.data import TavilyNewsClient
            tavily_client = TavilyNewsClient(settings.tavily_api_key)
            search_query = " ".join(keywords.search_keywords[:3]) if keywords.search_keywords else stock_name
            tavily_results = await asyncio.to_thread(
                tavily_client.search_stock_news,
                stock_name=search_query,
                days=30,
                max_results=5  # 只取5条
            )
        except Exception as e:
            print(f"[News] Tavily 获取失败: {e}")

        # 转换 AkShare 新闻 (前5条)
        if news_df is not None and not news_df.empty:
            for _, row in news_df.head(5).iterrows():  # 只取5条
                news_items.append(NewsItem(
                    title=row.get("新闻标题", ""),
                    content=row.get("新闻内容", "")[:300] if row.get("新闻内容") else "",
                    url=str(row.get("新闻链接", "")),
                    published_date=str(row.get("发布时间", "")),
                    source_type="domain_info"
                ))

        # 转换 Tavily 新闻 (前5条)
        for item in tavily_results.get("results", [])[:5]:  # 只取5条
            news_items.append(NewsItem(
                title=item.get("title", ""),
                content=item.get("content", "")[:300],
                url=item.get("url", ""),
                published_date=item.get("published_date") or "-",  # Tavily 通常不返回日期
                source_type="search"
            ))

        print(f"[News] 获取新闻: AkShare {min(5, len(news_df) if news_df is not None else 0)} 条, Tavily {len(tavily_results.get('results', [])[:5])} 条")

        # 构建情感分析数据
        sentiment_data = {
            "news_df": news_df,
            "tavily_results": tavily_results,
            "news_count": len(news_items)
        }

        return news_items, sentiment_data

    async def _fetch_rag_reports(self, keywords: List[str]) -> List[RAGSource]:
        """检索研报"""
        if not keywords:
            return []

        try:
            query = " ".join(keywords[:3])
            docs = await asyncio.to_thread(
                self.rag_agent.search_reports,
                query,
                5
            )

            return [
                RAGSource(
                    filename=doc["file_name"],
                    page=doc["page_number"],
                    content_snippet=doc.get("content", "")[:200],
                    score=doc["score"]
                )
                for doc in docs
            ]
        except Exception as e:
            print(f"[RAG] 研报检索失败: {e}")
            return []

    async def _summarize_news_items(
        self,
        _session_id: str,  # 暂时不使用，保留接口兼容
        news_items: List[NewsItem]
    ) -> List[SummarizedNewsItem]:
        """
        使用 LLM 批量总结新闻标题

        简化版：不使用 NewsRAGService，直接用一次 LLM 调用批量总结
        """
        if not news_items:
            return []

        try:
            from openai import AsyncOpenAI
            import json

            # 创建 LLM 客户端 (使用 DeepSeek)
            llm_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com"
            )

            # 构建批量总结 prompt
            news_text = ""
            for i, item in enumerate(news_items, 1):
                content_preview = item.content[:200] if item.content else ""
                news_text += f"{i}. 标题: {item.title}\n   内容: {content_preview}\n\n"

            prompt = f"""你是一个金融新闻编辑。请对以下 {len(news_items)} 条新闻进行总结：

{news_text}

要求:
1. 为每条新闻生成一个简洁的摘要标题 (不超过25字)
2. 为每条新闻生成一个简短的内容摘要 (不超过60字)
3. 保持客观中立，去除标题党成分
4. 突出与股票/金融相关的关键信息

请严格按照以下 JSON 数组格式输出，不要输出任何其他内容:
[
  {{"index": 1, "summarized_title": "...", "summarized_content": "..."}},
  {{"index": 2, "summarized_title": "...", "summarized_content": "..."}},
  ...
]"""

            response = await llm_client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )

            # 解析 LLM 返回的 JSON
            response_text = response.choices[0].message.content.strip()
            # 处理可能的 markdown 代码块
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            summaries = json.loads(response_text)

            # 构建结果
            result = []
            for i, item in enumerate(news_items):
                # 找到对应的总结
                summary = next((s for s in summaries if s.get("index") == i + 1), None)
                if summary:
                    result.append(SummarizedNewsItem(
                        summarized_title=summary.get("summarized_title", item.title[:50]),
                        summarized_content=summary.get("summarized_content", item.content[:100] if item.content else ""),
                        original_title=item.title,
                        url=item.url,
                        published_date=item.published_date,
                        source_type=item.source_type
                    ))
                else:
                    # 降级：使用原标题
                    result.append(SummarizedNewsItem(
                        summarized_title=item.title[:50] if len(item.title) > 50 else item.title,
                        summarized_content=item.content[:100] if item.content else "",
                        original_title=item.title,
                        url=item.url,
                        published_date=item.published_date,
                        source_type=item.source_type
                    ))

            print(f"[News] LLM 批量总结完成: {len(result)} 条")
            return result

        except Exception as e:
            print(f"[News] LLM 总结失败，使用原标题: {e}")
            # 降级：使用原标题
            return [
                SummarizedNewsItem(
                    summarized_title=n.title[:50] if len(n.title) > 50 else n.title,
                    summarized_content=n.content[:100] if n.content else "",
                    original_title=n.title,
                    url=n.url,
                    published_date=n.published_date,
                    source_type=n.source_type
                )
                for n in news_items
            ]

    async def _analyze_sentiment(self, sentiment_data: dict) -> dict:
        """分析情感"""
        if not sentiment_data or sentiment_data.get("news_count", 0) == 0:
            return {"score": 0, "description": "中性"}

        try:
            news_df = sentiment_data.get("news_df")
            tavily_results = sentiment_data.get("tavily_results", {})

            if tavily_results.get("count", 0) > 0:
                result = await asyncio.to_thread(
                    self.sentiment_agent.analyze_with_links,
                    news_df,
                    tavily_results
                )
            elif news_df is not None and not news_df.empty:
                result = await asyncio.to_thread(
                    self.sentiment_agent.analyze,
                    news_df
                )
            else:
                return {"score": 0, "description": "中性"}

            return {
                "score": result.get("overall_score", 0),
                "description": result.get("sentiment", "中性"),
                "raw": result
            }
        except Exception as e:
            print(f"[Sentiment] 分析失败: {e}")
            return {"score": 0, "description": "中性"}

    async def _run_forecast(
        self,
        df,
        model: str,
        horizon: int,
        prophet_params: dict
    ) -> dict:
        """运行预测模型"""
        if model == "prophet":
            forecaster = ProphetForecaster()
            return await asyncio.to_thread(forecaster.forecast, df, horizon, prophet_params)
        elif model == "xgboost":
            forecaster = XGBoostForecaster()
            return await asyncio.to_thread(forecaster.forecast, df, horizon)
        elif model == "randomforest":
            forecaster = RandomForestForecaster()
            return await asyncio.to_thread(forecaster.forecast, df, horizon)
        else:  # dlinear
            forecaster = DLinearForecaster()
            return await asyncio.to_thread(forecaster.forecast, df, horizon)

    def _df_to_points(self, df, is_prediction: bool = False) -> List[TimeSeriesPoint]:
        """DataFrame 转换为时序数据点"""
        points = []
        for _, row in df.iterrows():
            points.append(TimeSeriesPoint(
                date=str(row["ds"].date()) if hasattr(row["ds"], "date") else str(row["ds"]),
                value=float(row["y"]),
                is_prediction=is_prediction
            ))
        return points

    def _forecast_to_points(self, forecast: List[dict]) -> List[TimeSeriesPoint]:
        """预测结果转换为时序数据点"""
        return [
            TimeSeriesPoint(
                date=item["date"],
                value=item["value"],
                is_prediction=True
            )
            for item in forecast
        ]

    # ========== 非预测流程 ==========

    async def _execute_chat_v3(
        self,
        message: Message,
        session: Session,
        user_input: str,
        intent: UnifiedIntent,
        stock_match: Optional[StockMatchResult],
        keywords: ResolvedKeywords,
        conversation_history: List[dict]
    ):
        """
        执行非预测流程 (V3)

        根据工具开关并行获取数据，生成带引用的 Markdown 回答
        """
        # 确定步骤号 (股票验证后)
        step_num = 3 if intent.stock_mention else 2

        # === 并行数据获取 ===
        message.update_step_detail(step_num, "running", "获取相关信息...")

        tasks = []
        task_names = []

        # RAG 检索
        if intent.enable_rag:
            tasks.append(self._fetch_rag_reports(keywords.rag_keywords))
            task_names.append("rag")

        # 网络搜索
        if intent.enable_search:
            tasks.append(self._search_web(keywords.search_keywords))
            task_names.append("search")

        # 领域信息
        if intent.enable_domain_info:
            stock_code = stock_match.stock_info.stock_code if stock_match and stock_match.stock_info else ""
            tasks.append(self._fetch_domain_news(stock_code, keywords.domain_keywords))
            task_names.append("domain")

        results = {}
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for name, result in zip(task_names, task_results):
                if not isinstance(result, Exception):
                    results[name] = result

        message.update_step_detail(step_num, "completed", f"获取完成: {list(results.keys())}")

        # === 生成回答 ===
        step_num += 1
        message.update_step_detail(step_num, "running", "生成回答...")

        # 构建上下文
        context_parts = []

        if "rag" in results and results["rag"]:
            context_parts.append("=== 研报内容 ===")
            for source in results["rag"][:5]:
                context_parts.append(f"[{source.filename} 第{source.page}页]: {source.content_snippet}")

        if "search" in results and results["search"]:
            context_parts.append("\n=== 网络搜索 ===")
            for item in results["search"][:5]:
                context_parts.append(f"[{item.get('title', '')}]({item.get('url', '')}): {item.get('content', '')[:100]}")

        if "domain" in results and results["domain"]:
            context_parts.append("\n=== 即时新闻 ===")
            for item in results["domain"][:5]:
                title = item.get('title', '')
                url = item.get('url', '')
                content = item.get('content', '')[:100]
                # 如果有 URL，使用 markdown 链接格式
                if url:
                    context_parts.append(f"[{title}]({url}): {content}")
                else:
                    context_parts.append(f"- {title}: {content}")

        context = "\n".join(context_parts) if context_parts else ""

        # 生成回答
        answer = await asyncio.to_thread(
            self.intent_agent.generate_chat_response,
            user_input,
            conversation_history,
            context
        )

        message.save_conclusion(answer)

        # 保存来源
        if "rag" in results:
            message.save_rag_sources(results["rag"])

        message.update_step_detail(step_num, "completed", "回答完成")

    async def _search_web(self, keywords: List[str]) -> List[dict]:
        """网络搜索"""
        if not keywords:
            return []

        try:
            from app.data import TavilyNewsClient
            tavily_client = TavilyNewsClient(settings.tavily_api_key)
            query = " ".join(keywords[:3])
            result = await asyncio.to_thread(
                tavily_client.search,
                query=query,
                days=30,
                max_results=10
            )
            return result.get("results", [])
        except Exception as e:
            print(f"[Search] 搜索失败: {e}")
            return []

    async def _fetch_domain_news(self, stock_code: str, keywords: List[str]) -> List[dict]:
        """获取领域新闻 (AkShare)"""
        if not stock_code and not keywords:
            return []

        try:
            if stock_code:
                news_df = await asyncio.to_thread(DataFetcher.fetch_news, stock_code, 20)
            else:
                # 如果没有股票代码，尝试搜索关键词
                # 这里简化处理，返回空
                return []

            if news_df is None or news_df.empty:
                return []

            items = []
            for _, row in news_df.head(10).iterrows():
                items.append({
                    "title": row.get("新闻标题", ""),
                    "content": row.get("新闻内容", "")[:200] if row.get("新闻内容") else "",
                    "url": row.get("新闻链接", ""),  # AkShare 可能提供新闻链接
                    "date": str(row.get("发布时间", ""))
                })
            return items
        except Exception as e:
            print(f"[Domain] 获取新闻失败: {e}")
            return []


# ========== 兼容旧版 ==========

class UnifiedTaskProcessor(UnifiedTaskProcessorV3):
    """兼容旧版名称"""
    pass


# 单例获取
_task_processor: Optional[UnifiedTaskProcessorV3] = None


def get_task_processor(api_key: str) -> UnifiedTaskProcessorV3:
    """获取任务处理器单例"""
    global _task_processor
    if _task_processor is None:
        _task_processor = UnifiedTaskProcessorV3(api_key)
    return _task_processor
