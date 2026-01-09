"""
统一意图识别 Agent
==================

一次 LLM 调用返回所有意图信息:
- is_in_scope: 是否在服务范围内 (金融/股票相关)
- is_forecast: 是否需要预测分析
- 工具开关: enable_rag, enable_search, enable_domain_info
- stock_mention: 提及的股票
- raw_*_keywords: 初步关键词 (股票匹配后优化)
- 预测参数: forecast_model, history_days, forecast_horizon
"""

from typing import Dict, List, Optional, Generator
import json
from openai import OpenAI

from app.schemas.session_schema import UnifiedIntent, ResolvedKeywords


class IntentAgent:
    """统一意图识别 Agent"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        """
        初始化 Intent Agent

        Args:
            api_key: API Key
            base_url: API Base URL
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

    def recognize_intent(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> UnifiedIntent:
        """
        统一意图识别

        一次 LLM 调用返回所有意图信息

        Args:
            user_query: 用户问题
            conversation_history: 对话历史

        Returns:
            UnifiedIntent 对象
        """
        system_prompt = """你是金融时序分析助手的意图识别模块。根据用户问题，一次性判断所有意图信息。

## 服务范围 (is_in_scope)

判断问题是否在服务范围内（金融、股票、投资、经济相关）：
- in_scope=true:
  - 股票分析/预测（如"分析茅台走势"、"预测比亚迪"）
  - 金融新闻查询（如"最近有什么股市新闻"）
  - 研报查询（如"茅台的研报观点"）
  - 宏观经济问题（如"经济形势怎么样"）
  - 投资相关问题（如"该买什么股票"）
  - 金融闲聊（如"你好"、"谢谢" - 金融助手礼貌性回复）

- in_scope=false:
  - 完全无关的问题（如"今天天气怎么样"、"北京有什么好吃的"、"帮我写代码"）
  - 此时必须设置 out_of_scope_reply 友好拒绝

## 预测判断 (is_forecast)

判断是否需要执行股票预测分析：
- is_forecast=true:
  - 明确要求分析/预测股票走势（"分析茅台"、"预测未来走势"）
  - 要求改变模型重新分析（"换XGBoost模型"）
  - 要求改变时间参数（"预测未来60天"）

- is_forecast=false:
  - 只是查询新闻/研报（"茅台最近有什么新闻"、"茅台研报观点"）
  - 闲聊或追问（"刚才的结果什么意思"）
  - 无需预测的问题

## 工具开关

判断需要启用哪些工具（可同时开启多个）：

- enable_rag: 研报知识库检索
  - true: 用户提到研报、研究报告、券商观点、评级、行业分析
  - 示例: "茅台的研报观点"、"分析师怎么看比亚迪"

- enable_search: 网络搜索
  - true: 用户明确要搜索新闻/资讯，或需要最新信息
  - 示例: "搜索茅台新闻"、"帮我查一下新能源政策"

- enable_domain_info: 领域信息获取
  - true: 需要获取股票相关的领域信息（实时新闻、行情等）
  - 在预测流程中通常自动开启
  - 示例: "今天股市有什么新闻"

注意：
- 预测流程 (is_forecast=true) 通常自动开启 enable_search 和 enable_domain_info
- 非预测的新闻查询，如果用户只是随便问问，开启 enable_domain_info
- 非预测的明确搜索，开启 enable_search

## 股票提取 (stock_mention)

从用户问题中提取提到的股票名称/代码：
- 单股票: "茅台"、"600519"、"比亚迪"
- 多股票: "茅台,五粮液" (逗号分隔)
- 无股票: 留空

## 关键词提取 (raw_*_keywords)

提取初步搜索关键词（后续会根据股票匹配结果优化）：
- raw_search_keywords: 网络搜索关键词
- raw_rag_keywords: 研报检索关键词
- raw_domain_keywords: 领域信息关键词

示例：
- "分析茅台走势" → raw_search_keywords=["茅台走势", "茅台分析"]
- "搜索新能源政策" → raw_search_keywords=["新能源政策", "新能源补贴"]

## 预测参数

仅 is_forecast=true 时需要设置：
- forecast_model: prophet(默认)/xgboost/randomforest/dlinear
- history_days: 历史数据天数 (默认365)
- forecast_horizon: 预测天数 (默认30)

根据用户描述调整：
- "用XGBoost" → model="xgboost"
- "预测三个月" → forecast_horizon=90
- "看半年数据" → history_days=180

返回 JSON 格式:
{
    "is_in_scope": true/false,
    "is_forecast": true/false,
    "enable_rag": true/false,
    "enable_search": true/false,
    "enable_domain_info": true/false,
    "stock_mention": "股票名称或空字符串",
    "raw_search_keywords": ["关键词1", "关键词2"],
    "raw_rag_keywords": ["关键词1"],
    "raw_domain_keywords": ["关键词1"],
    "forecast_model": "prophet",
    "history_days": 365,
    "forecast_horizon": 30,
    "reason": "判断理由",
    "out_of_scope_reply": "若超出范围的友好回复，否则为null"
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
            "content": f"用户问题: {user_query}\n\n请进行意图识别。"
        })

        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # 转换为 UnifiedIntent
        return UnifiedIntent(
            is_in_scope=result.get("is_in_scope", True),
            is_forecast=result.get("is_forecast", False),
            enable_rag=result.get("enable_rag", False),
            enable_search=result.get("enable_search", False),
            enable_domain_info=result.get("enable_domain_info", False),
            stock_mention=result.get("stock_mention") or None,
            raw_search_keywords=result.get("raw_search_keywords", []),
            raw_rag_keywords=result.get("raw_rag_keywords", []),
            raw_domain_keywords=result.get("raw_domain_keywords", []),
            forecast_model=result.get("forecast_model", "prophet"),
            history_days=result.get("history_days", 365),
            forecast_horizon=result.get("forecast_horizon", 30),
            reason=result.get("reason", ""),
            out_of_scope_reply=result.get("out_of_scope_reply")
        )

    def resolve_keywords(
        self,
        intent: UnifiedIntent,
        stock_name: Optional[str] = None,
        stock_code: Optional[str] = None
    ) -> ResolvedKeywords:
        """
        根据股票匹配结果解析最终关键词

        将 raw_*_keywords 中的股票简称替换为全称/代码

        Args:
            intent: 意图识别结果
            stock_name: 匹配到的股票名称 (如 "贵州茅台")
            stock_code: 匹配到的股票代码 (如 "600519")

        Returns:
            ResolvedKeywords
        """
        # 如果没有股票匹配结果，直接返回原始关键词
        if not stock_name and not stock_code:
            return ResolvedKeywords(
                search_keywords=intent.raw_search_keywords,
                rag_keywords=intent.raw_rag_keywords,
                domain_keywords=intent.raw_domain_keywords
            )

        # 有股票匹配结果，增强关键词
        search_keywords = list(intent.raw_search_keywords)
        rag_keywords = list(intent.raw_rag_keywords)
        domain_keywords = list(intent.raw_domain_keywords)

        # 添加股票名称和代码
        if stock_name:
            if stock_name not in search_keywords:
                search_keywords.insert(0, stock_name)
            if stock_name not in rag_keywords:
                rag_keywords.insert(0, stock_name)
            if stock_name not in domain_keywords:
                domain_keywords.insert(0, stock_name)

        if stock_code:
            if stock_code not in search_keywords:
                search_keywords.append(stock_code)
            if stock_code not in domain_keywords:
                domain_keywords.append(stock_code)

        # 替换简称 (如果 stock_mention 存在且与 stock_name 不同)
        if intent.stock_mention and stock_name and intent.stock_mention != stock_name:
            for i, kw in enumerate(search_keywords):
                if intent.stock_mention in kw:
                    search_keywords[i] = kw.replace(intent.stock_mention, stock_name)
            for i, kw in enumerate(rag_keywords):
                if intent.stock_mention in kw:
                    rag_keywords[i] = kw.replace(intent.stock_mention, stock_name)
            for i, kw in enumerate(domain_keywords):
                if intent.stock_mention in kw:
                    domain_keywords[i] = kw.replace(intent.stock_mention, stock_name)

        return ResolvedKeywords(
            search_keywords=search_keywords,
            rag_keywords=rag_keywords,
            domain_keywords=domain_keywords
        )

    def generate_chat_response(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context: Optional[str] = None,
        stream: bool = False
    ):
        """
        生成聊天回复 (非预测流程)

        Args:
            user_query: 用户问题
            conversation_history: 对话历史
            context: 额外上下文 (如检索到的内容)
            stream: 是否流式输出

        Returns:
            回复文本或生成器
        """
        system_prompt = """你是专业的金融分析助手。根据上下文和对话历史回答用户问题。

要求：
1. 回答简洁专业
2. 如果引用了来源，使用 markdown 链接格式 [标题](url)
3. 如果引用了研报，使用格式 [研报名称](rag://文件名.pdf#page=页码)
4. 如果无法从上下文找到相关信息，如实说明"""

        messages = [{"role": "system", "content": system_prompt}]

        # 添加对话历史
        if conversation_history:
            recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            for msg in recent_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        # 构建用户消息
        user_content = user_query
        if context:
            user_content = f"参考信息:\n{context}\n\n用户问题: {user_query}"

        messages.append({"role": "user", "content": user_content})

        if stream:
            return self._stream_response(messages)
        else:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.3,
                max_tokens=800
            )
            return response.choices[0].message.content

    def _stream_response(self, messages: List[Dict]) -> Generator[str, None, None]:
        """流式响应"""
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

    def generate_conclusion(
        self,
        user_query: str,
        historical_analysis: str,
        news_summary: str,
        report_summary: str,
        emotion_result: Dict,
        prediction_result: Dict,
        stock_info: Dict,
    ) -> str:
        """
        生成预测流程的综合结论

        Args:
            user_query: 用户问题
            historical_analysis: 历史数据分析结果
            news_summary: 新闻总结
            report_summary: 研报观点总结
            emotion_result: 情感分析结果
            prediction_result: 预测结果
            stock_info: 股票信息

        Returns:
            综合分析报告
        """
        system_prompt = """你是专业的金融分析师。根据提供的分析结果，生成综合分析报告。

报告要求：
1. 结构清晰，分点论述
2. 综合考虑历史走势、新闻情绪、研报观点、模型预测
3. 给出合理的投资建议（需声明仅供参考）
4. 语言专业简洁
5. 如果某项数据缺失，不要提及

报告结构建议：
1. 近期走势回顾
2. 市场情绪分析
3. 研报观点总结（如有）
4. 模型预测结果
5. 综合观点与建议"""

        context = f"""股票: {stock_info.get('stock_name', '')} ({stock_info.get('stock_code', '')})

历史数据分析:
{historical_analysis}

新闻情绪:
{news_summary}
情绪分数: {emotion_result.get('score', 'N/A')} (范围 -1 到 1)
情绪描述: {emotion_result.get('summary', 'N/A')}

研报观点:
{report_summary if report_summary else '暂无研报数据'}

模型预测:
预测模型: {prediction_result.get('model', 'N/A')}
预测趋势: {prediction_result.get('trend', 'N/A')}
预测区间: {prediction_result.get('range', 'N/A')}"""

        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"用户问题: {user_query}\n\n分析数据:\n{context}\n\n请生成综合分析报告。"}
            ],
            temperature=0.3,
            max_tokens=1500
        )

        return response.choices[0].message.content
