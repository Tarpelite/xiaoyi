"""
Error Explainer Agent 模块
==========================

负责将技术错误转换为用户友好的解释
"""

from .base import BaseAgent
from app.data.fetcher import DataFetchError


class ErrorExplainerAgent(BaseAgent):
    """错误解释 Agent - 将技术错误转换为友好的用户解释"""

    DEFAULT_TEMPERATURE = 0.7

    SYSTEM_PROMPT = "你是小易，一个专业且友好的金融分析助手。你擅长用简单易懂的方式解释技术问题，并给出实用建议。"

    ERROR_CONTEXT_MAP = {
        "invalid_code": "股票代码不存在或格式错误",
        "network": "网络连接问题",
        "permission": "数据访问权限受限",
        "unknown": "数据获取失败"
    }

    def explain_data_fetch_error(
        self,
        error: DataFetchError,
        user_query: str
    ) -> str:
        """
        生成友好的错误解释和建议

        Args:
            error: DataFetchError 实例
            user_query: 用户原始问题

        Returns:
            Markdown 格式的友好解释（200-300字）
        """
        error_context = self.ERROR_CONTEXT_MAP.get(error.error_type, "数据获取失败")

        prompt = f"""用户尝试执行的问题: "{user_query}"

数据获取失败了:
- 错误类型: {error_context}
- 股票代码/标的: {error.context.get('symbol', 'unknown')}
- 技术错误信息: {error.original_error[:300]}

请你作为专业且友好的金融助手，用轻松易懂的语气生成一个解释和建议（200-300字），包括：

1. **开头**: 用友好的语气说明问题（如"抱歉，无法获取...的数据"）

2. **可能原因**: 列举2-3个可能的原因（用bullet points）
   - 针对 invalid_code: 代码不存在/已退市/格式错误
   - 针对 network: 网络问题/服务暂时不可用
   - 针对 permission: API限制/需要权限

3. **具体建议**: 给出可操作的建议
   - 如何修正（确认代码、检查格式）
   - 替代方案（试试其他代码/稍后重试）
   - 可选：推荐1-2个可用的热门股票示例（如 600519 茅台、000001 平安银行）

格式要求：
- 使用 Markdown 格式
- 专业但易懂，避免技术术语
- 语气友好、有帮助
- 不要过度道歉
"""

        messages = self.build_messages(
            user_content=prompt,
            system_prompt=self.SYSTEM_PROMPT
        )

        content = self.call_llm(messages, fallback=None)

        if content is None:
            return self._fallback_explanation(error, user_query)

        return content

    def _fallback_explanation(self, error: DataFetchError, user_query: str) -> str:
        """
        当 LLM 调用失败时的备用解释

        Args:
            error: DataFetchError 实例
            user_query: 用户原始问题

        Returns:
            简单的错误解释
        """
        symbol = error.context.get('symbol', '未知')

        if error.error_type == "invalid_code":
            return f"""抱歉，无法获取 "{symbol}" 的数据。

**可能原因：**
- 该股票代码不存在或已退市
- 代码格式可能有误（A股应为6位数字）

**建议：**
- 确认股票代码是否正确
- 尝试使用公司名称进行搜索
- 或者试试这些热门股票：600519（贵州茅台）、000001（平安银行）"""

        elif error.error_type == "network":
            return """抱歉，数据获取遇到网络问题。

**建议：**
- 请稍后重试
- 检查网络连接是否正常
- 如问题持续，可能是数据源暂时不可用"""

        elif error.error_type == "permission":
            return """抱歉，数据访问受限。

**可能原因：**
- API 请求频率限制
- 需要特殊权限访问该数据

**建议：**
- 请稍后重试
- 或尝试其他股票代码"""

        else:
            return f"""抱歉，获取数据时遇到问题。

**建议：**
- 请稍后重试
- 确认输入的股票代码是否正确
- 如问题持续，请联系技术支持

错误详情：{error.original_error[:200]}"""
