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
from app.models import (
    TimeSeriesAnalyzer,
    ProphetForecaster,
    XGBoostForecaster,
    DLinearForecaster,
    RandomForestForecaster
)
from app.sentiment import SentimentAnalyzer


class FinanceChatAgent:
    """
    金融对话 Agent

    完整流程:
    用户输入 → NLP解析 → 数据获取 → 新闻情绪分析 → 特征分析 → 参数推荐 → 预测 → 报告生成
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
        self.sentiment_analyzer = SentimentAnalyzer(self.api_key)

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
            model: 预测模型，可选 "prophet", "xgboost", "randomforest", "dlinear"
            verbose: 是否打印过程

        Returns:
            包含预测结果和分析报告的字典
        """
        if verbose:
            print("=" * 60)
            print(f"用户: {user_input}")
            print("=" * 60)

        # Step 1: 解析用户输入
        if verbose:
            print("\n Step 1: 解析需求...")

        parsed = self.nlp.parse(user_input)
        data_config = parsed["data_config"]
        analysis_config = parsed["analysis_config"]

        if verbose:
            print(f"   → 数据源: {data_config['api_function']}")
            print(f"   → 参数: {data_config['params']}")
            print(f"   → 预测: {analysis_config['forecast_horizon']} 天")

        # Step 2: 获取数据
        if verbose:
            print("\n Step 2: 获取数据...")

        raw_df = DataFetcher.fetch(data_config)
        df = DataFetcher.prepare(raw_df, data_config)

        if verbose:
            print(f"\n   股价原始数据 (最近5条):")
            print("-" * 50)
            if not raw_df.empty:
                # 显示最后5行
                display_df = raw_df.tail(5)
                for _, row in display_df.iterrows():
                    date_val = row.get('日期', row.get('date', 'N/A'))
                    close_val = row.get('收盘', row.get('close', 'N/A'))
                    open_val = row.get('开盘', row.get('open', 'N/A'))
                    high_val = row.get('最高', row.get('high', 'N/A'))
                    low_val = row.get('最低', row.get('low', 'N/A'))
                    vol_val = row.get('成交量', row.get('volume', 'N/A'))
                    print(f"   {date_val} | 开:{open_val} 高:{high_val} 低:{low_val} 收:{close_val} 量:{vol_val}")
            print("-" * 50)

        # 提取股票代码用于获取新闻
        stock_symbol = data_config.get("params", {}).get("symbol", "")

        # Step 3: 获取新闻 & 情绪分析
        if verbose:
            print("\n Step 3: 获取新闻 & 情绪分析...")

        news_df = DataFetcher.fetch_news(symbol=stock_symbol, limit=50)

        if verbose:
            print(f"\n   新闻原始数据 (最近10条):")
            print("-" * 60)
            if not news_df.empty:
                # 尝试不同的列名
                title_col = next((c for c in ["新闻标题", "标题", "title"] if c in news_df.columns), None)
                time_col = next((c for c in ["发布时间", "时间", "datetime"] if c in news_df.columns), None)
                source_col = next((c for c in ["文章来源", "来源", "source"] if c in news_df.columns), None)

                for i, (_, row) in enumerate(news_df.head(10).iterrows()):
                    title = row[title_col][:50] + "..." if title_col and len(str(row[title_col])) > 50 else (row[title_col] if title_col else "N/A")
                    time_val = row[time_col] if time_col else ""
                    source_val = row[source_col] if source_col else ""
                    print(f"   {i+1}. [{time_val}] {title}")
                    if source_val:
                        print(f"      来源: {source_val}")
            else:
                print("   (无新闻数据)")
            print("-" * 60)

        sentiment_result = self.sentiment_analyzer.analyze(news_df)

        if verbose:
            print(f"\n   情绪分析结果:")
            print("-" * 60)
            print(f"   整体情绪: {sentiment_result['sentiment']}")
            print(f"   情绪得分: {sentiment_result['overall_score']:.2f} (范围: -1 到 1)")
            print(f"   置信度:   {sentiment_result.get('confidence', 0):.2f}")
            print(f"   新闻数量: {sentiment_result['news_count']}")
            print(f"\n   关键事件:")
            for i, event in enumerate(sentiment_result.get('key_events', [])[:5], 1):
                print(f"      {i}. {event}")
            print(f"\n   分析说明: {sentiment_result.get('analysis_text', '无')}")
            print("-" * 60)

        # Step 4: 特征分析
        if verbose:
            print("\n Step 4: 分析特征...")

        features = TimeSeriesAnalyzer.analyze_features(df)

        if verbose:
            print(f"   → 趋势: {features['trend']}, 波动: {features['volatility']}")
            print(f"   → 最新价: {features['latest']}")

        # Step 5: 参数推荐
        if verbose:
            print("\n Step 5: 参数推荐...")

        prophet_params = self.sentiment_analyzer.recommend_params(sentiment_result, features)

        if verbose:
            # 默认参数
            default_params = {
                "changepoint_prior_scale": 0.05,
                "seasonality_prior_scale": 10,
                "changepoint_range": 0.8
            }

            print(f"\n   Prophet 参数配置:")
            print("-" * 60)
            print(f"   {'参数名':<30} {'默认值':<10} {'推荐值':<10} {'变化':<10}")
            print("-" * 60)

            for param, default_val in default_params.items():
                new_val = prophet_params.get(param, default_val)
                if new_val != default_val:
                    change = f"{'↑' if new_val > default_val else '↓'} {abs(new_val - default_val):.3f}"
                else:
                    change = "无变化"
                print(f"   {param:<30} {default_val:<10} {new_val:<10.3f} {change:<10}")

            print("-" * 60)
            print(f"\n   推荐理由: {prophet_params.get('reasoning', '使用默认参数')}")
            print("-" * 60)

        # Step 6: 预测
        if verbose:
            print("\n Step 6: 执行预测...")

        horizon = analysis_config.get("forecast_horizon", 30)
        model_name = model.lower() if model else analysis_config.get("model", "prophet").lower()

        # 验证模型名称
        valid_models = ["prophet", "xgboost", "randomforest", "dlinear"]
        if model_name not in valid_models:
            raise ValueError(f"不支持的模型: {model_name}。支持: {', '.join(valid_models)}")

        # 选择预测器
        if model_name == "prophet":
            forecast_result = self.prophet_forecaster.forecast(df, horizon, prophet_params=prophet_params)
        elif model_name == "xgboost":
            forecast_result = self.xgboost_forecaster.forecast(df, horizon)
        elif model_name == "randomforest":
            forecast_result = self.randomforest_forecaster.forecast(df, horizon)
        else:  # dlinear
            forecast_result = self.dlinear_forecaster.forecast(df, horizon)

        if verbose:
            print(f"   → 模型: {forecast_result['model']}")
            metrics_str = ", ".join([f"{k.upper()}: {v}" for k, v in forecast_result['metrics'].items()])
            print(f"   → 指标: {metrics_str}")

        # Step 7: 生成报告
        if verbose:
            print("\n Step 7: 生成报告...")

        user_question = analysis_config.get("user_question", user_input)
        report = self.reporter.generate(user_question, features, forecast_result, sentiment_result)

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
            "sentiment": sentiment_result,
            "prophet_params": prophet_params,
            "forecast": forecast_result["forecast"],
            "metrics": forecast_result["metrics"],
            "report": report,
        }

        if verbose:
            print("\n" + "=" * 60)
            print(" 分析报告")
            print("=" * 60)
            print(report)
            print("=" * 60)

        return result
