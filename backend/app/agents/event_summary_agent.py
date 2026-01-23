"""
事件总结Agent
==================

基于Deepseek的智能新闻聚合与事件凝练服务
用于将价格变化+新闻聚合总结为简洁的事件描述
"""

from typing import List, Dict
from datetime import datetime
from openai import OpenAI


class EventSummaryAgent:
    """
    事件总结Agent
    
    功能:
    - 聚合异常区间内的新闻
    - 结合价格变化
    - 生成30字以内的凝练事件摘要
    """
    
    def __init__(self, api_key: str = None):
        """
        初始化
        
        Args:
            api_key: Deepseek API密钥（可选，从环境变量读取）
        """
        import os
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )
    
    def summarize_zone(
        self,
        zone_dates: List[str],
        price_change: float,
        news_items: List[Dict]
    ) -> str:
        """
        总结异常区间的关键事件
        
        Args:
            zone_dates: 区间日期列表，如 ["2025-10-13", "2025-10-14", "2025-10-15"]
            price_change: 区间价格变化百分比，如 -3.2
            news_items: 新闻列表，每条包含 {title, content_type, publish_time}
            
        Returns:
            凝练的事件摘要（30字以内）
        """
        if not news_items:
            # 无新闻时，仅基于价格变化
            if abs(price_change) < 1:
                return "价格小幅波动"
            elif price_change > 0:
                return f"股价上涨{price_change:.1f}%"
            else:
                return f"股价下跌{abs(price_change):.1f}%"
        
        # 构建prompt
        start_date = zone_dates[0]
        end_date = zone_dates[-1]
        
        news_summary = "\n".join([
            f"- [{item.get('content_type', '资讯')}] {item.get('title', '')}"
            for item in news_items[:10]  # 最多传10条新闻
        ])
        
        prompt = f"""你是金融分析师。根据以下信息总结这段时期的关键事件（严格控制在30字以内）：

时间: {start_date} 至 {end_date}
价格变化: {price_change:+.1f}%
新闻:
{news_summary}

要求:
1. 提炼最核心的事件（如重大政策、业绩公告、重组等）
2. 突出价格变化的主因
3. 严格控制在30字以内，简洁专业
4. 不要使用"等"、"等等"等模糊词汇

示例：
- "茅台股价七连跌创新低，寒武纪市值反超"
- "首次回购股份，控股股东增持提振信心"
"""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是专业的金融分析师，擅长提炼核心事件。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.3  # 降低随机性，确保专业性
            )
            
            summary = response.choices[0].message.content.strip()
            
            # 截断超长输出
            if len(summary) > 40:
                summary = summary[:37] + "..."
            
            return summary
            
        except Exception as e:
            print(f"[EventSummaryAgent] Error calling Deepseek: {e}")
            # Fallback到简单总结
            if news_items:
                first_news = news_items[0].get('title', '')[:20]
                return f"{first_news}等{len(news_items)}条信息"
            else:
                return f"价格变化{price_change:+.1f}%"
