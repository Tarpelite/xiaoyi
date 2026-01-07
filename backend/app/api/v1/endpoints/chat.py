import asyncio
from typing import Optional, List, Dict
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.core.config import settings
from app.core.utils import format_sse, df_to_table, df_to_chart, detect_anomalies, forecast_to_chart, STEPS
from app.core.session_manager import get_session_manager
from app.agents import FinanceChatAgent, IntentAgent, SuggestionAgent
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


class ToolSettings(BaseModel):
    """Tool 开关设置"""
    forecast: bool = True       # 序列预测（默认开启）
    report_rag: bool = False    # 研报检索（默认关闭）
    news_rag: bool = False      # 新闻 RAG（默认关闭）


class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    model: str = "prophet"  # 预测模型：prophet, xgboost, randomforest, dlinear
    session_id: Optional[str] = None  # 会话ID，可选
    history: Optional[List[Dict[str, str]]] = None  # 对话历史，可选（用于兼容）
    tools: ToolSettings = ToolSettings()  # Tool 开关设置


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
            model = request.model.lower() if request.model else "prophet"

            # 验证模型名称
            if model not in ["prophet", "xgboost", "randomforest", "dlinear"]:
                yield format_sse("error", {"message": f"不支持的模型: {model}。支持: 'prophet', 'xgboost', 'randomforest', 'dlinear'"})
                return

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

            # 获取 Tools 设置
            tools = request.tools

            # ========== 意图判断 ==========
            intent_agent = IntentAgent(api_key)
            intent_result = await asyncio.to_thread(intent_agent.judge_intent, user_input, conversation_history)
            intent = intent_result.get("intent", "analyze")
            intent_reason = intent_result.get("reason", "")

            # 发送意图识别结果给前端
            yield format_sse("intent", {
                "intent": intent,
                "reason": intent_reason
            })

            # 如果 forecast tool 关闭，或者只是提问，直接回答
            if not tools.forecast or intent == "answer":
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

            # 检查用户问题中是否指定了模型（如"换个XGBoost模型"）
            user_input_lower = user_input.lower()
            if "xgboost" in user_input_lower or "xgb" in user_input_lower:
                model = "xgboost"
            elif "randomforest" in user_input_lower or "随机森林" in user_input or "rf" in user_input_lower:
                model = "randomforest"
            elif "dlinear" in user_input_lower or "d-linear" in user_input_lower:
                model = "dlinear"
            elif "prophet" in user_input_lower:
                model = "prophet"
            # 否则使用前端传递的 model 参数

            steps[0]["message"] = "获取数据中..."
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

            # ========== 步骤2: 新闻获取与情绪分析 ==========
            steps[1]["status"] = "running"
            steps[1]["message"] = "获取相关新闻..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # 获取股票代码
            stock_symbol = data_config.get("params", {}).get("symbol", "")

            # 获取新闻
            news_df = await asyncio.to_thread(DataFetcher.fetch_news, stock_symbol, 50)

            steps[1]["message"] = f"分析 {len(news_df)} 条新闻情绪..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # 情绪分析
            sentiment_result = await asyncio.to_thread(sentiment_analyzer.analyze, news_df)

            # 发送情绪分析结果
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
            steps[4]["message"] = "训练模型中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            horizon = analysis_config.get("forecast_horizon", 30)

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
