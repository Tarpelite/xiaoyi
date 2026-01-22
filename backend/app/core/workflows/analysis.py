"""
分析流程模块
=============

封装参数推荐的调用逻辑
"""

import asyncio
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents import SentimentAgent


async def recommend_forecast_params(
    sentiment_agent: "SentimentAgent",
    sentiment_result: Dict[str, Any],
    features: Dict[str, Any]
) -> Dict[str, Any]:
    """
    基于情绪分析和时序特征推荐 Prophet 参数

    Args:
        sentiment_agent: 情感分析 Agent 实例
        sentiment_result: 情感分析结果 {"score": float, "description": str}
        features: 时序特征

    Returns:
        Prophet 参数: changepoint_prior_scale, seasonality_prior_scale, changepoint_range
    """
    return await asyncio.to_thread(
        sentiment_agent.recommend_params,
        sentiment_result or {},
        features
    )
