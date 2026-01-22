"""
情绪分析 Agent
==============

使用 LLM 进行新闻情绪分析（流式输出）
"""

from typing import Dict, Any, Callable, Optional

from .base import BaseAgent


class SentimentAgent(BaseAgent):
    """新闻情绪分析 Agent（流式输出）"""

    DEFAULT_TEMPERATURE = 0.2

    SYSTEM_PROMPT = """你是金融情绪分析专家。分析以下股票新闻，给出情绪判断和分析说明。

分析要点:
- 关注利好/利空消息的比例和重要性
- 考虑政策、业绩、市场情绪等因素
- 提取最重要的3-5条新闻摘要

输出格式：
第一行输出情绪得分（-1到1之间的小数，负面为负，正面为正），格式：SCORE:0.35
第二行空行
之后输出分析说明（50-100字），包含：
1. 整体情绪判断（正面/中性/负面）
2. 主要影响因素
3. 关键事件摘要"""

    PARAMS_SYSTEM_PROMPT = """你是时序预测专家。根据股票特征和情绪分析推荐 Prophet 模型参数。

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

    def analyze_streaming(
        self,
        news_items: list,
        on_chunk: Callable[[str], None]
    ) -> Dict[str, Any]:
        """
        流式分析新闻情绪

        Args:
            news_items: 新闻列表 [{"title": ..., "content": ..., "source": ...}, ...]
            on_chunk: 流式回调函数，接收文本片段

        Returns:
            {"score": float, "description": str}
        """
        if not news_items:
            default_desc = "无新闻数据，默认中性情绪"
            on_chunk(default_desc)
            return {"score": 0.0, "description": default_desc}

        # 格式化新闻
        news_text = self._format_news_items(news_items)

        messages = self.build_messages(
            user_content=f"新闻列表:\n{news_text}",
            system_prompt=self.SYSTEM_PROMPT
        )

        # 流式调用
        full_content = ""
        score = 0.0
        description_started = False
        description_buffer = ""

        def stream_handler(chunk: str):
            nonlocal full_content, score, description_started, description_buffer

            full_content += chunk

            # 解析 score（第一行）
            if not description_started:
                if "\n\n" in full_content:
                    parts = full_content.split("\n\n", 1)
                    first_line = parts[0].strip()
                    # 解析 SCORE:xxx
                    if "SCORE:" in first_line.upper():
                        try:
                            score_str = first_line.upper().split("SCORE:")[-1].strip()
                            score = float(score_str)
                        except ValueError:
                            score = 0.0
                    description_started = True
                    # 如果已经有描述内容，发送
                    if len(parts) > 1 and parts[1]:
                        on_chunk(parts[1])
                        description_buffer = parts[1]
            else:
                # 描述部分，直接流式输出
                on_chunk(chunk)
                description_buffer += chunk

        self.call_llm(
            messages,
            stream=True,
            on_chunk=stream_handler,
            fallback=""
        )

        return {
            "score": score,
            "description": description_buffer.strip() or "中性情绪"
        }

    def recommend_params(
        self,
        sentiment_result: Dict[str, Any],
        features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        基于情绪分析和时序特征推荐 Prophet 参数

        Args:
            sentiment_result: 情绪分析结果
            features: 时序特征

        Returns:
            Prophet 参数
        """
        user_prompt = f"""股票特征:
- 趋势: {features.get('trend', '未知')}
- 波动性: {features.get('volatility', '未知')}
- 数据点数: {features.get('data_points', 0)}

情绪分析:
- 情绪得分: {sentiment_result.get('score', 0)}
- 描述: {sentiment_result.get('description', '中性')}"""

        messages = self.build_messages(
            user_content=user_prompt,
            system_prompt=self.PARAMS_SYSTEM_PROMPT
        )

        content = self.call_llm(
            messages,
            fallback=None,
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        if content is None:
            return self._default_params()

        return self.parse_json_safe(content, self._default_params())

    def _format_news_items(self, news_items: list, max_items: int = 20) -> str:
        """格式化新闻列表"""
        lines = []
        for i, item in enumerate(news_items[:max_items], 1):
            title = item.get("title", item.get("summarized_title", ""))
            content = item.get("content", item.get("summarized_content", ""))[:100]
            source = item.get("source_name", item.get("source_type", ""))
            lines.append(f"{i}. 【{title}】{content}... ({source})")
        return "\n".join(lines)

    def _default_params(self) -> Dict[str, Any]:
        """返回默认参数推荐"""
        return {
            "changepoint_prior_scale": 0.05,
            "seasonality_prior_scale": 10,
            "changepoint_range": 0.8,
            "reasoning": "使用默认参数"
        }
