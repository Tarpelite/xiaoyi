"""
Report Agent 模块
=================

负责生成金融分析报告
"""

import json
from typing import Dict, Any, List, Optional
from openai import OpenAI


class ReportAgent:
    """分析报告生成 Agent"""
    
    def __init__(self, api_key: str):
        """
        初始化 Report Agent
        
        Args:
            api_key: DeepSeek API Key
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    
    def generate(
        self,
        user_question: str,
        features: Dict[str, Any],
        forecast_result: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        生成分析报告
        
        Args:
            user_question: 用户原始问题
            features: 时序特征分析结果
            forecast_result: 预测结果
            conversation_history: 对话历史，格式: [{"role": "user", "content": "..."}, ...]
            
        Returns:
            生成的分析报告文本
        """
        forecast_preview = forecast_result["forecast"][:7]  # 前7天
        
        system_prompt = """你是专业的金融分析助手。根据用户问题和数据分析结果，生成简洁、专业、客观的分析报告。

如果用户的问题涉及之前的对话（如"这个预测的置信度"、"刚才的分析"），请结合对话历史来理解上下文并给出更准确的回答。"""
        
        prompt = f"""用户问题: {user_question}

数据特征:
- 趋势: {features['trend']}
- 波动性: {features['volatility']}
- 均值: {features['mean']}, 最新: {features['latest']}
- 区间: [{features['min']}, {features['max']}]
- 数据量: {features['data_points']} 天
- 时间: {features['date_range']}

预测结果 ({forecast_result['model']}):
- 预测天数: {len(forecast_result['forecast'])}
- 未来7天: {json.dumps(forecast_preview, ensure_ascii=False)}
- MAE: {forecast_result['metrics'].get('mae', 'N/A')}

请生成简洁的中文分析报告:
1. 历史走势分析 (2句)
2. 预测趋势解读 (2句)  
3. 投资建议 + 风险提示 (2句)

保持专业客观，总共不超过150字。"""
        
        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]
        
        # 如果有历史对话，添加到消息中（保留最近5轮）
        if conversation_history:
            # 只取最近的对话（避免token超限）
            recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            for msg in recent_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # 添加当前提示
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.3,
            max_tokens=300,
        )
        
        return response.choices[0].message.content
