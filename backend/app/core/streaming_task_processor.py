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
        model_name: Optional[str] = None
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
            await self._emit_event(event_queue, message, {
                "type": "step_start",
                "step": 1,
                "step_name": "意图识别"
            })

            message.update_step_detail(1, "running", "分析用户意图...")

            intent, thinking_content = await self._step_intent_streaming(
                user_input, conversation_history, event_queue, message
            )

            if not intent:
                await self._emit_error(event_queue, message, "意图识别失败")
                return

            # 如果用户通过 API 指定了模型，覆盖意图识别的结果
            print(f"[ModelSelection] API 传入的 model_name: {model_name}")
            print(f"[ModelSelection] 意图识别返回的 forecast_model: {intent.forecast_model}")
            if model_name is not None:
                intent.forecast_model = model_name
                print(f"[ModelSelection] 使用 API 指定的模型: {model_name}")
            else:
                # 如果用户没有通过 API 指定模型，且 LLM 返回的是 "prophet"（可能是默认值），
                # 则将其设为 None，触发自动模型选择
                if intent.forecast_model == "prophet":
                    print(f"[ModelSelection] 检测到 LLM 返回了 'prophet'，将其设为 None 以触发自动选择")
                    intent.forecast_model = None
                else:
                    print(f"[ModelSelection] LLM 返回的模型不是 'prophet'，保持原值: {intent.forecast_model}")

            # 保存意图
            message.save_unified_intent(intent)
            message.append_thinking_log("intent", "意图识别", thinking_content)

            # 发送意图结果
            await self._emit_event(event_queue, message, {
                "type": "intent",
                "intent": "forecast" if intent.is_forecast else "chat",
                "is_forecast": intent.is_forecast,
                "reason": intent.reason
            })

            # 处理超出范围
            if not intent.is_in_scope:
                reply = intent.out_of_scope_reply or "抱歉，我是金融时序分析助手，暂不支持此类问题。"
                message.save_conclusion(reply)
                message.update_step_detail(1, "completed", "超出服务范围")
                message.mark_completed()
                self._update_stream_status(message, "completed")
                await self._emit_event(event_queue, message, {
                    "type": "chat_chunk",
                    "content": reply,
                    "is_complete": True
                })
                await self._emit_done(event_queue, message)
                return

            await self._emit_event(event_queue, message, {
                "type": "step_complete",
                "step": 1,
                "data": {"intent": "forecast" if intent.is_forecast else "chat"}
            })
            message.update_step_detail(1, "completed", f"意图: {'预测' if intent.is_forecast else '对话'}")

            # === Step 2: 股票验证 ===
            stock_match_result = None
            resolved_keywords = None

            if intent.stock_mention:
                await self._emit_event(event_queue, message, {
                    "type": "step_start",
                    "step": 2,
                    "step_name": "股票验证"
                })

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
                    self._update_stream_status(message, "error")
                    await self._emit_error(event_queue, message, error_msg)
                    return

                stock_info = stock_match_result.stock_info
                resolved_keywords = self.intent_agent.resolve_keywords(
                    intent,
                    stock_name=stock_info.stock_name if stock_info else None,
                    stock_code=stock_info.stock_code if stock_info else None
                )
                message.save_resolved_keywords(resolved_keywords)

                await self._emit_event(event_queue, message, {
                    "type": "step_complete",
                    "step": 2,
                    "data": {
                        "stock_code": stock_info.stock_code if stock_info else "",
                        "stock_name": stock_info.stock_name if stock_info else ""
                    }
                })
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

            # === 根据意图执行不同流程 ===
            if intent.is_forecast:
                await self._execute_forecast_streaming(
                    message, session, user_input, intent, stock_match_result,
                    resolved_keywords, conversation_history, event_queue
                )
            else:
                await self._execute_chat_streaming(
                    message, session, user_input, intent, stock_match_result,
                    resolved_keywords, conversation_history, event_queue
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
        message: Message
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
                user_input,
                conversation_history,
                on_chunk
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
                await self._emit_event(event_queue, message, {
                    "type": "thinking",
                    "content": thinking_content
                })
            except thread_queue.Empty:
                if future.done():
                    # 处理剩余的 chunks
                    while not chunk_queue.empty():
                        chunk = chunk_queue.get_nowait()
                        if chunk is not None:
                            thinking_content += chunk
                            await self._emit_event(event_queue, message, {
                                "type": "thinking",
                                "content": thinking_content
                            })
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
        event_queue: asyncio.Queue | None
    ):
        """流式预测流程"""
        stock_info = stock_match.stock_info if stock_match else None
        stock_code = stock_info.stock_code if stock_info else ""
        stock_name = stock_info.stock_name if stock_info else user_input

        # === Step 3: 数据获取 ===
        await self._emit_event(event_queue, message, {
            "type": "step_start",
            "step": 3,
            "step_name": "数据获取"
        })
        message.update_step_detail(3, "running", "获取历史数据和新闻...")

        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=intent.history_days)).strftime("%Y%m%d")

        # 并行获取数据
        stock_data_task = asyncio.create_task(fetch_stock_data(stock_code, start_date, end_date))
        news_task = asyncio.create_task(fetch_news_all(stock_code, stock_name, intent.history_days))
        rag_available = await check_rag_availability() if intent.enable_rag else False
        rag_task = asyncio.create_task(fetch_rag_reports(self.rag_searcher, keywords.rag_keywords)) if intent.enable_rag and rag_available else None

        # 优先获取股票数据
        try:
            stock_result = await stock_data_task
        except Exception as e:
            stock_result = e

        # 处理股票数据
        df = None
        if isinstance(stock_result, DataFetchError):
            error_explanation = await asyncio.to_thread(
                self.error_explainer.explain_data_fetch_error,
                stock_result,
                user_input
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

        await self._emit_event(event_queue, message, {
            "type": "data",
            "data_type": "time_series_original",
            "data": [p.model_dump() for p in original_points]
        })

        # 等待新闻和 RAG
        pending_tasks = [news_task]
        if rag_task:
            pending_tasks.append(rag_task)

        other_results = await asyncio.gather(*pending_tasks, return_exceptions=True)

        news_result = other_results[0] if not isinstance(other_results[0], Exception) else ([], {})
        rag_sources = other_results[1] if len(other_results) > 1 and not isinstance(other_results[1], Exception) and intent.enable_rag else []

        news_items, sentiment_result = news_result

        # 总结新闻 - 直接调用 Agent
        if news_items:
            summarized_news, _ = await asyncio.to_thread(
                self.news_summary_agent.summarize,
                news_items
            )
        else:
            summarized_news = []

        message.save_news(summarized_news)

        # 发送新闻数据
        if summarized_news:
            await self._emit_event(event_queue, message, {
                "type": "data",
                "data_type": "news",
                "data": [n.model_dump() for n in summarized_news]
            })

        if rag_sources:
            message.save_rag_sources(rag_sources)

        await self._emit_event(event_queue, message, {
            "type": "step_complete",
            "step": 3,
            "data": {"data_points": len(df), "news_count": len(news_items)}
        })
        message.update_step_detail(3, "completed", f"历史数据 {len(df)} 天, 新闻 {len(news_items)} 条")

        # === Step 4: 分析处理（情绪流式输出）===
        await self._emit_event(event_queue, message, {
            "type": "step_start",
            "step": 4,
            "step_name": "分析处理"
        })
        message.update_step_detail(4, "running", "分析时序特征和市场情绪...")

        # 时序特征分析
        features = await asyncio.to_thread(TimeSeriesAnalyzer.analyze_features, df)

        # 流式情绪分析
        emotion_result = await self._step_sentiment_streaming(
            summarized_news, event_queue, message
        )

        message.save_emotion(emotion_result.get("score", 0), emotion_result.get("description", "中性"))

        await self._emit_event(event_queue, message, {
            "type": "step_complete",
            "step": 4,
            "data": {"trend": features.get("trend", "N/A"), "emotion": emotion_result.get("description", "中性")}
        })
        message.update_step_detail(
            4, "completed",
            f"趋势: {features.get('trend', 'N/A')}, 情绪: {emotion_result.get('description', 'N/A')}"
        )

        # === Step 5: 模型预测 ===
        await self._emit_event(event_queue, message, {
            "type": "step_start",
            "step": 5,
            "step_name": "模型预测"
        })
        message.update_step_detail(5, "running", "选择最佳模型...")

        # 计算预测天数
        last_date = df['ds'].max().to_pydatetime()
        print(f"[ModelSelection] 最后日期: {last_date}")
        target_date_from_start = last_date + timedelta(days=90)
        print(f"[ModelSelection] 目标日期从开始: {target_date_from_start}")
        target_date_to_today = datetime.now()
        print(f"[ModelSelection] 目标日期到今天: {target_date_to_today}")
        target_date = max(target_date_from_start, target_date_to_today)
        print(f"[ModelSelection] 目标日期: {target_date}")
        forecast_horizon = max((target_date - last_date).days, 1)
        print(f"[ModelSelection] 预测天数: {forecast_horizon}")

        # 模型选择：构建候选模型列表
        candidate_models = ["prophet", "xgboost", "randomforest", "dlinear"]
        user_specified_model = intent.forecast_model
        print(f"[ModelSelection] 用户指定模型: {user_specified_model}")

        # 调用模型选择器
        try:
            selection_result = await select_best_model(
                df,
                candidate_models,
                forecast_horizon,
                n_windows=3,
                min_train_size=60
            )

            best_model = selection_result["best_model"]
            baseline = selection_result["baseline"]
            model_comparison = selection_result["metrics"]
            is_better_than_baseline = selection_result["is_better_than_baseline"]

            print(f"[ModelSelection] 选择的最佳模型: {best_model}")
            print(f"[ModelSelection] Baseline: {baseline}")
            print(f"[ModelSelection] 用户指定模型: {user_specified_model}")

            # 确定最终使用的模型并生成解释信息
            model_selection_reason = ""
            enable_baseline_penalty = self.ENABLE_BASELINE_PENALTY
            
            if not user_specified_model or user_specified_model == "auto":
                print(f"[ModelSelection] 进入自动选择分支")
                # 用户未指定模型，使用最佳模型
                final_model = best_model
                print(f"[ModelSelection] 最终模型: {final_model}")
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
                    model_selection_reason = f"自动选择 {best_model.upper()} 作为最佳模型"
            else:
                # 用户指定了模型
                print(f"[ModelSelection] 进入用户指定模型分支，用户指定: {user_specified_model}")
                user_model_mae = model_comparison.get(user_specified_model)
                baseline_mae = model_comparison.get(baseline)

                # 根据开关决定是否启用 baseline 惩罚机制
                if enable_baseline_penalty and (
                    user_model_mae is not None and baseline_mae is not None and
                    user_model_mae >= baseline_mae
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
                        if not enable_baseline_penalty and baseline_mae is not None and user_model_mae >= baseline_mae:
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
                        model_selection_reason = f"使用用户指定的 {user_model_name} 模型"

            # 发送模型选择信息
            await self._emit_event(event_queue, message, {
                "type": "model_selection",
                "selected_model": final_model,
                "best_model": best_model,
                "baseline": baseline,
                "model_comparison": model_comparison,
                "is_better_than_baseline": is_better_than_baseline,
                "user_specified_model": user_specified_model,
                "model_selection_reason": model_selection_reason
            })

            # 保存模型选择信息到 Message
            message.save_model_selection(
                final_model,
                model_comparison,
                is_better_than_baseline
            )
            
            # 保存模型选择原因
            message.save_model_selection_reason(model_selection_reason)

            print(f"[ModelSelection] 最终确定的模型: {final_model}")
            message.update_step_detail(5, "running", f"训练 {final_model.upper()} 模型...")

        except Exception as e:
            # 如果模型选择失败，使用用户指定的模型或默认模型
            print(f"[ModelSelection] 模型选择失败: {e}")
            final_model = user_specified_model or "prophet"
            model_comparison = {}
            is_better_than_baseline = False
            
            # 生成失败时的解释信息
            if user_specified_model:
                model_selection_reason = (
                    f"模型选择过程出现错误，使用用户指定的 {user_specified_model.upper()} 模型"
                )
            else:
                model_selection_reason = (
                    f"模型选择过程出现错误，使用默认的 {final_model.upper()} 模型"
                )

            await self._emit_event(event_queue, message, {
                "type": "model_selection",
                "selected_model": final_model,
                "best_model": final_model,
                "baseline": "seasonal_naive",
                "model_comparison": model_comparison,
                "is_better_than_baseline": is_better_than_baseline,
                "user_specified_model": user_specified_model,
                "selection_failed": True,
                "error": str(e),
                "model_selection_reason": model_selection_reason
            })
            
            # 保存模型选择原因
            message.save_model_selection_reason(model_selection_reason)

        prophet_params = await recommend_forecast_params(
            self.sentiment_agent,
            emotion_result or {},
            features
        )

        # 只对最终选定的模型调用一次 run_forecast
        forecast_result = await run_forecast(
            df,
            final_model,
            forecast_horizon,
            prophet_params if final_model == "prophet" else None
        )

        # 保存并发送预测结果（forecast_result 是 ForecastResult 对象）
        full_points = original_points + forecast_result.points
        prediction_start = forecast_result.points[0].date if forecast_result.points else ""
        message.save_time_series_full(full_points, prediction_start)

        await self._emit_event(event_queue, message, {
            "type": "data",
            "data_type": "time_series_full",
            "data": [p.model_dump() for p in full_points],
            "prediction_start_day": prediction_start
        })

        metrics = forecast_result.metrics
        metrics_dict = {"mae": metrics.mae}
        if metrics.rmse:
            metrics_dict["rmse"] = metrics.rmse
        metrics_info = f"MAE: {metrics.mae}" + (f", RMSE: {metrics.rmse}" if metrics.rmse else "")
        await self._emit_event(event_queue, message, {
            "type": "step_complete",
            "step": 5,
            "data": {"metrics": metrics_dict}
        })
        message.update_step_detail(5, "completed", f"预测完成 ({metrics_info})")

        # 保存模型名称到 MessageData（使用最终选定的模型）
        message.save_model_name(final_model)

        # === Step 6: 报告生成（流式） ===
        await self._emit_event(event_queue, message, {
            "type": "step_start",
            "step": 6,
            "step_name": "报告生成"
        })
        message.update_step_detail(6, "running", "生成分析报告...")

        # 将 ForecastResult 转换为字典格式供报告生成使用
        forecast_dict = {
            "forecast": [{"date": p.date, "value": p.value} for p in forecast_result.points],
            "metrics": metrics_dict,
            "model": forecast_result.model
        }

        report_content = await self._step_report_streaming(
            user_input, features, forecast_dict, emotion_result or {},
            conversation_history, event_queue, message
        )

        message.save_conclusion(report_content)
        await self._emit_event(event_queue, message, {
            "type": "step_complete",
            "step": 6,
            "data": {}
        })
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
        event_queue: asyncio.Queue | None
    ):
        """流式聊天流程"""
        step_num = 3 if intent.stock_mention else 2

        # === 数据获取 ===
        await self._emit_event(event_queue, message, {
            "type": "step_start",
            "step": step_num,
            "step_name": "信息获取"
        })
        message.update_step_detail(step_num, "running", "获取相关信息...")

        tasks = []
        task_names = []

        if intent.enable_rag:
            rag_available = await check_rag_availability()
            if rag_available:
                tasks.append(fetch_rag_reports(self.rag_searcher, keywords.rag_keywords))
                task_names.append("rag")

        if intent.enable_search:
            tasks.append(search_web(keywords.search_keywords, intent.history_days))
            task_names.append("search")

        if intent.enable_domain_info:
            stock_code = stock_match.stock_info.stock_code if stock_match and stock_match.stock_info else ""
            tasks.append(fetch_domain_news(stock_code, keywords.domain_keywords))
            task_names.append("domain")

        results = {}
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for name, result in zip(task_names, task_results):
                if not isinstance(result, Exception):
                    results[name] = result

        await self._emit_event(event_queue, message, {
            "type": "step_complete",
            "step": step_num,
            "data": {"sources": list(results.keys())}
        })
        message.update_step_detail(step_num, "completed", f"获取完成: {list(results.keys())}")

        # === 生成回答（流式） ===
        step_num += 1
        await self._emit_event(event_queue, message, {
            "type": "step_start",
            "step": step_num,
            "step_name": "生成回答"
        })
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

        await self._emit_event(event_queue, message, {
            "type": "step_complete",
            "step": step_num,
            "data": {}
        })
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
        message: Message
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
                on_chunk
            )
            loop.call_soon_threadsafe(content_queue.put_nowait, ("done", content))

        future = loop.run_in_executor(None, run_in_thread)

        full_content = ""
        while True:
            try:
                event_type, data = await asyncio.wait_for(content_queue.get(), timeout=120.0)

                if event_type == "chunk":
                    full_content += data
                    await self._emit_event(event_queue, message, {
                        "type": "report_chunk",
                        "content": full_content
                    })
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
        message: Message
    ) -> Dict[str, Any]:
        """流式情绪分析"""
        # 转换为字典列表
        news_list = [
            {
                "title": n.summarized_title,
                "content": n.summarized_content,
                "source_name": n.source_name,
                "source_type": n.source_type,
            }
            for n in news_items
        ] if news_items else []

        if not news_list:
            # 无新闻数据，返回默认值
            default_desc = "无新闻数据，默认中性情绪"
            await self._emit_event(event_queue, message, {
                "type": "data",
                "data_type": "emotion",
                "data": {"score": 0.0, "description": default_desc}
            })
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
                event_type, data = await asyncio.wait_for(content_queue.get(), timeout=60.0)

                if event_type == "chunk":
                    description_buffer += data
                    # 流式发送（score 先设为 0，等完成后更新）
                    if not score_sent:
                        score_sent = True
                    await self._emit_event(event_queue, message, {
                        "type": "emotion_chunk",
                        "content": description_buffer
                    })
                elif event_type == "done":
                    break
            except asyncio.TimeoutError:
                break

        await future

        # 获取最终结果
        result = result_holder["result"] or {"score": 0.0, "description": description_buffer or "中性情绪"}

        # 发送最终情绪数据
        await self._emit_event(event_queue, message, {
            "type": "data",
            "data_type": "emotion",
            "data": {"score": result["score"], "description": result["description"]}
        })

        return result

    # ========== 流式聊天生成 ==========

    async def _step_chat_streaming(
        self,
        user_input: str,
        conversation_history: List[dict],
        context: str,
        event_queue: asyncio.Queue | None,
        message: Message
    ) -> str:
        """流式聊天生成"""
        loop = asyncio.get_running_loop()
        content_queue: asyncio.Queue = asyncio.Queue()

        def run_in_thread():
            gen = self.intent_agent.generate_chat_response(
                user_input,
                conversation_history,
                context,
                stream=True
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
                event_type, data = await asyncio.wait_for(content_queue.get(), timeout=120.0)

                if event_type == "chunk":
                    full_content = data
                    await self._emit_event(event_queue, message, {
                        "type": "chat_chunk",
                        "content": full_content
                    })
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

    async def _emit_event(self, event_queue: asyncio.Queue | None, message: Message, event: Dict):
        """发送事件到队列、PubSub 和 Stream"""
        # 1. 发送到本地队列（如果存在）
        if event_queue:
            await event_queue.put(event)

        try:
            # 2. 即时发布到 PubSub
            channel = f"stream:{message.message_id}"
            self.redis.publish(channel, json.dumps(event))

            # 3. 持久化到 Stream（供断点续传使用）
            stream_key = f"stream-events:{message.message_id}"
            self.redis.xadd(
                stream_key,
                {"data": json.dumps(event)},
                maxlen=1000,
                approximate=True
            )
            self.redis.expire(stream_key, 86400)  # 24小时 TTL

        except Exception as e:
            print(f"[StreamingTask] Event storage error: {e}")

    async def _emit_error(self, event_queue: asyncio.Queue | None, message: Message, error_msg: str):
        """发送错误事件"""
        await self._emit_event(event_queue, message, {
            "type": "error",
            "message": error_msg
        })

    async def _emit_done(self, event_queue: asyncio.Queue | None, message: Message):
        """发送完成事件"""
        await self._emit_event(event_queue, message, {
            "type": "done",
            "completed": True
        })


# 单例
_streaming_processor: Optional[StreamingTaskProcessor] = None


def get_streaming_processor() -> StreamingTaskProcessor:
    """获取流式任务处理器单例"""
    global _streaming_processor
    if _streaming_processor is None:
        _streaming_processor = StreamingTaskProcessor()
    return _streaming_processor
