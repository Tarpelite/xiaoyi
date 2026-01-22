"""
Agent 基类
==========

所有 LLM Agent 的基类，提供统一的初始化、调用和错误处理逻辑。
"""

import json
from abc import ABC
from typing import List, Dict, Any, Optional, Callable

from openai import OpenAI

from app.core.config import settings


class BaseAgent(ABC):
    """
    LLM Agent 基类

    提供：
    1. 统一的 OpenAI 客户端初始化
    2. 统一的 LLM 调用接口
    3. 统一的错误处理
    4. 统一的对话历史处理
    5. 统一的 JSON 解析
    """

    DEFAULT_MODEL = "deepseek-chat"
    DEFAULT_BASE_URL = "https://api.deepseek.com"
    DEFAULT_TEMPERATURE = 0.3
    DEFAULT_HISTORY_WINDOW = 6

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        """
        初始化 Agent

        Args:
            api_key: API Key，可选，默认从 settings 获取
            base_url: API 基础 URL，默认 DeepSeek
            model: 模型名称，默认 deepseek-chat
            temperature: 默认温度参数
        """
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self.temperature = temperature if temperature is not None else self.DEFAULT_TEMPERATURE
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @property
    def agent_name(self) -> str:
        """Agent 名称，用于日志"""
        return self.__class__.__name__

    def call_llm(
        self,
        messages: List[Dict[str, str]],
        *,
        stream: bool = False,
        on_chunk: Optional[Callable[[str], None]] = None,
        fallback: Optional[str] = None,
        temperature: Optional[float] = None,
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        统一 LLM 调用

        Args:
            messages: 消息列表
            stream: 是否流式输出
            on_chunk: 流式回调函数（仅 stream=True 时有效）
            fallback: 错误时返回值（设置后启用异常捕获）
            temperature: 温度参数（覆盖默认）
            response_format: 响应格式（如 {"type": "json_object"}）
            max_tokens: 最大 token 数

        Returns:
            LLM 响应内容字符串
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": stream
        }
        if response_format:
            kwargs["response_format"] = response_format
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        try:
            response = self.client.chat.completions.create(**kwargs)

            if stream:
                content = ""
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        delta = chunk.choices[0].delta.content
                        content += delta
                        if on_chunk:
                            on_chunk(delta)
                return content
            else:
                return response.choices[0].message.content

        except Exception as e:
            print(f"[{self.agent_name}] LLM 调用失败: {e}")
            if fallback is not None:
                return fallback
            raise

    def build_messages(
        self,
        user_content: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        history_window: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        构建消息列表

        Args:
            user_content: 用户消息内容
            system_prompt: 系统提示词
            conversation_history: 对话历史
            history_window: 对话历史窗口大小

        Returns:
            消息列表
        """
        messages = []

        # 系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 对话历史
        if conversation_history:
            window = history_window or self.DEFAULT_HISTORY_WINDOW
            recent = conversation_history[-window:] if len(conversation_history) > window else conversation_history
            for msg in recent:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        # 用户消息
        messages.append({"role": "user", "content": user_content})

        return messages

    def parse_json(self, text: str) -> Dict[str, Any]:
        """
        解析 JSON，处理 markdown 代码块

        Args:
            text: 待解析的文本

        Returns:
            解析后的字典

        Raises:
            json.JSONDecodeError: JSON 解析失败
        """
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # 移除第一行（```json 或 ```）
            if lines[0].startswith("```"):
                lines = lines[1:]
            # 移除最后一行的 ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return json.loads(text)

    def parse_json_safe(self, text: str, fallback: Optional[Dict] = None) -> Dict[str, Any]:
        """
        安全的 JSON 解析

        Args:
            text: 待解析的文本
            fallback: 解析失败时的返回值

        Returns:
            解析后的字典或 fallback
        """
        try:
            return self.parse_json(text)
        except Exception as e:
            print(f"[{self.agent_name}] JSON 解析失败: {e}")
            return fallback if fallback is not None else {}
