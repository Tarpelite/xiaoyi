"""
Session 管理模块
=================

基于 Redis 的会话状态管理

支持两种模式:
1. 新版统一架构: Session + Message 模型
2. 兼容旧版: AnalysisSession 模型
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from redis import Redis

from app.core.redis_client import get_redis
from app.schemas.session_schema import (
    # 新版模型
    Session as SessionModel,
    Message,
    UnifiedIntent,
    ResolvedKeywords,
    StockMatchResult,
    StockInfo,
    SummarizedNewsItem,
    ReportItem,
    NewsItem,
    # 兼容旧版
    AnalysisSession,
    SessionStatus,
    StepStatus,
    TimeSeriesPoint,
    StepDetail,
    RAGSource,
)
from app.core.step_definitions import get_steps_for_intent, get_step_count


class SessionManager:
    """
    统一会话管理器 (新版架构)

    使用 Session + Message 模型:
    - Session: 多轮对话容器
    - Message: 单轮 QA
    """

    def __init__(self, session_id: str, redis_client: Optional[Redis] = None):
        self.session_id = session_id
        self.redis = redis_client or get_redis()
        self.session_key = f"session:v3:{session_id}"
        self.ttl = 86400  # 24小时过期

    @classmethod
    def create(cls, context: str = "") -> "SessionManager":
        """创建新会话"""
        session_id = str(uuid.uuid4())
        manager = cls(session_id)

        now = datetime.now()
        session = SessionModel(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            status=SessionStatus.PENDING,
            context=context,
            messages=[],
        )

        manager._save_session(session)
        print(f"✅ Created new session: {session_id}")
        return manager

    @classmethod
    def get_or_create(cls, session_id: Optional[str], context: str = "") -> "SessionManager":
        """获取或创建会话"""
        if session_id and cls.exists(session_id):
            return cls(session_id)
        return cls.create(context)

    @classmethod
    def exists(cls, session_id: str) -> bool:
        """检查会话是否存在"""
        redis = get_redis()
        return redis.exists(f"session:v3:{session_id}") > 0

    def get_session(self) -> Optional[SessionModel]:
        """获取会话数据"""
        data = self.redis.get(self.session_key)
        if not data:
            return None
        return SessionModel.model_validate_json(data)

    def _save_session(self, session: SessionModel):
        """保存会话数据"""
        session.updated_at = datetime.now()
        json_data = session.model_dump_json()
        self.redis.setex(self.session_key, self.ttl, json_data)

    # ========== Message 操作 ==========

    def create_message(self, user_query: str, intent: UnifiedIntent) -> Message:
        """
        创建新消息

        Args:
            user_query: 用户问题
            intent: 意图识别结果

        Returns:
            新创建的 Message
        """
        session = self.get_session()
        if not session:
            raise ValueError(f"Session {self.session_id} not found")

        message_id = str(uuid.uuid4())
        message = Message(
            message_id=message_id,
            session_id=self.session_id,
            created_at=datetime.now(),
            user_query=user_query,
            intent=intent,
            is_forecast=intent.is_forecast,
            status=SessionStatus.PROCESSING,
        )

        session.messages.append(message)
        session.current_message_id = message_id
        session.status = SessionStatus.PROCESSING
        self._save_session(session)

        print(f"📝 Created message: {message_id} for session: {self.session_id}")
        return message

    def get_current_message(self) -> Optional[Message]:
        """获取当前正在处理的消息"""
        session = self.get_session()
        if not session or not session.current_message_id:
            return None

        for msg in session.messages:
            if msg.message_id == session.current_message_id:
                return msg
        return None

    def get_message(self, message_id: str) -> Optional[Message]:
        """获取指定消息"""
        session = self.get_session()
        if not session:
            return None

        for msg in session.messages:
            if msg.message_id == message_id:
                return msg
        return None

    def update_message(self, message_id: str, **updates) -> Optional[Message]:
        """
        更新消息字段

        Args:
            message_id: 消息 ID
            **updates: 要更新的字段

        Returns:
            更新后的 Message
        """
        session = self.get_session()
        if not session:
            return None

        for i, msg in enumerate(session.messages):
            if msg.message_id == message_id:
                # 更新字段
                msg_dict = msg.model_dump()
                msg_dict.update(updates)
                session.messages[i] = Message.model_validate(msg_dict)
                self._save_session(session)
                return session.messages[i]

        return None

    # ========== 便捷方法 ==========

    def save_stock_match(self, message_id: str, result: StockMatchResult):
        """保存股票匹配结果"""
        self.update_message(message_id, stock_match=result)
        if result.success and result.stock_info:
            self.update_message(message_id, stock_info=result.stock_info)
        print(f"🏷️ Stock match saved: {result.success}")

    def save_resolved_keywords(self, message_id: str, keywords: ResolvedKeywords):
        """保存最终关键词"""
        self.update_message(message_id, resolved_keywords=keywords)
        print(f"🔑 Keywords resolved: search={len(keywords.search_keywords)}, rag={len(keywords.rag_keywords)}")

    def save_time_series(
        self,
        message_id: str,
        original: List[TimeSeriesPoint],
        predicted: Optional[List[TimeSeriesPoint]] = None
    ):
        """保存时序数据"""
        updates = {"time_series_original": original}
        if predicted:
            updates["time_series_predicted"] = predicted
        self.update_message(message_id, **updates)
        print(f"📈 Time series saved: {len(original)} original, {len(predicted or [])} predicted")

    def save_news_items(self, message_id: str, items: List[SummarizedNewsItem]):
        """保存新闻条目"""
        self.update_message(message_id, news_items=items)
        print(f"📰 News items saved: {len(items)}")

    def save_report_items(self, message_id: str, items: List[ReportItem]):
        """保存研报条目"""
        self.update_message(message_id, report_items=items)
        print(f"📚 Report items saved: {len(items)}")

    def save_emotion(self, message_id: str, score: float, summary: str):
        """保存情感分析结果"""
        self.update_message(message_id, emotion_score=score, emotion_summary=summary)
        print(f"😊 Emotion saved: {score:.2f}")

    def save_conclusion(self, message_id: str, conclusion: str):
        """保存结论"""
        self.update_message(message_id, conclusion=conclusion)
        print(f"📝 Conclusion saved: {len(conclusion)} chars")

    def save_model_info(self, message_id: str, model_name: str, config: Optional[Dict] = None):
        """保存模型信息"""
        updates = {"model_used": model_name}
        if config:
            updates["model_config"] = config
        self.update_message(message_id, **updates)
        print(f"🤖 Model info saved: {model_name}")

    # ========== 步骤管理 ==========

    def init_steps(self, message_id: str, intent_type: str):
        """
        初始化步骤

        Args:
            message_id: 消息 ID
            intent_type: 意图类型 (forecast/chat/rag/search)
        """
        steps = get_steps_for_intent(intent_type)
        step_details = [
            StepDetail(id=s["id"], name=s["name"], status=StepStatus.PENDING)
            for s in steps
        ]
        self.update_message(
            message_id,
            step_details=step_details,
            total_steps=len(steps),
            current_step=0
        )
        print(f"📊 Steps initialized: {len(steps)} steps for {intent_type}")

    def update_step(self, message_id: str, step: int, status: StepStatus, message: str = ""):
        """
        更新步骤状态

        Args:
            step: 步骤编号 (1-based)
            status: 状态
            message: 状态消息
        """
        msg = self.get_message(message_id)
        if not msg or step < 1 or step > len(msg.step_details):
            return

        step_details = msg.step_details.copy()
        step_details[step - 1] = StepDetail(
            id=step_details[step - 1].id,
            name=step_details[step - 1].name,
            status=status,
            message=message
        )

        self.update_message(
            message_id,
            step_details=step_details,
            current_step=step
        )
        print(f"📊 Step {step}/{len(step_details)} [{status.value}]: {message}")

    # ========== 状态管理 ==========

    def mark_message_completed(self, message_id: str):
        """标记消息完成"""
        msg = self.get_message(message_id)
        if msg:
            # 更新所有步骤为完成
            step_details = [
                StepDetail(id=s.id, name=s.name, status=StepStatus.COMPLETED, message=s.message)
                for s in msg.step_details
            ]
            self.update_message(
                message_id,
                status=SessionStatus.COMPLETED,
                step_details=step_details,
                current_step=len(step_details)
            )

        session = self.get_session()
        if session:
            session.status = SessionStatus.COMPLETED
            session.current_message_id = None
            self._save_session(session)

        print(f"✅ Message {message_id} completed")

    def mark_message_error(self, message_id: str, error: str):
        """标记消息错误"""
        self.update_message(
            message_id,
            status=SessionStatus.ERROR,
            error_message=error
        )

        session = self.get_session()
        if session:
            session.status = SessionStatus.ERROR
            session.error_message = error
            self._save_session(session)

        print(f"❌ Message {message_id} error: {error}")

    # ========== 对话历史 ==========

    def get_conversation_history(self, max_turns: int = 10) -> List[Dict[str, str]]:
        """
        获取对话历史 (用于 LLM 上下文)

        Returns:
            [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
        """
        session = self.get_session()
        if not session:
            return []

        history = []
        for msg in session.messages[-max_turns:]:
            history.append({"role": "user", "content": msg.user_query})
            if msg.conclusion:
                history.append({"role": "assistant", "content": msg.conclusion})

        return history

    def delete(self):
        """删除会话"""
        self.redis.delete(self.session_key)
        print(f"🗑️ Session {self.session_id} deleted")


# ========== 兼容旧版 Session 类 ==========

class Session:
    """
    分析会话管理器 (兼容旧版 AnalysisSession)

    注意: 新代码应使用 SessionManager 类
    """

    def __init__(self, session_id: str, redis_client: Optional[Redis] = None):
        self.session_id = session_id
        self.redis = redis_client or get_redis()
        self.key = f"session:{session_id}"
        self.ttl = 86400  # 24小时过期

    @classmethod
    def create(cls, context: str = "", model_name: str = "prophet") -> "Session":
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session = cls(session_id)

        now = datetime.now().isoformat()
        initial_data = AnalysisSession(
            session_id=session_id,
            context=context,
            model_name=model_name,
            status=SessionStatus.PENDING,
            created_at=now,
            updated_at=now
        )

        session._save(initial_data)
        return session

    def get(self) -> Optional[AnalysisSession]:
        """获取会话数据"""
        data = self.redis.get(self.key)
        if not data:
            return None
        return AnalysisSession.model_validate_json(data)

    def _save(self, data: AnalysisSession):
        """保存会话数据"""
        data.updated_at = datetime.now().isoformat()
        json_data = data.model_dump_json()
        self.redis.setex(self.key, self.ttl, json_data)
        print(f"✅ Session {self.session_id} saved: status={data.status}, steps={data.steps}")

    def update_step(self, step: int):
        """更新当前步骤"""
        data = self.get()
        if data:
            data.steps = step
            data.status = SessionStatus.PROCESSING
            self._save(data)
            print(f"📊 Step {step}/7 updated")

    def save_time_series_original(self, points: List[TimeSeriesPoint]):
        """保存原始时序数据"""
        data = self.get()
        if data:
            data.time_series_original = points
            self._save(data)
            print(f"📈 Saved {len(points)} original data points")

    def save_time_series_full(self, points: List[TimeSeriesPoint], prediction_start: str):
        """保存完整时序数据（含预测）"""
        data = self.get()
        if data:
            data.time_series_full = points
            data.prediction_start_day = prediction_start
            data.prediction_done = True
            self._save(data)
            print(f"🔮 Saved {len(points)} full data points (with predictions)")

    def save_news(self, news: List[Dict[str, Any]]):
        """保存新闻列表"""
        data = self.get()
        if data:
            data.news_list = news
            self._save(data)
            print(f"📰 Saved {len(news)} news items")

    def save_emotion(self, score: float, description: str):
        """保存情绪分析"""
        data = self.get()
        if data:
            data.emotion = score
            data.emotion_des = description
            self._save(data)
            print(f"😊 Saved emotion: {score}")

    def save_conclusion(self, conclusion: str):
        """保存综合报告"""
        data = self.get()
        if data:
            data.conclusion = conclusion
            self._save(data)
            print(f"📝 Saved conclusion: {len(conclusion)} characters")

    def mark_completed(self):
        """标记为完成"""
        data = self.get()
        if data:
            data.status = SessionStatus.COMPLETED
            data.steps = 7
            self._save(data)
            print(f"✅✅✅ Session {self.session_id} MARKED AS COMPLETED ✅✅✅")

    def mark_error(self, error_message: str):
        """标记为错误"""
        data = self.get()
        if data:
            data.status = SessionStatus.ERROR
            data.error_message = error_message
            self._save(data)
            print(f"❌ Session marked as ERROR: {error_message}")

    def delete(self):
        """删除会话"""
        self.redis.delete(self.key)
        print(f"🗑️ Session {self.session_id} deleted")

    @classmethod
    def exists(cls, session_id: str) -> bool:
        """检查会话是否存在"""
        redis = get_redis()
        return redis.exists(f"session:{session_id}") > 0

    # ========== v2 新增方法 ==========

    def save_intent_result(self, intent: str, intent_result: dict):
        """保存意图识别结果并初始化步骤"""
        data = self.get()
        if data:
            data.intent = intent
            data.intent_result = intent_result

            steps = get_steps_for_intent(intent)
            data.total_steps = len(steps)
            data.step_details = [
                StepDetail(id=s["id"], name=s["name"], status=StepStatus.PENDING, message="")
                for s in steps
            ]

            self._save(data)
            print(f"🎯 Intent saved: {intent}, total_steps={data.total_steps}")

    def save_unified_intent(self, intent: UnifiedIntent):
        """保存统一意图识别结果"""
        data = self.get()
        if data:
            data.unified_intent = intent
            data.is_forecast = intent.is_forecast

            # 设置旧版 intent 字段以兼容
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
            print(f"🎯 Unified intent saved: forecast={intent.is_forecast}, scope={intent.is_in_scope}")

    def save_stock_match(self, result: StockMatchResult):
        """保存股票匹配结果"""
        data = self.get()
        if data:
            data.stock_match = result
            if result.success and result.stock_info:
                data.stock_code = result.stock_info.stock_code
            self._save(data)
            print(f"🏷️ Stock match saved: {result.success}")

    def save_resolved_keywords(self, keywords: ResolvedKeywords):
        """保存最终关键词"""
        data = self.get()
        if data:
            data.resolved_keywords = keywords
            self._save(data)
            print(f"🔑 Keywords resolved")

    def update_step_detail(self, step: int, status: str, message: str = ""):
        """更新步骤详情"""
        data = self.get()
        if data and 0 < step <= len(data.step_details):
            data.steps = step
            data.status = SessionStatus.PROCESSING
            data.step_details[step - 1].status = StepStatus(status)
            data.step_details[step - 1].message = message
            self._save(data)
            print(f"📊 Step {step}/{data.total_steps} [{status}]: {message}")

    def save_rag_sources(self, sources: List[RAGSource]):
        """保存 RAG 来源"""
        data = self.get()
        if data:
            data.rag_sources = sources
            self._save(data)
            print(f"📚 Saved {len(sources)} RAG sources")

    def get_conversation_history(self) -> List[dict]:
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
            print(f"💬 Added {role} message to history")

    def reset_for_new_query(self):
        """重置会话状态（用于多轮对话的新查询）"""
        data = self.get()
        if data:
            data.status = SessionStatus.PENDING
            data.steps = 0
            data.intent = "pending"
            data.intent_result = None
            data.unified_intent = None
            data.stock_match = None
            data.resolved_keywords = None
            data.total_steps = 0
            data.step_details = []
            data.time_series_original = []
            data.time_series_full = []
            data.prediction_done = False
            data.prediction_start_day = None
            data.news_list = []
            data.rag_sources = []
            data.emotion = None
            data.emotion_des = None
            data.conclusion = ""
            data.error_message = None
            data.is_forecast = False
            self._save(data)
            print(f"🔄 Session reset for new query")

    def mark_completed_v2(self):
        """标记为完成（v2 版本）"""
        data = self.get()
        if data:
            data.status = SessionStatus.COMPLETED
            data.steps = data.total_steps
            for step in data.step_details:
                if step.status != StepStatus.ERROR:
                    step.status = StepStatus.COMPLETED
            self._save(data)
            print(f"✅✅✅ Session {self.session_id} COMPLETED ({data.total_steps} steps) ✅✅✅")
