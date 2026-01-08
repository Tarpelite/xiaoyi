"""
意图判断 Agent 模块
===================

判断用户意图：是否需要执行新的数据分析，还是只需要回答问题
"""

from typing import Dict, Any, List, Optional, Generator
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
        system_prompt = """你是意图判断助手。根据用户问题和对话历史，判断用户意图、需要的功能、模型和时间窗口参数。

## 意图判断 (intent)

返回 "analyze" 的情况：
- 用户要求分析股票或数据（如"分析一下茅台"、"预测下个季度"、"看看比亚迪走势"）
- 用户要求更换模型重新分析（如"换个XGBoost模型"、"用随机森林预测"）
- 用户要求改变预测参数（如"预测未来60天"）
- 用户明确要求执行分析、预测等操作

返回 "answer" 的情况：
- 用户只是提问（如"这个预测的置信度是多少"、"刚才的结果什么意思"）
- 用户询问已有结果的含义、解释、建议
- 闲聊或与分析无关的问题

## 功能判断 (tools)

- forecast: 是否需要序列预测（用户提到预测、分析走势、趋势等）
- report_rag: 是否需要研报检索（用户提到研报、券商报告、评级、行业分析、能源报告、研究报告等）
- news_rag: 是否需要新闻搜索
  - 返回 true: 用户明确要搜索新闻、查询资讯、了解消息
    - 例如: "茅台最近有什么新闻"、"搜索比亚迪的资讯"、"查一下宁德时代的报道"、"最近有什么关于新能源的消息"
  - 返回 false: 用户只是分析/预测（forecast 流程内部会自动获取新闻做情绪分析）
    - 例如: "分析茅台"、"预测走势"

## 模型选择 (model)

根据用户描述选择最合适的预测模型：
- "prophet": 默认模型，适合长期预测、季节性数据
- "xgboost": 用户提到 XGBoost、XGB、梯度提升、非线性
- "randomforest": 用户提到随机森林、RF、集成学习
- "dlinear": 用户提到 DLinear、线性模型、轻量

如果用户没有指定模型，默认使用 "prophet"。

## 时间窗口参数 (params)

根据用户描述识别时间窗口：

history_days (历史数据天数):
- 用户提到"过去一年"、"近一年" → 365
- 用户提到"过去半年"、"近半年" → 180
- 用户提到"过去三个月"、"近三个月" → 90
- 用户提到"过去一个月"、"近一个月" → 30
- 默认值: 365

forecast_horizon (预测天数):
- 用户提到"预测一年"、"未来一年" → 365
- 用户提到"下个季度"、"未来三个月" → 90
- 用户提到"下个月"、"未来一个月" → 30
- 用户提到"未来两周"、"下两周" → 14
- 用户提到"未来一周" → 7
- 用户提到"未来N天" → N
- 默认值: 30

只返回 JSON 格式：
{
    "intent": "analyze" 或 "answer",
    "reason": "判断理由",
    "tools": {
        "forecast": true/false,
        "report_rag": true/false,
        "news_rag": true/false
    },
    "model": "prophet" 或 "xgboost" 或 "randomforest" 或 "dlinear",
    "params": {
        "history_days": 365,
        "forecast_horizon": 30
    }
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

    def answer_question_stream(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Generator[str, None, None]:
        """
        基于对话历史流式回答问题（不执行新分析）

        Args:
            user_query: 用户问题
            conversation_history: 对话历史

        Yields:
            文本片段
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

        # 使用流式响应
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.3,
            max_tokens=500,
            stream=True
        )

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def summarize_news_stream(
        self,
        user_query: str,
        news_context: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Generator[str, None, None]:
        """
        流式总结新闻内容

        Args:
            user_query: 用户问题
            news_context: 新闻搜索结果（格式化后的文本）
            conversation_history: 对话历史

        Yields:
            文本片段
        """
        system_prompt = """你是专业的财经新闻分析师。根据搜索到的新闻内容，为用户提供简洁的总结。

要求：
1. 提取最重要的 3-5 条新闻要点
2. 分析新闻对市场/股票的潜在影响
3. 语言简洁，重点突出
4. 如果新闻数量较少或质量不高，如实说明
5. **重要**：在提到具体新闻时，必须使用 markdown 链接格式 [新闻标题](url) 嵌入原文链接

示例输出格式：
根据搜索到的新闻，贵州茅台近期主要有以下动态：

1. **业绩表现**：[贵州茅台发布年报，营收突破1500亿](https://finance.sina.com.cn/xxx)，显示公司业绩稳健增长。

2. **市场动态**：[茅台酒批价春节前稳中有升](https://eastmoney.com/xxx)，市场需求持续旺盛。"""

        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            recent_history = conversation_history[-4:] if len(conversation_history) > 4 else conversation_history
            for msg in recent_history:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({
            "role": "user",
            "content": f"用户问题: {user_query}\n\n搜索到的新闻:\n{news_context}\n\n请总结这些新闻。"
        })

        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.3,
            max_tokens=800,
            stream=True
        )

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def extract_search_keywords(self, user_query: str) -> Dict[str, Any]:
        """
        从用户查询中提取搜索关键词，判断是否股票相关

        Args:
            user_query: 用户原始问题，如 "找茅台最近的新闻"

        Returns:
            {
                "keywords": str,      # 提取的关键词
                "is_stock": bool,     # 是否是股票相关
                "stock_name": str,    # 股票名称（如有）
                "stock_code": str,    # 股票代码（如有）
            }
        """
        system_prompt = """从用户问题中提取搜索关键词，判断是否股票相关。

分析用户想搜索什么，提取核心关键词，判断是否涉及具体股票/公司。

示例：
- "找茅台最近的新闻" → keywords="贵州茅台", is_stock=true, stock_name="贵州茅台", stock_code="600519"
- "搜索比亚迪的资讯" → keywords="比亚迪", is_stock=true, stock_name="比亚迪", stock_code="002594"
- "查一下新能源行业动态" → keywords="新能源行业", is_stock=false, stock_name="", stock_code=""
- "最近有什么关于人工智能的消息" → keywords="人工智能", is_stock=false, stock_name="", stock_code=""
- "宁德时代最新动态" → keywords="宁德时代", is_stock=true, stock_name="宁德时代", stock_code="300750"
- "中石油有什么新闻" → keywords="中国石油", is_stock=true, stock_name="中国石油", stock_code="601857"

返回 JSON 格式:
{
    "keywords": "提取的搜索关键词",
    "is_stock": true/false,
    "stock_name": "股票名称或空字符串",
    "stock_code": "股票代码或空字符串"
}"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"用户问题: {user_query}"}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            import json
            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"[IntentAgent] 关键词提取失败: {e}")
            return {
                "keywords": user_query,
                "is_stock": False,
                "stock_name": "",
                "stock_code": ""
            }

