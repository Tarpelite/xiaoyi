"""
统一任务处理器
==============

核心架构:
- 统一意图识别 (UnifiedIntent)
- 股票 RAG 匹配 (当 stock_mention 非空时)
- 并行数据获取 (股票数据 + 新闻 + 研报)
- Session/Message 分离管理
  - Session: 存储对话历史，用于 LLM 上下文
  - Message: 存储单轮分析结果，用于前端展示
"""

import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Optional, List

from app.core.session import Session, Message
from app.core.config import settings
from app.schemas.session_schema import (
    TimeSeriesPoint,
    UnifiedIntent,
    ResolvedKeywords,
    StockMatchResult,
    SummarizedNewsItem,
    ReportItem,
    RAGSource,
    NewsItem,
)

# Services
from app.services.stock_matcher import get_stock_matcher
from app.services.rag_client import check_rag_availability

# Agents
from app.agents import (
    IntentAgent,
    ReportAgent,
    ErrorExplainerAgent,
    SentimentAgent,
    NewsSummaryAgent,
)

# Data clients
from app.data import TavilyNewsClient
from app.data.rag_searcher import RAGSearcher

# Data & Models
from app.data import DataFetcher, format_datetime, extract_domain
from app.data.fetcher import DataFetchError
from app.models import (
    TimeSeriesAnalyzer,
    ProphetForecaster,
    XGBoostForecaster,
    RandomForestForecaster,
    DLinearForecaster
)


class UnifiedTaskProcessor:
    """
    统一任务处理器

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
        self.rag_searcher = RAGSearcher()
        self.report_agent = ReportAgent(api_key)
        self.error_explainer = ErrorExplainerAgent(api_key)
        self.sentiment_agent = SentimentAgent(api_key)
        self.news_summary_agent = NewsSummaryAgent(api_key)
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

            # 保存意图识别的思考日志
            intent_thinking = f"判断结果:\n- 范围内: {intent.is_in_scope}\n- 预测任务: {intent.is_forecast}\n- 股票提及: {intent.stock_mention}\n- 启用RAG: {intent.enable_rag}\n- 启用搜索: {intent.enable_search}\n- 原因: {intent.reason}"
            message.append_thinking_log("intent", "意图识别", intent_thinking)

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
                await self._execute_forecast(
                    message, session, user_input, intent, stock_match_result,
                    resolved_keywords, conversation_history
                )
            else:
                await self._execute_chat(
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
                await self._execute_forecast(
                    message, session, user_input, intent, stock_match_result,
                    resolved_keywords, conversation_history
                )
            else:
                await self._execute_chat(
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
            print(f"❌ execute_after_intent error: {traceback.format_exc()}")
            message.mark_error(str(e))
            raise

    # ========== 预测流程 ==========

    async def _execute_forecast(
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
        执行预测流程

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

        # === 阶段 2: 数据获取 (并行，但股票数据优先保存) ===
        message.update_step_detail(3, "running", "获取历史数据和新闻...")

        # 设置日期范围
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=intent.history_days)).strftime("%Y%m%d")

        # 创建并行任务
        stock_data_task = asyncio.create_task(self._fetch_stock_data(stock_code, start_date, end_date))
        news_task = asyncio.create_task(self._fetch_news_combined(stock_code, stock_name, keywords, intent.history_days))
        # 检查 RAG 可用性，不可用时跳过（避免等待超时）
        rag_available = await check_rag_availability() if intent.enable_rag else False
        rag_task = asyncio.create_task(self._fetch_rag_reports(keywords.rag_keywords)) if intent.enable_rag and rag_available else None

        # 优先等待股票数据，获取后立即保存（让前端尽快显示图表）
        try:
            stock_result = await stock_data_task
        except Exception as e:
            stock_result = e

        # 处理股票数据获取结果
        df = None
        if isinstance(stock_result, DataFetchError):
            # 使用 ErrorExplainerAgent 生成友好的错误解释
            error_explanation = await asyncio.to_thread(
                self.error_explainer.explain_data_fetch_error,
                stock_result,
                user_input
            )
            message.save_conclusion(error_explanation)
            message.update_step_detail(3, "error", "数据获取失败")
            # 取消其他任务
            news_task.cancel()
            if rag_task:
                rag_task.cancel()
            return
        elif isinstance(stock_result, Exception):
            message.save_conclusion(f"获取数据时发生错误: {str(stock_result)}")
            message.update_step_detail(3, "error", "数据获取失败")
            news_task.cancel()
            if rag_task:
                rag_task.cancel()
            return
        else:
            df = stock_result

        if df is None or df.empty:
            message.save_conclusion(f"无法获取 {stock_name} 的历史数据，请检查股票代码是否正确。")
            message.update_step_detail(3, "error", "数据获取失败")
            news_task.cancel()
            if rag_task:
                rag_task.cancel()
            return

        # 🚀 立即保存股票数据，前端可以先显示历史价格图表
        original_points = self._df_to_points(df, is_prediction=False)
        message.save_time_series_original(original_points)
        print(f"[UnifiedTask] 股票数据已保存 ({len(df)} 天)，等待新闻获取...")

        # 等待新闻和 RAG 任务完成
        pending_tasks = [news_task]
        if rag_task:
            pending_tasks.append(rag_task)

        other_results = await asyncio.gather(*pending_tasks, return_exceptions=True)

        news_result = other_results[0] if not isinstance(other_results[0], Exception) else ([], {})
        rag_sources = other_results[1] if len(other_results) > 1 and not isinstance(other_results[1], Exception) and intent.enable_rag else []

        news_items, sentiment_result = news_result
        # 使用 LLM 总结新闻标题
        if news_items:
            summarized_news, news_summary_raw = await self._summarize_news_items(session.session_id, news_items)
            # 保存新闻总结的思考日志
            if news_summary_raw:
                message.append_thinking_log("news_summary", "新闻总结", news_summary_raw)
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
        print(f"[Emotion Debug] emotion_result: {emotion_result}")
        if emotion_result:
            # 从 raw 中获取 LLM 生成的描述
            raw = emotion_result.get("raw", {})
            # 优先使用 analysis_text，其次从 formatted_text 提取，最后降级到 sentiment
            llm_description = raw.get("analysis_text") or ""
            if not llm_description and raw.get("formatted_text"):
                # 从 formatted_text 提取纯文本（去除 markdown 格式）
                formatted = raw.get("formatted_text", "")
                if "**分析说明:**" in formatted:
                    llm_description = formatted.split("**分析说明:**")[-1].strip()
                else:
                    llm_description = formatted
            description = llm_description or emotion_result.get("description", "中性")
            # 确保 description 不为空字符串
            if not description or not description.strip():
                description = "中性"

            score = emotion_result.get("score", 0)
            print(f"[Emotion Debug] Saving emotion: score={score}, description={description}")
            message.save_emotion(score, description)

            # 保存情感分析的思考日志
            raw_response = emotion_result.get("raw", {}).get("raw_response", "")
            if raw_response:
                message.append_thinking_log("sentiment", "情感分析", raw_response)
        else:
            # emotion_result 为空时，保存默认值确保前端能显示
            print("[Emotion Debug] emotion_result is empty, saving default emotion")
            message.save_emotion(0, "中性")

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

        report_result = await asyncio.to_thread(
            self.report_agent.generate,
            user_input,
            features,
            forecast_result,
            emotion_result or {},  # 使用分析后的情绪结果，包含 score 和 description
            conversation_history
        )

        # 处理报告生成结果（现在返回字典）
        report_content = report_result.get("content", str(report_result)) if isinstance(report_result, dict) else report_result
        message.save_conclusion(report_content)

        # 保存报告生成的思考日志
        if isinstance(report_result, dict) and report_result.get("raw_response"):
            message.append_thinking_log("report", "报告生成", report_result["raw_response"])

        message.update_step_detail(6, "completed", "报告生成完成")

    async def _fetch_stock_data(self, stock_code: str, start_date: str, end_date: str):
        """获取股票历史数据，遇到错误时抛出 DataFetchError"""
        raw_df = await asyncio.to_thread(
            DataFetcher.fetch_stock_data,
            stock_code, start_date, end_date
        )
        df = await asyncio.to_thread(DataFetcher.prepare, raw_df)
        return df

    async def _fetch_news_combined(
        self,
        stock_code: str,
        stock_name: str,
        keywords: ResolvedKeywords,
        history_days: int = 30
    ) -> tuple:
        """
        获取合并新闻 (AkShare + Tavily)

        简化版：各取前5条，共10条新闻

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            keywords: 解析后的关键词
            history_days: 历史数据天数，新闻搜索范围与此保持一致

        Returns:
            (news_items, sentiment_data)
        """
        news_items = []
        tavily_results = {"results": [], "count": 0}
        news_df = None

        # 计算新闻搜索的时间范围（与历史数据保持一致）
        news_end_date = datetime.now().strftime("%Y-%m-%d")
        news_start_date = (datetime.now() - timedelta(days=history_days)).strftime("%Y-%m-%d")

        # AkShare 新闻 (取前5条)
        try:
            news_df = await asyncio.to_thread(DataFetcher.fetch_news, stock_code, 20)
        except Exception as e:
            print(f"[News] AkShare 获取失败: {e}")

        # Tavily 新闻 (取前5条)
        # 使用精确时间范围搜索，配合 CN_FINANCE_DOMAINS 白名单获取相关中文新闻
        try:
            tavily_client = TavilyNewsClient(settings.tavily_api_key)
            tavily_results = await asyncio.to_thread(
                tavily_client.search_stock_news,
                stock_name=stock_name,  # 直接使用股票名称
                start_date=news_start_date,
                end_date=news_end_date,
                max_results=5  # 只取5条
            )
            print(f"[News] Tavily 搜索时间范围: {news_start_date} ~ {news_end_date}")
        except Exception as e:
            print(f"[News] Tavily 获取失败: {e}")

        # 转换 AkShare 新闻 (前5条)
        if news_df is not None and not news_df.empty:
            for _, row in news_df.head(5).iterrows():  # 只取5条
                news_items.append(NewsItem(
                    title=row.get("新闻标题", ""),
                    content=row.get("新闻内容", "")[:300] if row.get("新闻内容") else "",
                    url=str(row.get("新闻链接", "")),
                    published_date=format_datetime(str(row.get("发布时间", ""))),
                    source_type="domain_info",
                    source_name=str(row.get("文章来源", ""))  # AKShare 直接提供来源
                ))

        # 转换 Tavily 新闻 (前5条)
        for item in tavily_results.get("results", [])[:5]:  # 只取5条
            url = item.get("url", "")
            # Tavily API 不返回日期，使用客户端从 URL 提取的日期
            pub_date = item.get("published_date") or ""
            news_items.append(NewsItem(
                title=item.get("title", ""),
                content=item.get("content", "")[:300],
                url=url,
                published_date=format_datetime(pub_date) if pub_date else "-",
                source_type="search",
                source_name=extract_domain(url)  # 从 URL 提取域名
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
                self.rag_searcher.search_reports,
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
    ) -> tuple:
        """
        使用 NewsSummaryAgent 批量总结新闻标题

        Returns:
            (summarized_news_list, raw_llm_response)
        """
        if not news_items:
            return [], ""

        # 使用 asyncio.to_thread 调用同步 Agent
        return await asyncio.to_thread(
            self.news_summary_agent.summarize,
            news_items
        )

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

    async def _execute_chat(
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
        执行非预测流程

        根据工具开关并行获取数据，生成带引用的 Markdown 回答
        """
        # 确定步骤号 (股票验证后)
        step_num = 3 if intent.stock_mention else 2

        # === 并行数据获取 ===
        message.update_step_detail(step_num, "running", "获取相关信息...")

        tasks = []
        task_names = []

        # RAG 检索（先检查可用性，避免等待超时）
        if intent.enable_rag:
            rag_available = await check_rag_availability()
            if rag_available:
                tasks.append(self._fetch_rag_reports(keywords.rag_keywords))
                task_names.append("rag")

        # 网络搜索（使用与历史数据相同的时间范围）
        if intent.enable_search:
            tasks.append(self._search_web(keywords.search_keywords, intent.history_days))
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

    async def _search_web(self, keywords: List[str], history_days: int = 30) -> List[dict]:
        """
        网络搜索

        Args:
            keywords: 搜索关键词列表
            history_days: 搜索时间范围（天数），与历史数据保持一致
        """
        if not keywords:
            return []

        try:
            tavily_client = TavilyNewsClient(settings.tavily_api_key)
            query = " ".join(keywords[:3])

            # 计算时间范围
            search_end_date = datetime.now().strftime("%Y-%m-%d")
            search_start_date = (datetime.now() - timedelta(days=history_days)).strftime("%Y-%m-%d")

            result = await asyncio.to_thread(
                tavily_client.search,
                query=query,
                start_date=search_start_date,
                end_date=search_end_date,
                max_results=10
            )
            print(f"[Search] 网络搜索时间范围: {search_start_date} ~ {search_end_date}")
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


# 单例获取
_task_processor: Optional[UnifiedTaskProcessor] = None


def get_task_processor(api_key: str) -> UnifiedTaskProcessor:
    """获取任务处理器单例"""
    global _task_processor
    if _task_processor is None:
        _task_processor = UnifiedTaskProcessor(api_key)
    return _task_processor
