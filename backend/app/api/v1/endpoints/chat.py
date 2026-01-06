import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.core.config import settings
from app.models.chat import ChatRequest
from app.core.utils import format_sse, df_to_table, df_to_chart, forecast_to_chart, STEPS
from app.agents import FinanceChatAgent
from app.data import DataFetcher
from app.forecasting import TimeSeriesAnalyzer, ProphetForecaster, XGBoostForecaster
from app.sentiment import SentimentAnalyzer

router = APIRouter()

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
            if model not in ["prophet", "xgboost"]:
                yield format_sse("error", {"message": f"不支持的模型: {model}。支持: 'prophet', 'xgboost'"})
                return

            # 初始化步骤状态
            steps = [{"id": s["id"], "name": s["name"], "status": "pending"} for s in STEPS]

            # ========== 步骤1: 数据获取与预处理 ==========
            steps[0]["status"] = "running"
            steps[0]["message"] = "解析用户需求..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)

            # NLP 解析
            parsed = await asyncio.to_thread(agent.nlp.parse, user_input)
            data_config = parsed["data_config"]
            analysis_config = parsed["analysis_config"]

            steps[0]["message"] = "获取股价数据中..."
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
            else:  # xgboost
                xgboost_forecaster = XGBoostForecaster()
                forecast_result = await asyncio.to_thread(xgboost_forecaster.forecast, df, horizon)

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

            # 生成报告（包含情绪分析）
            user_question = analysis_config.get("user_question", user_input)
            report = await asyncio.to_thread(
                agent.reporter.generate, user_question, features, forecast_result, sentiment_result
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
