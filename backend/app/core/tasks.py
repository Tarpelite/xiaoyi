"""
异步任务处理模块
================

处理分析任务的异步执行
"""

import asyncio
import pandas as pd
import time
from typing import Dict, Any
from datetime import datetime

from app.core.session import Session
from app.core.session_manager import get_session_manager
from app.schemas.session_schema import TimeSeriesPoint, SessionStatus
from app.agents.nlp_agent import NLPAgent
from app.agents.report_agent import ReportAgent
from app.agents.feature_agents import NewsAgent, EmotionAnalyzer
from app.agents.error_explainer import ErrorExplainerAgent
from app.data import DataFetcher
from app.data.fetcher import DataFetchError
from app.models import TimeSeriesAnalyzer, ProphetForecaster, XGBoostForecaster, RandomForestForecaster, DLinearForecaster


class AnalysisTask:
    """分析任务处理器"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.nlp_agent = NLPAgent(api_key)
        self.report_agent = ReportAgent(api_key)
        self.news_agent = NewsAgent(api_key)
        self.emotion_analyzer = EmotionAnalyzer(api_key)
        self.error_explainer = ErrorExplainerAgent(api_key)
    
    async def execute(self, session_id: str, user_input: str, model_name: str):
        """
        执行分析任务
        
        Args:
            session_id: 会话ID
            user_input: 用户输入
            model_name: 模型名称
        """
        session = Session(session_id)
        
        try:
            print(f"\n{'='*60}")
            print(f"🚀 Starting analysis for session: {session_id}")
            print(f"{'='*60}\n")
            
            # Step 1: NLP 解析
            session.update_step(1)
            parsed = await asyncio.to_thread(self.nlp_agent.parse, user_input)
            data_config = parsed["data_config"]
            analysis_config = parsed["analysis_config"]
            
            # 提取股票代码
            stock_code = data_config.get("params", {}).get("symbol", "000001")
            
            # Step 2: 获取数据
            session.update_step(2)
            try:
                raw_df = await asyncio.to_thread(DataFetcher.fetch, data_config)
                df = await asyncio.to_thread(DataFetcher.prepare, raw_df, data_config)
                
            except DataFetchError as e:
                # 数据获取失败 - 切换到对话模式
                print(f"\n{'⚠️ '*20}")
                print(f"数据获取失败: {e.error_type}")
                print(f"股票代码: {e.context.get('symbol')}")
                print(f"{'⚠️ '*20}\n")
                
                # 使用 AI 生成友好解释
                print("🤖 生成友好解释...")
                explanation = await asyncio.to_thread(
                    self.error_explainer.explain_data_fetch_error,
                    e,
                    user_input
                )
                
                # 更新 session - 切换到对话模式
                data = session.get()
                if data:
                    data.is_time_series = False  # 标记为对话模式
                    data.error_type = "data_fetch_failed"
                    data.conversational_response = explanation
                    data.status = SessionStatus.COMPLETED
                    data.steps = 2  # 在第2步失败
                    session._save(data)
                
                print(f"✅ 已切换到对话模式，生成了 {len(explanation)} 字解释\n")
                print(f"{'='*60}\n")
                return  # 提前结束流程
            
            # 保存原始时序数据
            original_points = self._df_to_points(df, is_prediction=False)
            session.save_time_series_original(original_points)
            
            # Step 3: 特征分析
            session.update_step(3)
            features = await asyncio.to_thread(TimeSeriesAnalyzer.analyze_features, df)
            
            # Step 4: 获取新闻
            session.update_step(4)
            news_list = await asyncio.to_thread(self.news_agent.fetch_and_summarize, stock_code)
            session.save_news(news_list)
            
            # Step 5: 情绪分析
            session.update_step(5)
            emotion = await asyncio.to_thread(self.emotion_analyzer.analyze, news_list, features)
            session.save_emotion(emotion)
            
            # Step 6: 模型预测
            session.update_step(6)
            horizon = analysis_config.get("forecast_horizon", 30)
            forecaster = self._get_forecaster(model_name)
            forecast_result = await asyncio.to_thread(forecaster.forecast, df, horizon)
            
            # 合并历史和预测数据
            full_points = original_points + self._forecast_to_points(
                forecast_result["forecast"],
                is_prediction=True
            )
            prediction_start = forecast_result["forecast"][0]["date"]
            session.save_time_series_full(full_points, prediction_start)
            
            # Step 7: 生成报告
            session.update_step(7)
            user_question = analysis_config.get("user_question", user_input)
            report = await asyncio.to_thread(
                self.report_agent.generate,
                user_question,
                features,
                forecast_result
            )
            session.save_conclusion(report)
            
            # 添加助手回复到会话历史
            session_manager = get_session_manager()
            session_manager.add_message(session_id, "assistant", report)
            
            # 标记完成 - 使用重试机制确保成功
            print(f"\n{'='*60}")
            print(f"🎯 Marking session {session_id} as COMPLETED")
            print(f"{'='*60}\n")
            
            # 尝试3次确保成功
            for attempt in range(3):
                try:
                    session.mark_completed()
                    time.sleep(0.3)  # 等待Redis写入
                    
                    # 验证
                    verification = session.get()
                    if verification and verification.status == SessionStatus.COMPLETED:
                        print(f"\n{'✅'*20}")
                        print(f"SUCCESS: Session {session_id} marked as COMPLETED")
                        print(f"  Status: {verification.status}")
                        print(f"  Steps: {verification.steps}/7")
                        print(f"{'✅'*20}\n")
                        break
                    else:
                        print(f"⚠️  Attempt {attempt+1}: Verification failed, retrying...")
                        if attempt == 2:
                            print(f"❌ CRITICAL: Failed to mark completed after 3 attempts!")
                except Exception as e:
                    print(f"❌ Attempt {attempt+1} exception: {e}")
                    if attempt == 2:
                        raise
            
            print(f"\n{'='*60}")
            print(f"🎉 Analysis completed for session: {session_id}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"\n{'='*60}")
            print(f"❌ ERROR in session {session_id}: {str(e)}")
            print(f"{'='*60}\n")
            session.mark_error(str(e))
            raise
    
    def _get_forecaster(self, model_name: str):
        """根据模型名称获取预测器"""
        forecasters = {
            "prophet": ProphetForecaster(),
            "xgboost": XGBoostForecaster(),
            "randomforest": RandomForestForecaster(),
            "dlinear": DLinearForecaster()
        }
        return forecasters.get(model_name.lower(), ProphetForecaster())
    
    def _df_to_points(self, df: pd.DataFrame, is_prediction: bool = False) -> list[TimeSeriesPoint]:
        """DataFrame 转换为 TimeSeriesPoint 列表"""
        points = []
        for _, row in df.iterrows():
            points.append(TimeSeriesPoint(
                date=row["ds"].strftime("%Y-%m-%d"),
                value=round(float(row["y"]), 2),
                is_prediction=is_prediction
            ))
        return points
    
    def _forecast_to_points(self, forecast: list, is_prediction: bool = True) -> list[TimeSeriesPoint]:
        """预测结果转换为 TimeSeriesPoint 列表"""
        return [
            TimeSeriesPoint(
                date=item["date"],
                value=item["value"],
                is_prediction=is_prediction
            )
            for item in forecast
        ]


# 全局任务处理器
_task_processor = None


def get_task_processor(api_key: str = None) -> AnalysisTask:
    """获取任务处理器单例"""
    global _task_processor
    if _task_processor is None:
        _task_processor = AnalysisTask(api_key)
    return _task_processor
