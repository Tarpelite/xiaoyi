"""
流式任务处理器
===============

完全流式架构 - 所有步骤的输出都通过 SSE 实时返回
支持断点续传：流式数据同时存入 Redis
"""

import asyncio
import json
import traceback
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable, Awaitable

from app.core.session import Session, Message
from app.core.redis_client import get_redis
from app.schemas.session_schema import (
    TimeSeriesPoint,
    UnifiedIntent,
    ResolvedKeywords,
    StockMatchResult,
    SummarizedNewsItem,
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
from app.data.rag_searcher import RAGSearcher
import pandas as pd
from app.services.trend_service import TrendService
from app.services.stock_signal_service import StockSignalService
from app.agents.event_summary_agent import EventSummaryAgent


# Data & Models
from app.data.fetcher import DataFetchError
from app.models import TimeSeriesAnalyzer

# Workflows
from app.core.workflows import (
    fetch_stock_data,
    fetch_news_all,
    fetch_rag_reports,
    search_web,
    fetch_domain_news,
    run_forecast,
    df_to_points,
    recommend_forecast_params,
    select_best_model,
)


class StreamingTaskProcessor:
    """
    流式任务处理器

    核心流程（全程流式）:
    1. 意图识别 - 流式返回思考过程
    2. 股票验证 - 返回匹配结果
    3. 数据获取 - 返回历史数据和新闻
    4. 分析处理 - 返回特征和情绪
    5. 模型预测 - 返回预测结果
    6. 报告生成 - 流式返回报告内容
    """

    # Baseline 惩罚机制开关
    # True: 启用惩罚机制，用户指定模型不如 baseline 时降级为 baseline
    # False: 禁用惩罚机制，即使最佳模型不如 baseline 也使用最佳模型
    ENABLE_BASELINE_PENALTY = False

    def __init__(self):
        self.intent_agent = IntentAgent()
        self.rag_searcher = RAGSearcher()
        self.report_agent = ReportAgent()
        self.error_explainer = ErrorExplainerAgent()
        self.sentiment_agent = SentimentAgent()
        self.news_summary_agent = NewsSummaryAgent()
        self.stock_matcher = get_stock_matcher()
        self.redis = get_redis()

    async def execute_streaming(
        self,
        session_id: str,
        message_id: str,
        user_input: str,
        event_queue: asyncio.Queue | None,
        model_name: Optional[str] = None,
    ):
        """
        执行完全流式任务

        Args:
            session_id: 会话 ID
            message_id: 消息 ID
            user_input: 用户输入
            event_queue: 事件队列（发送到 SSE，后台任务时为 None）
            model_name: 预测模型名称
        """
        session = Session(session_id)
        message = Message(message_id, session_id)

        # 设置流式状态
        self._update_stream_status(message, "streaming")

        try:
            conversation_history = session.get_conversation_history()

            # === Step 1: 意图识别（流式） ===
            await self._emit_event(
                event_queue,
                message,
                {"type": "step_start", "step": 1, "step_name": "意图识别"},
            )

            message.update_step_detail(1, "running", "分析用户意图...")

            intent, thinking_content = await self._step_intent_streaming(
                user_input, conversation_history, event_queue, message
            )

            if not intent:
                await self._emit_error(event_queue, message, "意图识别失败")
                return

            # 如果用户通过 API 指定了模型，覆盖意图识别的结果
            # print(f"[ModelSelection] API 传入的 model_name: {model_name}")
            # print(f"[ModelSelection] 意图识别返回的 forecast_model: {intent.forecast_model}")
            if model_name is not None:
                intent.forecast_model = model_name
                # print(f"[ModelSelection] 使用 API 指定的模型: {model_name}")
            else:
                # 如果用户没有通过 API 指定模型，且 LLM 返回的是 "prophet"（可能是默认值），
                # 则将其设为 None，触发自动模型选择
                intent.forecast_model = None

            # 保存意图
            message.save_unified_intent(intent)
            message.append_thinking_log("intent", "意图识别", thinking_content)

            # 发送意图结果
            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "intent",
                    "intent": "forecast" if intent.is_forecast else "chat",
                    "is_forecast": intent.is_forecast,
                    "reason": intent.reason,
                },
            )

            # 处理超出范围
            if not intent.is_in_scope:
                reply = (
                    intent.out_of_scope_reply
                    or "抱歉，我是金融时序分析助手，暂不支持此类问题。"
                )
                message.save_conclusion(reply)
                message.update_step_detail(1, "completed", "超出服务范围")
                message.mark_completed()
                self._update_stream_status(message, "completed")
                await self._emit_event(
                    event_queue,
                    message,
                    {"type": "chat_chunk", "content": reply, "is_complete": True},
                )
                await self._emit_done(event_queue, message)
                return

            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "step_complete",
                    "step": 1,
                    "data": {"intent": "forecast" if intent.is_forecast else "chat"},
                },
            )
            message.update_step_detail(
                1, "completed", f"意图: {'预测' if intent.is_forecast else '对话'}"
            )

            # === Step 2: 股票验证 ===
            stock_match_result = None
            resolved_keywords = None

            if intent.stock_mention:
                await self._emit_event(
                    event_queue,
                    message,
                    {"type": "step_start", "step": 2, "step_name": "股票验证"},
                )

                query_name = intent.stock_full_name or intent.stock_mention
                message.update_step_detail(2, "running", f"验证股票: {query_name}")

                stock_match_result = await asyncio.to_thread(
                    self.stock_matcher.match, query_name
                )

                message.save_stock_match(stock_match_result)

                if not stock_match_result.success:
                    error_msg = stock_match_result.error_message or "股票验证失败"
                    message.save_conclusion(error_msg)
                    message.update_step_detail(2, "error", error_msg)
                    message.mark_completed()
                    self._update_stream_status(message, "error")
                    await self._emit_error(event_queue, message, error_msg)
                    return

                stock_info = stock_match_result.stock_info
                resolved_keywords = self.intent_agent.resolve_keywords(
                    intent,
                    stock_name=stock_info.stock_name if stock_info else None,
                    stock_code=stock_info.stock_code if stock_info else None,
                )
                message.save_resolved_keywords(resolved_keywords)

                await self._emit_event(
                    event_queue,
                    message,
                    {
                        "type": "step_complete",
                        "step": 2,
                        "data": {
                            "stock_code": stock_info.stock_code if stock_info else "",
                            "stock_name": stock_info.stock_name if stock_info else "",
                        },
                    },
                )
                message.update_step_detail(
                    2,
                    "completed",
                    f"匹配: {stock_info.stock_name}({stock_info.stock_code})"
                    if stock_info
                    else "无匹配",
                )
            else:
                resolved_keywords = ResolvedKeywords(
                    search_keywords=intent.raw_search_keywords,
                    rag_keywords=intent.raw_rag_keywords,
                    domain_keywords=intent.raw_domain_keywords,
                )

            # === 根据意图执行不同流程 ===
            if intent.is_forecast:
                await self._execute_forecast_streaming(
                    message,
                    session,
                    user_input,
                    intent,
                    stock_match_result,
                    resolved_keywords,
                    conversation_history,
                    event_queue,
                )
            else:
                await self._execute_chat_streaming(
                    message,
                    session,
                    user_input,
                    intent,
                    stock_match_result,
                    resolved_keywords,
                    conversation_history,
                    event_queue,
                )

            # 标记完成
            message.mark_completed()
            self._update_stream_status(message, "completed")

            # 添加助手回复到对话历史
            data = message.get()
            if data and data.conclusion:
                session.add_conversation_message("assistant", data.conclusion)

            await self._emit_done(event_queue, message)

        except Exception as e:
            print(f"❌ Streaming task error: {traceback.format_exc()}")
            message.mark_error(str(e))
            self._update_stream_status(message, "error")
            await self._emit_error(event_queue, message, str(e))

    # ========== 流式意图识别 ==========

    async def _step_intent_streaming(
        self,
        user_input: str,
        conversation_history: List[dict],
        event_queue: asyncio.Queue | None,
        message: Message,
    ) -> tuple:
        """流式意图识别"""
        import queue as thread_queue

        chunk_queue: thread_queue.Queue = thread_queue.Queue()

        def on_chunk(chunk: str):
            """同步回调 - 放入线程安全队列"""
            chunk_queue.put(chunk)

        def run_intent():
            """在线程中运行意图识别"""
            result = self.intent_agent.recognize_intent_streaming(
                user_input, conversation_history, on_chunk
            )
            chunk_queue.put(None)  # 结束标记
            return result

        # 启动线程任务
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(None, run_intent)

        # 轮询队列，通过 _emit_event 发送事件
        thinking_content = ""
        while True:
            try:
                chunk = chunk_queue.get_nowait()
                if chunk is None:
                    break
                thinking_content += chunk
                await self._emit_event(
                    event_queue,
                    message,
                    {"type": "thinking", "content": thinking_content},
                )
            except thread_queue.Empty:
                if future.done():
                    # 处理剩余的 chunks
                    while not chunk_queue.empty():
                        chunk = chunk_queue.get_nowait()
                        if chunk is not None:
                            thinking_content += chunk
                            await self._emit_event(
                                event_queue,
                                message,
                                {"type": "thinking", "content": thinking_content},
                            )
                    break
                await asyncio.sleep(0.01)

        intent, final_thinking = await future
        return intent, final_thinking or thinking_content

    # ========== 预测流程（流式） ==========

    async def _execute_forecast_streaming(
        self,
        message: Message,
        session: Session,
        user_input: str,
        intent: UnifiedIntent,
        stock_match: Optional[StockMatchResult],
        keywords: ResolvedKeywords,
        conversation_history: List[dict],
        event_queue: asyncio.Queue | None,
    ):
        """流式预测流程"""
        stock_info = stock_match.stock_info if stock_match else None
        stock_code = stock_info.stock_code if stock_info else ""
        stock_name = stock_info.stock_name if stock_info else user_input

        # === Step 3: 数据获取 ===
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_start", "step": 3, "step_name": "数据获取"},
        )
        message.update_step_detail(3, "running", "获取历史数据和新闻...")

        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=intent.history_days)).strftime(
            "%Y%m%d"
        )

        # 并行获取数据
        stock_data_task = asyncio.create_task(
            fetch_stock_data(stock_code, start_date, end_date)
        )
        news_task = asyncio.create_task(
            fetch_news_all(stock_code, stock_name, intent.history_days)
        )
        rag_available = await check_rag_availability() if intent.enable_rag else False
        rag_task = (
            asyncio.create_task(
                fetch_rag_reports(self.rag_searcher, keywords.rag_keywords)
            )
            if intent.enable_rag and rag_available
            else None
        )

        # 优先获取股票数据
        try:
            stock_result = await stock_data_task
        except Exception as e:
            stock_result = e

        # 处理股票数据
        df = None
        if isinstance(stock_result, DataFetchError):
            error_explanation = await asyncio.to_thread(
                self.error_explainer.explain_data_fetch_error, stock_result, user_input
            )
            message.save_conclusion(error_explanation)
            message.update_step_detail(3, "error", "数据获取失败")
            news_task.cancel()
            if rag_task:
                rag_task.cancel()
            await self._emit_error(event_queue, message, error_explanation)
            return
        elif isinstance(stock_result, Exception):
            error_msg = f"获取数据时发生错误: {str(stock_result)}"
            message.save_conclusion(error_msg)
            message.update_step_detail(3, "error", "数据获取失败")
            news_task.cancel()
            if rag_task:
                rag_task.cancel()
            await self._emit_error(event_queue, message, error_msg)
            return
        else:
            df = stock_result

        if df is None or df.empty:
            error_msg = f"无法获取 {stock_name} 的历史数据，请检查股票代码是否正确。"
            message.save_conclusion(error_msg)
            message.update_step_detail(3, "error", "数据获取失败")
            news_task.cancel()
            if rag_task:
                rag_task.cancel()
            await self._emit_error(event_queue, message, error_msg)
            return

        # 立即保存并发送股票数据
        original_points = df_to_points(df, is_prediction=False)
        message.save_time_series_original(original_points)

        await self._emit_event(
            event_queue,
            message,
            {
                "type": "data",
                "data_type": "time_series_original",
                "data": [p.model_dump() for p in original_points],
            },
        )

        # 等待新闻和 RAG
        pending_tasks = [news_task]
        if rag_task:
            pending_tasks.append(rag_task)

        other_results = await asyncio.gather(*pending_tasks, return_exceptions=True)

        news_result = (
            other_results[0]
            if not isinstance(other_results[0], Exception)
            else ([], {})
        )
        rag_sources = (
            other_results[1]
            if len(other_results) > 1
            and not isinstance(other_results[1], Exception)
            and intent.enable_rag
            else []
        )

        news_items, sentiment_result = news_result

        # 总结新闻 - 直接调用 Agent
        if news_items:
            summarized_news, _ = await asyncio.to_thread(
                self.news_summary_agent.summarize, news_items
            )
        else:
            summarized_news = []

        message.save_news(summarized_news)

        # 发送新闻数据
        if summarized_news:
            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "data",
                    "data_type": "news",
                    "data": [n.model_dump() for n in summarized_news],
                },
            )

        # [DEBUG] Check flow
        print(
            f"[DEBUG] _execute_forecast_streaming: rag_sources count={len(rag_sources) if rag_sources else 0}"
        )
        if rag_sources:
            message.save_rag_sources(rag_sources)
            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "data",
                    "data_type": "rag_sources",
                    "data": [source.model_dump() for source in rag_sources],
                },
            )

        # === 计算异常区域（在Step 3完成前，确保resume时能获取到）===
        print(
            f"[AnomalyZones] Starting dynamic clustering for message {message.message_id}"
        )
        try:
            import pandas as pd

            # from app.services.stock_signal_service import StockSignalService  # Re-enabled
            from app.services.trend_service import TrendService
            from app.services.stock_signal_service import StockSignalService

            # from app.services.anomaly_service import AnomalyService # Deprecated
            from app.agents.event_summary_agent import EventSummaryAgent

            # 从 df 提取日期、收盘价、成交量
            sig_df = pd.DataFrame(
                {
                    "date": df["ds"].dt.strftime("%Y-%m-%d"),
                    "close": df["y"],
                    "volume": df.get("volume", [1] * len(df)),
                }
            )

            # 构建新闻计数字典（按日期）
            news_counts = {}
            for news_item in summarized_news or []:
                try:
                    date_key = (
                        news_item.published_date[:10]
                        if news_item.published_date
                        else None
                    )
                    if date_key:
                        news_counts[date_key] = news_counts.get(date_key, 0) + 1
                except Exception as e:
                    pass

            # === Redis 全局缓存检查 ===
            redis_client = get_redis()
            cache_key = f"stock_zones_v5:{stock_code}"  # Version 5: Switched to StockSignalService
            cached_data_json = None

            try:
                cached_data_json = redis_client.get(cache_key)
                if cached_data_json:
                    import json

                    cached_data = json.loads(cached_data_json)
                    anomaly_zones = cached_data.get("zones", [])
                    semantic_zones = cached_data.get("semantic_zones", [])
                    anomalies = cached_data.get("anomalies", [])
                    print(
                        f"[AnomalyZones] ✓ Using Redis cached {len(anomaly_zones)} raw zones, {len(semantic_zones)} semantic zones for {stock_code}"
                    )
            except Exception as e:
                print(f"[AnomalyZones] Redis cache read error: {e}")
                cached_data_json = None
                anomaly_zones = []
                semantic_zones = []
                anomalies = []

            # 如果缓存不存在，计算并保存
            if not cached_data_json:
                # 1. Trend Analysis (Regime Segmentation)
                trend_service = TrendService()
                # Use all methods but prefer PLR for visual zones
                trend_results = trend_service.analyze_trend(sig_df, method="plr")

                # Debug Prints for Trend Algorithms
                print("\n" + "=" * 50)

                print(
                    f"\nBottom-Up PLR (Trend Lines): Found {len(trend_results.get('plr', []))} segments"
                )
                for i, seg in enumerate(trend_results.get("plr", [])[:3]):
                    print(
                        f"   - Segment {i + 1}: {seg['startDate']} to {seg['endDate']} ({seg['direction']})"
                    )
                print("=" * 50 + "\n")

                # Map PLR segments to anomaly_zones format expected by frontend
                plr_segments = trend_results.get("plr", [])

                # Combine all segments for frontend selection
                all_segments = []
                # Re-enable all algorithms as user wants full data
                all_segments.extend(plr_segments)

                # NEW: Generate Semantic Broad Regimes (Merged PLR)
                # This creates broad "Event Flow" phases
                semantic_raw = trend_service.process_semantic_regimes(
                    plr_segments, min_duration_days=7
                )
                semantic_zones = []

                for seg in semantic_raw:
                    # Determine sentiment/color
                    sentiment = "neutral"
                    direction = seg.get("direction", "").lower()
                    seg_type = seg.get("type", "").lower()

                    if direction == "up" or seg_type == "bull":
                        sentiment = "positive"
                    elif direction == "down" or seg_type == "bear":
                        sentiment = "negative"

                    # Calculate return
                    try:
                        start_p = float(seg.get("startPrice", 0))
                        end_p = float(seg.get("endPrice", 0))
                        change_pct = (end_p - start_p) / start_p if start_p else 0
                    except:
                        change_pct = 0

                    semantic_zones.append(
                        {
                            "startDate": seg["startDate"],
                            "endDate": seg["endDate"],
                            "avg_return": change_pct,
                            "avg_score": abs(change_pct) * 10,
                            "zone_type": "semantic_regime",
                            "method": "plr_merged",
                            "sentiment": sentiment,
                            "summary": f"{seg.get('direction', seg.get('type', 'Phase')).title()} ({change_pct * 100:.1f}%)",
                            "description": f"Phase from {seg['startDate']} to {seg['endDate']}. Return: {change_pct * 100:.1f}%",
                            "type": seg_type,
                            "normalizedType": seg_type,
                            "direction": direction,
                            "events": [],  # Placeholder for events
                        }
                    )

                anomaly_zones = []
                for seg in all_segments:
                    # Determine sentiment/color
                    sentiment = "neutral"
                    direction = seg.get("direction", "").lower()
                    seg_type = seg.get("type", "").lower()  # HMM uses type

                    if direction == "up" or seg_type == "bull":
                        sentiment = "positive"
                    elif direction == "down" or seg_type == "bear":
                        sentiment = "negative"

                    # Calculate simple impact/score
                    # HMM segments might have avgPrice, change based on start/end
                    # Ensure keys exist
                    start_p = seg.get("startPrice", seg.get("avgPrice", 1.0))
                    end_p = seg.get("endPrice", seg.get("avgPrice", 1.0))

                    # NEW: Try to use actual prices from raw data if available (passed via args or lookup)
                    # We don't have price_map easily accessible here without passing it into process_semantic_regimes
                    # But anomaly_segments usually come from significant point detection which uses raw data.
                    # For now, trust the segment data but ensure 0 handling.

                    change_pct = (end_p - start_p) / start_p if start_p else 0

                    anomaly_zones.append(
                        {
                            "startDate": seg["startDate"],
                            "endDate": seg["endDate"],
                            "avg_return": change_pct,
                            "avg_score": abs(change_pct) * 10,  # Mock score
                            "zone_type": "trend_segment",  # New type
                            "method": seg.get(
                                "method", "plr"
                            ),  # Default to plr if missing
                            "sentiment": sentiment,  # Explicit sentiment for frontend
                            "summary": f"{seg.get('direction', seg.get('type', 'Trend')).title()} ({change_pct * 100:.1f}%)",  # Used as fallback title
                            "description": f"Trend detected from {seg['startDate']} to {seg['endDate']}. Return: {change_pct * 100:.1f}%",  # Detail text
                            "type": seg_type,  # Pass original type (for HMM/Frontend logic)
                            "normalizedType": seg_type,  # Ensure compatibility
                            "direction": direction,  # Pass original direction (for PLR)
                        }
                    )

                # Enhance summaries with RAG/News context if available
                # Logic: Find news items falling within the segment's date range
                # Enhance summaries with RAG/News context if available
                # Logic: Find news items falling within the segment's date range
                if summarized_news:
                    # 1. Attach news to Raw Zones (anomaly_zones)
                    for zone in anomaly_zones:
                        try:
                            # Use pd from outer scope
                            z_start = pd.to_datetime(zone["startDate"])
                            z_end = pd.to_datetime(zone["endDate"])

                            relevant_titles = []
                            for news in summarized_news:
                                # summarized_news items have 'published_date' field
                                n_date = pd.to_datetime(news.published_date)
                                # Check if news falls within the zone or close to it (within 3 days padding to catch lead/lag)
                                if (
                                    (z_start - pd.Timedelta(days=3))
                                    <= n_date
                                    <= (z_end + pd.Timedelta(days=3))
                                ):
                                    # Fix: Use summarized_title if available (SummarizedNewsItem)
                                    title = getattr(
                                        news,
                                        "summarized_title",
                                        getattr(news, "title", ""),
                                    )
                                    relevant_titles.append(title)

                            if relevant_titles:
                                # Prioritize LLM summarized title for rich narrative
                                zone["summary"] = relevant_titles[0]
                        except Exception as e:
                            print(f"[AnomalyZones] Error matching news to zone: {e}")
                            continue

                    # 2. Attach news to Semantic Sub-Events (semantic_zones -> events)
                    # This ensures the "Event Flow" tooltip has text!
                    for s_zone in semantic_zones:
                        for event in s_zone.get("events", []):
                            # Strategy A: Match against ALREADY ENRICHED raw anomaly_zones
                            # This is preferred because they might have "Title (Correction)" format
                            found_match = False
                            for raw in anomaly_zones:
                                if (
                                    raw["startDate"] == event["startDate"]
                                    and raw["endDate"] == event["endDate"]
                                ):
                                    # Use event_summary if available (from Agent), else fallback to summary
                                    event["summary"] = raw.get(
                                        "event_summary", raw.get("summary", "")
                                    )
                                    found_match = True
                                    break

                            # Strategy B: Fallback to direct news search if no raw match found
                            if not found_match:
                                try:
                                    z_start = pd.to_datetime(event["startDate"])
                                    z_end = pd.to_datetime(event["endDate"])
                                    relevant_titles = []
                                    for news in summarized_news:
                                        n_date = pd.to_datetime(news.published_date)
                                        if (
                                            (z_start - pd.Timedelta(days=2))
                                            <= n_date
                                            <= (z_end + pd.Timedelta(days=2))
                                        ):
                                            # Use LLM summarized title if available, else original
                                            title = getattr(
                                                news,
                                                "summarized_title",
                                                getattr(news, "title", ""),
                                            )
                                            relevant_titles.append(title)
                                    if relevant_titles:
                                        # Use the first relevant title
                                        event["summary"] = relevant_titles[0]
                                except Exception as e:
                                    print(f"[SemanticEvent] Error attaching news: {e}")
                                    pass

                    # 3. Generate concatenated "Event Flow" summary for each semantic zone
                    # This is what appears in the tooltip when hovering over a semantic zone
                    for s_zone in semantic_zones:
                        events = s_zone.get("events", [])
                        if events:
                            # Sort events by startDate to maintain chronological order
                            sorted_events = sorted(
                                events, key=lambda e: e.get("startDate", "")
                            )
                            # Concatenate summaries with arrow separator for flow
                            event_summaries = [
                                e.get("summary", "阶段性事件") for e in sorted_events
                            ]
                            s_zone["event_flow_summary"] = " → ".join(event_summaries)
                            print(
                                f"[SemanticZone] {s_zone['startDate']} - {s_zone['endDate']}: Event Flow = {s_zone['event_flow_summary']}"
                            )
                        else:
                            # Fallback if no sub-events
                            s_zone["event_flow_summary"] = s_zone.get(
                                "summary", "语义合并区间"
                            )

                # 2. Anomaly Detection (Local Anomalies)
                # 2. Anomaly Detection (Significant Points via StockSignalService)
                # Replaced old 3 algorithms (BCPD/STL/Matrix) with singular StockSignalService
                signal_service = StockSignalService()

                # Calculate significant points
                # Returns list of {date, score, type, reason, is_pivot}
                significant_points = signal_service.calculate_points(
                    sig_df, news_counts, top_k=15
                )

                # Create price lookup map
                price_map = pd.Series(sig_df.close.values, index=sig_df.date).to_dict()

                anomalies = []
                print(
                    f"\n🚨 [Anomaly] StockSignalService found {len(significant_points)} points"
                )

                for pt in significant_points:
                    pt_date = pt["date"]
                    price = price_map.get(pt_date)
                    if price is None:
                        continue

                    anomalies.append(
                        {
                            "method": "signal_service",  # Uniform method name
                            "date": pt_date,
                            "price": float(price),
                            "score": pt["score"],
                            "description": pt["reason"] or "Significant Event",
                            "significance": pt.get(
                                "type", "neutral"
                            ),  # positive/negative
                            "is_pivot": pt.get("is_pivot", False),
                        }
                    )
                    print(
                        f"   - Point: {pt_date} (Score: {pt['score']}) - {pt['reason']}"
                    )

                # Sort by date
                anomalies.sort(key=lambda x: x["date"])

                # Validate anomaly data structure
                valid_anomalies = []
                for anom in anomalies:
                    # Ensure all required fields exist
                    if all(
                        key in anom
                        for key in ["method", "date", "price", "score", "description"]
                    ):
                        # Ensure date format is YYYY-MM-DD
                        if (
                            len(anom["date"]) == 10
                            and anom["date"][4] == "-"
                            and anom["date"][7] == "-"
                        ):
                            valid_anomalies.append(anom)
                        else:
                            print(
                                f"[AnomalyZones] ⚠️ Invalid date format for anomaly: {anom['date']}"
                            )
                    else:
                        missing = [
                            k
                            for k in ["method", "date", "price", "score", "description"]
                            if k not in anom
                        ]
                        print(
                            f"[AnomalyZones] ⚠️ Anomaly missing required fields: {missing}"
                        )

                anomalies = valid_anomalies

                print(
                    f"[AnomalyZones] ⚙️ Generated {len(anomaly_zones)} zones and {len(anomalies)} valid anomalies"
                )

            # 为每个区域生成事件摘要（仅当不是从缓存读取时）
            # FIXED: Generate summaries for RAW ZONES (anomaly_zones) instead of semantic zones
            # Semantic zones will use concatenated summaries from their sub-events
            if anomaly_zones and not cached_data_json:
                try:
                    event_agent = EventSummaryAgent()

                    # 导入MongoDB client（从stock_db.py）
                    from app.data.stock_db import get_mongo_client

                    mongo_client = None

                    try:
                        mongo_client = get_mongo_client()
                        # 使用环境变量配置数据库和集合名称
                        # 使用环境变量配置数据库和集合名称
                        from app.core.config import settings

                        db_name = settings.MONGODB_DATABASE
                        collection_name = settings.MONGODB_COLLECTION
                        news_collection = mongo_client[db_name][collection_name]

                        # define helper function for parallel execution
                        def process_single_zone(zone):
                            try:
                                start = zone["startDate"]
                                end = zone["endDate"]

                                # 使用正则表达式查询区域内的新闻
                                zone_dates = []
                                current = datetime.strptime(start, "%Y-%m-%d")
                                end_dt = datetime.strptime(end, "%Y-%m-%d")
                                while current <= end_dt:
                                    zone_dates.append(current.strftime("%Y-%m-%d"))
                                    current += timedelta(days=1)

                                # 从MongoDB查询这些日期的所有内容
                                regex_pattern = "^(" + "|".join(zone_dates) + ")"
                                zone_news_cursor = news_collection.find(
                                    {
                                        "stock_code": stock_code,
                                        "publish_time": {"$regex": regex_pattern},
                                    }
                                ).limit(20)

                                zone_news_dicts = []
                                for news_doc in zone_news_cursor:
                                    zone_news_dicts.append(
                                        {
                                            "title": news_doc.get("title", ""),
                                            "content_type": news_doc.get(
                                                "content_type", "资讯"
                                            ),
                                            "publish_time": news_doc.get(
                                                "publish_time", ""
                                            ),
                                        }
                                    )

                                # 使用Agent生成摘要
                                event_summary = event_agent.summarize_zone(
                                    zone_dates=zone_dates,
                                    price_change=zone.get("avg_return", 0) * 100,
                                    news_items=zone_news_dicts,
                                )
                                return zone, event_summary
                            except Exception as e:
                                print(
                                    f"[AnomalyZones] Error processing zone {zone.get('startDate')}: {e}"
                                )
                                return zone, None

                        # Use ThreadPoolExecutor for parallel processing
                        import concurrent.futures

                        with concurrent.futures.ThreadPoolExecutor(
                            max_workers=5
                        ) as executor:
                            future_to_zone = {
                                executor.submit(process_single_zone, zone): zone
                                for zone in anomaly_zones
                            }
                            for future in concurrent.futures.as_completed(
                                future_to_zone
                            ):
                                zone, event_summary = future.result()
                                if event_summary:
                                    zone["event_summary"] = event_summary
                                    zone["summary"] = event_summary
                                    print(
                                        f"[AnomalyZones] Zone {zone['startDate']}-{zone['endDate']} summarized"
                                    )

                    finally:
                        if mongo_client:
                            mongo_client.close()

                except Exception as e:
                    import traceback

                    print(f"[AnomalyZones] Error generating event summaries: {e}")
                    print(f"[AnomalyZones] Traceback: {traceback.format_exc()}")
                    # Fallback: 使用简单摘要
                    for zone in anomaly_zones:
                        if "event_summary" not in zone:
                            zone["event_summary"] = (
                                f"价格变化{zone.get('avg_return', 0) * 100:+.1f}%"
                            )
                            zone["summary"] = zone["event_summary"]

            # === 保存到Redis全局缓存 ===
            if not cached_data_json:
                try:
                    import json

                    cache_data = {
                        "zones": anomaly_zones,
                        "semantic_zones": semantic_zones,
                        "anomalies": anomalies,
                    }

                    zones_json = json.dumps(cache_data, ensure_ascii=False)
                    redis_client.setex(
                        cache_key,
                        12 * 60 * 60,  # 12小时TTL
                        zones_json,
                    )
                    print(
                        f"[AnomalyZones] 💾 Saved {len(anomaly_zones)} zones and {len(anomalies)} anomalies to Redis cache (12 hours)"
                    )
                except Exception as e:
                    print(f"[AnomalyZones] Redis cache save error: {e}")

            # 保存并发送异常区域数据
            # We save both zones and points.
            # Use save_anomaly_zones for zones (compatible)
            if anomaly_zones:
                message.save_anomaly_zones(anomaly_zones, stock_code)

            # Save anomaly points (CRITICAL for frontend rendering on refresh)
            if anomalies:
                message.save_anomalies(anomalies)

            # Save semantic zones (history) - CRITICAL for Event Flow tooltip persistence
            if semantic_zones:
                message.save_semantic_zones(semantic_zones)

            # Send combined data
            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "data",
                    "data_type": "anomaly_zones",
                    "data": {
                        "zones": anomaly_zones,
                        "semantic_zones": semantic_zones,
                        "anomalies": anomalies,  # Add anomalies here for frontend
                        "ticker": stock_code,
                    },
                },
            )
            print(f"[AnomalyZones] Successfully saved and emitted")

        except Exception as e:
            import traceback

            print(f"// console.log('[ChatArea]rror: {e}")
            print(f"[AnomalyZones] Traceback:\n{traceback.format_exc()}")

        await self._emit_event(
            event_queue,
            message,
            {
                "type": "step_complete",
                "step": 3,
                "data": {"data_points": len(df), "news_count": len(news_items)},
            },
        )
        message.update_step_detail(
            3, "completed", f"历史数据 {len(df)} 天, 新闻 {len(news_items)} 条"
        )

        # === Step 4: 分析处理（情绪流式输出）===
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_start", "step": 4, "step_name": "分析处理"},
        )
        message.update_step_detail(4, "running", "分析时序特征和市场情绪...")

        # 时序特征分析
        features = await asyncio.to_thread(TimeSeriesAnalyzer.analyze_features, df)

        # 流式情绪分析
        emotion_result = await self._step_sentiment_streaming(
            summarized_news, event_queue, message
        )

        message.save_emotion(
            emotion_result.get("score", 0), emotion_result.get("description", "中性")
        )

        await self._emit_event(
            event_queue,
            message,
            {
                "type": "step_complete",
                "step": 4,
                "data": {
                    "trend": features.get("trend", "N/A"),
                    "emotion": emotion_result.get("description", "中性"),
                },
            },
        )
        message.update_step_detail(
            4,
            "completed",
            f"趋势: {features.get('trend', 'N/A')}, 情绪: {emotion_result.get('description', 'N/A')}",
        )

        # === Step 5: 模型预测 ===
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_start", "step": 5, "step_name": "模型预测"},
        )
        message.update_step_detail(5, "running", f"训练模型...")

        prophet_params = await recommend_forecast_params(
            self.sentiment_agent, emotion_result or {}, features
        )

        # 计算预测天数
        last_date = df["ds"].max().to_pydatetime()
        target_date_from_start = last_date + timedelta(days=90)
        # print(f"[ModelSelection] 目标日期从开始: {target_date_from_start}")
        target_date_to_today = datetime.now()
        # print(f"[ModelSelection] 目标日期到今天: {target_date_to_today}")
        target_date = max(target_date_from_start, target_date_to_today)
        # print(f"[ModelSelection] 目标日期: {target_date}")
        forecast_horizon = max((target_date - last_date).days, 1)
        # print(f"[ModelSelection] 预测天数: {forecast_horizon}")

        # 模型选择：构建候选模型列表
        candidate_models = ["prophet", "xgboost", "randomforest", "dlinear"]
        user_specified_model = intent.forecast_model
        # print(f"[ModelSelection] 用户指定模型: {user_specified_model}")

        # 调用模型选择器
        try:
            selection_result = await select_best_model(
                df, candidate_models, forecast_horizon, n_windows=3, min_train_size=60
            )

            best_model = selection_result["best_model"]
            baseline = selection_result["baseline"]
            model_comparison = selection_result["metrics"]
            is_better_than_baseline = selection_result["is_better_than_baseline"]

            # print(f"[ModelSelection] 选择的最佳模型: {best_model}")
            # print(f"[ModelSelection] Baseline: {baseline}")
            # print(f"[ModelSelection] 用户指定模型: {user_specified_model}")

            # 确定最终使用的模型并生成解释信息
            model_selection_reason = ""
            enable_baseline_penalty = self.ENABLE_BASELINE_PENALTY

            if not user_specified_model or user_specified_model == "auto":
                # print(f"[ModelSelection] 进入自动选择分支")
                # 用户未指定模型，使用最佳模型
                final_model = best_model
                # print(f"[ModelSelection] 最终模型: {final_model}")
                # 生成解释：最佳模型在最近 n_windows 个时间窗口的 MAE 均低于 baseline
                best_mae = model_comparison.get(best_model)
                baseline_mae = model_comparison.get(baseline)

                if best_mae is not None and baseline_mae is not None:
                    model_name_upper = best_model.upper()
                    baseline_name = baseline.replace("_", " ").title()
                    if enable_baseline_penalty and best_mae >= baseline_mae:
                        # 如果启用惩罚机制且最佳模型不如 baseline，使用 baseline
                        final_model = baseline
                        model_selection_reason = (
                            f"最佳模型 {model_name_upper} 在最近 3 个时间窗口的 MAE ({best_mae:.4f}) "
                            f"不优于 {baseline_name} ({baseline_mae:.4f})，已自动降级为 {baseline_name}"
                        )
                    else:
                        model_selection_reason = (
                            f"{model_name_upper} 在最近 3 个时间窗口的 MAE ({best_mae:.4f}) "
                            f"均低于 {baseline_name} ({baseline_mae:.4f})"
                        )
                else:
                    model_selection_reason = (
                        f"自动选择 {best_model.upper()} 作为最佳模型"
                    )
            else:
                # 用户指定了模型
                # print(f"[ModelSelection] 进入用户指定模型分支，用户指定: {user_specified_model}")
                user_model_mae = model_comparison.get(user_specified_model)
                baseline_mae = model_comparison.get(baseline)

                # 根据开关决定是否启用 baseline 惩罚机制
                if enable_baseline_penalty and (
                    user_model_mae is not None
                    and baseline_mae is not None
                    and user_model_mae >= baseline_mae
                ):
                    # 启用惩罚机制：如果用户指定的模型 MAE >= baseline，则降级为 baseline
                    final_model = baseline
                    user_model_name = user_specified_model.upper()
                    baseline_name = baseline.replace("_", " ").title()
                    model_selection_reason = (
                        f"用户指定模型 {user_model_name} 在历史回测中不优于基线 "
                        f"({user_model_mae:.4f} >= {baseline_mae:.4f})，已自动降级为 {baseline_name}"
                    )
                else:
                    # 禁用惩罚机制或用户模型优于 baseline：使用用户指定的模型
                    final_model = user_specified_model
                    user_model_name = user_specified_model.upper()
                    if user_model_mae is not None:
                        if (
                            not enable_baseline_penalty
                            and baseline_mae is not None
                            and user_model_mae >= baseline_mae
                        ):
                            # 禁用惩罚机制但用户模型不如 baseline
                            model_selection_reason = (
                                f"使用用户指定的 {user_model_name} 模型 "
                                f"(历史回测 MAE: {user_model_mae:.4f}，baseline: {baseline_mae:.4f})"
                            )
                        else:
                            model_selection_reason = (
                                f"使用用户指定的 {user_model_name} 模型 "
                                f"(历史回测 MAE: {user_model_mae:.4f})"
                            )
                    else:
                        model_selection_reason = (
                            f"使用用户指定的 {user_model_name} 模型"
                        )

            # 发送模型选择信息
            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "model_selection",
                    "selected_model": final_model,
                    "best_model": best_model,
                    "baseline": baseline,
                    "model_comparison": model_comparison,
                    "is_better_than_baseline": is_better_than_baseline,
                    "user_specified_model": user_specified_model,
                    "model_selection_reason": model_selection_reason,
                },
            )

            # 保存模型选择信息到 Message
            message.save_model_selection(
                final_model, model_comparison, is_better_than_baseline
            )

            # 保存模型选择原因
            message.save_model_selection_reason(model_selection_reason)

            # print(f"[ModelSelection] 最终确定的模型: {final_model}")
            message.update_step_detail(
                5, "running", f"训练 {final_model.upper()} 模型..."
            )

        except Exception as e:
            # 如果模型选择失败，使用用户指定的模型或默认模型
            # print(f"[ModelSelection] 模型选择失败: {e}")
            final_model = user_specified_model or "prophet"
            model_comparison = {}
            is_better_than_baseline = False

            # 生成失败时的解释信息
            if user_specified_model:
                model_selection_reason = f"模型选择过程出现错误，使用用户指定的 {user_specified_model.upper()} 模型"
            else:
                model_selection_reason = (
                    f"模型选择过程出现错误，使用默认的 {final_model.upper()} 模型"
                )

            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "model_selection",
                    "selected_model": final_model,
                    "best_model": final_model,
                    "baseline": "seasonal_naive",
                    "model_comparison": model_comparison,
                    "is_better_than_baseline": is_better_than_baseline,
                    "user_specified_model": user_specified_model,
                    "selection_failed": True,
                    "error": str(e),
                    "model_selection_reason": model_selection_reason,
                },
            )

            # 保存模型选择原因
            message.save_model_selection_reason(model_selection_reason)

        prophet_params = await recommend_forecast_params(
            self.sentiment_agent, emotion_result or {}, features
        )

        # 只对最终选定的模型调用一次 run_forecast
        forecast_result = await run_forecast(
            df, intent.forecast_model, max(forecast_horizon, 1), prophet_params
        )

        # 保存并发送预测结果（forecast_result 是 ForecastResult 对象）
        full_points = original_points + forecast_result.points
        prediction_start = (
            forecast_result.points[0].date if forecast_result.points else ""
        )
        message.save_time_series_full(full_points, prediction_start)

        # === NEW: Calculate Semantic Regimes for Prediction Data ===
        prediction_semantic_zones = []
        if forecast_result.points:
            try:
                # 1. Construct Prediction DataFrame
                pred_df = pd.DataFrame(
                    [
                        {"date": p.date, "close": p.value, "volume": 1}
                        for p in forecast_result.points
                    ]
                )

                # 2. Re-instantiate TrendService (if needed) or use existing
                # Note: trend_service was instantiated in Step 3 logic, might not be in scope if skipped
                # Safest to instantiate distinct service for prediction
                # from app.services.trend_service import TrendService (already imported)
                pred_trend_service = TrendService()

                # 3. Analyze Trend (PLR)
                pred_results = pred_trend_service.analyze_trend(pred_df, method="plr")
                pred_plr = pred_results.get("plr", [])

                # 4. Process Semantic Regimes
                # Use slightly relaxed duration for future (e.g. 5 days) as prediction is smoother?
                # Or keep 7 days. Let's use 7 days.
                pred_semantic_raw = pred_trend_service.process_semantic_regimes(
                    pred_plr, min_duration_days=7
                )

                # 5. Format for Frontend
                for seg in pred_semantic_raw:
                    # Determine sentiment/color
                    direction = seg.get("direction", "").lower()
                    seg_type = seg.get("type", "").lower()

                    sentiment = "neutral"
                    if direction == "up" or seg_type == "bull":
                        sentiment = "positive"
                    elif direction == "down" or seg_type == "bear":
                        sentiment = "negative"

                    start_p = float(seg.get("startPrice", 0))
                    end_p = float(seg.get("endPrice", 0))
                    change_pct = (end_p - start_p) / start_p if start_p else 0

                    prediction_semantic_zones.append(
                        {
                            "startDate": seg["startDate"],
                            "endDate": seg["endDate"],
                            "avg_return": change_pct,
                            "zone_type": "prediction_semantic_regime",
                            "method": "plr_merged_prediction",
                            "sentiment": sentiment,
                            "summary": f"Predicted {seg.get('direction', 'Trend').title()} ({change_pct * 100:.1f}%)",
                            "description": f"Predicted phase from {seg['startDate']} to {seg['endDate']}",
                            "type": seg_type,
                            "displayType": direction
                            or seg_type,  # For frontend coloring
                            "normalizedType": direction or seg_type,
                            "direction": direction,
                            "events": [],  # No real events for future yet
                            "isPrediction": True,  # Flag for frontend if needed
                        }
                    )

                print(
                    f"[PredictionZones] Generated {len(prediction_semantic_zones)} semantic zones for prediction data."
                )

            except Exception as e:
                print(f"[PredictionZones] Error generating prediction regimes: {e}")
                prediction_semantic_zones = []

        # Prepare data for time_series_full event
        # Retrieve current message state safely
        current_msg_data = message.get()
        saved_anomalies = current_msg_data.anomalies if current_msg_data else []
        saved_semantic_zones = (
            current_msg_data.semantic_zones if current_msg_data else []
        )
        saved_anomaly_zones = current_msg_data.anomaly_zones if current_msg_data else []

        # Resolve final variables to ensure data integrity
        final_anomalies = anomalies if "anomalies" in locals() else saved_anomalies
        final_semantic_zones = (
            semantic_zones if "semantic_zones" in locals() else saved_semantic_zones
        )
        final_stock_zones = (
            anomaly_zones if "anomaly_zones" in locals() else saved_anomaly_zones
        )

        # Debugging Output
        print(f"================[ TimeSeriesFull Debug Start ]================")
        print(f"Anomalies in locals: {'anomalies' in locals()}")
        print(f"Anomalies count (Final): {len(final_anomalies)}")
        if len(final_anomalies) > 0:
            print(f"Sample Anomaly: {final_anomalies[0]}")

        print(f"SemanticZones count (Final): {len(final_semantic_zones)}")
        print(f"PredictionZones count: {len(prediction_semantic_zones)}")
        if len(prediction_semantic_zones) > 0:
            print(f"Sample PredictionZone: {prediction_semantic_zones[0]}")
        print(f"================[ TimeSeriesFull Debug End ]==================")

        await self._emit_event(
            event_queue,
            message,
            {
                "type": "data",
                "data_type": "time_series_full",
                "data": [p.model_dump() for p in full_points],
                "prediction_start_day": prediction_start,
                "prediction_semantic_zones": prediction_semantic_zones,
                "anomalies": final_anomalies,
                "semantic_zones": final_semantic_zones,
                "stock_zones": final_stock_zones,
            },
        )

        metrics = forecast_result.metrics
        metrics_dict = {"mae": metrics.mae}
        if metrics.rmse:
            metrics_dict["rmse"] = metrics.rmse
        metrics_info = f"MAE: {metrics.mae}" + (
            f", RMSE: {metrics.rmse}" if metrics.rmse else ""
        )

        # ------------------------------------------------------------------
        # CRITICAL FIX: Atomic Persistence of Analysis Data
        # ------------------------------------------------------------------
        # Before completing the step, we MUST save all generated data (zones, anomalies, time series).
        # We use the new atomic method to prevent partial overwrites.
        message.save_analysis_result(
            time_series_full=full_points,
            prediction_start=prediction_start,
            semantic_zones=final_semantic_zones,
            prediction_zones=prediction_semantic_zones,
            anomalies=final_anomalies,
            anomaly_zones=final_stock_zones,
            ticker=stock_code,
        )

        await self._emit_event(
            event_queue,
            message,
            {"type": "step_complete", "step": 5, "data": {"metrics": metrics_dict}},
        )
        message.update_step_detail(5, "completed", f"预测完成 ({metrics_info})")

        # 保存模型名称到 MessageData（使用最终选定的模型）
        message.save_model_name(final_model)

        # === Step 6: 报告生成（流式） ===
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_start", "step": 6, "step_name": "报告生成"},
        )
        message.update_step_detail(6, "running", "生成分析报告...")

        # 将 ForecastResult 转换为字典格式供报告生成使用
        forecast_dict = {
            "forecast": [
                {"date": p.date, "value": p.value} for p in forecast_result.points
            ],
            "metrics": metrics_dict,
            "model": forecast_result.model,
        }

        report_content = await self._step_report_streaming(
            user_input,
            features,
            forecast_dict,
            emotion_result or {},
            conversation_history,
            event_queue,
            message,
        )

        message.save_conclusion(report_content)
        await self._emit_event(
            event_queue, message, {"type": "step_complete", "step": 6, "data": {}}
        )
        message.update_step_detail(6, "completed", "报告生成完成")

    # ========== 聊天流程（流式） ==========

    async def _execute_chat_streaming(
        self,
        message: Message,
        _session: Session,  # 保留参数以保持接口一致性
        user_input: str,
        intent: UnifiedIntent,
        stock_match: Optional[StockMatchResult],
        keywords: ResolvedKeywords,
        conversation_history: List[dict],
        event_queue: asyncio.Queue | None,
    ):
        """流式聊天流程"""
        step_num = 3 if intent.stock_mention else 2

        # === 数据获取 ===
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_start", "step": step_num, "step_name": "信息获取"},
        )
        message.update_step_detail(step_num, "running", "获取相关信息...")

        tasks = []
        task_names = []

        if intent.enable_rag:
            rag_available = await check_rag_availability()
            if rag_available:
                tasks.append(
                    fetch_rag_reports(self.rag_searcher, keywords.rag_keywords)
                )
                task_names.append("rag")

        if intent.enable_search:
            tasks.append(search_web(keywords.search_keywords, intent.history_days))
            task_names.append("search")

        if intent.enable_domain_info:
            stock_code = (
                stock_match.stock_info.stock_code
                if stock_match and stock_match.stock_info
                else ""
            )
            tasks.append(fetch_domain_news(stock_code, keywords.domain_keywords))
            task_names.append("domain")

        results = {}
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for name, result in zip(task_names, task_results):
                if not isinstance(result, Exception):
                    results[name] = result

        await self._emit_event(
            event_queue,
            message,
            {
                "type": "step_complete",
                "step": step_num,
                "data": {"sources": list(results.keys())},
            },
        )
        message.update_step_detail(
            step_num, "completed", f"获取完成: {list(results.keys())}"
        )

        # === 生成回答（流式） ===
        step_num += 1
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_start", "step": step_num, "step_name": "生成回答"},
        )
        message.update_step_detail(step_num, "running", "生成回答...")

        # 构建上下文
        context_parts = []

        if "rag" in results and results["rag"]:
            context_parts.append("=== 研报内容 ===")
            for source in results["rag"][:5]:
                context_parts.append(
                    f"[{source.filename} 第{source.page}页]: {source.content_snippet}"
                )

        if "search" in results and results["search"]:
            context_parts.append("\n=== 网络搜索 ===")
            for item in results["search"][:5]:
                context_parts.append(
                    f"[{item.get('title', '')}]({item.get('url', '')}): {item.get('content', '')[:100]}"
                )

        if "domain" in results and results["domain"]:
            context_parts.append("\n=== 即时新闻 ===")
            for item in results["domain"][:5]:
                title = item.get("title", "")
                url = item.get("url", "")
                content = item.get("content", "")[:100]
                if url:
                    context_parts.append(f"[{title}]({url}): {content}")
                else:
                    context_parts.append(f"- {title}: {content}")

        context = "\n".join(context_parts) if context_parts else ""

        # 流式生成回答
        answer = await self._step_chat_streaming(
            user_input, conversation_history, context, event_queue, message
        )

        message.save_conclusion(answer)

        if "rag" in results:
            message.save_rag_sources(results["rag"])
            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "data",
                    "data_type": "rag_sources",
                    "data": [source.model_dump() for source in results["rag"]],
                },
            )

        await self._emit_event(
            event_queue,
            message,
            {"type": "step_complete", "step": step_num, "data": {}},
        )
        message.update_step_detail(step_num, "completed", "回答完成")

    # ========== 流式报告生成 ==========

    async def _step_report_streaming(
        self,
        user_input: str,
        features: Dict,
        forecast_result: Dict,
        emotion_result: Dict,
        conversation_history: List[dict],
        event_queue: asyncio.Queue | None,
        message: Message,
    ) -> str:
        """流式报告生成"""
        loop = asyncio.get_running_loop()
        content_queue: asyncio.Queue = asyncio.Queue()

        def run_in_thread():
            def on_chunk(chunk: str):
                loop.call_soon_threadsafe(content_queue.put_nowait, ("chunk", chunk))

            content = self.report_agent.generate_streaming(
                user_input,
                features,
                forecast_result,
                emotion_result,
                conversation_history,
                on_chunk,
            )
            loop.call_soon_threadsafe(content_queue.put_nowait, ("done", content))

        future = loop.run_in_executor(None, run_in_thread)

        full_content = ""
        while True:
            try:
                event_type, data = await asyncio.wait_for(
                    content_queue.get(), timeout=120.0
                )

                if event_type == "chunk":
                    full_content += data
                    await self._emit_event(
                        event_queue,
                        message,
                        {"type": "report_chunk", "content": full_content},
                    )
                elif event_type == "done":
                    full_content = data
                    break
            except asyncio.TimeoutError:
                break

        await future

        return full_content

    # ========== 流式情绪分析 ==========

    async def _step_sentiment_streaming(
        self,
        news_items: List[SummarizedNewsItem],
        event_queue: asyncio.Queue | None,
        message: Message,
    ) -> Dict[str, Any]:
        """流式情绪分析"""
        # 转换为字典列表
        news_list = (
            [
                {
                    "title": n.summarized_title,
                    "content": n.summarized_content,
                    "source_name": n.source_name,
                    "source_type": n.source_type,
                }
                for n in news_items
            ]
            if news_items
            else []
        )

        if not news_list:
            # 无新闻数据，返回默认值
            default_desc = "无新闻数据，默认中性情绪"
            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "data",
                    "data_type": "emotion",
                    "data": {"score": 0.0, "description": default_desc},
                },
            )
            return {"score": 0.0, "description": default_desc}

        loop = asyncio.get_running_loop()
        content_queue: asyncio.Queue = asyncio.Queue()
        result_holder = {"result": None}

        def run_in_thread():
            def on_chunk(chunk: str):
                loop.call_soon_threadsafe(content_queue.put_nowait, ("chunk", chunk))

            result = self.sentiment_agent.analyze_streaming(news_list, on_chunk)
            result_holder["result"] = result
            loop.call_soon_threadsafe(content_queue.put_nowait, ("done", None))

        future = loop.run_in_executor(None, run_in_thread)

        # 实时发送情绪描述
        description_buffer = ""
        score_sent = False

        while True:
            try:
                event_type, data = await asyncio.wait_for(
                    content_queue.get(), timeout=60.0
                )

                if event_type == "chunk":
                    description_buffer += data
                    # 流式发送（score 先设为 0，等完成后更新）
                    if not score_sent:
                        score_sent = True
                    await self._emit_event(
                        event_queue,
                        message,
                        {"type": "emotion_chunk", "content": description_buffer},
                    )
                elif event_type == "done":
                    break
            except asyncio.TimeoutError:
                break

        await future

        # 获取最终结果
        result = result_holder["result"] or {
            "score": 0.0,
            "description": description_buffer or "中性情绪",
        }

        # 发送最终情绪数据
        await self._emit_event(
            event_queue,
            message,
            {
                "type": "data",
                "data_type": "emotion",
                "data": {
                    "score": result["score"],
                    "description": result["description"],
                },
            },
        )

        return result

    # ========== 流式聊天生成 ==========

    async def _step_chat_streaming(
        self,
        user_input: str,
        conversation_history: List[dict],
        context: str,
        event_queue: asyncio.Queue | None,
        message: Message,
    ) -> str:
        """流式聊天生成"""
        loop = asyncio.get_running_loop()
        content_queue: asyncio.Queue = asyncio.Queue()

        def run_in_thread():
            gen = self.intent_agent.generate_chat_response(
                user_input, conversation_history, context, stream=True
            )
            full = ""
            for chunk in gen:
                full += chunk
                loop.call_soon_threadsafe(content_queue.put_nowait, ("chunk", full))
            loop.call_soon_threadsafe(content_queue.put_nowait, ("done", full))

        future = loop.run_in_executor(None, run_in_thread)

        full_content = ""
        while True:
            try:
                event_type, data = await asyncio.wait_for(
                    content_queue.get(), timeout=120.0
                )

                if event_type == "chunk":
                    full_content = data
                    await self._emit_event(
                        event_queue,
                        message,
                        {"type": "chat_chunk", "content": full_content},
                    )
                elif event_type == "done":
                    full_content = data
                    break
            except asyncio.TimeoutError:
                break

        await future
        return full_content

    # ========== 辅助方法 ==========

    def _update_stream_status(self, message: Message, status: str):
        """更新流式状态"""
        data = message.get()
        if data:
            data.stream_status = status
            message._save(data)

    async def _emit_event(
        self, event_queue: asyncio.Queue | None, message: Message, event: Dict
    ):
        """发送事件到队列、PubSub 和 Stream"""

        # 1. 发送到本地队列（如果存在）
        if event_queue:
            await event_queue.put(event)

        try:
            # 2. 即时发布到 PubSub
            channel = f"stream:{message.message_id}"
            json_payload = json.dumps(event)
            self.redis.publish(channel, json_payload)

            # 3. 持久化到 Stream（供断点续传使用）
            stream_key = f"stream-events:{message.message_id}"
            self.redis.xadd(
                stream_key, {"data": json_payload}, maxlen=1000, approximate=True
            )
            self.redis.expire(stream_key, 86400)  # 24小时 TTL

        except Exception as e:
            print(f"[StreamingTask] Event storage error: {e}")

    async def _emit_error(
        self, event_queue: asyncio.Queue | None, message: Message, error_msg: str
    ):
        """发送错误事件"""
        await self._emit_event(
            event_queue, message, {"type": "error", "message": error_msg}
        )

    async def _emit_done(self, event_queue: asyncio.Queue | None, message: Message):
        """发送完成事件"""
        await self._emit_event(
            event_queue, message, {"type": "done", "completed": True}
        )


# 单例
_streaming_processor: Optional[StreamingTaskProcessor] = None


def get_streaming_processor() -> StreamingTaskProcessor:
    """获取流式任务处理器单例"""
    global _streaming_processor
    if _streaming_processor is None:
        _streaming_processor = StreamingTaskProcessor()
    return _streaming_processor
