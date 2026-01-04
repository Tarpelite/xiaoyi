"""
轻量级时序分析 Agent
====================

基于 Pydantic AI + Prophet 的简洁实现

依赖:
    pip install pydantic-ai prophet pandas matplotlib akshare

环境变量:
    DEEPSEEK_API_KEY: DeepSeek API Key
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Literal
from dataclasses import dataclass
from pydantic import BaseModel, Field

# ============================================================
# 数据模型
# ============================================================

class ForecastConfig(BaseModel):
    """预测配置"""
    horizon: int = Field(default=30, description="预测天数")
    freq: str = Field(default="D", description="数据频率: D=日, W=周, M=月")
    model: str = Field(default="prophet", description="模型: prophet, arima, ets")
    
class ForecastResult(BaseModel):
    """预测结果"""
    model_used: str
    forecast_values: List[Dict[str, Any]]  # [{date, value, lower, upper}, ...]
    metrics: Dict[str, float] = {}  # MAE, RMSE 等
    analysis: str = ""  # LLM 生成的分析

class TimeSeriesFeatures(BaseModel):
    """时序特征"""
    trend: str = Field(description="趋势: up/down/flat")
    seasonality: Optional[str] = Field(description="季节性: daily/weekly/monthly/yearly/none")
    volatility: str = Field(description="波动性: high/medium/low")
    data_points: int
    date_range: str
    summary: str


# ============================================================
# 时序模型调度器
# ============================================================

class ModelDispatcher:
    """时序模型调度器 - 支持多种模型"""
    
    def __init__(self):
        self._models = {
            "prophet": self._forecast_prophet,
            "naive": self._forecast_naive,
            # 后续可扩展: "arima", "ets", "chronos" 等
        }
    
    def available_models(self) -> List[str]:
        return list(self._models.keys())
    
    def forecast(
        self, 
        df: pd.DataFrame, 
        model: str = "prophet",
        horizon: int = 30,
        freq: str = "D"
    ) -> Dict[str, Any]:
        """
        执行预测
        
        Args:
            df: 必须包含 'ds' (datetime) 和 'y' (float) 列
            model: 模型名称
            horizon: 预测步数
            freq: 频率
        """
        if model not in self._models:
            raise ValueError(f"不支持的模型: {model}, 可用: {self.available_models()}")
        
        return self._models[model](df, horizon, freq)
    
    def _forecast_prophet(self, df: pd.DataFrame, horizon: int, freq: str) -> Dict[str, Any]:
        """Prophet 预测"""
        from prophet import Prophet
        
        # Prophet 需要 ds 和 y 列
        prophet_df = df[["ds", "y"]].copy()
        
        # 初始化模型
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True if freq == "D" else False,
            yearly_seasonality=True,
            changepoint_prior_scale=0.05,
        )
        
        # 训练
        model.fit(prophet_df)
        
        # 生成未来日期
        future = model.make_future_dataframe(periods=horizon, freq=freq)
        
        # 预测
        forecast = model.predict(future)
        
        # 提取预测部分
        forecast_only = forecast.tail(horizon)
        
        # 格式化结果
        forecast_values = [
            {
                "date": row["ds"].strftime("%Y-%m-%d"),
                "value": round(row["yhat"], 2),
                "lower": round(row["yhat_lower"], 2),
                "upper": round(row["yhat_upper"], 2),
            }
            for _, row in forecast_only.iterrows()
        ]
        
        # 计算训练集指标
        train_forecast = forecast.head(len(prophet_df))
        mae = np.mean(np.abs(prophet_df["y"].values - train_forecast["yhat"].values))
        
        return {
            "model": "prophet",
            "forecast_values": forecast_values,
            "metrics": {"mae": round(mae, 4)},
            "forecast_df": forecast_only[["ds", "yhat", "yhat_lower", "yhat_upper"]],
        }
    
    def _forecast_naive(self, df: pd.DataFrame, horizon: int, freq: str) -> Dict[str, Any]:
        """朴素预测 (使用最后一个值)"""
        last_value = df["y"].iloc[-1]
        last_date = df["ds"].iloc[-1]
        
        forecast_values = []
        for i in range(1, horizon + 1):
            if freq == "D":
                future_date = last_date + timedelta(days=i)
            elif freq == "W":
                future_date = last_date + timedelta(weeks=i)
            else:
                future_date = last_date + timedelta(days=i * 30)
            
            forecast_values.append({
                "date": future_date.strftime("%Y-%m-%d"),
                "value": round(last_value, 2),
                "lower": round(last_value * 0.95, 2),
                "upper": round(last_value * 1.05, 2),
            })
        
        return {
            "model": "naive",
            "forecast_values": forecast_values,
            "metrics": {},
        }


# ============================================================
# 时序特征分析器
# ============================================================

class FeatureAnalyzer:
    """时序特征分析"""
    
    @staticmethod
    def analyze(df: pd.DataFrame) -> TimeSeriesFeatures:
        """分析时序特征"""
        y = df["y"].values
        
        # 趋势判断
        first_half_mean = np.mean(y[:len(y)//2])
        second_half_mean = np.mean(y[len(y)//2:])
        
        if second_half_mean > first_half_mean * 1.05:
            trend = "up"
        elif second_half_mean < first_half_mean * 0.95:
            trend = "down"
        else:
            trend = "flat"
        
        # 波动性
        cv = np.std(y) / np.mean(y) if np.mean(y) != 0 else 0
        if cv > 0.3:
            volatility = "high"
        elif cv > 0.1:
            volatility = "medium"
        else:
            volatility = "low"
        
        # 季节性检测 (简化版)
        seasonality = None
        if len(y) >= 365:
            seasonality = "yearly"
        elif len(y) >= 30:
            seasonality = "monthly"
        elif len(y) >= 7:
            seasonality = "weekly"
        
        return TimeSeriesFeatures(
            trend=trend,
            seasonality=seasonality,
            volatility=volatility,
            data_points=len(y),
            date_range=f"{df['ds'].min().strftime('%Y-%m-%d')} ~ {df['ds'].max().strftime('%Y-%m-%d')}",
            summary=f"数据呈{{'up':'上升','down':'下降','flat':'平稳'}}[trend]趋势，波动性{{'high':'较高','medium':'中等','low':'较低'}}[volatility]，共{len(y)}个数据点"
        )


# ============================================================
# Pydantic AI Agent
# ============================================================

from pydantic_ai import Agent, RunContext

# Agent 依赖
@dataclass
class AgentDeps:
    df: pd.DataFrame
    features: TimeSeriesFeatures
    config: ForecastConfig

# 创建 Agent
forecast_agent = Agent(
    "deepseek:deepseek-chat",
    deps_type=AgentDeps,
    system_prompt="""你是一个专业的金融时序分析师。
    
你的任务是:
1. 分析时序数据的特征
2. 解释预测结果
3. 给出投资建议（附带风险提示）

请用中文回答，保持专业、客观、简洁。
""",
)

@forecast_agent.tool
async def get_data_features(ctx: RunContext[AgentDeps]) -> str:
    """获取时序数据特征"""
    features = ctx.deps.features
    return f"""
数据特征:
- 趋势: {features.trend}
- 季节性: {features.seasonality or '不明显'}
- 波动性: {features.volatility}
- 数据量: {features.data_points} 个点
- 时间范围: {features.date_range}
"""

@forecast_agent.tool
async def run_forecast(ctx: RunContext[AgentDeps]) -> str:
    """执行时序预测"""
    dispatcher = ModelDispatcher()
    
    result = dispatcher.forecast(
        df=ctx.deps.df,
        model=ctx.deps.config.model,
        horizon=ctx.deps.config.horizon,
        freq=ctx.deps.config.freq,
    )
    
    # 存储结果供后续使用
    ctx.deps.__dict__["forecast_result"] = result
    
    # 返回摘要
    values = result["forecast_values"]
    return f"""
预测完成:
- 模型: {result['model']}
- 预测期: {len(values)} 天
- 起始预测: {values[0]['date']} = {values[0]['value']}
- 结束预测: {values[-1]['date']} = {values[-1]['value']}
- 预测区间: [{values[0]['lower']}, {values[0]['upper']}]
"""


# ============================================================
# 主管道
# ============================================================

class TimeSeriesPipeline:
    """时序分析管道"""
    
    def __init__(self, deepseek_api_key: str = None):
        if deepseek_api_key:
            os.environ["DEEPSEEK_API_KEY"] = deepseek_api_key
        
        self.dispatcher = ModelDispatcher()
        self.analyzer = FeatureAnalyzer()
    
    def prepare_data(self, df: pd.DataFrame, date_col: str = None, value_col: str = None) -> pd.DataFrame:
        """
        准备数据为标准格式 (ds, y)
        """
        result = df.copy()
        
        # 自动检测日期列
        if date_col is None:
            for col in ["日期", "date", "Date", "ds", "时间"]:
                if col in result.columns:
                    date_col = col
                    break
        
        # 自动检测值列
        if value_col is None:
            for col in ["收盘", "close", "Close", "y", "value"]:
                if col in result.columns:
                    value_col = col
                    break
        
        if date_col is None or value_col is None:
            raise ValueError(f"无法自动检测列，请指定 date_col 和 value_col。当前列: {list(result.columns)}")
        
        # 标准化
        return pd.DataFrame({
            "ds": pd.to_datetime(result[date_col]),
            "y": result[value_col].astype(float)
        }).sort_values("ds").reset_index(drop=True)
    
    def forecast(
        self,
        df: pd.DataFrame,
        horizon: int = 30,
        model: str = "prophet",
        freq: str = "D",
        query: str = None,
    ) -> Dict[str, Any]:
        """
        执行预测
        
        Args:
            df: 标准格式数据 (ds, y)
            horizon: 预测天数
            model: 模型名称
            freq: 频率
            query: 用户问题（可选，用于 LLM 分析）
        """
        # 1. 特征分析
        features = self.analyzer.analyze(df)
        print(f"📊 数据特征: {features.summary}")
        
        # 2. 执行预测
        print(f"🔮 使用 {model} 模型预测 {horizon} {freq}...")
        result = self.dispatcher.forecast(df, model, horizon, freq)
        print(f"✅ 预测完成，MAE: {result.get('metrics', {}).get('mae', 'N/A')}")
        
        # 3. LLM 分析 (如果有 query)
        analysis = ""
        if query:
            print("🤖 生成分析报告...")
            analysis = self._generate_analysis(df, features, result, query)
        
        return {
            "features": features,
            "forecast": result["forecast_values"],
            "metrics": result.get("metrics", {}),
            "model": model,
            "analysis": analysis,
            "forecast_df": result.get("forecast_df"),
        }
    
    def _generate_analysis(
        self, 
        df: pd.DataFrame, 
        features: TimeSeriesFeatures, 
        forecast_result: Dict,
        query: str
    ) -> str:
        """使用 LLM 生成分析"""
        from openai import OpenAI
        
        client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
        
        # 构建 prompt
        forecast_summary = forecast_result["forecast_values"][:5]  # 前5天
        
        prompt = f"""
用户问题: {query}

数据特征:
- 趋势: {features.trend}
- 波动性: {features.volatility}
- 数据量: {features.data_points} 天
- 时间范围: {features.date_range}

预测结果 (使用 {forecast_result.get('model', 'prophet')} 模型):
- 预测天数: {len(forecast_result['forecast_values'])}
- 前5天预测: {json.dumps(forecast_summary, ensure_ascii=False)}
- MAE: {forecast_result.get('metrics', {}).get('mae', 'N/A')}

请基于以上信息，用中文给出:
1. 数据走势分析 (2-3句)
2. 预测趋势解读 (2-3句)
3. 投资建议 (附风险提示)

保持简洁专业。
"""
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        
        return response.choices[0].message.content


# ============================================================
# 便捷函数
# ============================================================

def quick_forecast(
    df: pd.DataFrame,
    horizon: int = 30,
    model: str = "prophet",
    query: str = None,
    date_col: str = None,
    value_col: str = None,
) -> Dict[str, Any]:
    """
    快速预测函数
    
    Example:
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol="000001", period="daily", 
                                start_date="20240101", end_date="20241231")
        result = quick_forecast(df, horizon=30, query="预测未来走势")
    """
    pipeline = TimeSeriesPipeline()
    
    # 准备数据
    prepared_df = pipeline.prepare_data(df, date_col, value_col)
    
    # 执行预测
    return pipeline.forecast(prepared_df, horizon, model, query=query)


# ============================================================
# 可视化
# ============================================================

def plot_forecast(df: pd.DataFrame, forecast_values: List[Dict], title: str = "时序预测"):
    """绘制预测图"""
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(12, 5))
    
    # 历史数据
    ax.plot(df["ds"], df["y"], label="历史数据", color="blue", linewidth=1.5)
    
    # 预测数据
    forecast_dates = pd.to_datetime([f["date"] for f in forecast_values])
    forecast_y = [f["value"] for f in forecast_values]
    forecast_lower = [f["lower"] for f in forecast_values]
    forecast_upper = [f["upper"] for f in forecast_values]
    
    ax.plot(forecast_dates, forecast_y, label="预测", color="red", linewidth=2, linestyle="--")
    ax.fill_between(forecast_dates, forecast_lower, forecast_upper, alpha=0.2, color="red", label="置信区间")
    
    ax.set_title(title)
    ax.set_xlabel("日期")
    ax.set_ylabel("值")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    return fig


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    # 测试示例
    import akshare as ak
    
    print("获取平安银行数据...")
    df = ak.stock_zh_a_hist(
        symbol="000001", 
        period="daily",
        start_date="20240101", 
        end_date="20241231",
        adjust=""
    )
    
    print("执行预测...")
    result = quick_forecast(
        df, 
        horizon=30, 
        query="分析平安银行走势，预测未来30天"
    )
    
    print("\n" + "="*50)
    print("预测结果 (前10天):")
    for item in result["forecast"][:10]:
        print(f"  {item['date']}: {item['value']} [{item['lower']}, {item['upper']}]")
    
    print("\n分析报告:")
    print(result["analysis"])
