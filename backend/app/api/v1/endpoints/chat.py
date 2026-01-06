import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.core.config import settings
from app.models.chat import ChatRequest
from app.core.utils import format_sse, df_to_table, df_to_chart, detect_anomalies, forecast_to_chart, STEPS
from app.agents import FinanceChatAgent
from app.data import DataFetcher
from app.forecasting import (
    TimeSeriesAnalyzer, 
    ProphetForecaster, 
    XGBoostForecaster,
    RandomForestForecaster,
    DLinearForecaster
)

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
            user_input = request.message
            model = request.model.lower() if request.model else "prophet"
            
            # 验证模型名称
            if model not in ["prophet", "xgboost", "randomforest", "dlinear"]:
                yield format_sse("error", {"message": f"不支持的模型: {model}。支持: 'prophet', 'xgboost', 'randomforest', 'dlinear'"})
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
            
            # ========== 步骤2: 时序特征分析 ==========
            steps[1]["status"] = "running"
            steps[1]["message"] = "分析中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            features = await asyncio.to_thread(TimeSeriesAnalyzer.analyze_features, df)
            
            steps[1]["status"] = "completed"
            steps[1]["message"] = f"趋势: {features['trend']}, 波动性: {features['volatility']}"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # ========== 步骤3: 异常检测 ==========
            steps[2]["status"] = "running"
            steps[2]["message"] = "检测中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            anomalies = await asyncio.to_thread(detect_anomalies, df)
            
            steps[2]["status"] = "completed"
            steps[2]["message"] = f"检测到 {anomalies['count']} 个异常波动点"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # ========== 步骤4: 模型训练与评估 ==========
            steps[3]["status"] = "running"
            steps[3]["message"] = "训练模型中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            horizon = analysis_config.get("forecast_horizon", 30)
            
            # 根据选择的模型进行预测
            if model == "prophet":
                prophet_forecaster = ProphetForecaster()
                forecast_result = await asyncio.to_thread(prophet_forecaster.forecast, df, horizon)
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
            steps[3]["status"] = "completed"
            steps[3]["message"] = f"{forecast_result['model'].upper()} 模型训练完成 ({metrics_info})"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # ========== 步骤5: 预测生成 ==========
            steps[4]["status"] = "running"
            steps[4]["message"] = "生成预测中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            steps[4]["status"] = "completed"
            steps[4]["message"] = f"生成未来 {horizon} 天预测"
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
            
            # ========== 步骤7: 分析完成 ==========
            steps[6]["status"] = "running"
            steps[6]["message"] = "生成报告中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # 生成报告
            user_question = analysis_config.get("user_question", user_input)
            report = await asyncio.to_thread(agent.reporter.generate, user_question, features, forecast_result)
            
            # 发送文本内容（分析报告）
            text_content = {
                "type": "text",
                "text": report
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
