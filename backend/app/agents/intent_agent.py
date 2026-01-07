"""
意图判断 Agent 模块
===================

判断用户意图：是否需要执行新的数据分析，还是只需要回答问题
"""

from typing import Dict, Any, List, Optional
from openai import OpenAI


class IntentAgent:
    """意图判断 Agent"""
    
    def __init__(self, api_key: str):
        """
        初始化 Intent Agent
        
        Args:
            api_key: DeepSeek API Key
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    
    def judge_intent(
        self, 
        user_query: str, 
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        判断用户意图
        
        Args:
            user_query: 用户当前问题
            conversation_history: 对话历史
            
        Returns:
            包含 intent 和 reason 的字典
            intent: "analyze" (需要执行新分析) 或 "answer" (只需要回答问题)
        """
        system_prompt = """你是意图判断助手。根据用户问题和对话历史，判断用户是想执行新的数据分析，还是只想提问。

判断标准 - 返回 "analyze" 的情况：
- 用户要求分析新的股票或数据（如"分析一下茅台"、"预测下个季度"）
- 用户要求更换模型重新分析（如"换个XGBoost模型"、"用随机森林预测一下"、"换个模型预测"）
- 用户要求改变预测参数（如"预测未来60天"、"预测下个季度"）
- 用户明确要求执行分析、预测等操作
- 对话历史为空，且用户问题包含分析、预测等关键词

判断标准 - 返回 "answer" 的情况：
- 用户只是提问，不要求执行新分析（如"这个预测的置信度是多少"、"刚才的分析结果是什么"、"这个模型怎么样"）
- 用户询问已有结果的含义、解释、建议等
- 用户要求总结、说明、解释之前的结果

重要：如果用户说"换个模型"、"用XX模型预测"、"重新预测"等，必须返回 "analyze"，因为需要执行新的分析。

只返回 JSON 格式：
{
    "intent": "analyze" 或 "answer",
    "reason": "判断理由"
}"""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加对话历史
        if conversation_history:
            recent_history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
            for msg in recent_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # 添加当前问题
        messages.append({
            "role": "user", 
            "content": f"用户问题: {user_query}\n\n请判断用户意图。"
        })
        
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        return result
    
    def answer_question(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        基于对话历史回答问题（不执行新分析）
        
        Args:
            user_query: 用户问题
            conversation_history: 对话历史
            
        Returns:
            回答文本
        """
        system_prompt = """你是专业的金融分析助手。根据对话历史中的分析结果，回答用户的问题。

如果对话历史中有之前的分析结果，请基于这些结果回答问题。
如果问题涉及预测结果、模型性能、数据特征等，请从对话历史中提取相关信息。
如果无法从历史中找到相关信息，请礼貌地说明需要先进行分析。"""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加对话历史
        if conversation_history:
            recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            for msg in recent_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # 添加当前问题
        messages.append({
            "role": "user",
            "content": user_query
        })
        
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.3,
            max_tokens=500,
        )
        
        return response.choices[0].message.content

