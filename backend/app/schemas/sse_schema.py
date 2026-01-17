"""
SSE (Server-Sent Events) Schema Definitions
===========================================

定义所有SSE事件类型的数据结构

事件类型:
- session_created: 会话创建
- thinking_chunk: 思考内容片段
- thinking_complete: 思考完成
- intent_determined: 意图确定
- step_update: 步骤更新
- step_complete: 步骤完成
- chat_chunk: 聊天内容片段
- chat_complete: 聊天完成
- conclusion_chunk: 报告内容片段 (可选)
- conclusion_complete: 报告完成
- analysis_complete: 整个分析完成
- error: 错误
- heartbeat: 心跳
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any
from datetime import datetime


# ========== 基础事件类型 ==========

class SSEEventBase(BaseModel):
    """SSE事件基类"""
    type: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    session_id: str
    message_id: str


# ========== 具体事件类型 ==========

class SessionCreatedEvent(SSEEventBase):
    """会话创建事件"""
    type: Literal["session_created"] = "session_created"
    data: Dict[str, str] = Field(default_factory=dict)


class ThinkingChunkEvent(SSEEventBase):
    """思考内容片段事件"""
    type: Literal["thinking_chunk"] = "thinking_chunk"
    data: Dict[str, str]  # {chunk: str, accumulated: str}
    
    @classmethod
    def create(cls, session_id: str, message_id: str, chunk: str, accumulated: str):
        """便捷创建方法"""
        return cls(
            session_id=session_id,
            message_id=message_id,
            data={"chunk": chunk, "accumulated": accumulated}
        )


class ThinkingCompleteEvent(SSEEventBase):
    """思考完成事件"""
    type: Literal["thinking_complete"] = "thinking_complete"
    data: Dict[str, Any]  # {thinking_content: str, total_length: int}


class IntentDeterminedEvent(SSEEventBase):
    """意图确定事件"""
    type: Literal["intent_determined"] = "intent_determined"
    data: Dict[str, Any]  # UnifiedIntent的dict


class StepUpdateEvent(SSEEventBase):
    """步骤更新事件"""
    type: Literal["step_update"] = "step_update"
    data: Dict[str, Any]  # {step: int, status: str, message: str}
    
    @classmethod
    def create(cls, session_id: str, message_id: str, step: int, status: str, message: str = ""):
        """便捷创建方法"""
        return cls(
            session_id=session_id,
            message_id=message_id,
            data={"step": step, "status": status, "message": message}
        )


class StepCompleteEvent(SSEEventBase):
    """步骤完成事件"""
    type: Literal["step_complete"] = "step_complete"
    data: Dict[str, Any]  # {step: int, message: str}


class ChatChunkEvent(SSEEventBase):
    """聊天内容片段事件"""
    type: Literal["chat_chunk"] = "chat_chunk"
    data: Dict[str, str]  # {chunk: str, accumulated: str}
    
    @classmethod
    def create(cls, session_id: str, message_id: str, chunk: str, accumulated: str):
        """便捷创建方法"""
        return cls(
            session_id=session_id,
            message_id=message_id,
            data={"chunk": chunk, "accumulated": accumulated}
        )


class ChatCompleteEvent(SSEEventBase):
    """聊天完成事件"""
    type: Literal["chat_complete"] = "chat_complete"
    data: Dict[str, Any]  # {chat_response: str, total_length: int}


class ConclusionChunkEvent(SSEEventBase):
    """报告内容片段事件 (可选,如果conclusion也要流式)"""
    type: Literal["conclusion_chunk"] = "conclusion_chunk"
    data: Dict[str, str]  # {chunk: str, accumulated: str}


class ConclusionCompleteEvent(SSEEventBase):
    """报告完成事件"""
    type: Literal["conclusion_complete"] = "conclusion_complete"
    data: Dict[str, str]  # {conclusion: str}


class AnalysisCompleteEvent(SSEEventBase):
    """整个分析完成事件"""
    type: Literal["analysis_complete"] = "analysis_complete"
    data: Dict[str, Any] = Field(default_factory=dict)  # {}


class ErrorEvent(SSEEventBase):
    """错误事件"""
    type: Literal["error"] = "error"
    data: Dict[str, Any]  # {error: str, error_code: str, retry_able: bool, suggested_action: str}
    
    @classmethod
    def create(
        cls, 
        session_id: str, 
        message_id: str, 
        error: str, 
        error_code: str = "unknown",
        retry_able: bool = True,
        suggested_action: str = "请稍后重试"
    ):
        """便捷创建方法"""
        return cls(
            session_id=session_id,
            message_id=message_id,
            data={
                "error": error,
                "error_code": error_code,
                "retry_able": retry_able,
                "suggested_action": suggested_action
            }
        )


class HeartbeatEvent(SSEEventBase):
    """心跳事件"""
    type: Literal["heartbeat"] = "heartbeat"
    data: Dict[str, Any] = Field(default_factory=dict)


# ========== 错误代码常量 ==========

class ErrorCode:
    """错误代码枚举"""
    TIMEOUT = "timeout"
    LLM_ERROR = "llm_error"
    RAG_ERROR = "rag_error"
    DATA_FETCH_ERROR = "data_fetch_error"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


# ========== 类型联合 ==========

SSEEvent = (
    SessionCreatedEvent |
    ThinkingChunkEvent |
    ThinkingCompleteEvent |
    IntentDeterminedEvent |
    StepUpdateEvent |
    StepCompleteEvent |
    ChatChunkEvent |
    ChatCompleteEvent |
    ConclusionChunkEvent |
    ConclusionCompleteEvent |
    AnalysisCompleteEvent |
    ErrorEvent |
    HeartbeatEvent
)
