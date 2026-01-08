"""
统一任务处理器
===============

复刻 chat.py 的逻辑到异步模式
支持 forecast/rag/news/chat 四种意图
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from app.core.session import Session
from app.core.config import settings
from app.schemas.session_schema import (
    SessionStatus,
    TimeSeriesPoint,
    NewsItem,
    RAGSource,
    EmotionAnalysis
)

# Agents
from app.agents import IntentAgent, RAGAgent, FinanceChatAgent

# Data & Models
from app.data import DataFetcher
from app.models import (
    TimeSeriesAnalyzer,
    ProphetForecaster,
    XGBoostForecaster,
    RandomForestForecaster,
    DLinearForecaster
)

# Sentiment
from app.sentiment import SentimentAnalyzer


class UnifiedTaskProcessor:
    """统一任务处理器"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.intent_agent = IntentAgent(api_key)
        self.rag_agent = RAGAgent(api_key)
        self.finance_agent = FinanceChatAgent(api_key)
        self.sentiment_analyzer = SentimentAnalyzer(api_key)

    async def execute(
        self,
        session_id: str,
        user_input: str,
        model_name: str = "prophet",
        force_intent: Optional[str] = None
    ):
        """
        执行统一任务

        Args:
            session_id: 会话 ID
            user_input: 用户输入
            model_name: 预测模型名称
            force_intent: 强制指定意图
        """
        session = Session(session_id)

        try:
            # 获取对话历史
            conversation_history = session.get_conversation_history()

            # Step 0: 意图识别
            if force_intent:
                intent = force_intent
                intent_result = {
                    "intent": force_intent,
                    "reason": "用户强制指定",
                    "tools": self._get_tools_for_intent(force_intent),
                    "model": model_name,
                    "params": {"history_days": 365, "forecast_horizon": 30}
                }
            else:
                intent_result = await asyncio.to_thread(
                    self.intent_agent.judge_intent, user_input, conversation_history
                )
                intent = self._determine_intent(intent_result)

            # 保存意图结果（会自动初始化步骤）
            session.save_intent_result(intent, intent_result)

            # 路由到对应处理器
            if intent == "forecast":
                await self._execute_forecast(session, user_input, intent_result, conversation_history)
            elif intent == "rag":
                await self._execute_rag(session, user_input, conversation_history)
            elif intent == "news":
                await self._execute_news(session, user_input, conversation_history)
            else:  # chat
                await self._execute_chat(session, user_input, conversation_history)

            # 标记完成
            session.mark_completed_v2()

            # 添加助手回复到对话历史
            data = session.get()
            if data and data.conclusion:
                session.add_conversation_message("assistant", data.conclusion)

        except Exception as e:
            import traceback
            print(f"❌ Task execution error: {traceback.format_exc()}")
            session.mark_error(str(e))
            raise

    def _determine_intent(self, intent_result: dict) -> str:
        """从意图识别结果确定执行意图"""
        tools = intent_result.get("tools", {})
        intent = intent_result.get("intent", "analyze")

        if tools.get("report_rag"):
            return "rag"
        if tools.get("news_rag") and not tools.get("forecast"):
            return "news"
        if tools.get("forecast") or intent == "analyze":
            return "forecast"
        return "chat"

    def _get_tools_for_intent(self, intent: str) -> dict:
        """根据意图获取 tools 配置"""
        mapping = {
            "forecast": {"forecast": True, "report_rag": False, "news_rag": False},
            "rag": {"forecast": False, "report_rag": True, "news_rag": False},
            "news": {"forecast": False, "report_rag": False, "news_rag": True},
            "chat": {"forecast": False, "report_rag": False, "news_rag": False},
        }
        return mapping.get(intent, {"forecast": False, "report_rag": False, "news_rag": False})

    # ========== 预测流程（7步） ==========

    async def _execute_forecast(
        self,
        session: Session,
        user_input: str,
        intent_result: dict,
        conversation_history: List[dict]
    ):
        """执行预测分析流程"""
        params = intent_result.get("params", {})
        model = intent_result.get("model", "prophet")
        history_days = params.get("history_days", 365)
        forecast_horizon = params.get("forecast_horizon", 30)

        # Step 1: 数据获取与预处理
        session.update_step_detail(1, "running", "解析用户需求...")

        # NLP 解析
        parsed = await asyncio.to_thread(
            self.finance_agent.nlp.parse, user_input, conversation_history
        )
        data_config = parsed["data_config"]
        analysis_config = parsed["analysis_config"]

        # 设置日期范围
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=history_days)).strftime("%Y%m%d")
        if "params" not in data_config:
            data_config["params"] = {}
        data_config["params"]["start_date"] = start_date
        data_config["params"]["end_date"] = end_date

        session.update_step_detail(1, "running", f"获取 {history_days} 天历史数据...")

        # 获取数据
        raw_df = await asyncio.to_thread(DataFetcher.fetch, data_config)
        df = await asyncio.to_thread(DataFetcher.prepare, raw_df, data_config)

        # 保存原始时序数据
        original_points = self._df_to_points(df, is_prediction=False)
        session.save_time_series_original(original_points)

        # 保存股票代码
        stock_symbol = data_config.get("params", {}).get("symbol", "")
        stock_name = analysis_config.get("stock_name", user_input)
        data = session.get()
        if data:
            data.stock_code = stock_symbol
            session._save(data)

        session.update_step_detail(1, "completed", f"已获取历史数据 {len(df)} 天")

        # Step 2: 新闻获取与情绪分析（始终使用 AkShare + Tavily）
        session.update_step_detail(2, "running", "获取相关新闻...")

        news_list, sentiment_result = await self._fetch_news_and_sentiment(
            stock_symbol, stock_name
        )
        session.save_news(news_list)

        if sentiment_result:
            emotion = EmotionAnalysis(
                score=sentiment_result.get("overall_score", 0),
                description=sentiment_result.get("sentiment", "中性")
            )
            session.save_emotion(emotion)

        session.update_step_detail(
            2, "completed",
            f"情绪: {sentiment_result.get('sentiment', '中性')} (得分: {sentiment_result.get('overall_score', 0):.2f})"
        )

        # Step 3: 时序特征分析
        session.update_step_detail(3, "running", "分析时序特征...")

        features = await asyncio.to_thread(TimeSeriesAnalyzer.analyze_features, df)

        session.update_step_detail(
            3, "completed",
            f"趋势: {features['trend']}, 波动性: {features['volatility']}"
        )

        # Step 4: 参数智能推荐
        session.update_step_detail(4, "running", "根据情绪推荐模型参数...")

        prophet_params = await asyncio.to_thread(
            self.sentiment_analyzer.recommend_params, sentiment_result, features
        )

        session.update_step_detail(
            4, "completed",
            f"推荐参数已生成: {prophet_params.get('reasoning', '')[:30]}..."
        )

        # Step 5: 模型训练与预测
        session.update_step_detail(5, "running", f"训练 {model.upper()} 模型，预测 {forecast_horizon} 天...")

        forecast_result = await self._run_forecast(df, model, forecast_horizon, prophet_params)

        metrics_info = ", ".join([f"{k.upper()}: {v}" for k, v in forecast_result['metrics'].items()])
        session.update_step_detail(5, "completed", f"{forecast_result['model'].upper()} 完成 ({metrics_info})")

        # Step 6: 结果可视化（保存完整时序数据）
        session.update_step_detail(6, "running", "生成图表中...")

        # 合并历史和预测数据
        full_points = original_points + self._forecast_to_points(forecast_result["forecast"])
        prediction_start = forecast_result["forecast"][0]["date"] if forecast_result["forecast"] else ""
        session.save_time_series_full(full_points, prediction_start)

        session.update_step_detail(6, "completed", "图表已生成")

        # Step 7: 报告生成
        session.update_step_detail(7, "running", "生成分析报告...")

        user_question = analysis_config.get("user_question", user_input)
        report = await asyncio.to_thread(
            self.finance_agent.reporter.generate,
            user_question, features, forecast_result, sentiment_result, conversation_history
        )
        session.save_conclusion(report)

        session.update_step_detail(7, "completed", "分析报告已生成")

    async def _fetch_news_and_sentiment(
        self,
        stock_symbol: str,
        stock_name: str
    ) -> tuple:
        """
        获取新闻和情绪分析

        分析请求始终使用 AkShare + Tavily 双数据源
        """
        news_items = []
        tavily_results = {"results": [], "count": 0}

        # AkShare 新闻（始终获取）
        news_df = await asyncio.to_thread(DataFetcher.fetch_news, stock_symbol, 50)

        # Tavily 新闻（始终获取，用于补充和提供链接）
        try:
            from app.news import TavilyNewsClient
            tavily_client = TavilyNewsClient(settings.tavily_api_key)
            tavily_results = await asyncio.to_thread(
                tavily_client.search_stock_news,
                stock_name=stock_name,
                days=30,
                max_results=10
            )
            print(f"[Tavily] 找到 {tavily_results['count']} 条新闻")

            # 转换为 NewsItem
            for item in tavily_results.get("results", []):
                news_items.append(NewsItem(
                    title=item.get("title", ""),
                    summary=item.get("content", "")[:200],
                    date=item.get("published_date", ""),
                    source="Tavily",
                    url=item.get("url", "")
                ))
        except Exception as e:
            print(f"[Tavily] 搜索失败（降级为仅 AkShare）: {e}")

        # AkShare 新闻转换
        if news_df is not None and not news_df.empty:
            for _, row in news_df.head(10).iterrows():
                news_items.append(NewsItem(
                    title=row.get("新闻标题", ""),
                    summary=row.get("新闻内容", "")[:200] if row.get("新闻内容") else "",
                    date=str(row.get("发布时间", "")),
                    source="AkShare",
                    url=""
                ))

        # 情绪分析（始终使用带链接版本，因为始终有 Tavily）
        sentiment_result = {}
        if tavily_results.get("count", 0) > 0:
            # 有 Tavily 结果：使用带链接分析
            sentiment_result = await asyncio.to_thread(
                self.sentiment_analyzer.analyze_with_links,
                news_df, tavily_results
            )
        elif news_df is not None and not news_df.empty:
            # 仅 AkShare：使用原有分析
            sentiment_result = await asyncio.to_thread(
                self.sentiment_analyzer.analyze, news_df
            )
        else:
            sentiment_result = {"sentiment": "中性", "overall_score": 0, "news_count": 0}

        return news_items, sentiment_result

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
        """DataFrame 转换为时序数据点列表"""
        points = []
        for _, row in df.iterrows():
            points.append(TimeSeriesPoint(
                date=str(row["ds"].date()) if hasattr(row["ds"], "date") else str(row["ds"]),
                value=float(row["y"]),
                is_prediction=is_prediction
            ))
        return points

    def _forecast_to_points(self, forecast: List[dict]) -> List[TimeSeriesPoint]:
        """预测结果转换为时序数据点列表"""
        points = []
        for item in forecast:
            points.append(TimeSeriesPoint(
                date=item["date"],
                value=item["value"],
                is_prediction=True
            ))
        return points

    # ========== RAG 流程（2步） ==========

    async def _execute_rag(
        self,
        session: Session,
        user_input: str,
        conversation_history: List[dict]
    ):
        """执行 RAG 研报检索流程"""
        # Step 1: 研报检索
        session.update_step_detail(1, "running", "正在检索相关研报...")

        retrieved_docs = await asyncio.to_thread(
            self.rag_agent.search_reports, user_input, 5
        )

        # 保存 RAG 来源
        sources = [
            RAGSource(
                file_name=doc["file_name"],
                page_number=doc["page_number"],
                score=doc["score"],
                content=doc.get("content", "")[:200]
            )
            for doc in retrieved_docs
        ]
        session.save_rag_sources(sources)

        session.update_step_detail(1, "completed", f"找到 {len(sources)} 条相关内容")

        # Step 2: 生成回答
        session.update_step_detail(2, "running", "基于研报内容生成回答...")

        answer = await asyncio.to_thread(
            self.rag_agent.generate_answer, user_input, retrieved_docs, conversation_history
        )
        session.save_conclusion(answer)

        session.update_step_detail(2, "completed", "回答生成完成")

    # ========== 新闻流程（3步） ==========

    async def _execute_news(
        self,
        session: Session,
        user_input: str,
        conversation_history: List[dict]
    ):
        """执行新闻搜索流程"""
        from app.news import TavilyNewsClient

        # Step 1: 解析查询，提取关键词
        session.update_step_detail(1, "running", "正在解析搜索意图...")

        try:
            # 使用 LLM 提取关键词
            keyword_result = await asyncio.to_thread(
                self.intent_agent.extract_search_keywords,
                user_input
            )
            keywords = keyword_result.get("keywords", user_input)
            is_stock = keyword_result.get("is_stock", False)
            stock_name = keyword_result.get("stock_name", "")
            stock_code = keyword_result.get("stock_code", "")

            print(f"[News] 关键词提取: keywords={keywords}, is_stock={is_stock}, stock_name={stock_name}, stock_code={stock_code}")

            session.update_step_detail(1, "completed", f"关键词: {keywords}")

            # Step 2: 新闻搜索
            session.update_step_detail(2, "running", "正在搜索相关新闻...")

            tavily_client = TavilyNewsClient(settings.tavily_api_key)
            tavily_results = {"results": [], "count": 0}
            akshare_news_df = None
            news_items = []

            # 根据是否股票相关选择数据源
            if is_stock and stock_code:
                # 股票相关：使用 AkShare + Tavily
                print(f"[News] 股票搜索模式: AkShare + Tavily")

                akshare_news_df = await asyncio.to_thread(DataFetcher.fetch_news, stock_code, 50)
                tavily_results = await asyncio.to_thread(
                    tavily_client.search_stock_news,
                    stock_name=stock_name or keywords,
                    days=30,
                    max_results=10
                )

                # AkShare 新闻转换
                if akshare_news_df is not None and not akshare_news_df.empty:
                    for _, row in akshare_news_df.head(10).iterrows():
                        news_items.append(NewsItem(
                            title=row.get("新闻标题", ""),
                            summary=row.get("新闻内容", "")[:200] if row.get("新闻内容") else "",
                            date=str(row.get("发布时间", "")),
                            source="AkShare",
                            url=""
                        ))
            else:
                # 非股票：仅 Tavily（使用中文域名过滤）
                print(f"[News] 通用搜索模式: Tavily only")
                tavily_results = await asyncio.to_thread(
                    tavily_client.search_stock_news,
                    stock_name=keywords,
                    days=30,
                    max_results=10
                )

            # Tavily 新闻转换
            for item in tavily_results.get("results", []):
                news_items.append(NewsItem(
                    title=item.get("title", ""),
                    summary=item.get("content", "")[:200],
                    date=item.get("published_date", ""),
                    source="Tavily",
                    url=item.get("url", "")
                ))

            session.save_news(news_items)

            akshare_count = len(akshare_news_df) if akshare_news_df is not None and not akshare_news_df.empty else 0
            tavily_count = tavily_results.get("count", 0)
            total_count = akshare_count + tavily_count

            print(f"[News] 找到新闻: AkShare={akshare_count}, Tavily={tavily_count}, 总计={total_count}")

            session.update_step_detail(2, "completed", f"找到 {total_count} 条相关新闻")

            # Step 3: 新闻总结
            session.update_step_detail(3, "running", "生成新闻摘要...")

            # 构建综合新闻上下文
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

            # 流式生成转为同步
            full_answer = ""
            for chunk in self.intent_agent.summarize_news_stream(user_input, news_context, conversation_history):
                full_answer += chunk

            session.save_conclusion(full_answer)
            session.update_step_detail(3, "completed", "总结完成")

        except ValueError as e:
            session.update_step_detail(1, "error", f"新闻搜索服务未配置: {str(e)}")
            session.save_conclusion(f"新闻搜索服务未配置: {str(e)}")
        except Exception as e:
            session.update_step_detail(1, "error", f"新闻搜索失败: {str(e)}")
            session.save_conclusion(f"新闻搜索失败: {str(e)}")

    # ========== 对话流程（1步） ==========

    async def _execute_chat(
        self,
        session: Session,
        user_input: str,
        conversation_history: List[dict]
    ):
        """执行纯对话流程"""
        # Step 1: 生成回答
        session.update_step_detail(1, "running", "生成回答...")

        # 流式生成转为同步
        full_answer = ""
        for chunk in self.intent_agent.answer_question_stream(user_input, conversation_history):
            full_answer += chunk

        session.save_conclusion(full_answer)
        session.update_step_detail(1, "completed", "回答完成")


# 单例获取
_task_processor: Optional[UnifiedTaskProcessor] = None


def get_task_processor(api_key: str) -> UnifiedTaskProcessor:
    """获取任务处理器单例"""
    global _task_processor
    if _task_processor is None:
        _task_processor = UnifiedTaskProcessor(api_key)
    return _task_processor
