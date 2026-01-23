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

from typing import Dict, List, Optional, Generator, Callable, Tuple
import json

from .base import BaseAgent
from app.schemas.session_schema import UnifiedIntent, ResolvedKeywords


class IntentAgent(BaseAgent):
    """统一意图识别 Agent"""

    DEFAULT_TEMPERATURE = 0.1

    INTENT_SYSTEM_PROMPT = """你是金融时序分析助手的意图识别模块。根据用户问题，一次性判断所有意图信息。

## 服务范围 (is_in_scope)

**原则：尽可能帮助用户，宽松判断，只对明显无关的问题拒绝**

- in_scope=true（绝大多数情况）:
  - 股票分析/预测（如"分析茅台走势"、"预测比亚迪"）
  - 金融/经济/投资相关问题
  - 研报/新闻查询
  - 日常闲聊、打招呼（如"你好"、"谢谢"）
  - 关于助手自身的问题（如"你是谁"、"你能做什么"）
  - 任何可以用金融知识或常识回答的问题
  - 模糊边界的问题（先尝试回答）

- in_scope=false（仅限明显不相关）:
  - 明确要求非金融服务（如"帮我写代码"、"翻译这段话"、"写一首诗"）
  - 此时设置 out_of_scope_reply 友好拒绝并说明能力范围

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

## 股票提取 (stock_mention + stock_full_name)

从用户问题中提取提到的股票名称/代码：
- stock_mention: 用户原始输入的股票名称/代码
  - 单股票: "茅台"、"600519"、"比亚迪"
  - 多股票: "茅台,五粮液" (逗号分隔)
  - 无股票: 留空

- stock_full_name: 你需要根据知识，将用户输入的简称/别名转换为官方股票全称
  - "茅台"/"茅子" → "贵州茅台"
  - "中石油" → "中国石油"
  - "宁德"/"CATL" → "宁德时代"
  - "招行" → "招商银行"
  - "工行"/"宇宙行" → "工商银行"
  - "平安" → "中国平安"
  - "汾酒" → "山西汾酒"
  - 如果用户输入的已经是全称，直接使用
  - 如果是股票代码，尝试转换为名称，如无法确定则保持代码
  - 多股票时用逗号分隔: "贵州茅台,五粮液"
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
- forecast_model: 如果用户明确指定了模型（如"用XGBoost"、"用prophet模型"），则返回对应的模型名称（prophet/xgboost/randomforest/dlinear）；如果用户没有指定模型，则返回 null（表示自动选择最佳模型）
- history_days: 历史数据天数 (默认365)
- forecast_horizon: 预测天数 (默认30)

根据用户描述调整：
- "用XGBoost" → forecast_model="xgboost"
- "用prophet模型" → forecast_model="prophet"
- 用户没有提到具体模型 → forecast_model=null
- "预测三个月" → forecast_horizon=90
- "看半年数据" → history_days=180

返回 JSON 格式:
{
    "is_in_scope": true/false,
    "is_forecast": true/false,
    "enable_rag": true/false,
    "enable_search": true/false,
    "enable_domain_info": true/false,
    "stock_mention": "用户原始输入的股票名称或空字符串",
    "stock_full_name": "转换后的官方股票全称或空字符串",
    "raw_search_keywords": ["关键词1", "关键词2"],
    "raw_rag_keywords": ["关键词1"],
    "raw_domain_keywords": ["关键词1"],
    "forecast_model": null,
    "history_days": 365,
    "forecast_horizon": 30,
    "reason": "判断理由",
    "out_of_scope_reply": "若超出范围的友好回复，否则为null"
}"""

    STREAMING_SYSTEM_PROMPT = """你是金融时序分析助手的意图识别模块。请先分析用户意图，然后返回结果。

## 分析步骤（请详细描述你的思考过程）

1. **理解问题**: 用户在问什么？是否涉及金融/股票/投资？
2. **判断范围**: 是否在服务范围内？
3. **识别意图**: 是否需要预测分析？还是只是查询/闲聊？
4. **提取信息**: 提到了哪些股票？需要哪些工具？
5. **设置参数**: 如果需要预测，设置预测参数

## 服务范围 (is_in_scope) - 宽松判断
- true: 金融/投资/经济相关问题、日常闲聊、关于助手的问题、任何可以回答的问题
- false: 仅限明确要求非金融服务（如写代码、翻译），需设置 out_of_scope_reply

## 预测判断 (is_forecast)
- true: 明确要求分析/预测股票走势
- false: 只是查询新闻/研报、闲聊或追问

## 工具开关
- enable_rag: 研报知识库检索
- enable_search: 网络搜索
- enable_domain_info: 领域信息获取（股票新闻、行情）

## 预测参数（仅 is_forecast=true）
- forecast_model: 如果用户明确指定了模型（如"用XGBoost"、"用prophet模型"），则返回对应的模型名称（prophet/xgboost/randomforest/dlinear）；如果用户没有指定模型，则返回 null（表示自动选择最佳模型）
- history_days: 历史数据天数
- forecast_horizon: 预测天数

请先输出你的思考过程，然后用 ```json 代码块输出结果：
```json
{
    "is_in_scope": true/false,
    "is_forecast": true/false,
    "enable_rag": true/false,
    "enable_search": true/false,
    "enable_domain_info": true/false,
    "stock_mention": "用户原始输入的股票名称或空字符串",
    "stock_full_name": "转换后的官方股票全称或空字符串",
    "raw_search_keywords": ["关键词"],
    "raw_rag_keywords": ["关键词"],
    "raw_domain_keywords": ["关键词"],
    "forecast_model": null,
    "history_days": 365,
    "forecast_horizon": 30,
    "reason": "简短判断理由",
    "out_of_scope_reply": null
}
```"""

    CHAT_SYSTEM_PROMPT = """你是专业的金融分析助手。根据上下文和对话历史回答用户问题。

要求：
1. 回答简洁专业
2. 如果引用了来源，使用 markdown 链接格式 [标题](url)
3. 如果引用了研报，使用格式 [研报名称](rag://文件名.pdf#page=页码)
4. 如果无法从上下文找到相关信息，如实说明"""

    def _build_intent(self, result: Dict) -> UnifiedIntent:
        """从 LLM 返回的 dict 构建 UnifiedIntent 对象"""
        return UnifiedIntent(
            is_in_scope=result.get("is_in_scope", True),
            is_forecast=result.get("is_forecast", False),
            enable_rag=result.get("enable_rag", False),
            enable_search=result.get("enable_search", False),
            enable_domain_info=result.get("enable_domain_info", False),
            stock_mention=result.get("stock_mention") or None,
            stock_full_name=result.get("stock_full_name") or None,
            raw_search_keywords=result.get("raw_search_keywords", []),
            raw_rag_keywords=result.get("raw_rag_keywords", []),
            raw_domain_keywords=result.get("raw_domain_keywords", []),
            forecast_model=result.get("forecast_model"),  # None 表示自动选择
            history_days=result.get("history_days", 365),
            forecast_horizon=result.get("forecast_horizon", 30),
            reason=result.get("reason", ""),
            out_of_scope_reply=result.get("out_of_scope_reply")
        )

    def recognize_intent_streaming(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        on_thinking_chunk: Optional[Callable[[str], None]] = None
    ) -> Tuple[UnifiedIntent, str]:
        """
        流式意图识别 - 实时返回思考过程

        Args:
            user_query: 用户问题
            conversation_history: 对话历史
            on_thinking_chunk: 回调函数，接收思考内容片段

        Returns:
            (UnifiedIntent, 完整思考内容)
        """
        messages = self.build_messages(
            user_content=f"用户问题: {user_query}\n\n请分析意图。",
            system_prompt=self.STREAMING_SYSTEM_PROMPT,
            conversation_history=conversation_history
        )

        # 使用状态变量跟踪是否进入 JSON 块
        state = {"full_content": "", "in_json_block": False, "thinking_content": ""}

        def _on_chunk(delta: str):
            state["full_content"] += delta

            if "```json" in state["full_content"] and not state["in_json_block"]:
                state["in_json_block"] = True
                state["thinking_content"] = state["full_content"].split("```json")[0].strip()

            if not state["in_json_block"] and on_thinking_chunk:
                on_thinking_chunk(delta)

        full_content = self.call_llm(messages, stream=True, on_chunk=_on_chunk)

        # 提取 JSON 结果
        try:
            if "```json" in full_content:
                json_str = full_content.split("```json")[1]
                if "```" in json_str:
                    json_str = json_str.split("```")[0]
                result = json.loads(json_str.strip())
            else:
                result = json.loads(full_content)
        except json.JSONDecodeError:
            print(f"[{self.agent_name}] JSON 解析失败: {full_content}")
            result = {
                "is_in_scope": True,
                "is_forecast": False,
                "reason": "解析失败，使用默认值"
            }

        thinking_content = state["thinking_content"]
        if not thinking_content:
            thinking_content = result.get("reason", "")

        return self._build_intent(result), thinking_content

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
        if not stock_name and not stock_code:
            return ResolvedKeywords(
                search_keywords=intent.raw_search_keywords,
                rag_keywords=intent.raw_rag_keywords,
                domain_keywords=intent.raw_domain_keywords
            )

        search_keywords = list(intent.raw_search_keywords)
        rag_keywords = list(intent.raw_rag_keywords)
        domain_keywords = list(intent.raw_domain_keywords)

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
        user_content = user_query
        if context:
            user_content = f"参考信息:\n{context}\n\n用户问题: {user_query}"

        messages = self.build_messages(
            user_content=user_content,
            system_prompt=self.CHAT_SYSTEM_PROMPT,
            conversation_history=conversation_history,
            history_window=10
        )

        if stream:
            return self._stream_response(messages)
        else:
            return self.call_llm(messages, temperature=0.3)

    def _stream_response(self, messages: List[Dict]) -> Generator[str, None, None]:
        """流式响应 - 生成器模式"""
        # 使用底层 client 直接调用以支持生成器模式
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            stream=True
        )

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
