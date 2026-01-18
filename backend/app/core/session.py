"""
Session 管理模块
=================

基于 Redis 的会话状态管理

架构:
- Session: 一整个多轮对话 (存储 session_id, conversation_history, message_ids)
- Message: 一轮 QA (存储所有分析结果数据)
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict
from redis import Redis

from app.core.redis_client import get_redis
from app.schemas.session_schema import (
    SessionData,
    MessageData,
    MessageStatus,
    StepStatus,
    StepDetail,
    ThinkingLogEntry,
    UnifiedIntent,
    ResolvedKeywords,
    StockMatchResult,
    TimeSeriesPoint,
    RAGSource,
    SummarizedNewsItem,
    ReportItem,
)
from app.core.step_definitions import get_steps_for_intent


class Message:
    """
    单轮 QA 管理器

    存储单轮对话的所有分析结果数据
    """

    def __init__(self, message_id: str, session_id: str, redis_client: Optional[Redis] = None):
        self.message_id = message_id
        self.session_id = session_id
        self.redis = redis_client or get_redis()
        self.key = f"message:{message_id}"
        self.ttl = 86400  # 24小时过期

    @classmethod
    def create(cls, session_id: str, user_query: str) -> "Message":
        """创建新消息"""
        message_id = str(uuid.uuid4())
        message = cls(message_id, session_id)

        now = datetime.now().isoformat()
        initial_data = MessageData(
            message_id=message_id,
            session_id=session_id,
            user_query=user_query,
            status=MessageStatus.PENDING,
            created_at=now,
            updated_at=now
        )

        message._save(initial_data)
        print(f"[Message] Created: {message_id} for session {session_id}")
        return message

    @classmethod
    def exists(cls, message_id: str) -> bool:
        """检查消息是否存在"""
        redis = get_redis()
        return redis.exists(f"message:{message_id}") > 0

    def get(self) -> Optional[MessageData]:
        """获取消息数据"""
        data = self.redis.get(self.key)
        if not data:
            return None
        return MessageData.model_validate_json(data)

    def _save(self, data: MessageData):
        """保存消息数据"""
        data.updated_at = datetime.now().isoformat()
        json_data = data.model_dump_json()
        self.redis.setex(self.key, self.ttl, json_data)

    def delete(self):
        """删除消息"""
        self.redis.delete(self.key)
        print(f"[Message] Deleted: {self.message_id}")

    # ========== 意图相关 ==========

    def save_unified_intent(self, intent: UnifiedIntent):
        """保存统一意图识别结果"""
        data = self.get()
        if data:
            data.unified_intent = intent

            # 设置 intent 字段
            if not intent.is_in_scope:
                data.intent = "out_of_scope"
            elif intent.is_forecast:
                data.intent = "forecast"
            elif intent.enable_rag:
                data.intent = "rag"
            elif intent.enable_search or intent.enable_domain_info:
                data.intent = "news"
            else:
                data.intent = "chat"

            # 初始化步骤
            steps = get_steps_for_intent(data.intent)
            data.total_steps = len(steps)
            data.step_details = [
                StepDetail(id=s["id"], name=s["name"], status=StepStatus.PENDING, message="")
                for s in steps
            ]

            self._save(data)
            print(f"[Message] Intent: {data.intent}, forecast={intent.is_forecast}")

    # ========== 股票相关 ==========

    def save_stock_match(self, result: StockMatchResult):
        """保存股票匹配结果"""
        data = self.get()
        if data:
            data.stock_match = result
            self._save(data)
            print(f"[Message] Stock match: {result.success}")

    def save_resolved_keywords(self, keywords: ResolvedKeywords):
        """保存最终关键词"""
        data = self.get()
        if data:
            data.resolved_keywords = keywords
            self._save(data)

    # ========== 步骤管理 ==========

    def update_step_detail(self, step: int, status: str, message: str = ""):
        """更新步骤详情"""
        data = self.get()
        if data and 0 < step <= len(data.step_details):
            data.steps = step
            data.status = MessageStatus.PROCESSING
            data.step_details[step - 1].status = StepStatus(status)
            data.step_details[step - 1].message = message
            self._save(data)
            print(f"[Message] Step {step}/{data.total_steps} [{status}]: {message}")

    # ========== 数据保存 ==========

    def save_time_series_original(self, points: List[TimeSeriesPoint]):
        """保存原始时序数据"""
        data = self.get()
        if data:
            data.time_series_original = points
            self._save(data)

    def save_time_series_full(self, points: List[TimeSeriesPoint], prediction_start: str):
        """保存完整时序数据（含预测）"""
        data = self.get()
        if data:
            data.time_series_full = points
            data.prediction_start_day = prediction_start
            data.prediction_done = True
            self._save(data)

    def save_news(self, news: List[SummarizedNewsItem]):
        """保存新闻列表"""
        data = self.get()
        if data:
            data.news_list = news
            self._save(data)

    def save_reports(self, reports: List[ReportItem]):
        """保存研报列表"""
        data = self.get()
        if data:
            data.report_list = reports
            self._save(data)

    def save_rag_sources(self, sources: List[RAGSource]):
        """保存 RAG 来源"""
        data = self.get()
        if data:
            data.rag_sources = sources
            self._save(data)

    def save_emotion(self, score: float, description: str):
        """保存情绪分析"""
        data = self.get()
        if data:
            data.emotion = score
            data.emotion_des = description
            self._save(data)

    def save_conclusion(self, conclusion: str):
        """保存综合报告"""
        data = self.get()
        if data:
            data.conclusion = conclusion
            self._save(data)

    # ========== 状态管理 ==========

    def mark_completed(self):
        """标记为完成"""
        data = self.get()
        if data:
            data.status = MessageStatus.COMPLETED
            data.steps = data.total_steps
            for step in data.step_details:
                if step.status != StepStatus.ERROR:
                    step.status = StepStatus.COMPLETED
            self._save(data)
            print(f"[Message] Completed: {self.message_id}")

    def mark_error(self, error_message: str):
        """标记为错误"""
        data = self.get()
        if data:
            data.status = MessageStatus.ERROR
            data.error_message = error_message
            self._save(data)
            print(f"[Message] Error: {error_message}")

    # ========== 思考日志 ==========

    def append_thinking_log(self, step_id: str, step_name: str, content: str):
        """追加思考日志条目（累积显示）"""
        data = self.get()
        if data:
            entry = ThinkingLogEntry(
                step_id=step_id,
                step_name=step_name,
                content=content,
                timestamp=datetime.now().isoformat()
            )
            data.thinking_logs.append(entry)
            self._save(data)
            print(f"[Message] Thinking log: {step_id} - {len(content)} chars")


class Session:
    """
    会话管理器 (多轮对话容器)

    存储全局信息和消息列表，每个消息的详细数据在 Message 中
    """

    def __init__(self, session_id: str, redis_client: Optional[Redis] = None):
        self.session_id = session_id
        self.redis = redis_client or get_redis()
        self.key = f"session:{session_id}"
        self.ttl = 86400  # 24小时过期

    @classmethod
    def create(cls) -> "Session":
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session = cls(session_id)

        now = datetime.now().isoformat()
        initial_data = SessionData(
            session_id=session_id,
            created_at=now,
            updated_at=now
        )

        session._save(initial_data)
        print(f"[Session] Created: {session_id}")
        return session

    @classmethod
    def exists(cls, session_id: str) -> bool:
        """检查会话是否存在"""
        redis = get_redis()
        return redis.exists(f"session:{session_id}") > 0

    def get(self) -> Optional[SessionData]:
        """获取会话数据"""
        data = self.redis.get(self.key)
        if not data:
            return None
        return SessionData.model_validate_json(data)

    def _save(self, data: SessionData):
        """保存会话数据"""
        data.updated_at = datetime.now().isoformat()
        json_data = data.model_dump_json()
        self.redis.setex(self.key, self.ttl, json_data)

    def delete(self):
        """删除会话及其所有消息"""
        data = self.get()
        if data:
            # 删除所有关联的消息
            for message_id in data.message_ids:
                msg = Message(message_id, self.session_id)
                msg.delete()
        self.redis.delete(self.key)
        print(f"[Session] Deleted: {self.session_id}")

    # ========== 消息管理 ==========

    def create_message(self, user_query: str) -> Message:
        """创建新消息"""
        data = self.get()
        if not data:
            raise ValueError(f"Session {self.session_id} not found")

        # 创建消息
        message = Message.create(
            session_id=self.session_id,
            user_query=user_query
        )

        # 添加到 session
        data.message_ids.append(message.message_id)
        data.current_message_id = message.message_id
        self._save(data)

        return message

    def get_current_message(self) -> Optional[Message]:
        """获取当前正在处理的消息"""
        data = self.get()
        if data and data.current_message_id:
            return Message(data.current_message_id, self.session_id)
        return None

    def get_message(self, message_id: str) -> Optional[Message]:
        """获取指定消息"""
        if Message.exists(message_id):
            return Message(message_id, self.session_id)
        return None

    def get_all_messages(self) -> List[Message]:
        """获取所有消息"""
        data = self.get()
        if not data:
            return []
        return [Message(mid, self.session_id) for mid in data.message_ids if Message.exists(mid)]

    # ========== 对话历史 ==========

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        data = self.get()
        return data.conversation_history if data else []

    def add_conversation_message(self, role: str, content: str):
        """添加对话消息"""
        data = self.get()
        if data:
            data.conversation_history.append({"role": role, "content": content})
            if len(data.conversation_history) > 20:
                data.conversation_history = data.conversation_history[-20:]
            self._save(data)

    # ========== Session 元数据管理 ==========

    def update_title(self, new_title: str):
        """更新会话标题"""
        data = self.get()
        if data:
            data.title = new_title
            self._save(data)
            print(f"[Session] Title updated: {new_title}")

    def auto_generate_title(self, first_message: str):
        """从首条消息自动生成标题（截断到50字符）"""
        data = self.get()
        if data and data.title == "New Chat":  # 只在默认标题时自动生成
            title = first_message[:50]
            if len(first_message) > 50:
                title += "..."
            data.title = title
            self._save(data)
            print(f"[Session] Auto-generated title: {title}")
