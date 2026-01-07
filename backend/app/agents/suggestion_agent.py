"""
快速追问建议生成 Agent
=======================

根据对话上下文生成相关的快速追问建议
"""

from typing import List, Dict, Optional
from openai import OpenAI


class SuggestionAgent:
    """快速追问建议生成 Agent"""
    
    def __init__(self, api_key: str):
        """
        初始化 Suggestion Agent
        
        Args:
            api_key: DeepSeek API Key
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    
    def generate_suggestions(
        self,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> List[str]:
        """
        根据对话历史生成快速追问建议
        
        Args:
            conversation_history: 对话历史，格式: [{"role": "user", "content": "..."}, ...]
            
        Returns:
            4个相关的快速追问建议列表
        """
        system_prompt = """你是金融分析助手的快速追问建议生成器。根据对话历史，生成4个相关的快速追问建议。

要求：
1. 如果对话中提到了具体的股票（如"茅台"、"平安银行"），追问建议应该围绕该股票
2. 如果对话中提到了预测结果，追问建议可以包括：置信度、风险、投资建议等
3. 如果对话中提到了模型，追问建议可以包括：换模型、模型对比等
4. 如果对话为空或没有明确主题，提供通用的分析建议
5. 每个建议应该简洁明了，不超过20个字
6. 建议应该具有实际价值，能够帮助用户深入了解分析结果

返回格式：JSON数组，包含4个字符串
{
    "suggestions": ["建议1", "建议2", "建议3", "建议4"]
}"""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加对话历史
        if conversation_history:
            recent_history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
            context_parts = ["对话历史："]
            for msg in recent_history:
                role_name = "用户" if msg["role"] == "user" else "助手"
                context_parts.append(f"{role_name}: {msg['content']}")
            messages.append({
                "role": "user",
                "content": "\n".join(context_parts) + "\n\n请根据以上对话历史，生成4个相关的快速追问建议。"
            })
        else:
            messages.append({
                "role": "user",
                "content": "当前没有对话历史，请生成4个通用的股票分析快速追问建议。"
            })
        
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        suggestions = result.get("suggestions", [])
        
        # 确保返回4个建议，如果不够则补充默认建议
        default_suggestions = [
            "帮我分析一下茅台，预测下个季度走势",
            "查看最近的市场趋势",
            "对比几只白酒股的表现",
            "生成一份投资分析报告"
        ]
        
        while len(suggestions) < 4:
            suggestions.append(default_suggestions[len(suggestions)])
        
        return suggestions[:4]

