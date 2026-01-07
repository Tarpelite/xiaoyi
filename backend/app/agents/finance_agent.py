"""
Finance Chat Agent 模块
=======================

负责编排整个金融数据分析流程
"""

import os
from typing import Dict, Any
from .nlp_agent import NLPAgent
from .report_agent import ReportAgent
from app.data import DataFetcher
from app.models import TimeSeriesAnalyzer, ProphetForecaster, XGBoostForecaster, DLinearForecaster, \
    RandomForestForecaster


class FinanceChatAgent:
    """
    金融对话 Agent
    
    完整流程:
    用户输入 → NLP解析 → 数据获取 → 特征分析 → 预测 → 报告生成
    """

    def __init__(self, api_key: str = None):
        """
        初始化 Finance Chat Agent
        
        Args:
            api_key: DeepSeek API Key，如果不提供则从环境变量读取
        """
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("请设置 DEEPSEEK_API_KEY")

        self.nlp = NLPAgent(self.api_key)
        self.reporter = ReportAgent(self.api_key)

        # 预测器实例
        self.prophet_forecaster = ProphetForecaster()
        self.xgboost_forecaster = XGBoostForecaster()
        self.randomforest_forecaster = RandomForestForecaster()
        self.dlinear_forecaster = DLinearForecaster()

    def chat(self, user_input: str, model: str = "prophet", verbose: bool = True) -> Dict[str, Any]:
        """
        对话接口
        
        Args:
            user_input: 用户自然语言输入
            model: 预测模型，可选 "prophet" 或 "xgboost"，默认为 "prophet"
            verbose: 是否打印过程
            
        Returns:
            包含预测结果和分析报告的字典
        """
        if verbose:
            print("=" * 60)
            print(f"📝 用户: {user_input}")
            print("=" * 60)

        # Step 1: 解析用户输入
        if verbose:
            print("\n🤖 Step 1: 解析需求...")

        parsed = self.nlp.parse(user_input)
        data_config = parsed["data_config"]
        analysis_config = parsed["analysis_config"]

        if verbose:
            print(f"   → 数据源: {data_config['api_function']}")
            print(f"   → 参数: {data_config['params']}")
            print(f"   → 预测: {analysis_config['forecast_horizon']} 天")

        # Step 2: 获取数据
        if verbose:
            print("\n📊 Step 2: 获取数据...")

        raw_df = DataFetcher.fetch(data_config)
        df = DataFetcher.prepare(raw_df, data_config)

        # Step 3: 特征分析
        if verbose:
            print("\n📈 Step 3: 分析特征...")

        features = TimeSeriesAnalyzer.analyze_features(df)

        if verbose:
            print(f"   → 趋势: {features['trend']}, 波动: {features['volatility']}")
            print(f"   → 最新价: {features['latest']}")

        # Step 4: 预测
        if verbose:
            print("\n🔮 Step 4: 执行预测...")

        horizon = analysis_config.get("forecast_horizon", 30)
        model_name = model.lower() if model else analysis_config.get("model", "prophet").lower()

        # 验证模型名称
        if model_name not in ["prophet", "xgboost"]:
            raise ValueError(f"不支持的模型: {model_name}。支持: 'prophet', 'xgboost'")

        # 选择预测器
        if model_name == "prophet":
            forecast_result = self.prophet_forecaster.forecast(df, horizon)
        else:  # xgboost
            forecast_result = self.xgboost_forecaster.forecast(df, horizon)

        if verbose:
            print(f"   → 模型: {forecast_result['model']}")
            metrics_str = ", ".join([f"{k.upper()}: {v}" for k, v in forecast_result['metrics'].items()])
            print(f"   → 指标: {metrics_str}")

        # Step 5: 生成报告
        if verbose:
            print("\n📋 Step 5: 生成报告...")

        user_question = analysis_config.get("user_question", user_input)
        report = self.reporter.generate(user_question, features, forecast_result)

        # 结果
        result = {
            "config": {
                "data": data_config,
                "analysis": analysis_config
            },
            "data": {
                "raw_shape": raw_df.shape,
                "prepared_shape": df.shape,
                "df": df,  # 标准化后的数据
            },
            "features": features,
            "forecast": forecast_result["forecast"],
            "metrics": forecast_result["metrics"],
            "report": report,
        }

        if verbose:
            print("\n" + "=" * 60)
            print("💡 分析报告")
            print("=" * 60)
            print(report)
            print("=" * 60)

        return result
