"""
情绪分析 Agent
==============

使用 LLM 进行新闻情绪分析和 Prophet 参数推荐
"""

import json
from typing import Dict, Any, List
import pandas as pd
from openai import OpenAI


class SentimentAgent:
    """新闻情绪分析 Agent"""

    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

    def analyze(self, news_df: pd.DataFrame) -> Dict[str, Any]:
        """
        分析新闻情绪

        Args:
            news_df: 新闻数据 DataFrame

        Returns:
            情绪分析结果: overall_score, sentiment, confidence, key_events, analysis_text
        """
        if news_df is None or news_df.empty:
            return self._default_sentiment()

        news_list = self._format_news(news_df)

        system_prompt = """你是金融情绪分析专家。分析以下股票新闻，给出整体情绪判断。

返回 JSON 格式:
{
    "overall_score": float,  // -1(极负面) 到 1(极正面)
    "sentiment": str,        // 正面/偏正面/中性/偏负面/负面
    "confidence": float,     // 0-1 置信度
    "key_events": [str],     // 3-5个关键事件摘要，每个不超过20字
    "analysis_text": str     // 50字以内的情绪分析说明
}

分析要点:
- 关注利好/利空消息的比例和重要性
- 考虑政策、业绩、市场情绪等因素
- key_events 提取最重要的3-5条新闻摘要
- 只返回 JSON"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"新闻列表:\n{news_list}"}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            result["news_count"] = len(news_df)
            return result

        except Exception as e:
            print(f"情绪分析失败: {e}")
            return self._default_sentiment()

    def recommend_params(
        self,
        sentiment_result: Dict[str, Any],
        features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        基于情绪分析和时序特征推荐 Prophet 参数

        Returns:
            Prophet 参数: changepoint_prior_scale, seasonality_prior_scale, changepoint_range
        """
        system_prompt = """你是时序预测专家。根据股票特征和情绪分析推荐 Prophet 模型参数。

参数说明:
- changepoint_prior_scale: 趋势变化敏感度 (0.001-0.5)，默认 0.05
- seasonality_prior_scale: 季节性强度 (1-25)，默认 10
- changepoint_range: 变点检测范围 (0.8-0.95)，默认 0.8

返回 JSON 格式:
{
    "changepoint_prior_scale": float,
    "seasonality_prior_scale": float,
    "changepoint_range": float,
    "reasoning": str  // 30字以内的推荐理由
}

只返回 JSON"""

        user_prompt = f"""股票特征:
- 趋势: {features.get('trend', '未知')}
- 波动性: {features.get('volatility', '未知')}
- 数据点数: {features.get('data_points', 0)}

情绪分析:
- 情绪: {sentiment_result.get('sentiment', '中性')}
- 得分: {sentiment_result.get('overall_score', 0)}
- 关键事件: {sentiment_result.get('key_events', [])}"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"参数推荐失败: {e}")
            return self._default_params()

    def _format_news(self, news_df: pd.DataFrame, max_items: int = 30) -> str:
        """格式化新闻列表"""
        news_items = []

        title_cols = ["新闻标题", "标题", "title", "Title"]
        content_cols = ["新闻内容", "内容", "content", "Content"]
        time_cols = ["发布时间", "时间", "datetime", "time", "Date"]

        title_col = next((c for c in title_cols if c in news_df.columns), None)
        content_col = next((c for c in content_cols if c in news_df.columns), None)
        time_col = next((c for c in time_cols if c in news_df.columns), None)

        for idx, row in news_df.head(max_items).iterrows():
            item = f"{idx + 1}. "
            if title_col:
                item += f"【{row[title_col]}】"
            if content_col:
                content = str(row[content_col])[:100]
                item += f" {content}"
            if time_col:
                item += f" ({row[time_col]})"
            news_items.append(item)

        return "\n".join(news_items)

    def _default_sentiment(self) -> Dict[str, Any]:
        """返回默认情绪结果"""
        return {
            "overall_score": 0.0,
            "sentiment": "中性",
            "confidence": 0.5,
            "key_events": [],
            "news_count": 0,
            "analysis_text": "无新闻数据，默认中性情绪"
        }

    def _default_params(self) -> Dict[str, Any]:
        """返回默认参数推荐"""
        return {
            "changepoint_prior_scale": 0.05,
            "seasonality_prior_scale": 10,
            "changepoint_range": 0.8,
            "reasoning": "使用默认参数"
        }

    def analyze_with_links(
        self,
        akshare_news_df: pd.DataFrame,
        tavily_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析新闻情绪，生成带链接的格式化文本

        Args:
            akshare_news_df: AkShare 新闻 DataFrame（无 URL）
            tavily_results: Tavily 搜索结果（有 URL）

        Returns:
            包含 sentiment、overall_score、formatted_text 的字典
        """
        combined_context = self._build_combined_context(akshare_news_df, tavily_results)

        if not combined_context:
            return self._default_sentiment_with_text()

        system_prompt = """你是金融情绪分析专家。分析以下新闻，返回情绪判断和格式化摘要。

返回 JSON 格式:
{
    "overall_score": float,  // -1(极负面) 到 1(极正面)
    "sentiment": str,        // 正面/偏正面/中性/偏负面/负面
    "confidence": float,     // 0-1 置信度
    "formatted_text": str    // markdown 格式文本
}

formatted_text 格式要求:
1. 开头写整体情绪判断和得分
2. 列出 3-5 条关键新闻，每条一行
3. 如果新闻有 URL，使用 markdown 链接 [标题](url)
4. 结尾写简短分析说明

只返回 JSON"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"新闻内容:\n{combined_context}"}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            akshare_count = len(akshare_news_df) if akshare_news_df is not None and not akshare_news_df.empty else 0
            result["news_count"] = akshare_count + tavily_results.get("count", 0)
            return result

        except Exception as e:
            print(f"情绪分析（带链接）失败: {e}")
            return self._default_sentiment_with_text()

    def _build_combined_context(
        self,
        akshare_df: pd.DataFrame,
        tavily_results: Dict[str, Any]
    ) -> str:
        """构建综合新闻上下文"""
        context_parts = []

        if akshare_df is not None and not akshare_df.empty:
            context_parts.append("=== 即时新闻（AkShare）===")
            title_col = next((c for c in ["新闻标题", "标题", "title"] if c in akshare_df.columns), None)
            content_col = next((c for c in ["新闻内容", "内容", "content"] if c in akshare_df.columns), None)

            for _, row in akshare_df.head(20).iterrows():
                title = row.get(title_col, "") if title_col else ""
                content = str(row.get(content_col, ""))[:100] if content_col else ""
                if title:
                    context_parts.append(f"- {title}: {content}")

        if tavily_results.get("results"):
            context_parts.append("\n=== 网络新闻（Tavily，带URL）===")
            for item in tavily_results["results"]:
                title = item.get("title", "")
                url = item.get("url", "")
                content = item.get("content", "")[:100]
                context_parts.append(f"- 【{title}】({url}): {content}")

        return "\n".join(context_parts)

    def _default_sentiment_with_text(self) -> Dict[str, Any]:
        """返回默认情绪结果（带格式化文本）"""
        return {
            "overall_score": 0.0,
            "sentiment": "中性",
            "confidence": 0.5,
            "news_count": 0,
            "formatted_text": """**市场情绪分析**

- 整体情绪: 中性
- 情绪得分: 0.00

**分析说明:** 未获取到相关新闻，默认中性情绪。"""
        }
