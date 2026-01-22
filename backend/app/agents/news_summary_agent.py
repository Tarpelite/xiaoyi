"""
新闻总结 Agent
==============

使用 LLM 批量总结新闻标题和内容
"""

import json
from typing import Dict, Any, List, Tuple

from .base import BaseAgent
from app.schemas.session_schema import NewsItem, SummarizedNewsItem


class NewsSummaryAgent(BaseAgent):
    """新闻总结 Agent - 批量总结新闻标题和内容"""

    DEFAULT_TEMPERATURE = 0.3

    def summarize(self, news_items: List[NewsItem]) -> Tuple[List[SummarizedNewsItem], str]:
        """
        批量总结新闻

        Args:
            news_items: 原始新闻列表

        Returns:
            Tuple of:
            - summarized_news: 总结后的新闻列表
            - raw_response: LLM 原始输出 (用于思考日志)
        """
        if not news_items:
            return [], ""

        news_text = self._format_news_for_prompt(news_items)
        prompt = self._build_prompt(news_text, len(news_items))

        messages = self.build_messages(user_content=prompt)

        content = self.call_llm(messages, fallback=None)

        if content is None:
            print(f"[{self.agent_name}] LLM 总结失败，使用原标题")
            return self._fallback_result(news_items), ""

        try:
            parsed_response = self.parse_json(content)
            result = self._build_result(news_items, parsed_response)
            print(f"[{self.agent_name}] LLM 批量总结完成: {len(result)} 条")
            return result, content
        except Exception as e:
            print(f"[{self.agent_name}] JSON 解析失败: {e}")
            return self._fallback_result(news_items), ""

    def _format_news_for_prompt(self, news_items: List[NewsItem]) -> str:
        """格式化新闻列表用于 prompt"""
        news_text = ""
        for i, item in enumerate(news_items, 1):
            content_preview = item.content[:200] if item.content else ""
            news_text += f"{i}. 标题: {item.title}\n"
            news_text += f"   内容: {content_preview}\n"
            news_text += f"   URL: {item.url}\n"
            news_text += f"   当前来源: {item.source_name}\n\n"
        return news_text

    def _build_prompt(self, news_text: str, count: int) -> str:
        """构建 LLM prompt"""
        return f"""你是一个金融新闻编辑。请对以下 {count} 条新闻进行总结：

{news_text}

要求:
1. 为每条新闻生成一个简洁的摘要标题 (不超过25字)
2. 为每条新闻生成一个简短的内容摘要 (不超过60字)
3. 根据 URL 识别新闻来源的中文名称（如 eastmoney.com → 东方财富，sina.com.cn → 新浪财经，cls.cn → 财联社，10jqka.com.cn → 同花顺）。如果"当前来源"已经是有意义的中文名称，可以直接使用。
4. 保持客观中立，去除标题党成分
5. 突出与股票/金融相关的关键信息

请严格按照以下 JSON 数组格式输出，不要输出任何其他内容:
[
  {{"index": 1, "summarized_title": "...", "summarized_content": "...", "source_name": "东方财富"}},
  {{"index": 2, "summarized_title": "...", "summarized_content": "...", "source_name": "新浪财经"}},
  ...
]"""

    def _build_result(
        self,
        news_items: List[NewsItem],
        summaries: List[Dict[str, Any]]
    ) -> List[SummarizedNewsItem]:
        """根据 LLM 总结构建结果列表"""
        result = []
        for i, item in enumerate(news_items):
            summary = next((s for s in summaries if s.get("index") == i + 1), None)
            if summary:
                source_name = summary.get("source_name") or item.source_name
                result.append(SummarizedNewsItem(
                    summarized_title=summary.get("summarized_title", item.title[:50]),
                    summarized_content=summary.get("summarized_content", item.content[:100] if item.content else ""),
                    original_title=item.title,
                    url=item.url,
                    published_date=item.published_date,
                    source_type=item.source_type,
                    source_name=source_name
                ))
            else:
                result.append(SummarizedNewsItem(
                    summarized_title=item.title[:50] if len(item.title) > 50 else item.title,
                    summarized_content=item.content[:100] if item.content else "",
                    original_title=item.title,
                    url=item.url,
                    published_date=item.published_date,
                    source_type=item.source_type,
                    source_name=item.source_name
                ))
        return result

    def _fallback_result(self, news_items: List[NewsItem]) -> List[SummarizedNewsItem]:
        """LLM 调用失败时的降级处理"""
        return [
            SummarizedNewsItem(
                summarized_title=n.title[:50] if len(n.title) > 50 else n.title,
                summarized_content=n.content[:100] if n.content else "",
                original_title=n.title,
                url=n.url,
                published_date=n.published_date,
                source_type=n.source_type,
                source_name=n.source_name
            )
            for n in news_items
        ]
